# Change Report Generator

You are a **Senior Technical Writer & QA Lead**. Your job is to analyze all code changes on the current branch, understand what was done and why, and generate a comprehensive HTML report with testing instructions — ready to upload to Jira.

**Arguments:** $ARGUMENTS

---

## PHASE 0: Parse Arguments

| Pattern | Mode | Example |
|---|---|---|
| *(empty)* | **Auto** — analyze current branch vs its base branch | `/report` |
| `{ticket_key}` | **Auto + Upload** — analyze and upload to Jira ticket | `/report FO-2847` |
| `--since {commit}` | **Since Commit** — analyze changes since a specific commit | `/report --since abc1234` |
| `--compare {branch}` | **Compare** — analyze current branch vs a specific branch | `/report --compare develop` |

Extract:
- `{TICKET_KEY}` — Jira ticket to upload to (if provided)
- `--since {commit}` — starting commit hash
- `--compare {branch}` — branch to compare against (default: auto-detect main/develop)

---

## PHASE 1: Analyze Changes

### Step 1.1 — Detect Branch Context

```
[Report] Analyzing branch context...
```

```bash
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

# Detect base branch (what this branch was created from)
# Try common patterns: main, master, develop
for base in main master develop; do
  if git rev-parse --verify "$base" > /dev/null 2>&1; then
    MERGE_BASE=$(git merge-base "$base" HEAD 2>/dev/null)
    if [ -n "$MERGE_BASE" ]; then
      echo "Base branch: $base"
      echo "Merge base: $MERGE_BASE"
      COMMITS_AHEAD=$(git rev-list --count "$base"..HEAD)
      echo "Commits ahead: $COMMITS_AHEAD"
      break
    fi
  fi
done
```

If `--compare {branch}` was specified, use that as the base instead.
If `--since {commit}` was specified, use that as the starting point.

### Step 1.2 — Gather All Changes

```
[Report] Gathering changes ({COMMITS_AHEAD} commits)...
```

**Get the full diff:**
```bash
git diff {base}..HEAD --stat
```

**Get all commit messages:**
```bash
git log {base}..HEAD --oneline --no-merges
```

**Get detailed commit info:**
```bash
git log {base}..HEAD --format="%H|%an|%ad|%s" --date=short --no-merges
```

**Get changed files with change type:**
```bash
git diff {base}..HEAD --name-status
```

**Get the actual diff for reading:**
```bash
git diff {base}..HEAD
```

### Step 1.3 — Understand the Changes

```
[Report] Analyzing what was changed and why...
```

Read the diff and understand:

1. **What changed** — for each file, summarize what was modified (not just "lines added/removed" but the actual functional change)
2. **Why it changed** — infer from commit messages, code context, and the nature of the change
3. **Impact** — what parts of the application are affected
4. **Risk areas** — changes that might break other things or need careful testing

Categorize each change:
- **New Feature** — new files, new endpoints, new components, new functionality
- **Bug Fix** — fixes to existing behavior, error handling improvements
- **Refactoring** — code restructuring without behavior change
- **Configuration** — env vars, build config, dependencies
- **Database** — migrations, schema changes
- **Styling** — CSS, visual changes
- **Tests** — new or modified tests
- **Documentation** — README, comments, docs

### Step 1.4 — Determine Testing Requirements

```
[Report] Determining testing requirements...
```

For each change, determine what needs to be tested:

**UI changes:**
- Which pages/views need to be checked
- What interactions to test (clicks, forms, navigation)
- What to look for (correct data, layout, responsiveness)

**API changes:**
- Which endpoints changed
- What request/response shapes to verify
- Edge cases to test (empty data, invalid input, auth)

**Database changes:**
- Migration verification
- Data integrity checks

**Bug fixes:**
- Steps to reproduce the original bug
- Verification that the bug is fixed
- Regression check (didn't break anything else)

### Step 1.5 — Take Screenshots (if app is running)

```
[Report] Checking if app is running for screenshots...
```

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:4200 2>/dev/null || curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null
```

If the app is running AND changes include UI modifications:
- Check for `.claude/project-profile.json` — use it for login
- If profile missing or incomplete, ask the user for login details
- Use Playwright to capture screenshots of affected pages
- Save to `reports/change-screenshots/`
- Resize to max 1600px

```bash
mkdir -p reports/change-screenshots
```

If app is not running, skip screenshots and note it in the report.

---

## PHASE 2: Generate HTML Report

```
[Report] Generating change report...
```

### Step 2.1 — Load Design Profile

Check `.claude/project-profile.json` for design settings. Use project-appropriate styling (see design profile rules).

### Step 2.2 — Generate the Report

Write `reports/change-report.html` — a self-contained HTML document.

**The report MUST include these sections:**

**1. Header**
- Branch name and base branch
- Date generated
- Author (from git config or commits)
- Number of commits, files changed, lines added/removed
- Jira ticket reference (if provided or detected from branch name like `feature/FO-2847`)

**2. Executive Summary**
- 2-3 sentence overview of what this branch does
- Scope: what areas of the application are affected
- Risk assessment: Low / Medium / High

**3. Changes by Category**
Group all changes into categories with badges:
- NEW FEATURE (green badge)
- BUG FIX (amber badge)
- REFACTORING (blue badge)
- CONFIGURATION (gray badge)
- DATABASE (purple badge)
- STYLING (cyan badge)
- TESTS (teal badge)

For each change:
- Title (what was done)
- Description (1-2 sentences explaining the change)
- Files affected (list)
- Commit(s) associated

**4. Files Changed**
Table: file path | change type (Added/Modified/Deleted) | category | summary

**5. Screenshots** (if captured)
Embedded as base64 with clickable lightbox. Each screenshot labeled with what page/view it shows.

**6. Testing Instructions for QA**

**CRITICAL SECTION — this is what testers need.**

For each testable change, provide:

```
### Test Case {N}: {title}

**Category:** {Feature / Bug Fix / etc.}
**Priority:** {Must test / Should test / Nice to test}
**Preconditions:** {what needs to be set up before testing}

**Steps:**
1. {exact step — e.g., "Navigate to /invoices"}
2. {exact step — e.g., "Click the 'Export' button"}
3. {exact step — e.g., "Select PDF format"}
4. {exact step — e.g., "Click 'Download'"}

**Expected Result:**
- {what should happen — e.g., "PDF downloads with all line items visible"}
- {what should NOT happen — e.g., "No blank pages, no missing data"}

**Test Data:** {any specific data needed, e.g., "Use invoice FO-2847"}

**Screenshots:** {reference to screenshot if available}
```

Organize test cases by priority:
- **Must Test** — critical paths, new features, bug fix verification
- **Should Test** — related areas that might be affected
- **Nice to Test** — edge cases, regression checks

**7. Commit History**
Chronological list of all commits with: hash, author, date, message

**8. Technical Details** (collapsible)
- Full list of changed files with line counts
- Dependencies added/removed (if any)
- Database migrations (if any)
- Environment variable changes (if any)
- Configuration changes (if any)

**Styling:**
- Use project design profile if available
- Clickable screenshot lightbox
- Collapsible sections for detailed content
- Color-coded category badges
- Print-friendly
- Self-contained (all images as base64)
- Checkboxes next to each test case (so testers can mark off as they go)

### Step 2.3 — Auto-Open in Browser

**MANDATORY — open the report before asking about Jira upload.**

```bash
start "" "reports/change-report.html" 2>/dev/null || open "reports/change-report.html" 2>/dev/null || xdg-open "reports/change-report.html" 2>/dev/null
```

```
[Report] Change report opened in your browser.
```

---

## PHASE 3: Present Results & Jira Upload

### Step 3.1 — Present Summary

```
## Change Report Generated

**Branch:** {current_branch} (vs {base_branch})
**Commits:** {count}
**Files changed:** {count} ({added} added, {modified} modified, {deleted} deleted)
**Lines:** +{added} / -{removed}

**Changes:**
- {X} new features
- {Y} bug fixes
- {Z} other changes

**Test cases:** {count} ({must_test} must-test, {should_test} should-test)

**Report:** `reports/change-report.html` (opened in browser)
```

### Step 3.2 — Ask About Jira Upload

**If a ticket key was provided in the arguments**, skip straight to uploading.

**If no ticket key was provided**, ask:

> "Would you like to upload this report to a Jira ticket?"

Options:
1. **Upload to Jira** — I'll specify the ticket key (type in text box, e.g., "FO-2847")
2. **No thanks** — I'll upload manually or don't need Jira

**If uploading to Jira:**

Ask for the ticket key if not already provided:
> "Which Jira ticket should I upload this to? (e.g., FO-2847)"

Then upload:

**Step A — Upload the HTML report as attachment:**
```bash
source .env && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "X-Atlassian-Token: no-check" \
  -F "file=@reports/change-report.html" \
  "${JIRA_BASE_URL}/rest/api/3/issue/{TICKET_KEY}/attachments"
```

**Step B — Upload screenshots (if any):**
```bash
source .env && for f in reports/change-screenshots/*.png; do
  [ -f "$f" ] && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
    -X POST \
    -H "X-Atlassian-Token: no-check" \
    -F "file=@$f" \
    "${JIRA_BASE_URL}/rest/api/3/issue/{TICKET_KEY}/attachments" && echo "Uploaded: $f"
done
```

**Step C — Post a summary comment on the ticket:**
```bash
source .env && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  "${JIRA_BASE_URL}/rest/api/3/issue/{TICKET_KEY}/comment" \
  -d '{
    "body": {
      "type": "doc",
      "version": 1,
      "content": [
        {
          "type": "paragraph",
          "content": [
            {
              "type": "text",
              "text": "Change report uploaded for branch {current_branch}.",
              "marks": [{"type": "strong"}]
            }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            {
              "type": "text",
              "text": "{executive_summary}"
            }
          ]
        },
        {
          "type": "paragraph",
          "content": [
            {
              "type": "text",
              "text": "Changes: {X} new features, {Y} bug fixes, {Z} other. {count} test cases documented. Full HTML report attached."
            }
          ]
        }
      ]
    }
  }'
```

Report the result:
```
[Report] Uploaded to {TICKET_KEY}:
- HTML report attached
- {count} screenshots attached
- Summary comment posted
```

**If Jira credentials not configured:**
> "Jira is not configured. To upload, add JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN to your .env file. The report is saved locally at `reports/change-report.html`."

---

### MANDATORY — USE PROJECT DESIGN PROFILE FOR HTML REPORTS
When generating the HTML report, check for a `design` section in `.claude/project-profile.json`. If it exists, use those colors, fonts, and styling. The report should look like it belongs to the project.

### MANDATORY — CLICKABLE SCREENSHOTS IN HTML REPORTS
All screenshots must be clickable with a JavaScript lightbox for full-size viewing.

### MANDATORY — UNDERSTAND EXISTING CODE BEFORE WRITING
Before analyzing changes, read existing code to understand the context of what was changed and why. This helps write accurate descriptions and meaningful test cases.

### MANDATORY STATUS REPORTING
**Print a status line before EVERY major step.** Format:
```
[Report] {what is happening now}
```

## Rules

- **Analyze ALL commits on the branch** — not just the latest one
- **Write test cases a human tester can follow** — exact steps, expected results, no ambiguity
- **Categorize every change** — new feature, bug fix, refactor, config, etc.
- **Include risk assessment** — flag changes that might break other things
- **Screenshots where possible** — visual evidence of the current state
- **Self-contained HTML** — all images as base64, works offline
- **Auto-open in browser** — always open the report before asking about Jira
- **Detect ticket key from branch name** — if branch is `feature/FO-2847-description`, extract FO-2847
- **Support both AI and manual work** — the report covers ALL changes on the branch regardless of how they were made
- **Always use `source .env`** when loading Jira credentials
- **Report goes to `reports/change-report.html`**
