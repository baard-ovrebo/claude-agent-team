# /init-design-system — Generate the project's persistent design manifest

You are the **Design System Manifest Generator**. Your job: scan a project once, distill its design language into a hand-tunable JSON file, and persist it as `.claude/project-design.json`. This manifest becomes the **source of truth** for `/prompt` and `/quality-gate` — they will read it instead of re-deriving the project's design language on every call.

**Arguments:** `$ARGUMENTS`

| Pattern | Mode |
|---|---|
| *(empty)* | Scan current project, generate fresh manifest, overwrite if exists |
| `--refresh` | Re-scan, but preserve any `_overrides` block the user added by hand |
| `--show` | Print the existing manifest without re-scanning |
| `--diff` | Show what would change vs the existing manifest, don't write |
| `--validate` | Lint the existing manifest (schema check, dead references) |
| `--screenshots` | Guide the user through capturing reference screenshots of the real running app into `.claude/design-screenshots/` |

---

## Reference screenshots (optional but the strongest style anchor)

Text-derived tokens get you ~90% style fidelity; screenshots of the real running app close the rest. With `--screenshots` (or any time the user wants):

1. Ask the user for the app's local dev URL (or have them capture manually).
2. If a browser automation tool (Playwright MCP) is available: navigate to the main list/table screen, a form/modal, and a detail view; screenshot each at 1440px width.
3. Save to `.claude/design-screenshots/{screen-name}.png` and record them in the manifest:

```json
"screenshots": [
  { "file": ".claude/design-screenshots/customer-list.png", "shows": ["table", "badges", "search", "button"] },
  { "file": ".claude/design-screenshots/edit-modal.png",    "shows": ["modal", "form", "button"] }
]
```

`/prompt` reads these as visual ground truth (Step 1.5b.2) and `/quality-gate` Layer C compares generated output against them instead of a synthesized canonical. **A real screenshot beats any amount of extracted SCSS.**

---

## PHASE 1 — Scan

Identify the project root (`git rev-parse --show-toplevel`). Walk the file tree, skipping `node_modules`, `dist`, `build`, `out`, `.git`, `.angular`, `.next`, `.nuxt`, `.svelte-kit`, `target`, `bin`, `obj`, `coverage`.

Collect file paths for these extensions: `.scss`, `.sass`, `.css`, `.less`, `.html`, `.ts`, `.tsx`, `.js`, `.jsx`, `.vue`, `.svelte`, `.json`, `.md`.

Report:

```
[Init Design System] Project: {name} ({N} files indexed)
```

---

## PHASE 2 — Extract raw tokens (deterministic, no AI)

### 2.1 — SCSS / CSS / Less

For each style file, run these extractions:

| Token | Regex |
|---|---|
| SCSS variable definitions | `\$([a-zA-Z][\w-]*)\s*:\s*([^;{}\n]+?)\s*(?:!default\s*)?;` |
| CSS custom properties (in `:root` or `*`) | `--([a-zA-Z][\w-]*)\s*:\s*([^;{}\n]+?)\s*;` |
| Hex color usage frequency | `#([0-9a-f]{3}\|[0-9a-f]{6})\b` |
| RGB/RGBA color usage | `rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)` |
| `font-family` declarations | `font-family\s*:\s*([^;{}\n]+?);` |
| `border-radius` declarations | `border-radius\s*:\s*([^;{}\n]+?);` |
| Standard padding/margin values | `(padding\|margin)(?:-(?:top\|right\|bottom\|left))?\s*:\s*([^;{}\n]+?);` |
| `box-shadow` declarations | `box-shadow\s*:\s*([^;{}\n]+?);` |

Resolve one level of SCSS variable indirection: if `$tableHeaderBg: $primaryBlue;` and `$primaryBlue: #312E6B;` → record `$tableHeaderBg = #312E6B (originally $primaryBlue)`.

### 2.2 — Component patterns (HTML / template files)

For each `.html` / `.tsx` / `.jsx` / `.vue` / `.svelte` file, regex-detect component patterns:

| Pattern | Detect | Snippet |
|---|---|---|
| Tables | `<table\b\|<mat-table\b\|<p-table\b\|<cdk-table\b` | 1800 chars |
| Lists | `<ul\b[^>]*class=\|<mat-list\b\|<p-listbox\b\|<li\b[^>]*\*ngFor` | 1200 chars |
| Cards | `<mat-card\b\|<p-card\b\|class="[^"]*\bcard\b` | 1200 chars |
| Modals | `<mat-dialog\b\|<p-dialog\b\|class="[^"]*\b(modal\|dialog)\b` | 1500 chars |
| Forms | `<form\b\|<mat-form-field\b\|formControlName=` | 1200 chars |
| Badges/pills | `<mat-chip\b\|<p-chip\b\|<p-tag\b\|class="[^"]*\b(badge\|chip\|pill\|tag\|status-?\w*)\b` | 700 chars |
| Styled buttons | `<button\b[^>]*class="[^"]*\b(primary\|secondary\|outlined\|raised\|fab\|btn-[\w-]+)\b\|<mat-button\b\|<p-button\b` | 500 chars |

Pair each match with its companion stylesheet (Angular: `foo.component.html` ↔ `foo.component.scss`; React: same file or sibling `.module.scss`).

For each pattern type, keep the top 3 examples ranked by richness (snippet length + paired-SCSS length).

### 2.3 — Reuse registry (imports & exports)

For each `.ts`/`.tsx`/`.js`/`.jsx` file, extract:

- `export class \w+`, `export function \w+`, `export const \w+`, `export default function \w+`
- Angular: `@Component({ selector: '...' })`, `@Injectable()`
- React: `export default function ComponentName`, `function ComponentName({ ... })`

Build a registry of every **exported** symbol with its file path and inferred type (`Component`, `Util`, `Service`, `Hook`, `Type`).

Look for these conventional locations and tag them as `shared`:

- `src/app/shared/**`
- `src/shared/**`
- `src/common/**`
- `src/components/shared/**`
- `src/ui/**`
- `src/lib/**`
- `packages/ui/**`

Anything in `shared/` or matching the pattern goes into the reuse registry with `available: true`. Other exports go into the registry too but with `local: true`.

### 2.4 — Project conventions

Sniff for:

- **Language**: scan HTML for Norwegian-specific markers (Bilagsnr, Beløp, Fakturaer, etc.) vs English. Pick the dominant language.
- **Currency**: scan for `kr`, `€`, `$`, `£` and pick the dominant.
- **Date format**: scan rendered dates in HTML for `DD.MM.YYYY` vs `MM/DD/YYYY` vs `YYYY-MM-DD`.
- **Number format**: `1 000,00` (Norwegian/EU) vs `1,000.00` (US).
- **Framework**: read `package.json` to detect Angular / React / Vue / Svelte.

---

## PHASE 3 — Assign semantic roles (LLM-assisted)

This is where the manifest transcends "list of tokens" to "design language documentation."

Send a focused LLM call with **only** the extracted SCSS variables, CSS variables, top-15 hex codes, and the canonical examples of each component pattern (NOT the raw file dump — keep it under 30 kB).

Ask the model to assign **semantic roles** to colors:

```
You are reverse-engineering a project's design system from its extracted tokens
and example components. Assign one role to each significant color. Output ONLY
a JSON object matching this schema.

Required roles (assign one color to each):
  primary       — main brand color, used for headers, primary buttons
  accent        — secondary brand color (may equal primary)
  text_primary  — main body text color
  text_muted    — secondary / caption text
  border        — borders + dividers
  background    — main page background
  surface_alt   — alternate row backgrounds, hover states

Optional roles (assign if you find a clear match):
  success       — positive status / approved badges
  warning       — pending / caution badges
  danger        — error / rejected badges
  info          — informational badges

For each role, output:
  { "hex": "#...", "scss_name": "$..." or null, "confidence": 0.0–1.0, "evidence": "why" }

EXTRACTED TOKENS:
{list of $vars with resolved hex}

TOP COLORS:
{top 15 hex codes with usage counts}

CANONICAL TABLE:
{paired HTML + SCSS}

CANONICAL BUTTON:
{paired HTML + SCSS}

CANONICAL BADGE:
{paired HTML + SCSS}
```

Parse the response. If `confidence < 0.5` for any role, mark it `"needs_review": true` so the user can hand-tune.

Use the same LLM call (or a follow-up) to identify **component-role mappings**:

```
For each canonical component, output:
  table: {
    header_color_role: "primary",
    header_text_color_role: "background",
    row_alt_color_role: "surface_alt",
    border_color_role: "border"
  },
  button: {
    primary_bg_role: "primary",
    primary_text_role: "background",
    secondary_bg_role: "background",
    secondary_text_role: "primary",
    radius: "<extracted px/rem value>"
  },
  badge: {
    success: { bg_role: "success", text: "background" },
    warning: { bg_role: "warning", text: "text_primary" },
    danger:  { bg_role: "danger", text: "background" }
  }
```

---

## PHASE 4 — Write `.claude/project-design.json`

Schema:

```json
{
  "$schema": "claude-agent-team/project-design.v1.json",
  "version": 1,
  "project": "control-frontend",
  "generated_at": "2026-06-11T08:00:00Z",
  "generator": { "command": "/init-design-system", "claude_model": "claude-sonnet-4-6" },

  "framework": "angular",

  "colors": {
    "primary":      { "hex": "#312E6B", "scss_name": "$primaryBlue",     "role": "headers + primary actions", "confidence": 0.95, "evidence": "used in 47 SCSS files as $primaryBlue, dominant in headers" },
    "accent":       { "hex": "#086A91", "scss_name": "$lighterBlue",     "role": "secondary headers + active states" },
    "text_primary": { "hex": "#212529", "role": "body text" },
    "text_muted":   { "hex": "#6c757d", "role": "secondary text" },
    "border":       { "hex": "#E5E7EB", "role": "borders + dividers" },
    "background":   { "hex": "#FFFFFF", "role": "page + surface backgrounds" },
    "surface_alt":  { "hex": "#F3F3F7", "scss_name": "$lightGrey",        "role": "alternate rows + hover" },
    "success":      { "hex": "#28a745", "role": "success badges + states" },
    "warning":      { "hex": "#ffc107", "role": "pending badges" },
    "danger":       { "hex": "#dc3545", "role": "rejected + error" }
  },

  "typography": {
    "primary": {
      "family": "'Lexend Deca', -apple-system, BlinkMacSystemFont, sans-serif",
      "files": ["src/styles.scss"]
    },
    "scale": {
      "xs":   "0.75rem",
      "sm":   "0.875rem",
      "base": "1rem",
      "lg":   "1.125rem",
      "xl":   "1.5rem"
    },
    "weights": { "normal": 400, "medium": 500, "bold": 700 }
  },

  "spacing": {
    "radius_base":  "4px",
    "radius_pill":  "12px",
    "cell_padding": "12px 16px",
    "card_padding": "16px 20px"
  },

  "components": {
    "table": {
      "canonical_example": "src/app/modules/flow/agreement-template/agreement-template-list/agreement-template-list.component.html",
      "scss_companion":    "src/app/modules/flow/agreement-template/agreement-template-list/agreement-template-list.component.scss",
      "html_snippet": "<table class=\"agreement-table\">...</table>",
      "scss_snippet": "table.agreement-table { ... }",
      "header_color_role": "primary",
      "header_text_color_role": "background",
      "row_alt_color_role": "surface_alt",
      "border_color_role": "border"
    },
    "button": {
      "canonical_example": "src/app/shared/button/button.component.html",
      "import_path": "@app/shared/button",
      "primary_bg_role": "primary",
      "primary_text_role": "background",
      "radius_role": "spacing.radius_base",
      "variants": ["primary", "secondary", "outlined"]
    },
    "badge": {
      "canonical_example": "src/app/modules/flow/agreement-template-list/...",
      "shape": "pill",
      "radius_role": "spacing.radius_pill",
      "states": {
        "success": { "bg_role": "success", "text_role": "background", "label_example": "Godkjent" },
        "warning": { "bg_role": "warning", "text_role": "text_primary", "label_example": "Til kontroll" },
        "danger":  { "bg_role": "danger",  "text_role": "background", "label_example": "Avvist" }
      }
    },
    "modal": { "canonical_example": "...", "scss_companion": "..." },
    "form":  { "canonical_example": "...", "scss_companion": "..." },
    "card":  { "canonical_example": "...", "scss_companion": "..." },
    "list":  { "canonical_example": "...", "scss_companion": "..." }
  },

  "reuse_registry": [
    { "name": "Button",      "kind": "Component", "import_path": "@app/shared/button",     "exports": ["primary","secondary","outlined"], "available": true,  "file": "src/app/shared/button/button.component.ts" },
    { "name": "Modal",       "kind": "Component", "import_path": "@app/shared/modal",      "exports": ["default"],                           "available": true,  "file": "src/app/shared/modal/modal.component.ts" },
    { "name": "Card",        "kind": "Component", "import_path": "@app/shared/card",       "exports": ["default"],                           "available": true,  "file": "src/app/shared/card/card.component.ts" },
    { "name": "formatDate",  "kind": "Util",      "import_path": "@app/utils/dates",       "exports": ["formatDueDate"],                     "available": true,  "file": "src/app/utils/dates.ts" },
    { "name": "AgreementTemplateList", "kind": "Component", "available": false, "local": true, "file": "src/app/modules/flow/..." }
  ],

  "conventions": {
    "language": "no",
    "currency": "NOK",
    "currency_format": "12 000 kr",
    "date_format": "DD.MM.YYYY",
    "number_format": "1 234,56"
  },

  "_overrides": {
    "_note": "Anything in _overrides wins on next --refresh. Use this to lock in corrections."
  }
}
```

Write the file with this command order:
1. If `.claude/project-design.json` already exists AND no flag forces overwrite → abort and tell user to use `--refresh`.
2. Create `.claude/` directory if it doesn't exist.
3. Write the JSON, formatted, sorted keys for readability.
4. Print a summary:

```
[Init Design System] Wrote .claude/project-design.json
  - {N} semantic color roles assigned ({M} need review, confidence < 0.5)
  - {K} component patterns catalogued
  - {R} entries in reuse registry ({S} marked available, {L} local)
  - Conventions: language={no|en}, currency={NOK|...}, date={DD.MM.YYYY|...}

Next steps:
  - Review {file path} and adjust any role assignments marked "needs_review": true
  - Move corrections into the "_overrides" section to lock them in across regenerations
  - Run /prompt or /quality-gate — both will now read this manifest automatically
```

---

## PHASE 5 — `--refresh`, `--show`, `--diff`, `--validate`

### `--refresh`

1. Read existing `.claude/project-design.json` → extract `_overrides` block.
2. Re-run phases 1–4 from scratch.
3. Deep-merge `_overrides` on top of the new manifest before writing (overrides win).
4. Print which fields the user's overrides preserved across the refresh.

### `--show`

Pretty-print the existing manifest to stdout. No regeneration.

### `--diff`

1. Read existing manifest as `OLD`.
2. Run phases 1–3 (extraction, role assignment) but don't write.
3. Diff old vs new JSON. Print as a structured diff:

```
[Init Design System] Diff vs existing manifest:
  ~ colors.accent.hex:  "#086A91" → "#0A75A1"  (new: appeared in 4 SCSS files this iteration)
  + colors.info:        added — #17a2b8 (used 6 times, role: info badges)
  - components.calendar.canonical_example  (removed — calendar component appears deleted)
  = 31 other fields unchanged
```

### `--validate`

1. Schema-check the existing manifest (all required color roles present, all `canonical_example` paths exist on disk, all `reuse_registry.import_path` resolve to a real export).
2. Report dead references:

```
[Init Design System] Validation:
  ⚠ components.table.canonical_example points to deleted file
  ⚠ reuse_registry "FormatDate" → @app/utils/dates::formatDate not found
  ✓ 8 color roles assigned and resolved
  ✓ 7 component canonicals exist
```

---

## Why this command exists

| Without manifest | With manifest |
|---|---|
| `/prompt` re-extracts SCSS vars from raw files on every call (~80 kB system prompt) | Reads `.claude/project-design.json` (~5 kB) |
| Quality Gate's Layer B has to re-infer "what role does this color play" every time | Manifest already says it |
| Style fidelity inconsistent run-to-run because raw extraction is order-dependent | Stable across runs |
| User can't correct mistakes — model re-makes them on next call | User edits `_overrides` once, persists forever |
| No reuse registry — AI has to grep for imports every time, often misses some | Registry is enumerated up-front |

This is the foundation for every other quality improvement that follows.

---

### MANDATORY STATUS REPORTING

Print a status line before EVERY major step. Format:

```
[Init Design System] {what is happening now}
```
