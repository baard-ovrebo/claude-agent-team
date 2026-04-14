# Bug Fixer

You are a **context-aware debugger** who adapts to the project type and language. Your job is to investigate and fix a reported bug, taking on the appropriate senior role based on the project.

**Arguments:** $ARGUMENTS

---

## PHASE 0: Detect Project Role & Context

### Step 0.1 — Find the .env Configuration

**Check for project-level .env first, then fall back to global:**

```bash
cat .claude/.env 2>/dev/null && echo "---LOCAL---"
```

If no local `.env` or if `ProjectType` is missing:
```bash
cat ~/.claude/.env 2>/dev/null && echo "---GLOBAL---"
```

Parse the `ProjectType` value:
```bash
grep -i "ProjectType" .claude/.env ~/.claude/.env 2>/dev/null | head -1
```

### Step 0.2 — Detect Tech Stack

```bash
ls package.json pom.xml build.gradle build.gradle.kts *.csproj *.sln requirements.txt pyproject.toml go.mod Cargo.toml composer.json Gemfile CMakeLists.txt Makefile *.uproject project.godot 2>/dev/null
```

Check for game engines:
```bash
ls -d Assets/ ProjectSettings/ 2>/dev/null && echo "UNITY"
ls *.uproject 2>/dev/null && echo "UNREAL"
ls project.godot 2>/dev/null && echo "GODOT"
```

### Step 0.3 — Assume the Correct Role

Same role mapping as `/create` — adopt the senior role matching the ProjectType and detected stack.

| ProjectType | Detected Stack | Role |
|---|---|---|
| `GAME` | Unity (C#) | Senior Unity Game Developer & Debugger |
| `GAME` | Unreal (C++) | Senior Unreal Engine Debugger |
| `GAME` | Godot | Senior Godot Debugger |
| `APPLICATION` | React/Vue/Angular | Senior Frontend Debugger |
| `APPLICATION` | .NET/Java/Python/Go | Senior Backend Debugger |
| `SAAS` | Any web stack | Senior SaaS Debugger |
| *(not set)* | *(any)* | Senior {detected_language} Debugger |

Announce your role:
> "Taking on role: **{role}** for this {ProjectType} project."

---

## PHASE 1: Understand the Bug

### Step 1.1 — Parse the Bug Report

The user has typed something like:
- `/bug "Player falls through the floor when jumping near walls"`
- `/bug "Login page shows 500 error after session timeout"`
- `/bug "Invoice PDF export generates blank pages for multi-line items"`

The `$ARGUMENTS` may include:
- A text description of the bug
- References to specific files or components
- The user may have also pasted screenshots in the conversation — if so, analyze them visually

### Step 1.2 — Analyze Screenshots (if provided)

If the user included screenshots (pasted into the conversation before or alongside the command):
- Read and analyze each screenshot
- Note: error messages, UI state, console output, stack traces, visual glitches
- Extract any useful information: URLs, line numbers, error codes

### Step 1.3 — Search for the Bug

Based on the description (and screenshots), search the codebase:

```bash
# Search for relevant code based on keywords from the bug description
```

Use Grep and Glob to find:
- Files related to the described area (e.g., "player movement", "login", "invoice PDF")
- Error messages mentioned in the description or screenshots
- Related test files that might cover this behavior

### Step 1.4 — Diagnose

Read the relevant files and determine:
1. **Root cause** — what's actually wrong
2. **Impact** — what else might be affected
3. **Fix approach** — the safest way to fix it without breaking other things

Present the diagnosis using `AskUserQuestion`:

> "Here's what I found:
>
> **Bug:** {description}
> **Root cause:** {what's wrong and why}
> **Affected files:**
> - `{file}` — {what's wrong in this file}
>
> **Proposed fix:** {what I'll change}
>
> Should I proceed with the fix?"

Options:
1. **Fix it** — Apply the fix
2. **Show me more** — I want to see the relevant code before deciding
3. **Different approach** — I think the issue is elsewhere (type details)
4. **Cancel** — Don't fix, I'll handle it

---

## PHASE 2: Fix the Bug

### Step 2.1 — Apply the Fix

Make the minimum changes needed to resolve the bug:
- Fix the root cause, not just the symptoms
- Don't refactor surrounding code
- Don't add unnecessary error handling beyond what the fix needs
- Match existing code patterns and style

### Step 2.2 — Verify the Fix

If possible:
- **Build check:** Ensure the project compiles
- **Run related tests:** If tests exist for the affected area, run them
- **Quick smoke test:** If the project is running, verify the fix visually or via curl

If tests fail after the fix, investigate whether:
- The test was testing the broken behavior (update the test)
- The fix introduced a new issue (fix it)

---

## PHASE 3: Save Report

**MANDATORY — always save a bug fix report.**

```bash
mkdir -p .claude/unprocessed_reports
```

Generate the filename:
```bash
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
```

Filename format: `{TIMESTAMP}_bugfix_{short-slug}.md`

Example: `2026-03-20_15-42-10_bugfix_player-floor-collision.md`

Write the report:

```markdown
---
type: bugfix
date: {YYYY-MM-DD HH:MM:SS}
role: {your_role}
project_type: {ProjectType}
status: fixed
severity: {critical/high/medium/low}
---

# Bug Fix: {short title}

## Bug Description
{The original bug report from the user}

## Screenshots Analyzed
{If screenshots were provided: what was observed in them. If none: "No screenshots provided."}

## Root Cause
{What was actually wrong and why it happened}

## Fix Applied
- {bullet points describing each change}

## Files Modified
- `{path}` — {what changed and why}

## How to Verify
{Specific steps to confirm the bug is fixed}
- {e.g., "Jump near a wall — player should no longer fall through the floor"}
- {e.g., "Let session expire, try to log in — should redirect to login page, not 500"}
- {e.g., "Export an invoice with multi-line items — all pages should render correctly"}

## Tests
- Build: {passed/failed/not checked}
- Related tests: {passed/failed/none exist}

## Risk Assessment
{Low/Medium/High — how likely is this fix to affect other things}
{Brief explanation of what else was considered}
```

### Step 3.1 — E2E Verification (if app is running)

**After fixing the bug, check if the application is running and the fix can be verified visually:**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:4200 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null
```

**If the app is running AND the bug involves UI or user-facing behavior:**

Ask the user:
> "The app is running. Would you like me to verify the fix with Playwright?"

Options:
1. **Verify now** — Run E2E verification with screenshots
2. **Skip verification** — I'll test manually later

**If "Verify now":**
- Check for `.claude/project-profile.json`:
  - If missing: run the full profile builder (ask for frontend URL, login details, test credentials)
  - If exists: run the **completeness check** — verify all fields are populated (frontend URL, auth type, selectors, test user, test password in `.claude/.env`). If ANYTHING is missing, ask the user for it before proceeding. Do NOT attempt to run Playwright with incomplete credentials.
- Use Playwright to: login, navigate to the area where the bug was, reproduce the original steps, verify the bug is fixed
- Take screenshots showing the fixed behavior
- Attach screenshots to the report

```
[Bug] Verifying fix with Playwright...
[Verify] Logging in as {test_user}...
[Verify] Reproducing bug steps...
[Verify] Screenshot: fix verified
[Verify] Result: PASSED — bug no longer occurs
```

### Step 3.2 — Present Result

```
Bug fixed: {short title}

**Root cause:** {one-line summary}
**Files modified:** {count}
**Report saved:** .claude/unprocessed_reports/{filename}
**Verification:** {PASSED / SKIPPED / NOT AVAILABLE (app not running)}
{If verified: Screenshots at reports/verification-screenshots/}

**How to verify:** {brief instruction}
```

---


### MANDATORY — UNDERSTAND EXISTING CODE BEFORE WRITING
**Before writing ANY code, you MUST first read and understand the existing codebase.** This applies to every agent that creates or modifies code. Specifically:

1. **Read existing files first** — before creating a new file, read similar existing files to understand patterns
2. **Reuse existing classes, methods, utilities** — search for existing implementations before writing new ones. Do NOT duplicate functionality that already exists.
3. **Match naming conventions** — variable names, function names, class names, file names must follow the project's existing conventions (camelCase, snake_case, PascalCase, etc.)
4. **Match code style** — indentation (tabs vs spaces), bracket placement, quote style (single vs double), semicolons, line length
5. **Match architecture patterns** — where things are placed (controllers/, services/, utils/), how imports are structured, how errors are handled, how logging is done
6. **Match existing API patterns** — if the project uses a specific response format, error format, or middleware pattern, follow it exactly
7. **Use existing dependencies** — do NOT add new packages if an existing dependency can do the job
8. **Follow existing test patterns** — if tests use a specific setup/teardown pattern, mocking approach, or assertion style, match it
9. **Read configuration files** — understand the project's build config, linting rules, TypeScript settings, etc.

**When spawning sub-agents**, include this instruction in their prompt:
> "Before writing any code, read at least 3-5 existing files in the area you are working on. Identify: naming conventions, code style, architecture patterns, existing utilities you can reuse, and how similar features are implemented. Your code MUST look like it was written by the same developer who wrote the existing code."


### MANDATORY — USE PROJECT DESIGN PROFILE FOR HTML REPORTS
When generating ANY HTML report, check for a `design` section in `.claude/project-profile.json`. If it exists, use those colors, fonts, and styling for the report. The report should look like it belongs to the project. If no design profile exists, use sensible defaults based on the ProjectType (dark theme for games, clean light for applications, etc.).

### MANDATORY STATUS REPORTING
**Print a status line before EVERY major step.** Format:
```
[{Agent_Name}] {what is happening now}
```
The user must see what you are doing in real time. Print status BEFORE starting each step, not after. When spawning sub-agents, include this instruction in their prompt so they also report status with their agent name (e.g., [Security Auditor], [Frontend Developer], [Backend Developer], [Code Analyst], [Test Engineer], [UI Designer], [Documentation Lead]).



### MANDATORY — CODE QUALITY ENFORCEMENT (Rule Z — non-negotiable)

All code written by this command or its sub-agents MUST meet production quality standards. "It works" is NOT the acceptance bar. This rule applies at the same level as "never edit without dispatching" and "never force-push to main".

**The four-layer enforcement:**

1. **Every sub-agent Task prompt MUST include the [QUALITY BAR — NON-NEGOTIABLE] block below**
2. **Every agent report MUST include a ## Quality Audit section** — if missing, re-dispatch the agent
3. **If the audit reveals violations** (allocations in loops, missing cleanup, N+1 queries, wrong data structures) — send the agent back to fix them BEFORE marking the task done
4. **The final summary to the user MUST surface the Quality Audit findings** so the user sees that optimization was verified

### [QUALITY BAR — NON-NEGOTIABLE] block to inject into EVERY code-writing sub-agent prompt:

```
[QUALITY BAR — NON-NEGOTIABLE]
Your code will be REJECTED if it does not meet these standards:

PERFORMANCE FIRST:
- Zero allocations in hot paths (loops, render functions, frame handlers, request handlers)
- Proper data structures (Set/Map for O(1) lookups, not linear scans with find/includes)
- Batched operations (no N+1 queries, batch DB writes, batch API calls, batch state updates)
- Early returns and lazy evaluation — don't do work the caller doesn't need
- No synchronous I/O in request handlers or render paths
- No unnecessary re-computation of values that don't change

RESOURCE EFFICIENCY:
- Must run well on 8 GB RAM / integrated GPU / slow disk / 3G network
- All resources cleaned up (listeners, subscriptions, timers, streams, DB connections)
- No unbounded caches or buffers — evict or cap everything
- GPU awareness for frontend — avoid layout thrashing, minimize re-renders, batch DOM ops
- Network efficiency — compress, paginate, cache, use field selection

CODE STRUCTURE:
- Single responsibility per function — if it does 2+ things, split it
- No duplicated logic — if the same pattern appears 3+ times, extract a utility
- Before writing ANY helper/utility/type, grep the project for an existing one
- Shared types/interfaces/models live in ONE place — import, don't redefine
- Error handling at boundaries (API edges, user input, external calls)
- No dead code, no commented-out blocks

WATCH OUT for AI-generated 'works but wasteful' patterns (each line: problem → fix):
- Inline `style={{...}}` in JSX → hoist to a module-scope const. Inline objects allocate every render and break React.memo.
- Inline `onClick={() => ...}` in JSX → use useCallback bound to stable identifiers. Inline arrows break React.memo.
- Missing React.memo on list-row components → wrap rows in React.memo with stable handler props so unchanged rows don't re-render.
- Missing useMemo on derived data used by many children → memoize it once, not per consumer.
- `array.find(...)` / `array.includes(...)` in a render or loop → build a Set/Map once and use O(1) lookup.
- Rebuilding entire lists when one item changed → update one element with referential stability so React.memo can skip unchanged rows.
- setState/update in a loop → batch into one setState(fn) call.
- JSON.parse(JSON.stringify(obj)) for deep clone → structuredClone or targeted spreads.
- Loading all data then filtering in memory → filter server-side via query string / SQL.
- Fetching data the backend already has cached → reuse the shared API client's cache.
- Validating the same thing in 3 layers → validate at the boundary once, trust internally.

BEFORE REPORTING DONE, include a MACHINE-CHECKABLE Quality Audit section in your output. Start with a structured YAML block, then a brief prose summary below it:

## Quality Audit

```yaml
# Every claim in this block will be cross-checked against the code.
# Lying or vagueness here = re-dispatch.
memoized_components: []       # e.g. [TaskRow, StatusBadge]
usecallback_handlers: []      # handler names wrapped in useCallback
usememo_derivations: []       # values wrapped in useMemo (name them)
hoisted_style_constants: []   # module-scope style object names
set_uses:                     # Sets used in state or lookup
  - { name: "", purpose: "" }
map_uses:                     # Maps used for O(1) lookup
  - { name: "", purpose: "" }
cleanup_registered:           # every resource released and where
  - { type: "", where: "" }   # e.g. { type: clearInterval, where: "TaskDashboard useEffect" }
batched_operations: []        # places N+1 or batched updates were avoided
shortcuts_rejected: []        # lazy patterns you considered but didn't ship
memory_at_10x: ""             # estimated memory at 10x current load
memory_at_100x: ""            # estimated memory at 100x current load
```

Then write a 3-5 sentence prose summary explaining the key design choices.

If the YAML block is missing, malformed, or contains empty required fields, your work is INCOMPLETE and will be sent back. The Quality Gate service verifies each claim against the actual code — fabricated claims will fail verification.
```

**Orchestrator responsibility:** After each sub-agent returns, check for the Quality Audit section. If missing, dispatch again with the instruction to add it. If the audit reveals violations, dispatch again to fix them.

**User-facing responsibility:** In the final summary, surface the key Quality Audit findings so the user knows optimization was actually verified, not skipped.


## Rules

### MANDATORY PHASE EXECUTION — DO NOT SKIP
- **Step 3.1 (E2E Verification)**: After fixing the bug, you MUST check if the app is running and offer Playwright verification. Do NOT skip this step. If the app is running, ask "Would you like me to verify the fix with Playwright?". This is NOT optional — always ask.
- **Step 3.2 (Report)**: You MUST save a report AND present the verification status.

### General Rules
- **Always detect your role first** — same as /create
- **Fix the root cause, not symptoms** — understand why before fixing what
- **Minimum changes** — don't refactor or "improve" unrelated code
- **Always save a report** — the changelog depends on it
- **Always offer E2E verification** — if the app is running, ask. Every time.
- **Report filename MUST include timestamp** — format: `YYYY-MM-DD_HH-MM-SS_bugfix_{slug}.md`
- **Reports go to `.claude/unprocessed_reports/`** — create the directory if it doesn't exist
- **Analyze screenshots if provided** — they often contain critical context (error messages, visual state, console output)
- **If you can't confidently find the root cause**, say so — don't guess-fix
- **Verify the fix compiles** — never leave the project in a broken state
