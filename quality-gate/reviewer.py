"""
Fresh Reviewer — spawns an isolated Claude CLI instance to review the diff.

The reviewer has NO knowledge of what the original agent did. It only sees
the diff and is asked for an independent perspective on code quality. This
prevents anchoring bias — if the original agent made a bad choice, a reviewer
in the same conversation would likely justify it; a fresh reviewer will
spot it.

Uses `claude -p` (print mode) for a one-shot non-interactive review.
Falls back to OpenAI or Gemini if `claude` CLI isn't available and API keys
are configured.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


_REVIEWER_PROMPT = """You are a senior code reviewer performing an INDEPENDENT quality review.

You have NOT written this code. You have NOT seen the agent's reasoning.
Your job is to spot issues an anchored reviewer would miss.

Review the following changed files for these issues:

CRITICAL (must fix before merge):
- Allocations in hot paths (loops, render functions, frame handlers, request handlers)
- N+1 queries or sequential fetches that should be batched
- Memory leaks (event listeners not removed, subscriptions not released, timers not cleared)
- Wrong data structures (array.find/includes repeatedly when Set/Map is O(1))
- Missing cleanup (file handles, DB connections, WebSockets)
- SQL injection, XSS, command injection, hardcoded secrets
- Synchronous I/O in request handlers or render paths

MAJOR (should fix):
- Duplicated logic that should be a shared utility
- Linear scans on data that will grow
- Missing pagination on list endpoints
- Unbounded caches or buffers
- Allocations inside render/loop that could be hoisted

MINOR (note only):
- Oversized functions (>100 lines)
- Dead code, commented-out blocks
- Inconsistent naming

AI-GENERATED PATTERNS to watch for specifically:
- Rebuilding entire lists when one item changed
- Loading all data then filtering in memory (filter in SQL/API instead)
- setState/update inside loops
- Creating new functions inside render
- JSON.parse(JSON.stringify(obj)) for deep clone
- find/includes repeated on the same array in a hot path
- Fetching data the backend already has cached

Return your findings as a JSON array ONLY (no prose, no markdown fences).
Each finding is: {"severity": "critical|major|minor", "file": "path", "line": number, "rule": "short-name", "message": "what and why"}

If no issues, return [].
"""


def run_fresh_reviewer(changed_files: list[dict], quality_audit: str) -> list[dict]:
    """Run an independent reviewer. Returns list of findings."""
    # Build the review input
    files_text = _format_files(changed_files)
    audit_text = f"\n\nORIGINAL AGENT'S QUALITY AUDIT (for context only — do not assume it's correct):\n{quality_audit}" if quality_audit else ""

    user_prompt = f"{_REVIEWER_PROMPT}\n\nCHANGED FILES:\n{files_text}{audit_text}"

    # Try Claude CLI first (best quality, same model family)
    findings = _try_claude_cli(user_prompt)
    if findings is not None:
        return findings

    # Fallback to OpenAI via council.env if available
    findings = _try_openai(user_prompt)
    if findings is not None:
        return findings

    # Fallback to Gemini
    findings = _try_gemini(user_prompt)
    if findings is not None:
        return findings

    # All reviewers unavailable — return info note so user knows
    return [{
        "severity": "info",
        "line": None,
        "rule": "reviewer-unavailable",
        "message": "No fresh reviewer available. Install `claude` CLI or set OPENAI_API_KEY/GOOGLE_AI_KEY in .claude/council.env",
    }]


# --------------------------------------------------------------------------- #
def _format_files(files: list[dict]) -> str:
    parts: list[str] = []
    for f in files:
        header = f"=== {f.get('path')} ==="
        if f.get("diff"):
            parts.append(f"{header} (diff)\n{f['diff']}")
        elif f.get("content"):
            # Cap very long files
            content = f["content"]
            if len(content) > 8000:
                content = content[:8000] + "\n... [truncated]"
            parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
def _try_claude_cli(prompt: str) -> list[dict] | None:
    if not shutil.which("claude"):
        return None
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=90, check=False,
        )
        return _extract_json_array(result.stdout)
    except Exception:  # noqa: BLE001
        return None


def _try_openai(prompt: str) -> list[dict] | None:
    key = os.environ.get("OPENAI_API_KEY") or _load_env_var("OPENAI_API_KEY")
    if not key:
        return None
    import urllib.request
    body = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"]
        return _extract_json_array(text)
    except Exception:  # noqa: BLE001
        return None


def _try_gemini(prompt: str) -> list[dict] | None:
    key = os.environ.get("GOOGLE_AI_KEY") or _load_env_var("GOOGLE_AI_KEY")
    if not key:
        return None
    import urllib.request
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json_array(text)
    except Exception:  # noqa: BLE001
        return None


def _load_env_var(name: str) -> str | None:
    """Check .claude/council.env in common locations for a variable."""
    locations = [
        Path.home() / ".claude" / "council.env",
        Path.cwd() / ".claude" / "council.env",
    ]
    for loc in locations:
        if not loc.exists():
            continue
        for line in loc.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _extract_json_array(text: str) -> list[dict]:
    """Extract a JSON array from model output, tolerating prose wrapping."""
    if not text:
        return []
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    # Try direct parse
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        pass
    # Try to find an array in the text
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []
