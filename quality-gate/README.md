# Quality Gate Service

A local HTTP service that validates AI-generated code using **three independent checks** before allowing a sub-agent to complete:

1. **Linter pass** — language-specific (ESLint, ruff/pylint, go vet, cargo clippy, dotnet format, rubocop, phpstan)
2. **Fresh Claude reviewer** — independent Claude instance that reviews the diff with NO knowledge of the original agent's reasoning (prevents anchoring bias)
3. **Optional human review queue** — web UI for flagging items that need a human eye

Returns `PASS`, `FAIL` (with findings), or `HUMAN_REVIEW_REQUIRED`. The `quality-gate-check.py` hook uses the verdict to allow or block sub-agent completion.

## Why This Exists

Prompt-level enforcement (Rule Z) relies on the AI reading and following instructions. It's strong, but it's **soft enforcement** — there's no external validator. This service adds the external validator:

- **Linters catch mechanical issues** the AI might overlook (unused imports, wrong types, lint rules)
- **A fresh reviewer catches code-review-level issues** — an independent Claude instance sees the diff cold and spots things the original agent would rationalize
- **Human review catches judgment calls** — for high-stakes changes, a human decides

Together with the four enforcement layers in the command files, this makes it **as close to impossible as reasonable** for AI-generated code to skip quality review.

## Architecture

```
Agent finishes code
    ↓
SubagentStop hook (quality-audit-check.py)
    ↓  (if ## Quality Audit present)
SubagentStop hook (quality-gate-check.py)
    ↓  POST /gate/check
Quality Gate service
    ├── Linter pass (parallel per file)
    ├── Fresh reviewer (parallel, isolated Claude CLI)
    └── Human queue (if --require-human-review)
    ↓
Verdict: PASS | FAIL | HUMAN_REVIEW_REQUIRED
    ↓
Hook allows or blocks the agent turn
```

## Installation

### Option A: Docker (recommended)

```bash
cd quality-gate/
docker compose up -d
```

Service runs at `http://127.0.0.1:7733`.

### Option B: Native Python

```bash
cd quality-gate/
pip install -r requirements.txt
python server.py
```

## Wiring the Hook

Add to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          { "type": "command", "command": "python \"<repo>/hooks/quality-audit-check.py\"" },
          { "type": "command", "command": "python \"<repo>/hooks/quality-gate-check.py\"" }
        ]
      }
    ]
  }
}
```

Replace `<repo>` with the absolute path to where you cloned `claude-agent-team`.

Both hooks run in order:
1. `quality-audit-check.py` verifies the agent wrote a `## Quality Audit` section
2. `quality-gate-check.py` pushes the code to the gate service for linter + fresh reviewer checks

**If the service is down**, the hook logs a warning and allows the turn — it never blocks on service unavailability.

## Configuration

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `GATE_HOST` | `127.0.0.1` | Service bind address |
| `GATE_PORT` | `7733` | Service port |
| `GATE_DB` | `quality-gate.db` | SQLite path for the human review queue |
| `GATE_LINTER_TIMEOUT` | `60` | Linter timeout per file (seconds) |
| `GATE_REVIEWER_TIMEOUT` | `120` | Fresh reviewer timeout (seconds) |
| `GATE_URL` (hook) | `http://127.0.0.1:7733` | Where the hook calls the service |
| `GATE_TIMEOUT` (hook) | `180` | Total timeout the hook waits for verdict |
| `GATE_REQUIRE_HUMAN_REVIEW` (hook) | `false` | If `true`, every change requires human approval |

## Fresh Reviewer — How It Works

The reviewer runs a SEPARATE process (via `claude -p`, OpenAI API, or Gemini API) that sees ONLY:
- The changed files (content or diff)
- The original agent's Quality Audit (as context, not as truth)

It does NOT see the original agent's reasoning, the user's request, or any conversation history. This is deliberate: an anchored reviewer in the same conversation would justify the original choices. A fresh reviewer sees them for what they are.

Priority order:
1. **`claude` CLI** (best — same model family, same standards)
2. **OpenAI API** (fallback — needs `OPENAI_API_KEY` in `.claude/council.env`)
3. **Gemini API** (final fallback — needs `GOOGLE_AI_KEY` in `.claude/council.env`)

If none are available, the reviewer returns a note telling the user to install one. The linter still runs.

## Human Review UI

Open `http://127.0.0.1:7733/` in your browser to see pending review items.

Each item shows:
- The agent that made the change
- The files affected
- The agent's Quality Audit claims
- All findings from the linter and fresh reviewer
- Buttons to approve, reject, or defer

When you decide, the agent's turn in Claude Code unblocks (if polling) or the user can re-run the dispatch.

## API

### POST /gate/check

Request:
```json
{
  "session_id": "uuid",
  "agent_name": "frontend-dev",
  "project_root": "/path/to/project",
  "changed_files": [
    { "path": "src/foo.ts", "content": "..." }
  ],
  "quality_audit": "markdown text from agent",
  "require_human_review": false
}
```

Response:
```json
{
  "check_id": "uuid",
  "verdict": "PASS | FAIL | HUMAN_REVIEW_REQUIRED",
  "summary": "All checks passed",
  "findings": [
    { "source": "linter|reviewer|human", "severity": "critical|major|minor|info",
      "file": "...", "line": 42, "rule": "...", "message": "..." }
  ],
  "linter_ran": true,
  "reviewer_ran": true,
  "human_review_url": "http://.../review/uuid",
  "duration_ms": 3420
}
```

### GET /

HTML queue of pending human reviews.

### GET /review/{check_id}

HTML review page — approve/reject/defer.

### POST /review/{check_id}/decide

```json
{ "decision": "APPROVE|REJECT|DEFER", "comment": "..." }
```

## Adding a New Linter

Edit `linters.py`:
1. Add the file extension → language mapping in `_EXT_TO_LANG`
2. Add a runner function `_run_<lang>(file_path, project_root, content) -> list[dict]`
3. Register it in the `runners` dict in `run_linter`

Each runner returns a list of `{severity, line, rule, message}` dicts.

## Troubleshooting

**"Service not reachable"** — check the service is running: `curl http://127.0.0.1:7733/health`

**"No fresh reviewer available"** — install `claude` CLI or set API keys in `.claude/council.env`

**Linter errors marked `[info]`** — the linter isn't installed or couldn't run. Install it in the project (`npm install -D eslint`, `pip install ruff`, etc.)

**False positives from the fresh reviewer** — review the finding. If it's wrong, it's an uncommon miss; if the pattern recurs, fix the reviewer prompt in `reviewer.py` (`_REVIEWER_PROMPT`)

**Takes too long** — tune `GATE_LINTER_TIMEOUT` and `GATE_REVIEWER_TIMEOUT`; the default totals are ~3 min which is fine for a turn gate
