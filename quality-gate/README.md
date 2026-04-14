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

### Option A: Docker (easiest setup)

```bash
cd quality-gate/
docker compose up -d
```

Service runs at `http://127.0.0.1:7733`. The image includes Python + `ruff` + `pylint` so **Python linting works out of the box**. For other languages (JS/TS, Go, Rust, C#, Ruby, PHP), the linter tool is not included in the image — you'll see `linter-missing` info findings for those languages. Options:
- Run the service natively (Option B) — uses the host's installed linters
- Install tools inside the container via a custom Dockerfile
- Ignore it — the fresh reviewer can still validate those files if you configure an API key

### Option B: Native Python (best multi-language coverage)

```bash
cd quality-gate/
pip install -r requirements.txt
python server.py
```

Service picks up whatever linters are installed on the host: `eslint` (via `npx`), `ruff`, `pylint`, `go`, `cargo`, `dotnet`, `rubocop`, `phpstan`. You don't need all of them — only the ones for languages in your codebase.

### Verifying the service is up

```bash
curl http://127.0.0.1:7733/health
# → {"status":"ok","service":"quality-gate"}
```

If you get `connection refused`, check `docker compose ps` (for Docker) or that the Python process is running.

### Enable the Fresh Reviewer

The linter alone only catches mechanical issues. The fresh reviewer is what catches "works but wasteful" patterns. Configure ONE of:

```bash
# Option 1: Claude CLI (best — same model family used elsewhere)
# Just install claude CLI on the host and the reviewer uses it automatically.

# Option 2: OpenAI API
echo "OPENAI_API_KEY=sk-..." >> ~/.claude/council.env

# Option 3: Gemini API
echo "GOOGLE_AI_KEY=AIza..." >> ~/.claude/council.env
```

For Docker, mount the council.env into the container (edit `docker-compose.yml`):
```yaml
    volumes:
      - ./data:/data
      - ${HOME}/.claude/council.env:/root/.claude/council.env:ro
```

Without a configured reviewer, you'll see `reviewer-unavailable` info findings. The gate still works — linter findings are still enforced — but you lose the independent AI review layer.

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
| `GATE_PUBLIC_HOST` | auto | Hostname used in review links (auto-remaps `0.0.0.0` → `127.0.0.1`) |
| `GATE_DB` | `quality-gate.db` | SQLite path for the human review queue |
| `GATE_LINTER_TIMEOUT` | `60` | Linter timeout per file (seconds) |
| `GATE_REVIEWER_TIMEOUT` | `120` | Fresh reviewer timeout (seconds) |
| `GATE_STRICT` | `false` | If `true`, verdict is `FAIL` when neither linter nor reviewer actually ran |
| `GATE_URL` (hook) | `http://127.0.0.1:7733` | Where the hook calls the service |
| `GATE_TIMEOUT` (hook) | `180` | Total timeout the hook waits for verdict |
| `GATE_REQUIRE_HUMAN_REVIEW` (hook) | `false` | If `true`, every change requires human approval |
| `GATE_HUMAN_WAIT` (hook) | `600` | How long to WAIT for the human's decision before blocking (seconds). Default: 10 minutes. |
| `GATE_HUMAN_POLL_INTERVAL` (hook) | `5` | Poll interval while waiting (seconds) |
| `GATE_HUMAN_STATUS_EVERY` (hook) | `30` | How often to print "still waiting..." progress to stderr (seconds) |

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
- Buttons to **Approve**, **Reject**, or **Defer**

### How the agent waits for your decision

When a change requires human review, the `quality-gate-check.py` hook **polls the service and waits** for your decision. The Claude session is paused — the sub-agent cannot complete — until one of these happens:

| Your decision | What the hook does | What the agent sees |
|---|---|---|
| **Approve** | Allows the turn to complete | Sub-agent marks task done normally |
| **Reject** (with comment) | Blocks the turn and surfaces your comment | Orchestrator re-dispatches the agent to address your feedback |
| **Defer** (with comment) | Blocks the turn and surfaces your comment | Session stops; user re-triggers the command when the blocker is cleared |
| **No decision within `GATE_HUMAN_WAIT`** (default 10 min) | Blocks the turn with a timeout message | Session stops; user decides later and re-triggers the command |

While waiting, the hook prints progress to stderr every 30 seconds (configurable via `GATE_HUMAN_STATUS_EVERY`) so you can see it's alive:

```
[quality-gate-hook] Change queued for human review. Open http://127.0.0.1:7733/review/{id} to approve/reject. Waiting up to 600s for a decision.
[quality-gate-hook] Still waiting for human decision (570s remaining)...
[quality-gate-hook] Still waiting for human decision (540s remaining)...
[quality-gate-hook] Human approved {id}. Allowing turn to complete.
```

### Picking the right wait time

- **Short reviews** (quick eyeball checks): default 10 min is fine
- **Thorough reviews**: bump `GATE_HUMAN_WAIT=3600` (1 hour) for deeper inspection
- **Async reviews** (review comes hours later): use `GATE_HUMAN_WAIT=60` + manual re-trigger — keeping a Claude session open for hours isn't practical

If the wait times out, the review is still in the queue — nothing is lost. Decide in the UI, then re-trigger the command.

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

## Verifying end-to-end

After installation, run these to confirm each layer works. Exact commands, exact expected output:

```bash
# 1. Health
curl http://127.0.0.1:7733/health
# expect: {"status":"ok","service":"quality-gate"}

# 2. Python linting works (ruff catches unused imports)
curl -s -X POST http://127.0.0.1:7733/gate/check \
  -H "Content-Type: application/json" \
  -d '{"session_id":"t","agent_name":"test","project_root":"/tmp",
       "changed_files":[{"path":"bad.py","content":"import os\nimport sys\ndef f(x):\n    y=5\n    return x"}]}'
# expect: verdict = FAIL, findings include F401 (unused imports) and F841 (unused variable)

# 3. Weak validation warning for unsupported language (without a reviewer API)
curl -s -X POST http://127.0.0.1:7733/gate/check \
  -H "Content-Type: application/json" \
  -d '{"session_id":"t","agent_name":"test","project_root":"/tmp",
       "changed_files":[{"path":"x.ts","content":"const x = 1"}]}'
# expect: verdict = PASS (non-strict), weak-validation info finding present,
#         linter_ran=false, reviewer_ran=false

# 4. Human review queue
CID=$(curl -s -X POST http://127.0.0.1:7733/gate/check \
  -H "Content-Type: application/json" \
  -d '{"session_id":"t","agent_name":"test","project_root":"/tmp",
       "changed_files":[{"path":"x.py","content":"def f(): pass"}],
       "require_human_review":true}' | python -c "import json,sys;print(json.load(sys.stdin)['check_id'])")
echo "Review at: http://127.0.0.1:7733/review/$CID"
# Open that URL in a browser — Approve/Reject/Defer buttons should work.
```

If you've configured an OpenAI/Gemini/Claude reviewer, test that too:

```bash
curl -s -X POST http://127.0.0.1:7733/gate/check \
  -H "Content-Type: application/json" \
  -d '{"session_id":"t","agent_name":"test","project_root":"/tmp",
       "changed_files":[{"path":"bad.ts","content":"function find(users, id){for(let i=0;i<users.length;i++){if(users[i].id===id)return users[i]}return null}"}]}'
# expect: findings from source="reviewer" pointing out the linear search
#         (Set/Map recommendation) and reviewer_ran=true
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
