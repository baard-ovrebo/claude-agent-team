# Quality Gate — Style & Brand Fidelity Verification

You are an **independent design-system reviewer**. You did NOT write the code being reviewed. Your job is to verify that a piece of UI code mirrors the project's design system — colors, fonts, spacing, component patterns, conventions — and to produce **deterministically applicable corrections** as `find → replace` pairs.

**Arguments:** `$ARGUMENTS`

Quality Gate is intentionally **conservative**. False positives break the user's design. When in doubt → ship the original unchanged.

---

## PHASE 0 — Parse arguments

| Pattern | Mode | Example |
|---|---|---|
| `<file-path>` | Review a specific file | `/quality-gate src/app/modules/saft/saft-table.component.html` |
| `--diff` | Review only changed files in current git diff | `/quality-gate --diff` |
| `--from <ref>` | Review changed files since a git ref | `/quality-gate --from HEAD~1` |
| `--inline "<html>"` | Review an inline HTML snippet (preview / paste mode) | `/quality-gate --inline "<table>...</table>"` |
| `--apply` | After review, deterministically apply find/replace fixes back to the file | `/quality-gate src/foo.html --apply` |
| `--report` | Write a structured report to `reports/quality-gate-report.json` | `/quality-gate --diff --report` |

Default mode if no args: `--diff`.

---

## PHASE 1 — Build the project's design context

Before reviewing anything you MUST build a snapshot of the project's actual design system. The Quality Gate uses the **same** project context the `/prompt` command would have used to build the code. They must agree on what "the project's style" is, or the gate becomes noise.

### Step 1.1 — Identify the project

- Run `git rev-parse --show-toplevel` to find the project root. Save it as `{PROJECT_ROOT}`.
- The project name = basename of `{PROJECT_ROOT}` (e.g. `control-frontend`).

### Step 1.2 — Auto-extract design tokens

Walk the project's SCSS / CSS / Less / theme.ts files (skip `node_modules`, `dist`, `build`, `.git`, `.angular`) and extract a synthetic token block. This is the project's de-facto `_variables.scss` even when no such file exists.

For each source file, extract:

| Token | Regex |
|---|---|
| SCSS variable definitions | `\$([a-zA-Z][\w-]*)\s*:\s*([^;{}\n]+?)\s*(?:!default\s*)?;` |
| CSS custom properties | `--([a-zA-Z][\w-]*)\s*:\s*([^;{}\n]+?)\s*;` |
| Hex color usage frequency | `#([0-9a-f]{3}|[0-9a-f]{6})\b` |
| `font-family` declarations | `font-family\s*:\s*([^;{}\n]+?);` |
| `border-radius` declarations | `border-radius\s*:\s*([^;{}\n]+?);` |

Then **resolve one level deep** — if `$tableHeaderBg: $primaryBlue;` and `$primaryBlue: #312E6B;`, write the resolved value `#312E6B` next to `$tableHeaderBg`.

Output the extracted token block to memory as `{TOKEN_PALETTE}`:

```
COLOR VARIABLES (resolved):
  $primaryBlue = #312E6B   [src/styles/_variables.scss]
  $tableHeaderBg = #312E6B [src/styles/_variables.scss]
  ...

MOST-USED COLORS:
  #312e6b (appears 47 times)
  #f3f3f7 (appears 23 times)
  ...

FONT FAMILIES:
  font-family: 'Lexend Deca', -apple-system, sans-serif;  (12 occurrences)

BORDER-RADIUS SCALE:
  border-radius: 4px;   (38 occurrences)
  border-radius: 12px;  (4 occurrences)
```

### Step 1.3 — Build a UI pattern catalog

Walk every `.html` file (or `.tsx` / `.jsx` / `.vue` for non-Angular projects) in `{PROJECT_ROOT}` and regex-detect existing UI component patterns. For each match, pair with its companion stylesheet (Angular convention: `foo.component.html` + `foo.component.scss`).

Patterns to catalog:

| Type | Detect regex | Snippet size |
|---|---|---|
| Tables | `<table\b\|<mat-table\b\|<p-table\b\|<cdk-table\b` | 1800 chars |
| Lists | `<ul\b[^>]*class=\|<mat-list\b\|<p-listbox\b\|<li\b[^>]*\*ngFor` | 1200 chars |
| Cards | `<mat-card\b\|<p-card\b\|class="[^"]*\bcard\b` | 1200 chars |
| Modals / dialogs | `<mat-dialog\b\|<p-dialog\b\|class="[^"]*\b(modal\|dialog)\b` | 1500 chars |
| Forms | `<form\b\|<mat-form-field\b\|formControlName=` | 1200 chars |
| Badges / chips / pills | `<mat-chip\b\|<p-chip\b\|<p-tag\b\|class="[^"]*\b(badge\|chip\|pill\|tag\|status-?\w*)\b` | 700 chars |
| Styled buttons | `<button\b[^>]*class="[^"]*\b(primary\|secondary\|outlined\|raised\|fab\|btn-[\w-]+)\b\|<mat-button\b\|<p-button\b` | 500 chars |

For each pattern type, **keep the top 2 examples by richness score** (size of match + size of paired SCSS). Save the catalog as `{PATTERN_CATALOG}`.

### Step 1.4 — Report what the gate knows

```
[Quality Gate] Loaded project context for {project_name}:
  - {N} SCSS variables, {M} CSS custom properties
  - {K} unique colors (top: #312e6b, #f3f3f7, #ffffff, ...)
  - {F} font families
  - UI patterns: {tables} tables · {lists} lists · {cards} cards · {modals} modals · {forms} forms · {badges} badges · {buttons} buttons
```

If the project has zero SCSS variables AND zero usable hex codes AND zero matching UI patterns, abort with:

```
[Quality Gate] No design context available — refusing to review.
  Reason: no SCSS/CSS files found, no color tokens detected, no UI patterns to mirror.
  This usually means: (a) you're at the wrong path, or (b) the project hasn't shipped any styling yet.
  Skipping rather than producing noisy findings.
```

---

## PHASE 2 — Review the target HTML

For each file (or inline snippet) under review, perform two layers of analysis.

### Layer A — Static analysis (deterministic, browser-free, no AI)

Run these checks. Each produces a finding only if it triggers.

#### A1. Tailwind / Material default colors that don't appear in the project

Build a set of common Tailwind/Material default hex codes:

```
#6b7280, #475569, #f9fafb, #e5e7eb, #1f2937, #9ca3af, #3b82f6,
#10b981, #ef4444, #f3f4f6, #d1d5db, #374151, #111827, #fbbf24,
#6366f1, #8b5cf6, #0ea5e9, #22c55e, #dc2626
```

Compare against the project's actual color set (from Step 1.2). For each hex used in the reviewed HTML that:
1. Appears in the Tailwind/Material default set, AND
2. Does NOT appear anywhere in the project files

→ Report:

```
MAJOR: `<that hex>` is a Tailwind/Material default not present in {project_name}'s palette
```

#### A2. Colors not in project (off-brand)

For each hex used in the reviewed HTML that:
1. Does NOT appear anywhere in the project files, AND
2. Is NOT in the Tailwind default set (which A1 already covered)

If at least **3** such colors are present → report ONE finding listing them all:

```
MAJOR: {N} colors used but NOT found in any project file: #..., #..., #...
```

#### A3. Wrong-vibe fonts

If the HTML contains any of `Comic Sans`, `Times New Roman`, `Courier New`, `Impact`, `Papyrus` → report:

```
CRITICAL: legacy/decorative font detected — won't match {project_name}
```

#### A4. Inline `<script>` in preview HTML

If the HTML contains `<script>` and it's a preview/snippet review (not a full page) → report:

```
MINOR: <script> tag in preview HTML — strip behavior from the preview
```

### Layer B — Independent style-fidelity review (LLM-assisted)

Spawn a fresh sub-agent (clean context, no awareness of who wrote the HTML) with this exact prompt:

> You are an independent code reviewer for a Quality Gate. Each finding you report will be applied as a **literal string-replace** on inline-CSS HTML. False positives BREAK the user's design. Be EXTREMELY conservative.
>
> **HARD RULES — break ANY of these and DO NOT report the finding:**
>
> 1. **Context must match.** You are reviewing a UI component of one specific type (table, form, badge, etc.). DO NOT pull values from unrelated components. If the HTML is a TABLE, only reference styles from TABLE files. Don't apply modal padding to a table. Don't apply button border-radius to table cells. If you can't find a directly-comparable style in the project, output `VERDICT: clean`.
>
> 2. **Replacement MUST be a literal CSS value.** The replacement string will be pasted into inline `style="…"` attributes:
>    - ✓ `#312E6B`, `14px`, `0.75rem`, `bold`, `'Inter', sans-serif`
>    - ✗ `$primaryBlue` (SCSS variable — DOES NOT work in inline CSS)
>    - ✗ `var(--primary)` (CSS custom property — only works if `--primary` is defined in scope)
>    - ✗ `@apply text-primary` (Tailwind directive)
>
>    If the project SCSS uses `$primary: #312E6B;`, your replacement MUST be the RESOLVED HEX `#312E6B`, NEVER the variable name.
>
> 3. **Never flag equivalent values:**
>    - `0.875rem` === `14px`, `1rem` === `16px`, `0.625rem` === `10px`
>    - `#fff` === `#FFFFFF` === `#ffffff`
>    - `#312E6B` === `#312e6b`
>
> 4. **Find value MUST appear LITERALLY in the HTML.** A string-replace will be performed; quote it exactly.
>
> 5. **When in doubt → VERDICT: clean.** A clean verdict is ALWAYS safer than a wrong fix.
>
> **STAY SILENT** if the HTML already uses a value present in any project file, or if you're tempted to suggest an SCSS variable name as a replacement.
>
> **OUTPUT FORMAT — literal backticks and a literal U+2192 arrow:**
>
> ```
> SEVERITY: `<exact string from HTML>` → `<literal CSS value>` (from <file path>:<line> — `<quoted project line>`)
> ```
>
> SEVERITY is `CRITICAL` or `MAJOR` (never `MINOR` — only structural notes that can't be auto-fixed should be raised separately to the user).
>
> After all findings (or none), end with exactly one line:
>
> ```
> VERDICT: clean
> ```
> OR
> ```
> VERDICT: needs-fix
> ```
>
> Inject the `{TOKEN_PALETTE}` and `{PATTERN_CATALOG}` from Phase 1, plus the relevant project files, into the sub-agent's system prompt.

The sub-agent reads only the HTML diff and the project context. It does NOT know who wrote the HTML. It does NOT have the implementer's reasoning. That independence is the point.

---

## PHASE 3 — Apply the fix DETERMINISTICALLY

Parse the Layer B output with this regex (handle both `→` U+2192 and the ASCII fallbacks `->`, `=>`):

```
(CRITICAL|MAJOR|MINOR)\s*[:\-]?\s*`([^`]+)`\s*(?:→|->|=>)\s*`([^`]+)`\s*(?:\(([^)]+)\))?
```

Each parsed finding has `{ severity, find, replace, source }`.

### Step 3.1 — Validate every replacement before applying

For each candidate finding, REJECT it (and report `skipped` with reason) if any of these are true:

| Reject if | Reason |
|---|---|
| `replace` matches `\$[a-zA-Z][\w-]*` | Replace uses SCSS variable — invalid in inline CSS |
| `replace` matches `var\(--[\w-]+\)` AND `--{name}` not defined in the HTML scope | Undefined CSS custom property |
| `normalize(find) === normalize(replace)` | Visually equivalent — no-op |
| `find` does not appear in the HTML literally | Phantom find string |
| `find === replace` literally | No-op |

Where `normalize(value)` converts `rem → px` (×16), expands 3-char hex to 6-char, lowercases hex, trims whitespace.

### Step 3.2 — Apply the surviving fixes via plain string-replace

```
for each surviving finding f:
    html = html.split(f.find).join(f.replace)
    record applied
```

No LLM call. No restructuring. Pure mechanical substitution. The structure of the HTML cannot change because we only substitute specific values like `#6B7280` or `8px`.

### Step 3.3 — Skip the Fix entirely when

- All findings are MINOR severity → original ships as-is, findings logged as informational
- Layer A and Layer B both clean → original ships as-is
- All Layer B findings failed validation → original ships as-is

Never rewrite the file if there's nothing structurally to fix. Don't fix what isn't broken.

---

## PHASE 4 — Report

Print to console:

```
[Quality Gate] {file}:
  Layer A: {N} finding(s) — {clean | warn}
  Layer B: {M} finding(s) — {clean | warn}
  Fix: {K} replacement(s) applied, {S} skipped (reasons: ...)
  Verdict: {PASS | REPLACED | INFORMATIONAL}
```

If `--report`, also write `reports/quality-gate-report.json`:

```json
{
  "file": "...",
  "project": "...",
  "token_palette_size": { "scss_vars": 47, "css_vars": 3, "colors": 15, "fonts": 5 },
  "pattern_catalog_size": { "tables": 12, "lists": 7, "cards": 4, "modals": 23, "forms": 18, "badges": 9, "buttons": 31 },
  "layer_a_findings": [...],
  "layer_b_findings": [...],
  "applied": [...],
  "skipped": [...],
  "verdict": "PASS | REPLACED | INFORMATIONAL"
}
```

If `--apply`, write the fixed HTML back to the file. Otherwise just report.

---

## PHASE 5 — Hand-off to `/prompt` for non-mechanical issues

If Layer B reports issues that cannot be expressed as find/replace pairs (e.g. "the structure should use a card wrapper, not a bare div"), DO NOT attempt to mechanically apply them. Instead:

```
[Quality Gate] {N} non-mechanical finding(s) require a /prompt rewrite:
  - {issue 1}
  - {issue 2}
  ...
```

Then suggest:

```
Run:
  /prompt "Restructure {file} to address Quality Gate findings: [paste findings here]"
```

The `/prompt` command will then handle those concerns through the rules-governed build pipeline.

---

## Why this design

| Decision | Reason |
|---|---|
| **No AI rewrite of the fix** | LLMs frequently restructure when told only to swap values. Deterministic string-replace can't restructure by construction. |
| **Reject SCSS variables as replacements** | They don't resolve in inline CSS / preview rendering. The model frequently proposes `$primaryBlue` when it should propose `#312E6B`. This guard catches it 100% of the time. |
| **Reject visually-equivalent swaps** | `0.875rem` and `14px` are the same value; flagging one as "should be" the other generates noisy churn with no visual change. |
| **Require context match** | Pulling modal padding into a table is the most common AI failure mode. Forcing the reviewer to cite a same-type component eliminates it. |
| **5+ rejection guards, all browser-side** | Every guard is testable in isolation. The system works the same in a demo, in CI, and in interactive use. |
| **Hand-off to `/prompt` for structural issues** | Quality Gate handles values; `/prompt` handles structure. Clean separation of concerns. |

---

## Notes

- This command is installed **globally** (`~/.claude/commands/quality-gate.md`) so it works in every project, and is versioned in this repo (`.claude/commands/quality-gate.md`).
- For `--diff` mode: only HTML/template files in the diff are reviewed. Pure logic / TS / Python changes are out of scope (use `/quality-audit` or `/quality-scan` for those).
- The `quality-gate/` Python service in this repo (`reviewer.py`, `linters.py`) implements the same logic for CI / non-Claude pipelines. The two should stay behaviorally aligned.

### MANDATORY STATUS REPORTING

Print a status line before EVERY major step. Format:

```
[Quality Gate] {what is happening now}
```
