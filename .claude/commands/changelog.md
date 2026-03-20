# Changelog Generator

You are a **Documentation Specialist**. Your job is to read all unprocessed AI agent reports and compile them into a beautifully designed HTML changelog.

**Arguments:** $ARGUMENTS

---

## PHASE 1: Check for Unprocessed Reports

### Step 1.1 — Look for Reports

```bash
ls -la .claude/unprocessed_reports/*.md 2>/dev/null
```

**If the directory doesn't exist or is empty:**

Tell the user:
> "No changes have been made using AI agents that save their reports. The `.claude/unprocessed_reports/` directory is empty.
>
> Reports are created automatically by `/create` (features) and `/bug` (bug fixes) commands."

**Stop here — do not generate a changelog.**

**If reports exist:** Count them and proceed.

```bash
FEATURE_COUNT=$(ls .claude/unprocessed_reports/*_feature_*.md 2>/dev/null | wc -l)
BUGFIX_COUNT=$(ls .claude/unprocessed_reports/*_bugfix_*.md 2>/dev/null | wc -l)
TOTAL=$(ls .claude/unprocessed_reports/*.md 2>/dev/null | wc -l)
echo "Features: $FEATURE_COUNT, Bug fixes: $BUGFIX_COUNT, Total: $TOTAL"
```

### Step 1.2 — Read All Reports

Read every `.md` file in `.claude/unprocessed_reports/`, parsing the frontmatter and body of each:

For each report, extract:
- `type` — feature or bugfix (from frontmatter)
- `date` — when it was done (from frontmatter)
- `role` — what role the agent used
- `project_type` — GAME, APPLICATION, SAAS, etc.
- `status` — implemented/fixed
- `severity` — (bugfix only) critical/high/medium/low
- `title` — the heading after the frontmatter
- `summary` — the summary section
- `files_created` — list of created files
- `files_modified` — list of modified files
- `how_to_test` — verification instructions

Sort all reports by date (newest first).

---

## PHASE 2: Generate HTML Changelog

**Generate a polished, professional HTML changelog.**

Write to `reports/changelog.html`:

The report agent should create the HTML directly. Here are the requirements:

### Design Requirements

**Header:**
- Project name (from package.json, pom.xml, *.csproj, or directory name)
- "AI Agent Changelog" subtitle
- Date range: {oldest report date} to {newest report date}
- Summary stats: {X} features, {Y} bug fixes, {Z} total changes

**Visual Design:**
- Clean light theme (white/off-white background)
- System font stack
- Feature entries: left border in blue (#3b82f6)
- Bug fix entries: left border in amber (#f59e0b)
- Critical bug fixes: left border in red (#ef4444)
- Cards for each entry with subtle shadow
- Timeline layout — entries arranged chronologically with date markers
- Responsive, print-friendly

**For each entry (card):**
- Type badge: `FEATURE` (blue) or `BUG FIX` (amber/red based on severity)
- Date and time
- Title (from the report heading)
- Summary (1-2 sentences)
- Expandable "Details" section containing:
  - Full description of what was done
  - Files created (as a list)
  - Files modified (as a list)
  - How to test/verify
  - Technical notes (if any)
  - Role used (e.g., "Senior Unity Game Developer")

**Sections — group entries by date:**
- If all entries are from the same day: single section
- If spanning multiple days: group by date with date headers
- Within each date: features first, then bug fixes, sorted by time

**Statistics bar at the top:**
- Total changes count
- Features count (with blue dot)
- Bug fixes count (with amber dot)
- Files created total
- Files modified total

**Empty state:** Should never happen (we check in Phase 1), but just in case — show a friendly "No changes to report" message.

---

## PHASE 3: Process the Reports

### Step 3.1 — Move to Processed

After the changelog is generated, move the reports from `unprocessed_reports` to a `processed_reports` directory so they're not included in the next changelog:

```bash
mkdir -p .claude/processed_reports
mv .claude/unprocessed_reports/*.md .claude/processed_reports/
```

### Step 3.2 — Present the Result

```
## Changelog Generated

**Period:** {date range}
**Entries:** {X} features, {Y} bug fixes
**Files impacted:** {created count} created, {modified count} modified

**Report:** `reports/changelog.html`

Reports have been moved from `unprocessed_reports/` to `processed_reports/`.
```

---

## PHASE 4: Optional — Append to Cumulative Changelog

If `reports/changelog-history.html` already exists, ask:

> "A previous changelog exists. Would you like to merge them?"

Options:
1. **Merge** — Add the new entries to the existing changelog (newest on top)
2. **Replace** — Replace the old changelog with just the new entries
3. **Keep separate** — Save as `reports/changelog-{date}.html` instead

**If "Merge":** Read the existing changelog, insert the new entries at the top (maintaining chronological order within each section), and save.

---

## Rules

- **If no reports exist, just say so and stop** — do not generate an empty changelog
- **Reports are in `.claude/unprocessed_reports/`** — only read from this directory
- **After generating, move reports to `.claude/processed_reports/`** — prevents double-counting
- **Sort by date (newest first)** within each group
- **Differentiate clearly between features and bug fixes** — different colors, different badges
- **The HTML must look professional** — this is a document others might see
- **Include ALL information from each report** — don't summarize away the details
- **Print-friendly** — should look good when printed or exported to PDF
