#!/usr/bin/env python3
"""
Quality Gate Check — SubagentStop hook that calls the external Quality Gate service.

Runs AFTER quality-audit-check.py. If the audit was present, this hook pushes
the agent's code changes to the Quality Gate service which runs:
  1. Linter (language-specific)
  2. Fresh Claude reviewer (independent, no anchoring bias)
  3. Optional human review queue

If the service returns FAIL, blocks the agent completion and feeds the
findings back as instructions to fix.

The service is expected at GATE_URL (default http://127.0.0.1:7733). If the
service isn't running, this hook logs a warning and allows completion —
it never blocks the pipeline on service unavailability.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error


GATE_URL = os.environ.get("GATE_URL", "http://127.0.0.1:7733")
GATE_TIMEOUT_S = int(os.environ.get("GATE_TIMEOUT", "180"))
GATE_REQUIRE_HUMAN = os.environ.get("GATE_REQUIRE_HUMAN_REVIEW", "false").lower() == "true"

# Polling behavior for HUMAN_REVIEW_REQUIRED verdicts.
# Hook waits for the human to decide (APPROVE / REJECT / DEFER) by polling
# the /review/{id}/status endpoint until a decision is recorded OR the wait
# timeout expires.
HUMAN_WAIT_S = int(os.environ.get("GATE_HUMAN_WAIT", "600"))          # default: 10 min
HUMAN_POLL_INTERVAL_S = int(os.environ.get("GATE_HUMAN_POLL_INTERVAL", "5"))
HUMAN_STATUS_EVERY_S = int(os.environ.get("GATE_HUMAN_STATUS_EVERY", "30"))


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    transcript_path = payload.get("transcript_path", "")
    session_id = payload.get("session_id", "unknown")
    if not transcript_path:
        sys.exit(0)

    changed_files, agent_name, project_root, audit_text = _extract_changes_and_audit(transcript_path)
    if not changed_files:
        sys.exit(0)

    # Call the gate service
    request_body = {
        "session_id": session_id,
        "agent_name": agent_name or "unknown",
        "project_root": project_root or os.getcwd(),
        "changed_files": changed_files,
        "quality_audit": audit_text,
        "require_human_review": GATE_REQUIRE_HUMAN,
    }

    try:
        verdict = _call_gate(request_body)
    except urllib.error.URLError:
        # Service not running — log and allow
        print(
            f"[quality-gate-hook] Service not reachable at {GATE_URL}. "
            "Install with: python quality-gate/server.py",
            file=sys.stderr,
        )
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print(f"[quality-gate-hook] Error: {e}", file=sys.stderr)
        sys.exit(0)

    # Act on verdict
    if verdict.get("verdict") == "PASS":
        sys.exit(0)

    if verdict.get("verdict") == "HUMAN_REVIEW_REQUIRED":
        check_id = verdict.get("check_id", "")
        review_url = verdict.get("human_review_url", "")
        # Wait for a human decision (poll the service). Allows, blocks, or
        # times out depending on what the human chose.
        decision = _wait_for_human_decision(check_id, review_url)
        _handle_human_decision(decision, verdict)
        sys.exit(0)

    # FAIL — block with findings
    msg = _format_failure(verdict)
    print(json.dumps({"decision": "block", "reason": msg}))
    sys.exit(0)


def _wait_for_human_decision(check_id: str, review_url: str) -> dict:
    """Poll the status endpoint until a decision is recorded or we time out.

    Returns a dict: {outcome: APPROVE|REJECT|DEFER|TIMEOUT|ERROR, comment: str}
    """
    if not check_id:
        return {"outcome": "ERROR", "comment": "No check_id returned by gate"}

    status_url = f"{GATE_URL}/review/{check_id}/status"
    deadline = time.time() + HUMAN_WAIT_S
    last_status_print = 0.0

    # Tell the user what's happening (status line — stderr so it's visible but
    # doesn't end up in the block message)
    _progress(
        f"Change queued for human review. Open {review_url} to approve/reject. "
        f"Waiting up to {HUMAN_WAIT_S}s for a decision."
    )

    while time.time() < deadline:
        try:
            req = urllib.request.Request(status_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except urllib.error.URLError:
            return {
                "outcome": "ERROR",
                "comment": "Quality Gate service became unreachable while waiting for the decision",
            }
        except Exception as e:  # noqa: BLE001
            return {"outcome": "ERROR", "comment": f"Status poll error: {e}"}

        decision = (data.get("decision") or "").upper()
        if decision in ("APPROVE", "REJECT", "DEFER"):
            return {"outcome": decision, "comment": data.get("comment") or ""}

        # Periodic progress ping so the user knows we're still waiting
        now = time.time()
        if now - last_status_print >= HUMAN_STATUS_EVERY_S:
            remaining = int(deadline - now)
            _progress(f"Still waiting for human decision ({remaining}s remaining)...")
            last_status_print = now

        time.sleep(HUMAN_POLL_INTERVAL_S)

    return {"outcome": "TIMEOUT", "comment": ""}


def _handle_human_decision(decision: dict, verdict: dict) -> None:
    """Convert a human decision into a hook response (allow or block)."""
    outcome = decision.get("outcome", "ERROR")
    comment = decision.get("comment", "")
    review_url = verdict.get("human_review_url", "")
    check_id = verdict.get("check_id", "")

    if outcome == "APPROVE":
        _progress(f"Human approved {check_id}. Allowing turn to complete.")
        # Exit 0 with no JSON body = allow
        return

    if outcome == "REJECT":
        msg = (
            "## Quality Gate — Human REJECTED this change\n\n"
            f"**Reviewer:** {check_id}\n\n"
            f"**Comment:**\n\n{comment or '(no comment provided)'}\n\n"
            "Re-dispatch the sub-agent to address the reviewer's feedback. "
            "Include an updated `## Quality Audit` section in the new report."
        )
        print(json.dumps({"decision": "block", "reason": msg}))
        return

    if outcome == "DEFER":
        msg = (
            "## Quality Gate — Human DEFERRED this change\n\n"
            f"**Reviewer:** {check_id}\n\n"
            f"**Comment:**\n\n{comment or '(no comment provided)'}\n\n"
            f"The change is neither approved nor rejected — the reviewer needs more information.\n\n"
            f"Re-trigger the same command once the blocker is cleared, "
            f"or address the deferral reason above."
        )
        print(json.dumps({"decision": "block", "reason": msg}))
        return

    if outcome == "TIMEOUT":
        msg = (
            "## Quality Gate — Human review timed out\n\n"
            f"No decision was recorded within {HUMAN_WAIT_S} seconds.\n\n"
            f"**The change is still queued:** {review_url}\n\n"
            "The session has been blocked to prevent the sub-agent from continuing "
            "without a decision. Options:\n"
            f"- Decide in the web UI, then re-trigger the same command\n"
            f"- Increase `GATE_HUMAN_WAIT` (current: {HUMAN_WAIT_S}s) if reviews "
            f"commonly take longer than this"
        )
        print(json.dumps({"decision": "block", "reason": msg}))
        return

    # ERROR or unknown — surface the reason but don't silently allow
    msg = (
        "## Quality Gate — Error while waiting for human review\n\n"
        f"{comment or 'Unknown error'}\n\n"
        f"**Review queue entry (if created):** {review_url}\n\n"
        "The session has been blocked. Check the Quality Gate service logs and retry."
    )
    print(json.dumps({"decision": "block", "reason": msg}))


def _progress(msg: str) -> None:
    """Write a user-visible status line to stderr (stdout is reserved for hook JSON)."""
    print(f"[quality-gate-hook] {msg}", file=sys.stderr, flush=True)


def _call_gate(body: dict) -> dict:
    req = urllib.request.Request(
        f"{GATE_URL}/gate/check",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=GATE_TIMEOUT_S) as resp:
        return json.loads(resp.read())


def _extract_changes_and_audit(transcript_path: str) -> tuple[list[dict], str | None, str | None, str]:
    """Parse transcript to find edited/written files and the Quality Audit text."""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return [], None, None, ""

    changes: dict[str, dict] = {}
    audit_text = ""
    agent_name: str | None = None
    project_root: str | None = None

    # Walk forward collecting edits and final assistant message
    last_assistant_text = ""
    for line in lines[-300:]:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Track tool uses (Edit/Write/MultiEdit)
        content = msg.get("message", {}).get("content", []) or msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name", "")
                    inp = block.get("input", {}) or {}
                    if name in ("Edit", "Write", "MultiEdit"):
                        path = inp.get("file_path", "")
                        if path and not _is_doc_or_config(path):
                            changes.setdefault(path, {"path": path})
                            # For Write, capture full content; for Edit, capture new_string for context
                            if name == "Write":
                                changes[path]["content"] = inp.get("content", "")
                            elif name == "Edit":
                                changes[path]["content"] = inp.get("new_string", "")
                if block.get("type") == "text":
                    last_assistant_text = block.get("text", "") or last_assistant_text

    # Extract Quality Audit section from the last assistant message
    audit_match = re.search(
        r"#{2,3}\s*Quality\s+Audit\s*\n([\s\S]+?)(?=\n#{1,3}\s|\Z)",
        last_assistant_text,
        re.IGNORECASE,
    )
    if audit_match:
        audit_text = audit_match.group(1).strip()

    # Populate file content for files we don't have via tool inputs
    for path, data in changes.items():
        if not data.get("content"):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    data["content"] = f.read()[:8000]  # cap
            except Exception:
                data["content"] = ""

    # Best-effort project root detection
    if changes:
        first_path = next(iter(changes))
        project_root = _find_project_root(first_path)

    return list(changes.values()), agent_name, project_root, audit_text


def _is_doc_or_config(path: str) -> bool:
    p = path.lower().replace("\\", "/")
    for marker in ("/reports/", "/docs/", ".md", ".html", ".json", ".txt", ".rst",
                   "readme", "changelog", "license", ".env", ".gitignore"):
        if marker in p:
            return True
    return False


def _find_project_root(file_path: str) -> str:
    current = os.path.dirname(os.path.abspath(file_path))
    for _ in range(10):
        for marker in (".git", "package.json", "pom.xml", "Cargo.toml", "go.mod", "*.csproj"):
            if marker.startswith("*."):
                ext = marker[1:]
                if any(f.endswith(ext) for f in os.listdir(current)) if os.path.isdir(current) else False:
                    return current
            elif os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.dirname(os.path.abspath(file_path))


def _format_failure(verdict: dict) -> str:
    findings = verdict.get("findings", [])
    critical = [f for f in findings if f.get("severity") == "critical"]
    major = [f for f in findings if f.get("severity") == "major"]

    lines = [
        "## Quality Gate FAILED",
        "",
        f"**Summary:** {verdict.get('summary', 'Issues found')}",
        "",
    ]
    if critical:
        lines.append(f"### Critical ({len(critical)})")
        for f in critical[:20]:
            loc = f.get("file") or ""
            if f.get("line"):
                loc += f":{f['line']}"
            src = f.get("source", "")
            lines.append(f"- **[{src}]** `{loc}` — {f.get('message', '')}")
        lines.append("")
    if major:
        lines.append(f"### Major ({len(major)})")
        for f in major[:20]:
            loc = f.get("file") or ""
            if f.get("line"):
                loc += f":{f['line']}"
            src = f.get("source", "")
            lines.append(f"- **[{src}]** `{loc}` — {f.get('message', '')}")
        lines.append("")
    lines.append("---")
    lines.append("Re-dispatch the sub-agent to fix ALL critical and major findings above.")
    lines.append("Sources: `[linter]` = automated lint check; `[reviewer]` = independent Claude reviewer")
    lines.append("Include an updated `## Quality Audit` in the new report addressing each fix.")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
