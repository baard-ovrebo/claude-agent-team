#!/usr/bin/env python3
"""
Quality Reminder — UserPromptSubmit Hook

Runs before every user message is submitted to Claude. Prepends a short
reminder about Rule Z (Code Quality Enforcement) to keep it in short-term
context regardless of conversation length.

Only fires if the user prompt appears to be about development work (asking for
code, fixes, features). Skips for meta commands like `/help`, `/config`,
`/council --config`, `/tempo`, etc.

Installation: Called by the UserPromptSubmit hook in settings.json.
"""
import json
import sys
import re


SKIP_COMMANDS = {
    "/help", "/config", "/clear", "/fast", "/tempo",
    "/council --config", "/council --cost",
    "/jira teams", "/jira sprint",
    "/git status",
    "/deps --vuln-only", "/deps --outdated", "/deps --license",
    "/repo-setup --analyze-only",
    "/impact-scan --convert-json",
    "/changelog",
    "/jam",
}


REMINDER = """
[RULE Z — CODE QUALITY REMINDER]
All code written in this turn MUST be production-optimized:
- Zero allocations in hot paths (loops, renders, request handlers)
- Proper data structures (Set/Map for O(1) lookups, not linear scans)
- All resources cleaned up (listeners, timers, subscriptions, connections)
- Batched operations (no N+1 queries, batch updates)
- Must run well on 8 GB RAM / integrated GPU / slow disk / 3G network

When dispatching sub-agents, include the [QUALITY BAR — NON-NEGOTIABLE] block
and require a `## Quality Audit` section in their output. If that section is
missing from any agent's report, RE-DISPATCH them to add it before marking the
task done. The Quality Audit is not optional.
"""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    prompt = payload.get("prompt", "") or payload.get("user_prompt", "")
    if not prompt:
        sys.exit(0)

    # Skip for meta/non-development prompts
    prompt_lower = prompt.lower().strip()
    for skip in SKIP_COMMANDS:
        if prompt_lower.startswith(skip):
            sys.exit(0)

    # Skip for very short prompts that are unlikely to trigger code work
    if len(prompt.strip()) < 10:
        sys.exit(0)

    # Skip if the prompt is clearly not about development
    non_dev_keywords = ["hello", "hi", "thanks", "thank you", "goodbye", "bye"]
    if prompt_lower in non_dev_keywords:
        sys.exit(0)

    # Emit the reminder as additional context
    # UserPromptSubmit hook can add to the context via stdout JSON
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": REMINDER.strip(),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
