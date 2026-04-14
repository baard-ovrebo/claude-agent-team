"""
Language detection + linter runners.

Supports: JS/TS (eslint), Python (ruff, pylint fallback), Go (go vet),
Rust (clippy), C# (dotnet format), Ruby (rubocop), PHP (phpstan).

Each runner returns a list of dicts: {severity, line, rule, message}
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


_EXT_TO_LANG = {
    ".ts": "ts", ".tsx": "ts", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
    ".py": "py",
    ".go": "go",
    ".rs": "rs",
    ".cs": "cs",
    ".rb": "rb",
    ".php": "php",
    ".java": "java",
    ".kt": "kt",
    ".swift": "swift",
}


def detect_language(path: str) -> str | None:
    ext = Path(path).suffix.lower()
    return _EXT_TO_LANG.get(ext)


def run_linter(lang: str, file_path: str, project_root: str, content: str) -> list[dict]:
    """Dispatch to the correct linter for the language. Best-effort — missing tools return [].

    If the file doesn't exist at `file_path` (common when the gate runs as a
    separate service and receives file content over HTTP), writes the content
    to a temp file and lints that, then remaps diagnostic paths back to the
    original `file_path` so findings are reported with the caller's path.
    """
    import tempfile
    from pathlib import Path

    runners = {
        "js": _run_eslint,
        "ts": _run_eslint,
        "py": _run_python_linter,
        "go": _run_govet,
        "rs": _run_clippy,
        "cs": _run_dotnet_format,
        "rb": _run_rubocop,
        "php": _run_phpstan,
    }
    runner = runners.get(lang)
    if not runner:
        return []

    # If the file exists at file_path, use it directly. Otherwise write content
    # to a temp file that preserves the extension so the linter recognises it.
    cleanup_path: str | None = None
    lint_path = file_path
    try:
        if not os.path.exists(file_path) and content:
            suffix = Path(file_path).suffix or _default_suffix(lang)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix, delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(content)
                cleanup_path = tmp.name
                lint_path = tmp.name
    except Exception:  # noqa: BLE001
        # Couldn't stage a temp file — fall through and let the runner fail naturally
        pass

    try:
        raw = runner(lint_path, project_root, content)
    except FileNotFoundError:
        # Linter binary not installed — silently skip
        raw = []
    except Exception as e:  # noqa: BLE001
        raw = [{
            "severity": "info",
            "line": 0,
            "rule": "linter-error",
            "message": f"Linter failed: {e}",
        }]
    finally:
        if cleanup_path:
            try:
                os.unlink(cleanup_path)
            except OSError:
                pass

    # Normalise the reported path back to the caller's original file_path
    for item in raw:
        if "file" not in item:
            item["file"] = file_path
    return raw


def _default_suffix(lang: str) -> str:
    return {
        "js": ".js", "ts": ".ts", "py": ".py", "go": ".go", "rs": ".rs",
        "cs": ".cs", "rb": ".rb", "php": ".php",
    }.get(lang, "")


# --------------------------------------------------------------------------- #
# JavaScript / TypeScript — ESLint
# --------------------------------------------------------------------------- #
def _run_eslint(file_path: str, project_root: str, content: str) -> list[dict]:
    cmd = ["npx", "--no-install", "eslint", "--format", "json", "--no-color", file_path]
    result = subprocess.run(
        cmd, cwd=project_root, capture_output=True, text=True, timeout=45, check=False
    )
    if not result.stdout:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    findings: list[dict] = []
    for f in data:
        for msg in f.get("messages", []):
            findings.append({
                "severity": "critical" if msg.get("severity") == 2 else "minor",
                "line": msg.get("line"),
                "rule": msg.get("ruleId"),
                "message": msg.get("message", ""),
            })
    return findings


# --------------------------------------------------------------------------- #
# Python — ruff (fast, preferred) with pylint fallback
# --------------------------------------------------------------------------- #
def _run_python_linter(file_path: str, project_root: str, content: str) -> list[dict]:
    # Try ruff first (fast, modern)
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format", "json", file_path],
            cwd=project_root, capture_output=True, text=True, timeout=30, check=False,
        )
        if result.stdout:
            data = json.loads(result.stdout)
            return [
                {
                    "severity": _map_ruff_severity(item),
                    "line": item.get("location", {}).get("row"),
                    "rule": item.get("code"),
                    "message": item.get("message", ""),
                }
                for item in data
            ]
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback: pylint
    try:
        result = subprocess.run(
            ["pylint", "--output-format=json", file_path],
            cwd=project_root, capture_output=True, text=True, timeout=30, check=False,
        )
        if result.stdout:
            data = json.loads(result.stdout)
            return [
                {
                    "severity": _map_pylint_severity(item.get("type", "")),
                    "line": item.get("line"),
                    "rule": item.get("message-id"),
                    "message": item.get("message", ""),
                }
                for item in data
            ]
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    return []


def _map_ruff_severity(item: dict) -> str:
    code = (item.get("code") or "")
    if code.startswith("E"):
        return "critical"  # error
    if code.startswith("F"):
        return "major"  # pyflakes
    if code.startswith("W"):
        return "minor"  # warning
    return "minor"


def _map_pylint_severity(t: str) -> str:
    return {
        "error": "critical", "fatal": "critical",
        "warning": "major", "refactor": "minor", "convention": "minor",
    }.get(t, "minor")


# --------------------------------------------------------------------------- #
# Go — go vet
# --------------------------------------------------------------------------- #
def _run_govet(file_path: str, project_root: str, content: str) -> list[dict]:
    result = subprocess.run(
        ["go", "vet", file_path],
        cwd=project_root, capture_output=True, text=True, timeout=30, check=False,
    )
    findings: list[dict] = []
    for line in result.stderr.splitlines():
        # Format: file.go:line:col: message
        parts = line.split(":", 3)
        if len(parts) >= 4:
            try:
                findings.append({
                    "severity": "major",
                    "line": int(parts[1]),
                    "rule": "govet",
                    "message": parts[3].strip(),
                })
            except ValueError:
                pass
    return findings


# --------------------------------------------------------------------------- #
# Rust — cargo clippy (whole-project)
# --------------------------------------------------------------------------- #
def _run_clippy(file_path: str, project_root: str, content: str) -> list[dict]:
    result = subprocess.run(
        ["cargo", "clippy", "--message-format=json", "--", "-W", "clippy::all"],
        cwd=project_root, capture_output=True, text=True, timeout=60, check=False,
    )
    findings: list[dict] = []
    for line in result.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("reason") != "compiler-message":
            continue
        m = msg.get("message", {})
        spans = m.get("spans", [])
        if not spans:
            continue
        span = spans[0]
        if os.path.basename(span.get("file_name", "")) != os.path.basename(file_path):
            continue
        findings.append({
            "severity": "critical" if m.get("level") == "error" else "major" if m.get("level") == "warning" else "minor",
            "line": span.get("line_start"),
            "rule": (m.get("code") or {}).get("code") or "clippy",
            "message": m.get("message", ""),
        })
    return findings


# --------------------------------------------------------------------------- #
# C# — dotnet format verify-no-changes
# --------------------------------------------------------------------------- #
def _run_dotnet_format(file_path: str, project_root: str, content: str) -> list[dict]:
    result = subprocess.run(
        ["dotnet", "format", "--verify-no-changes", "--verbosity", "diagnostic", "--include", file_path],
        cwd=project_root, capture_output=True, text=True, timeout=60, check=False,
    )
    findings: list[dict] = []
    for line in result.stdout.splitlines():
        lower = line.lower()
        if "error" in lower or "warning" in lower:
            findings.append({
                "severity": "critical" if "error" in lower else "major",
                "line": None,
                "rule": "dotnet-format",
                "message": line.strip(),
            })
    return findings[:50]  # cap


# --------------------------------------------------------------------------- #
# Ruby — rubocop
# --------------------------------------------------------------------------- #
def _run_rubocop(file_path: str, project_root: str, content: str) -> list[dict]:
    result = subprocess.run(
        ["rubocop", "--format", "json", file_path],
        cwd=project_root, capture_output=True, text=True, timeout=30, check=False,
    )
    if not result.stdout:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    findings: list[dict] = []
    for f in data.get("files", []):
        for o in f.get("offenses", []):
            sev_map = {"fatal": "critical", "error": "critical", "warning": "major", "convention": "minor", "refactor": "minor"}
            findings.append({
                "severity": sev_map.get(o.get("severity", "minor"), "minor"),
                "line": (o.get("location") or {}).get("line"),
                "rule": o.get("cop_name"),
                "message": o.get("message", ""),
            })
    return findings


# --------------------------------------------------------------------------- #
# PHP — phpstan
# --------------------------------------------------------------------------- #
def _run_phpstan(file_path: str, project_root: str, content: str) -> list[dict]:
    result = subprocess.run(
        ["phpstan", "analyse", "--error-format=json", "--no-progress", file_path],
        cwd=project_root, capture_output=True, text=True, timeout=45, check=False,
    )
    if not result.stdout:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    findings: list[dict] = []
    for _, details in (data.get("files") or {}).items():
        for m in details.get("messages", []):
            findings.append({
                "severity": "major",
                "line": m.get("line"),
                "rule": "phpstan",
                "message": m.get("message", ""),
            })
    return findings
