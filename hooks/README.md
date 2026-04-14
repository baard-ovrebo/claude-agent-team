# Runtime Quality Enforcement Hooks

These Claude Code hooks enforce **Rule Z — Code Quality** at runtime, not just via prompts. They work as a safety net even if the AI tries to skip the Quality Audit.

## What They Do

### `quality-audit-check.py` — SubagentStop hook
Runs when any sub-agent completes. If the agent made code changes but did **not** include a `## Quality Audit` section in its report, it **blocks** the completion and instructs the orchestrator to re-dispatch the agent with specific audit requirements.

**Runtime enforcement.** The AI cannot skip the audit even if it wants to.

### `quality-reminder.py` — UserPromptSubmit hook
Runs before every user message. Prepends a short Rule Z reminder to the prompt context so the quality mandate stays in short-term memory regardless of conversation length. Skips for meta commands (`/help`, `/tempo`, `/jira teams`, etc.) that don't involve code writing.

**Keeps the rule top-of-mind** in long conversations where earlier system prompts may be deprioritized.

### `quality-gate-check.py` — SubagentStop hook (needs quality-gate service)
Runs AFTER `quality-audit-check.py`. Pushes the sub-agent's code changes to the **Quality Gate service** (`quality-gate/`) which runs linter + fresh Claude reviewer + optional human review queue. Uses the verdict to allow or block the sub-agent turn:

- **PASS** → allow
- **FAIL** → block with the findings; orchestrator re-dispatches
- **HUMAN_REVIEW_REQUIRED** → **polls the service and waits** for your decision (default 10 minutes, configurable via `GATE_HUMAN_WAIT`). On approval: allows. On rejection: blocks with your comment. On timeout: blocks with a "decide and re-trigger" message.

Environment variables (all optional):
- `GATE_URL` (default `http://127.0.0.1:7733`)
- `GATE_TIMEOUT` — total verdict timeout (default 180s)
- `GATE_REQUIRE_HUMAN_REVIEW` — force human review on every change (default `false`)
- `GATE_HUMAN_WAIT` — max time to wait for a human decision (default 600s = 10 min)
- `GATE_HUMAN_POLL_INTERVAL` — poll interval while waiting (default 5s)
- `GATE_HUMAN_STATUS_EVERY` — how often to print a "still waiting..." progress line to stderr (default 30s)

If the Quality Gate service isn't running, this hook logs a warning and allows the turn — it never blocks the pipeline on service unavailability.

See [`../quality-gate/README.md`](../quality-gate/README.md) for the full service setup.

## Installation

Add to your `~/.claude/settings.json` (global) or `.claude/settings.json` (per-project):

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PROJECT_DIR}/hooks/quality-audit-check.py\""
          },
          {
            "type": "command",
            "command": "python \"${CLAUDE_PROJECT_DIR}/hooks/quality-gate-check.py\""
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"${CLAUDE_PROJECT_DIR}/hooks/quality-reminder.py\""
          }
        ]
      }
    ]
  }
}
```

Replace `${CLAUDE_PROJECT_DIR}` with the absolute path to where you cloned this repo, or keep it as-is if you set the env var.

### Requirements
- Python 3 (uses only stdlib — no dependencies)
- The hook scripts must be readable

### Verification

After installation, run a test:

```
/create "Add a helper function that returns the sum of an array"
```

Expected behavior:
- Before Claude starts, you'll see the Rule Z reminder injected into context
- When a sub-agent finishes coding, the hook checks for `## Quality Audit`
- If missing, the hook blocks completion and re-dispatches the agent

## How the Blocking Works

When `quality-audit-check.py` detects a missing audit, it responds with:

```json
{
  "decision": "block",
  "reason": "Missing Quality Audit... re-dispatch with these instructions..."
}
```

Claude Code treats this as a hook block and the orchestrator is forced to address the missing audit before the task can complete.

## Customization

### Disable for a specific project
Add this to that project's `.claude/settings.json`:
```json
{
  "hooks": {
    "SubagentStop": [],
    "UserPromptSubmit": []
  }
}
```

### Change the Quality Audit threshold
Edit `quality-audit-check.py` — the `_is_doc_or_report()` function determines which file types count as "code changes". Add or remove patterns.

### Add more skip commands
Edit `quality-reminder.py` — the `SKIP_COMMANDS` set determines which commands skip the reminder injection.

## Philosophy

These hooks are the **fourth layer** of the quality enforcement model:

1. **Mandate** (prompt text) — explains the standards
2. **Hard Rule** (orchestrator prompt) — same level as "never force-push"
3. **Agent-level QUALITY BAR** (sub-agent prompt) — the agents see it
4. **Runtime hooks** (THIS) — the safety net when 1-3 are ignored

Together, they make it **as close to impossible as prompt engineering allows** for AI-generated code to skip optimization review.
