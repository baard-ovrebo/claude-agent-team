#!/usr/bin/env python3
"""
Quality Audit Check — SubagentStop Hook

Runs after every sub-agent completes. If the agent's final output claims to be
done with code changes but does NOT include a ## Quality Audit section, blocks
the completion with a message instructing the agent to add the audit before
returning.

Installation: Called by the SubagentStop hook in settings.json.

Exit codes:
  0 = Allow completion (audit present OR no code changes detected)
  2 = Block completion with message (audit required but missing)
"""
import json
import sys
import re


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # If we can't parse input, allow completion (don't break the pipeline)
        sys.exit(0)

    # Get the transcript path or messages from the hook payload
    transcript_path = payload.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    # Read the transcript and find the last assistant message
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        sys.exit(0)

    # Parse JSONL transcript from the end to find the last assistant text
    last_text = ""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("type") == "assistant" or msg.get("role") == "assistant":
            # Extract text content
            content = msg.get("message", {}).get("content", []) or msg.get("content", [])
            if isinstance(content, str):
                last_text = content
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                last_text = "\n".join(parts)
            if last_text:
                break

    if not last_text:
        sys.exit(0)

    # Detect if this agent made code changes (files edited/created)
    # Check transcript for tool_use of Edit, Write, NotebookEdit
    made_code_changes = False
    for line in lines[-200:]:  # only check recent tool uses
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        content = msg.get("message", {}).get("content", []) or msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
                        inp = block.get("input", {})
                        path = inp.get("file_path", "") or inp.get("notebook_path", "")
                        # Only count source code changes, not docs/reports
                        if path and not _is_doc_or_report(path):
                            made_code_changes = True
                            break
        if made_code_changes:
            break

    if not made_code_changes:
        # No code changes → no audit needed
        sys.exit(0)

    # Check for Quality Audit section in the last assistant message
    audit_pattern = re.compile(
        r"##\s+Quality\s+Audit|###\s+Quality\s+Audit|\*\*Quality\s+Audit\*\*",
        re.IGNORECASE,
    )
    if audit_pattern.search(last_text):
        # Audit present — allow completion
        sys.exit(0)

    # Missing audit → block with instruction
    block_message = (
        "## Missing Quality Audit\n\n"
        "Your sub-agent made code changes but did NOT include a `## Quality Audit` "
        "section in its final report. Per Rule Z, this work is INCOMPLETE.\n\n"
        "Re-dispatch the agent with these exact instructions:\n\n"
        "> Add a `## Quality Audit` section to your report covering:\n"
        "> - **Hot paths:** Which loops/handlers/renders you identified and how you kept them clean\n"
        "> - **Data structures:** Why Set vs Array vs Map, any O(1) lookups\n"
        "> - **Cleanup:** Subscriptions/timers/listeners/connections released\n"
        "> - **Caching:** What you memoized/cached and why\n"
        "> - **Batching:** What operations you batched, N+1 patterns avoided\n"
        "> - **Memory at scale:** Estimated usage at 10x and 100x current load\n"
        "> - **Code I avoided writing:** What shortcut/lazy option you rejected\n\n"
        "Do NOT mark the task as done until the Quality Audit is present and reveals no violations."
    )

    # Exit code 2 with a message on stderr blocks the agent completion
    # and injects the message as the next prompt
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": block_message,
            }
        )
    )
    sys.exit(0)


def _is_doc_or_report(path: str) -> bool:
    """Return True if the file is documentation, a report, or config (not source code)."""
    path = path.lower().replace("\\", "/")
    doc_patterns = [
        "/reports/",
        "/docs/",
        "/documentation/",
        ".md",
        ".html",
        ".json",  # usually config/reports
        ".txt",
        ".rst",
        "readme",
        "changelog",
        "license",
        ".env",
        ".gitignore",
    ]
    return any(p in path for p in doc_patterns)


if __name__ == "__main__":
    main()
