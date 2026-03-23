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

### Step 2.0 — Load Design Settings

**The changelog design MUST match the project it's inside.** Check for design settings in this priority order:

**Priority 1: Project profile design settings**
```bash
cat .claude/project-profile.json 2>/dev/null
```

Check for a `design` section in the profile. If it exists, use those settings (colors, fonts, theme, style).

**Priority 2: Detect from the project's existing CSS/styling**
Search the project for existing design tokens:
```bash
# React/Vue/Angular — check for CSS variables or theme files
cat src/index.css src/styles/globals.css src/theme.ts src/assets/css/main.css public/css/style.css 2>/dev/null | head -50
# Check for tailwind config
cat tailwind.config.js tailwind.config.ts 2>/dev/null | head -30
# Check package.json for project name and description
cat package.json 2>/dev/null | python -c "import json,sys; d=json.load(sys.stdin); print('NAME:'+d.get('name','')); print('DESC:'+d.get('description',''))" 2>/dev/null
```

Extract: primary color, accent color, background color, font family, border radius, project name.

**Priority 3: Auto-generate design based on ProjectType**

If no design settings found, generate a theme that matches the project type:

| ProjectType | Theme | Colors | Font | Style |
|---|---|---|---|---|
| `GAME` | Dark, immersive | Dark bg (#0a0a0f), neon accents (#00ff88 green, #ff6b6b red), glow effects | Monospace / pixel-style | Patch notes feel — version numbers, "ADDED/FIXED/CHANGED" tags, game-UI borders |
| `APPLICATION` | Clean professional | White bg, blue accent (#3b82f6), gray text | System-ui sans-serif | Corporate changelog — clean cards, status badges, timeline |
| `SAAS` | Modern minimal | Light bg (#fafafa), indigo accent (#6366f1), slate text | Inter / system-ui | Product update feel — feature highlights, improvement tags |
| `API` | Technical / dev | Dark bg (#1e293b), green accent (#22c55e), cyan (#06b6d4) | Monospace | API changelog feel — endpoint changes, version bumps, code blocks |
| `MOBILE` | App-like | White bg, rounded corners, vibrant accent | SF Pro / system-ui | App release notes feel — "What's New" style, app store vibes |
| *(not set)* | Neutral | Light gray bg, blue accent | System-ui | Standard changelog |

**For GAME projects specifically**, adapt further based on game genre/style if detectable:
- **Pixel/retro game**: Pixel font, CRT scan lines, 8-bit color palette, terminal green on black
- **Dark fantasy**: Gothic fonts, dark purple/red palette, parchment texture backgrounds
- **Sci-fi**: Neon cyan/blue on dark, HUD-style borders, tech font
- **Casual/mobile game**: Bright colors, rounded cards, playful font
- Check for clues in file names, asset folders, game engine config, README

**Save the auto-generated design to the project profile** so future changelogs use the same style:

```bash
python -c "
import json, os
profile_path = '.claude/project-profile.json'
profile = {}
if os.path.exists(profile_path):
    with open(profile_path) as f:
        profile = json.load(f)

profile['design'] = {
    'theme': '{light/dark}',
    'backgroundColor': '{hex}',
    'cardBackground': '{hex}',
    'textColor': '{hex}',
    'textMuted': '{hex}',
    'accentColor': '{hex}',
    'featureColor': '{hex}',
    'bugfixColor': '{hex}',
    'criticalColor': '{hex}',
    'fontFamily': '{font stack}',
    'borderRadius': '{px}',
    'style': '{description of the design vibe}',
    'headerTitle': '{project name} Changelog',
    'featureLabel': '{FEATURE / ADDED / NEW / UPDATE}',
    'bugfixLabel': '{BUG FIX / FIXED / PATCHED}',
    'autoGenerated': True,
    'basedOn': '{projectType or detected CSS}'
}

with open(profile_path, 'w') as f:
    json.dump(profile, f, indent=2)
print('Design settings saved to profile')
"
```

### Design Requirements

**Use the design settings from above.** The changelog MUST look like it belongs to this project.

**Header:**
- Project name (from profile, package.json, or directory name)
- Subtitle matching the style (e.g., "Patch Notes" for games, "Changelog" for apps, "Release Notes" for SaaS, "API Changes" for APIs)
- Date range: {oldest report date} to {newest report date}
- Summary stats: {X} features, {Y} bug fixes, {Z} total changes
- Styled with the project's colors and fonts

**Visual Design — use the design profile:**
- Background: `{backgroundColor}` from profile
- Cards: `{cardBackground}` from profile
- Text: `{textColor}` and `{textMuted}` from profile
- Feature entries: left border in `{featureColor}`
- Bug fix entries: left border in `{bugfixColor}`
- Critical bug fixes: left border in `{criticalColor}`
- Font: `{fontFamily}` from profile
- Border radius: `{borderRadius}` from profile
- Cards with shadow appropriate to the theme
- Timeline layout — entries arranged chronologically with date markers
- Responsive, print-friendly

**For GAME changelogs, use game-appropriate terminology:**
- Instead of "FEATURE": use "ADDED" or "NEW"
- Instead of "BUG FIX": use "FIXED" or "PATCHED"
- Add version-style headers if applicable (e.g., "Patch 2026.03.23")
- Use the game's color palette for entry badges
- Add subtle game-themed decorative elements if appropriate (pixel borders, glow effects, etc.)

**For each entry (card):**
- Type badge using `{featureLabel}` or `{bugfixLabel}` from profile
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
- Features count (with `{featureColor}` dot)
- Bug fixes count (with `{bugfixColor}` dot)
- Files created total
- Files modified total
- Styled to match the project's theme

**Empty state:** Should never happen (we check in Phase 1), but just in case — show a friendly "No changes to report" message matching the project's style.

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

### MANDATORY STATUS REPORTING
**Print a status line before EVERY major step.** Format:
```
[{Agent_Name}] {what is happening now}
```
The user must see what you are doing in real time. Print status BEFORE starting each step, not after. When spawning sub-agents, include this instruction in their prompt so they also report status with their agent name (e.g., [Security Auditor], [Frontend Developer], [Backend Developer], [Code Analyst], [Test Engineer], [UI Designer], [Documentation Lead]).


## Rules

- **If no reports exist, just say so and stop** — do not generate an empty changelog
- **Reports are in `.claude/unprocessed_reports/`** — only read from this directory
- **After generating, move reports to `.claude/processed_reports/`** — prevents double-counting
- **Sort by date (newest first)** within each group
- **Differentiate clearly between features and bug fixes** — different colors, different badges
- **The HTML must look professional** — this is a document others might see
- **Include ALL information from each report** — don't summarize away the details
- **Print-friendly** — should look good when printed or exported to PDF
