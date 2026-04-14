#!/usr/bin/env python3
"""
Quality Audit Verify Hook — cross-checks the YAML Quality Audit block against
the actual code changes.

Runs AFTER quality-audit-check.py (which checks the section exists) and BEFORE
quality-gate-check.py (which calls the Quality Gate service). If the agent's
YAML claims don't match the code — e.g. claims `memoized_components: [TaskRow]`
but TaskRow isn't wrapped in React.memo — this hook BLOCKS the sub-agent
completion with a specific list of unverified claims.

Why this exists: the Quality Audit was self-reported prose. The agent can write
a convincing audit that doesn't match the code. Rule Z v2 requires structured
YAML claims; this hook is the verifier that makes them load-bearing.

The hook is lenient — a claim is only flagged as unverified if we can prove
it's wrong. "Can't find it" usually means the grep heuristic missed something,
which is reported as a warning, not a block.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


CHECKS_STRICT = os.environ.get("QA_VERIFY_STRICT", "false").lower() == "true"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    transcript_path = payload.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    audit_yaml, changed_files = _extract_audit_and_files(transcript_path)
    if not audit_yaml:
        # No YAML audit found. Let quality-audit-check.py handle the
        # "audit missing" case; don't double-block here.
        sys.exit(0)

    claims = _parse_audit_yaml(audit_yaml)
    if not claims:
        # YAML was present but unparseable
        _block(
            "## Quality Audit YAML is malformed\n\n"
            "The Quality Audit block must be valid YAML. Re-emit the audit "
            "with correct syntax (no unquoted colons in values, proper list "
            "indentation, closed strings)."
        )
        return

    # Collect code we can verify against
    code_blob = _collect_changed_code(changed_files)
    if not code_blob:
        # We can't verify without code — allow completion
        sys.exit(0)

    unverified = _verify_claims(claims, code_blob)

    if not unverified:
        sys.exit(0)

    # In strict mode ANY unverified claim blocks. Otherwise only block if the
    # agent claimed something concrete that clearly contradicts the code.
    blockers = [u for u in unverified if u["severity"] == "contradiction"]
    warnings = [u for u in unverified if u["severity"] == "missing"]

    if not blockers and not CHECKS_STRICT:
        # Only soft warnings — allow completion but log
        for w in warnings:
            print(f"[quality-audit-verify] WARN: {w['message']}", file=sys.stderr)
        sys.exit(0)

    # Block
    reason_lines = [
        "## Quality Audit Verification FAILED",
        "",
        "Your YAML audit claimed things that don't match the code:",
        "",
    ]
    for u in (blockers + warnings if CHECKS_STRICT else blockers):
        reason_lines.append(f"- **{u['field']}**: {u['message']}")
    reason_lines.extend([
        "",
        "Either:",
        "  1. Fix the code to actually match your audit claims, or",
        "  2. Remove/correct the claims that don't match what you shipped",
        "",
        "Re-emit the Quality Audit YAML block with accurate claims.",
    ])
    _block("\n".join(reason_lines))


# --------------------------------------------------------------------------- #
def _extract_audit_and_files(transcript_path: str) -> tuple[str, dict[str, str]]:
    """Read the transcript. Return (yaml_audit_text, {file_path: content_written})."""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return "", {}

    files_written: dict[str, str] = {}
    last_assistant = ""

    for line in lines[-400:]:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        content = msg.get("message", {}).get("content", []) or msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name = block.get("name", "")
                inp = block.get("input", {}) or {}
                if name in ("Write", "Edit", "MultiEdit"):
                    path = inp.get("file_path", "")
                    if path and not _is_doc(path):
                        if name == "Write":
                            files_written[path] = inp.get("content", "")
                        elif name == "Edit":
                            # Append the new_string — best we can do
                            files_written.setdefault(path, "")
                            files_written[path] += "\n" + inp.get("new_string", "")
            if block.get("type") == "text":
                last_assistant = block.get("text", "") or last_assistant

    # Extract the YAML block from the last assistant message
    yaml_text = ""
    m = re.search(
        r"##\s*Quality\s+Audit\s*\n+```ya?ml\s*\n([\s\S]+?)```",
        last_assistant,
        re.IGNORECASE,
    )
    if m:
        yaml_text = m.group(1)

    return yaml_text, files_written


def _is_doc(path: str) -> bool:
    p = path.lower().replace("\\", "/")
    for marker in ("/reports/", "/docs/", ".md", ".html", ".txt", ".rst",
                   "readme", "changelog", "license", ".env", ".gitignore"):
        if marker in p:
            return True
    return False


def _collect_changed_code(files: dict[str, str]) -> str:
    """Concatenate the code from all changed source files.

    If we have the written content from the transcript, use that.
    Otherwise fall back to reading the file from disk.
    """
    parts: list[str] = []
    for path, content in files.items():
        if content:
            parts.append(content)
            continue
        try:
            parts.append(Path(path).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# YAML parsing — minimal, no external dependency
# --------------------------------------------------------------------------- #
def _parse_audit_yaml(yaml_text: str) -> dict | None:
    """Very small YAML subset parser — just enough for the audit schema.

    Supports: scalar strings, flow-style inline lists ([a, b]), flow-style inline
    dicts ({k: v}), and simple list-of-dicts blocks. Good enough for the audit.
    """
    try:
        # Strip comments and trailing whitespace
        lines = []
        for raw in yaml_text.splitlines():
            # drop trailing # comments (but preserve # inside quoted strings)
            stripped = _strip_inline_comment(raw).rstrip()
            if stripped:
                lines.append(stripped)

        result: dict = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip() or line.lstrip().startswith("#"):
                i += 1
                continue
            # Top-level key: value
            m = re.match(r"^([a-zA-Z_][\w]*)\s*:\s*(.*)$", line)
            if not m:
                i += 1
                continue
            key, value = m.group(1), m.group(2).strip()
            if value:
                # Inline scalar / list / dict
                result[key] = _parse_inline(value)
                i += 1
            else:
                # Block — consume indented children
                children = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                    child = lines[i].strip()
                    if child.startswith("-"):
                        children.append(_parse_inline(child[1:].strip()))
                    i += 1
                result[key] = children
        return result
    except Exception:
        return None


def _strip_inline_comment(line: str) -> str:
    """Strip a # comment outside of quotes."""
    in_single = in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:idx]
    return line


def _parse_inline(value: str):
    value = value.strip()
    if not value:
        return ""
    # Empty list
    if value in ("[]", "[ ]"):
        return []
    # Flow list
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip('"').strip("'") for v in _split_top(inner, ",")]
    # Flow dict
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        out: dict = {}
        for pair in _split_top(inner, ","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                out[k.strip().strip('"').strip("'")] = v.strip().strip('"').strip("'")
        return out
    # Quoted string
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _split_top(s: str, sep: str) -> list[str]:
    """Split on sep, respecting brace/bracket depth."""
    out: list[str] = []
    depth = 0
    buf = ""
    for ch in s:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    return out


# --------------------------------------------------------------------------- #
# Verification — cross-check claims against code
# --------------------------------------------------------------------------- #
def _verify_claims(claims: dict, code: str) -> list[dict]:
    """Return a list of unverified claims. Each: {field, severity, message}.

    severity = 'contradiction' (code disproves the claim — block)
             = 'missing' (can't find evidence — warn only, might be heuristic miss)
    """
    unverified: list[dict] = []

    # Prefer AST-based verification via the Node helper if available
    ast_result = _try_ast_verify(claims, code_files=_split_code(code))
    if ast_result is not None:
        # If AST verification succeeds, use its unverified list directly
        for item in ast_result.get("unverified", []):
            unverified.append({
                "field": item.get("field", "unknown"),
                "severity": "contradiction",
                "message": item.get("reason", "unverified"),
            })
        # Still run the contradiction-in-code checks below (inline style counts etc.)
        # because AST only covers the named-claim list, not "the audit claimed X but
        # the code still has 15 violations of X's pattern"
        # Skip the redundant regex checks for the claims the AST already handled
        _check_inline_style_contradictions(code, claims, unverified)
        _check_inline_arrow_contradictions(code, claims, unverified)
        _check_set_map_and_cleanup(code, claims, unverified)
        return unverified

    # Fallback: regex verification
    for name in _as_list(claims.get("memoized_components")):
        if not name:
            continue
        if not _is_memoized(name, code):
            unverified.append({
                "field": f"memoized_components.{name}",
                "severity": "contradiction",
                "message": (
                    f"claimed `{name}` is wrapped in React.memo, but no "
                    f"`React.memo({name})` or `memo({name})` found in changed code"
                ),
            })

    # usecallback_handlers: grep for useCallback(... handler ...) OR const name = useCallback(
    for name in _as_list(claims.get("usecallback_handlers")):
        if not name:
            continue
        if not _is_usecallback(name, code):
            unverified.append({
                "field": f"usecallback_handlers.{name}",
                "severity": "contradiction",
                "message": (
                    f"claimed `{name}` uses useCallback, but no "
                    f"`const {name} = useCallback(` or equivalent found"
                ),
            })

    # usememo_derivations
    for name in _as_list(claims.get("usememo_derivations")):
        if not name:
            continue
        if not _is_usememo(name, code):
            unverified.append({
                "field": f"usememo_derivations.{name}",
                "severity": "contradiction",
                "message": (
                    f"claimed `{name}` uses useMemo, but no "
                    f"`const {name} = useMemo(` found"
                ),
            })

    # hoisted_style_constants: each should appear as a top-level const
    for name in _as_list(claims.get("hoisted_style_constants")):
        if not name:
            continue
        if not _is_module_const(name, code):
            unverified.append({
                "field": f"hoisted_style_constants.{name}",
                "severity": "contradiction",
                "message": (
                    f"claimed `{name}` is a module-scope style constant, but "
                    f"no top-level `const {name} = ` found"
                ),
            })

    # set_uses and map_uses: at least one `new Set(` / `new Map(` must exist
    # for the claim to be plausible
    set_items = _as_list(claims.get("set_uses"))
    if set_items and not re.search(r"\bnew\s+Set\s*\(", code):
        unverified.append({
            "field": "set_uses",
            "severity": "contradiction",
            "message": f"claimed {len(set_items)} Set use(s) but no `new Set(` found in code",
        })

    map_items = _as_list(claims.get("map_uses"))
    if map_items and not re.search(r"\bnew\s+Map\s*\(", code):
        unverified.append({
            "field": "map_uses",
            "severity": "contradiction",
            "message": f"claimed {len(map_items)} Map use(s) but no `new Map(` found in code",
        })

    # cleanup_registered: at least one of clearInterval / clearTimeout / abort /
    # removeEventListener must exist if claims present
    cleanup_items = _as_list(claims.get("cleanup_registered"))
    if cleanup_items:
        cleanup_patterns = r"\b(clearInterval|clearTimeout|abort|removeEventListener|unsubscribe|dispose|close)\s*\("
        if not re.search(cleanup_patterns, code):
            unverified.append({
                "field": "cleanup_registered",
                "severity": "contradiction",
                "message": (
                    f"claimed {len(cleanup_items)} cleanup point(s) but no "
                    f"clearInterval/clearTimeout/abort/removeEventListener/unsubscribe found"
                ),
            })

    # Contradictions from code that show the audit LIED about avoidance:
    # if the code contains inline style={{...}} in JSX but audit claimed
    # hoisted_style_constants, that's a partial contradiction.
    inline_styles = len(re.findall(r"style\s*=\s*\{\{", code))
    if inline_styles >= 3 and claims.get("hoisted_style_constants"):
        unverified.append({
            "field": "hoisted_style_constants",
            "severity": "contradiction",
            "message": (
                f"claimed hoisted style constants exist, but code still has "
                f"{inline_styles} inline `style={{{{...}}}}` literals"
            ),
        })

    inline_arrows = len(re.findall(r"=\s*\{\s*\(?[a-zA-Z_]*\)?\s*=>", code))
    if inline_arrows >= 3 and claims.get("usecallback_handlers"):
        unverified.append({
            "field": "usecallback_handlers",
            "severity": "contradiction",
            "message": (
                f"claimed useCallback handlers exist, but code still has "
                f"{inline_arrows} inline arrow functions in JSX props"
            ),
        })

    return unverified


def _as_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _is_memoized(name: str, code: str) -> bool:
    patterns = [
        rf"React\.memo\s*\(\s*{re.escape(name)}\b",
        rf"\bmemo\s*\(\s*{re.escape(name)}\b",
        rf"\bconst\s+{re.escape(name)}\s*=\s*(React\.)?memo\s*\(",
        rf"\bconst\s+{re.escape(name)}\s*=\s*(React\.)?forwardRef\s*\(",
    ]
    return any(re.search(p, code) for p in patterns)


def _is_usecallback(name: str, code: str) -> bool:
    patterns = [
        rf"\bconst\s+{re.escape(name)}\s*=\s*useCallback\s*\(",
        rf"\blet\s+{re.escape(name)}\s*=\s*useCallback\s*\(",
    ]
    return any(re.search(p, code) for p in patterns)


def _is_usememo(name: str, code: str) -> bool:
    return bool(re.search(rf"\bconst\s+{re.escape(name)}\s*=\s*useMemo\s*\(", code))


def _is_module_const(name: str, code: str) -> bool:
    # Top-level (not indented) const NAME = ...
    return bool(re.search(rf"^const\s+{re.escape(name)}\s*[:=]", code, re.MULTILINE))


def _block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


# --------------------------------------------------------------------------- #
# AST helper delegation
# --------------------------------------------------------------------------- #
def _try_ast_verify(claims: dict, code_files: list[tuple[str, str]]) -> dict | None:
    """Invoke the Node.js AST helper. Returns its JSON result or None on failure.

    Writes a task JSON to a temp file and shells out to `node ast-verify.mjs`.
    If node isn't available, or the helper errors, returns None so the caller
    falls back to the regex checks.
    """
    import shutil as _sh
    import tempfile as _tmp
    import subprocess as _sp

    if not _sh.which("node"):
        return None
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ast-verify.mjs")
    if not os.path.exists(helper):
        return None

    # Write code to temp files so the AST helper can parse them
    temp_paths = []
    try:
        for i, (_, content) in enumerate(code_files):
            fd, path = _tmp.mkstemp(suffix=f"-qa{i}.tsx", text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            temp_paths.append(path)

        task = {
            "files": temp_paths,
            "claims": {
                "memoized_components": _as_list(claims.get("memoized_components")),
                "usecallback_handlers": _as_list(claims.get("usecallback_handlers")),
                "usememo_derivations": _as_list(claims.get("usememo_derivations")),
                "hoisted_style_constants": _as_list(claims.get("hoisted_style_constants")),
            },
        }
        fd, task_path = _tmp.mkstemp(suffix=".json", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(task, fh)

        result = _sp.run(
            ["node", helper, task_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except Exception:
        return None
    finally:
        for p in temp_paths:
            try:
                os.unlink(p)
            except OSError:
                pass


def _split_code(code: str) -> list[tuple[str, str]]:
    """Split concatenated code back into approximate files for AST handling."""
    # The code is already concatenated with "\n\n" separators — treat as one file
    return [("combined.tsx", code)]


def _check_inline_style_contradictions(code: str, claims: dict, unverified: list) -> None:
    inline = len(re.findall(r"style\s*=\s*\{\{", code))
    if inline >= 3 and claims.get("hoisted_style_constants"):
        unverified.append({
            "field": "hoisted_style_constants",
            "severity": "contradiction",
            "message": f"{inline} inline style={{...}} literals still in code despite hoisted_style_constants claim",
        })


def _check_inline_arrow_contradictions(code: str, claims: dict, unverified: list) -> None:
    arrows = len(re.findall(r"=\s*\{\s*\(?[a-zA-Z_]*\)?\s*=>", code))
    if arrows >= 3 and claims.get("usecallback_handlers"):
        unverified.append({
            "field": "usecallback_handlers",
            "severity": "contradiction",
            "message": f"{arrows} inline arrow functions in JSX props still in code despite usecallback_handlers claim",
        })


def _check_set_map_and_cleanup(code: str, claims: dict, unverified: list) -> None:
    if claims.get("set_uses") and not re.search(r"\bnew\s+Set\s*\(", code):
        unverified.append({"field": "set_uses", "severity": "contradiction",
                           "message": "no `new Set(` found despite set_uses claim"})
    if claims.get("map_uses") and not re.search(r"\bnew\s+Map\s*\(", code):
        unverified.append({"field": "map_uses", "severity": "contradiction",
                           "message": "no `new Map(` found despite map_uses claim"})
    if claims.get("cleanup_registered") and not re.search(
        r"\b(clearInterval|clearTimeout|abort|removeEventListener|unsubscribe|dispose|close)\s*\(", code
    ):
        unverified.append({"field": "cleanup_registered", "severity": "contradiction",
                           "message": "no cleanup calls found despite cleanup_registered claim"})


if __name__ == "__main__":
    main()
