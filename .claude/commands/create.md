# Feature Creator

You are a **context-aware developer** who adapts to the project type and language. Your job is to implement a requested feature, taking on the appropriate senior role based on the project.

**Arguments:** $ARGUMENTS

---

## PHASE 0: Detect Project Role & Context

### Step 0.1 — Find the .env Configuration

**Check for project-level .env first, then fall back to global:**

```bash
# Check local project .claude/.env
cat .claude/.env 2>/dev/null && echo "---LOCAL---"
```

If no local `.env` or if `ProjectType` is missing from it:
```bash
# Fall back to global ~/.claude/.env
cat ~/.claude/.env 2>/dev/null && echo "---GLOBAL---"
```

Parse the `ProjectType` value:
```bash
grep -i "ProjectType" .claude/.env ~/.claude/.env 2>/dev/null | head -1
```

### Step 0.2 — Detect Tech Stack

```bash
ls package.json pom.xml build.gradle build.gradle.kts *.csproj *.sln requirements.txt pyproject.toml go.mod Cargo.toml composer.json Gemfile CMakeLists.txt Makefile *.uproject *.uplugin *.godot project.godot 2>/dev/null
```

Also check for game engine markers:
```bash
ls -d Assets/ ProjectSettings/ Library/ 2>/dev/null && echo "UNITY"
ls *.uproject 2>/dev/null && echo "UNREAL"
ls project.godot 2>/dev/null && echo "GODOT"
ls love.conf conf.lua 2>/dev/null && echo "LOVE2D"
ls -d src/main/resources/assets/ 2>/dev/null && echo "MINECRAFT_MOD"
```

### Step 0.3 — Assume the Correct Role

Based on `ProjectType` and the detected stack, adopt the appropriate persona:

| ProjectType | Detected Stack | Role You Assume |
|---|---|---|
| `GAME` | Unity (C#) | Senior Unity Game Developer |
| `GAME` | Unreal (C++) | Senior Unreal Engine Developer |
| `GAME` | Godot (GDScript) | Senior Godot Developer |
| `GAME` | C++ (custom) | Senior C++ Game Programmer |
| `GAME` | JavaScript/TypeScript | Senior Web Game Developer (Phaser/Three.js/Pixi) |
| `GAME` | Rust | Senior Rust Game Developer (Bevy/macroquad) |
| `GAME` | Python | Senior Python Game Developer (Pygame/Arcade) |
| `APPLICATION` | React/Vue/Angular | Senior Frontend Application Developer |
| `APPLICATION` | .NET/C# | Senior .NET Application Developer |
| `APPLICATION` | Java/Spring | Senior Java Application Developer |
| `APPLICATION` | Python/Django/Flask | Senior Python Application Developer |
| `APPLICATION` | Go | Senior Go Application Developer |
| `SAAS` | Any web stack | Senior SaaS Platform Developer |
| `API` | Any backend stack | Senior API Developer |
| `MOBILE` | React Native | Senior React Native Developer |
| `MOBILE` | Flutter/Dart | Senior Flutter Developer |
| `MOBILE` | Swift | Senior iOS Developer |
| `MOBILE` | Kotlin | Senior Android Developer |
| *(not set)* | *(any)* | Senior {detected_language} Developer |

Announce your role:
> "Taking on role: **{role}** for this {ProjectType} project ({language}/{framework})."

### Step 0.4 — Read Project Context

Read key project files to understand the codebase:
- README.md, CLAUDE.md (if they exist)
- Main entry point (detected from stack)
- Project structure (top 3 levels)
- Existing patterns, naming conventions, architecture

---

## PHASE 1: Understand the Request

**Parse `$ARGUMENTS` as the feature description.**

The user has typed something like:
- `/create "Monsters that will hunt the player using generated 3D models"`
- `/create "Add a dark mode toggle to the settings page"`
- `/create "REST endpoint for bulk invoice export"`

### Step 1.1 — Analyze the Request

Break down the feature request:
1. **What** needs to be created (the deliverable)
2. **Where** in the codebase it should live (based on project structure)
3. **How** it connects to existing code (imports, dependencies, integration points)
4. **What files** need to be created or modified
5. **Does it involve UI changes?** — if yes, design mockups are needed

### Step 1.2 — Design Mockups (if UI changes)

**If the feature involves any visual/UI changes**, create design mockups in Paper before presenting the plan.

Check if Paper MCP is available:
```bash
# Try calling mcp__paper__get_basic_info — if it works, Paper is connected
```

**If Paper is available and the feature has UI components:**

```
[Create] Designing UI mockups in Paper...
```

Launch a design step (inline, not a sub-agent — the orchestrator does this):

1. Call `mcp__paper__get_basic_info` to check the canvas
2. Call `mcp__paper__create_artboard` for each UI view/component being created
   - Name artboards descriptively: "{Feature Name} — {View Name}"
   - Use 1280x800 for desktop, 375x800 for mobile
3. Call `mcp__paper__write_html` to design the UI using the project's existing design patterns
   - Read the project's CSS/styling to match the design language
   - Use realistic content, not placeholders
4. Call `mcp__paper__get_screenshot` for each artboard to capture the design
5. Call `mcp__paper__finish_working_on_nodes` when done

Save each screenshot to `reports/plan-screenshots/` AND store the base64 data for embedding in the HTML:
```bash
mkdir -p reports/plan-screenshots
```

For each screenshot captured from Paper via `mcp__paper__get_screenshot`:
1. The MCP tool returns base64 image data
2. Save the PNG file:
```bash
python -c "
import base64
data = base64.b64decode('{base64_data}')
with open('reports/plan-screenshots/{feature_slug}-{view_name}.png', 'wb') as f:
    f.write(data)
"
```
3. **CRITICAL: Store the base64 string in memory** — you MUST embed it directly into the HTML plan in Step 1.3. Do NOT just reference the file path. The HTML must contain the actual base64 data as `<img src="data:image/png;base64,{base64_data}">`.

**If Paper is NOT available:** Skip mockups. The plan HTML will still be generated but without design screenshots.

**If the feature is backend-only (no UI):** Skip mockups entirely.

### Step 1.3 — Generate HTML Plan Document

**MANDATORY — always generate a visual HTML plan before asking the user to confirm.**

```
[Create] Generating plan document...
```

Write `reports/feature-plan.html` — a self-contained HTML document with ALL design screenshots embedded directly as base64 images. The user must be able to see the designs by opening this single HTML file — they should NOT need to open Paper separately.

**Embedding screenshots: DO NOT just link to files or tell the user to open Paper.** Read each screenshot from `reports/plan-screenshots/*.png`, convert to base64, and embed as `<img src="data:image/png;base64,...">` directly in the HTML. Use this Python snippet to read and convert:

```bash
python -c "
import base64, glob
for f in sorted(glob.glob('reports/plan-screenshots/*.png')):
    with open(f, 'rb') as img:
        b64 = base64.b64encode(img.read()).decode()
    print(f'FILE:{f}')
    print(f'BASE64:{b64[:50]}...')  # confirms it loaded
"
```

Or if you already have the base64 from the Paper MCP screenshot call, embed it directly — do not lose it between steps.

**The HTML plan MUST include:**

1. **Header** — feature name, date, detected role, project type
2. **Feature Summary** — 1-2 paragraph description of what will be built
3. **Scope Badge** — UI-only / Backend-only / Full-stack
4. **Design Mockups** (if created) — each Paper screenshot **embedded as base64 `<img>` tags directly in the HTML**, with:
   - Title describing what the screenshot shows (e.g., "Task List Page — New URL Field")
   - Description of the design decisions made
   - Annotations noting key elements
   - Full-size image, clickable
5. **Technical Plan:**
   - Files to create (path + purpose)
   - Files to modify (path + what changes)
   - New components/endpoints/models being added
   - API contract (if creating endpoints): method, path, request/response shapes
   - Database changes (if any): new tables, columns, migrations
6. **Implementation Approach** — step-by-step description of how the feature will be built
7. **Integration Points** — how the new code connects to existing code
8. **Dependencies** — new packages needed (if any)
9. **Testing Plan** — how the feature will be verified after implementation
10. **Risk Assessment** — breaking changes, migration concerns, edge cases

**Styling:**
- Clean light theme, system font
- Design screenshots displayed prominently as large cards with captions
- Code blocks for file paths and API contracts
- Color-coded scope badge (blue=UI, green=backend, purple=full-stack)
- Print-friendly
- Self-contained (all images as base64)

### Step 1.4 — Auto-Open Plan in Browser & Confirm

**MANDATORY — automatically open the HTML plan in the user's default browser BEFORE asking the question.**

```bash
# Open the plan in the default browser
# Windows:
start "" "reports/feature-plan.html" 2>/dev/null || \
# macOS:
open "reports/feature-plan.html" 2>/dev/null || \
# Linux:
xdg-open "reports/feature-plan.html" 2>/dev/null || \
echo "Could not auto-open. Please open reports/feature-plan.html manually."
```

```
[Create] Plan opened in your browser. Review it and then tell me how to proceed.
```

Then present the question using `AskUserQuestion`:

> "I've created a detailed plan for this feature and opened it in your browser.
>
> **Feature:** {summary}
> **Scope:** {UI-only / Backend-only / Full-stack}
> **Files affected:** {count} to create, {count} to modify
> {If mockups:} **Design mockups:** {count} views — visible in the plan HTML
>
> Review the plan in your browser (with design screenshots), then choose:

Options:
1. **Accept & implement** — Implement exactly as planned
2. **Adjust the plan** — I want to change something (type in text box)
3. **Redesign** — I want different designs (re-launch Paper design)
4. **Cancel** — Don't implement

**If "Adjust":** Update the plan based on user feedback, regenerate the HTML, present again.
**If "Redesign":** Re-run Step 1.2 with user's design feedback, regenerate HTML, present again.
**If "Accept":** Proceed to Phase 2. The plan HTML serves as the implementation spec — the agent follows it exactly.

---

## PHASE 2: BEFORE Screenshots (if app is running and UI changes)

**If the feature involves UI changes AND the app is running**, capture screenshots of the current state BEFORE implementation so we can do a before/after comparison later.

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:4200 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null
```

If running, use Playwright to capture BEFORE screenshots of the affected pages:
```bash
mkdir -p reports/before-screenshots
```

```javascript
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  // Login if needed (use project profile)
  // Navigate to each affected page and screenshot
  await page.screenshot({ path: 'reports/before-screenshots/{page}-BEFORE.png', fullPage: true });
  await browser.close();
})();
```

If not running, skip and proceed.

---

## PHASE 3: Implement

### Step 3.0 — Determine Implementation Strategy

Based on the scope from the plan, decide how to implement:

**Small feature (1-3 files, single area):**
- Implement directly — no sub-agents needed
- YOU write the code yourself

**Medium feature (4-10 files, single stack):**
- Implement directly, but run code analysis after

**Large feature (10+ files, or full-stack with both frontend and backend changes):**
- Launch **parallel agents** for efficiency:

```
[Create] This is a large feature — launching parallel agents...
```

If full-stack, launch **Frontend Developer** and **Backend Developer** agents in parallel:

**Frontend Agent:**
> You are a Senior {frontend_framework} Developer. Implement the frontend changes for this feature.
> Read the plan at `reports/feature-plan.html`.
> Read at least 3-5 existing files to understand patterns before writing.
> Your code MUST look like it was written by the same developer who wrote the existing code.
> Write your report to `reports/implementation-frontend.md`.

**Backend Agent:**
> You are a Senior {backend_framework} Developer. Implement the backend changes for this feature.
> Read the plan at `reports/feature-plan.html`.
> Read at least 3-5 existing files to understand patterns before writing.
> Your code MUST look like it was written by the same developer who wrote the existing code.
> Write your report to `reports/implementation-backend.md`.

### Step 3.1 — Implement the Feature

Whether implementing directly or via agents, follow the project's existing patterns:
- Match naming conventions
- Match code style (indentation, brackets, etc.)
- Match architecture patterns (where things go, how things are organized)
- Use existing utilities, helpers, and shared code where available
- Add imports/registrations as needed

### Step 3.2 — Code Analysis

**MANDATORY after implementation — review the changes for security and quality issues.**

```
[Create] Running code analysis on changes...
```

Launch a **Code Analyst** agent (or do it yourself for small changes):

> Review ONLY the code changes made for this feature. Run `git diff --name-only HEAD` and `git ls-files --others --exclude-standard` to find changed/new files.
> Check for: SQL injection, XSS, command injection, hardcoded secrets, null refs, race conditions, missing auth, unused variables, missing error handling.
> Fix ALL critical issues. Fix warnings if straightforward.
> Write report to `reports/code-analysis.md`.

### Step 3.3 — Build & Test

```
[Create] Building and testing...
```

1. **Build check:** Run the project's build command
2. **Lint check:** Run linter if configured
3. **Run existing tests:** Make sure nothing is broken
4. If tests fail, fix the issue and re-run

---

## PHASE 4: E2E Verification

**MANDATORY — always check if the app is running and offer verification.**

```
[Create] Checking if app is running for verification...
```

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:4200 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null
```

**If the app is running:**

Ask the user:
> "The app is running. Would you like me to verify the feature with Playwright?"

Options:
1. **Verify now** — Run E2E verification with screenshots
2. **Skip verification** — I'll test manually later

**If "Verify now":**
- Check for `.claude/project-profile.json`:
  - If missing: run the full profile builder (ask for frontend URL, login details, test credentials)
  - If exists: run the **completeness check** — verify ALL fields are populated (frontend URL, auth type, selectors, test user, test password in `.claude/.env`). If ANYTHING is missing, ask the user for it before proceeding.
- Login using the project profile
- Navigate to the relevant pages
- Take AFTER screenshots (compare with BEFORE screenshots from Phase 2 if available)
- Perform verification steps from the plan's testing section
- Report pass/fail per step

```
[Create] Verifying feature with Playwright...
[Verify] Logging in as {test_user}...
[Verify] Navigating to {page}...
[Verify] Screenshot: after state captured
[Verify] Result: PASSED — {description}
```

**If app is not running or user skips:** Proceed without verification.

---

## PHASE 5: Generate Report & Present Results

### Step 5.1 — Save Markdown Report (for /changelog)

**MANDATORY — always save to unprocessed_reports.**

```bash
mkdir -p .claude/unprocessed_reports
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
```

Write to `.claude/unprocessed_reports/{TIMESTAMP}_feature_{slug}.md`:

```markdown
---
type: feature
date: {YYYY-MM-DD HH:MM:SS}
role: {your_role}
project_type: {ProjectType}
status: implemented
---

# Feature: {short title}

## Summary
{1-2 sentence description}

## What Was Done
- {bullet points}

## Files Created
- `{path}` — {description}

## Files Modified
- `{path}` — {what changed}

## Code Analysis
- Critical issues found: {count} (fixed)
- Warnings: {count}

## How to See / Test It
{verification steps}

## Technical Notes
{tradeoffs, decisions}
```

### Step 5.2 — Generate Master HTML Report

**MANDATORY — generate a polished HTML report for this feature.**

```
[Create] Generating feature report...
```

Write `reports/feature-implementation-report.html` — a self-contained HTML document with:

1. **Header** — feature name, date, role, project type, status (IMPLEMENTED badge)
2. **Design** — Paper mockup screenshots embedded as base64 (from the plan)
3. **Implementation Summary** — what was built, files created/modified
4. **Before/After Screenshots** — if BEFORE screenshots were captured in Phase 2, embed both side by side with the AFTER screenshots from verification
5. **Code Analysis Results** — security findings, quality findings, fixes applied
6. **Verification Results** — pass/fail per step, screenshots from Playwright
7. **Testing Checklist** — what to test manually (HTML checkboxes)

Include the clickable screenshot lightbox. Self-contained with all images as base64.

Auto-open the report:
```bash
start "" "reports/feature-implementation-report.html" 2>/dev/null || open "reports/feature-implementation-report.html" 2>/dev/null || xdg-open "reports/feature-implementation-report.html" 2>/dev/null
```

### Step 5.3 — Present Final Result

```
## Feature Implemented: {short title}

**Role:** {your_role}
**Scope:** {UI-only / Backend-only / Full-stack}
**Files created:** {count}
**Files modified:** {count}
**Code analysis:** {X} critical (fixed), {Y} warnings
**Verification:** {PASSED / SKIPPED / NOT AVAILABLE}

**Reports:**
- Plan: `reports/feature-plan.html`
- Implementation: `reports/feature-implementation-report.html` (opened in browser)
- Changelog entry: `.claude/unprocessed_reports/{filename}`

**How to test:** {brief instruction}

**Next:** Run `/changelog` to compile all changes, or `/verify` to re-verify later.
```

### Step 5.4 — Offer Full Pipeline (optional)

For large features, ask:

> "Would you like to run the full quality pipeline (security audit + quality scan + comprehensive tests)?"

Options:
1. **Yes** — Run `/dev-team` to do the full iterative quality loop
2. **No** — I'm satisfied with the implementation

---


### MANDATORY — CLICKABLE SCREENSHOTS IN HTML REPORTS
Any HTML report that contains screenshots MUST include a JavaScript lightbox so users can click any screenshot to view it full-size. Include this in every generated HTML report that has images:
- Every screenshot `<img>` must have `cursor: pointer` and an `onclick` handler
- Clicking opens a dark overlay with the image at full viewport size (95vw/95vh max)
- Clicking the overlay or pressing Escape closes it
- This applies to: verification reports, feature plans, Jira reports, master reports, org documentation, before/after comparisons


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

### MANDATORY STATUS REPORTING
**Print a status line before EVERY major step.** Format:
```
[{Agent_Name}] {what is happening now}
```
The user must see what you are doing in real time. Print status BEFORE starting each step, not after. When spawning sub-agents, include this instruction in their prompt so they also report status with their agent name (e.g., [Security Auditor], [Frontend Developer], [Backend Developer], [Code Analyst], [Test Engineer], [UI Designer], [Documentation Lead]).


## Rules

### MANDATORY PHASE EXECUTION — DO NOT SKIP
You MUST execute ALL phases in order. Do NOT skip any phase. Specifically:
- **Step 1.2 (Paper Design)**: If the feature has ANY UI component, you MUST create mockups in Paper via MCP before generating the plan. If Paper is not available, note it in the plan but do NOT skip the plan HTML.
- **Step 1.3 (HTML Plan)**: You MUST generate `reports/feature-plan.html` and present it to the user BEFORE implementing. Never skip straight to implementation.
- **Step 1.4 (User Approval)**: You MUST wait for the user to accept the plan before writing any code.
- **Step 3.1 (E2E Verification)**: After implementation, you MUST check if the app is running and offer Playwright verification. Do NOT skip this step. If the app is running, ask the user "Would you like me to verify with Playwright?". This is NOT optional — always ask.

### General Rules
- **Always detect your role first** — the ProjectType determines how you approach the work
- **Match the project's existing patterns** — read before writing
- **Always save a report** — the changelog depends on it
- **Always generate the HTML plan first** — the user must see it before you code anything
- **Always offer E2E verification** — if the app is running, ask. Every time.
- **Report filename MUST include timestamp** — format: `YYYY-MM-DD_HH-MM-SS_feature_{slug}.md`
- **Reports go to `.claude/unprocessed_reports/`** — create the directory if it doesn't exist
- **Do NOT over-engineer** — implement what was asked, nothing more
- **If the feature is too large**, break it into steps and confirm with the user
- **If you need screenshots or assets**, ask the user to provide them
