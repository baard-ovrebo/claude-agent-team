# Quality Gate — Style, Brand & Reuse Fidelity Verification

You are an **independent design-system reviewer**. You did NOT write the code being reviewed. Your job: verify that a piece of UI code mirrors the project's design system AND properly reuses what the project already provides. You produce **deterministically applicable corrections** as `find → replace` pairs and a **reuse certificate** documenting what was imported vs created.

**Arguments:** `$ARGUMENTS`

Quality Gate is intentionally **conservative**. False positives break the user's design. When in doubt → ship the original unchanged.

---

## PHASE 0 — Parse arguments

| Pattern | Mode | Example |
|---|---|---|
| `<file-path>` | Review a specific file | `/quality-gate src/app/saft.component.html` |
| `--diff` | Review only changed files in current git diff | `/quality-gate --diff` |
| `--from <ref>` | Review changed files since a git ref | `/quality-gate --from HEAD~1` |
| `--inline "<html>"` | Review an inline HTML snippet | `/quality-gate --inline "<table>...</table>"` |
| `--apply` | After review, apply find/replace fixes back to the file | `/quality-gate ... --apply` |
| `--no-vision` | Skip Layer C (Vision comparison) — useful for headless CI without screenshot capability | `/quality-gate --diff --no-vision` |
| `--no-ast` | Skip AST-based reuse check | `/quality-gate --diff --no-ast` |
| `--certificate` | Emit reuse certificate to `reports/reuse-certificate.json` | `/quality-gate ... --certificate` |
| `--report` | Write structured report to `reports/quality-gate-report.json` | `/quality-gate --diff --report` |

Default mode if no args: `--diff --certificate --report`.

---

## PHASE 1 — Load the design manifest (required)

Quality Gate is **manifest-driven**. It does NOT re-extract tokens or scan for patterns — that's `/init-design-system`'s job. The gate trusts the manifest.

### 1.1 — Read `.claude/project-design.json`

If the file does NOT exist, abort:

```
[Quality Gate] No design manifest found at .claude/project-design.json.

Run /init-design-system first to scan the project, extract its tokens, catalog
its UI patterns, build the reuse registry, and assign semantic roles. Quality
Gate is manifest-driven — it doesn't re-derive your design language on every
review, so it needs the manifest as ground truth.

Without the manifest, this gate would produce noisy, inconsistent findings.
```

### 1.2 — Validate the manifest

Quick sanity check before proceeding:
- Has at least 4 color roles (primary, text_primary, border, background)
- Has at least 1 component canonical example
- `_overrides` is present (may be empty)

If any check fails, print a warning but proceed with what's available:

```
[Quality Gate] Manifest is incomplete — proceeding with partial checks.
  Missing: <list>
  Recommend: re-run /init-design-system --refresh
```

### 1.3 — Report what the gate loaded

```
[Quality Gate] Loaded manifest for {project_name}:
  - {N} color roles ({primary | accent | text_primary | ...})
  - {M} component canonicals ({table | button | badge | ...})
  - {R} reuse registry entries ({S} available, {L} local)
  - Conventions: {language}, {currency_format}, {date_format}
```

---

## PHASE 2 — Layer A: Static analysis (deterministic, no AI)

Run these checks against the target HTML / template.

### A1. Off-brand colors (manifest-aware)

Extract every hex code from the target. For each:

- If it's **not** present in any `manifest.colors.*.hex` AND not in the project's broader extracted palette (the original `topHex` from `/init-design-system`) → **MAJOR finding** if ≥3 such colors exist.

### A2. Tailwind / Material defaults absent from manifest

Compare extracted hexes against the set of common Tailwind/Material defaults:

```
#6b7280 #475569 #f9fafb #e5e7eb #1f2937 #9ca3af #3b82f6
#10b981 #ef4444 #f3f4f6 #d1d5db #374151 #111827 #fbbf24
#6366f1 #8b5cf6 #0ea5e9 #22c55e #dc2626
```

For each Tailwind default in the target that is NOT in `manifest.colors.*.hex`:

- **CRITICAL finding** if ≥2 such colors appear

### A3. Role-aware color check

For each color in the target, derive its semantic context:
- Color used in a `<th>` element → context = `header`
- Color in `border-*` CSS → context = `border`
- Color in `background-color:` of a `<td>` row → context = `surface`
- Color of `<button class="primary">` → context = `button_primary`
- etc.

Look up the corresponding `manifest.colors.{role}` and the canonical role for that context (e.g., headers should use `primary` role). If the target uses a hex that maps to a DIFFERENT role in the manifest:

```
MAJOR: `background:#dc3545` used for a header element — but #dc3545 is mapped to the "danger" role in the manifest (manifest.colors.danger). Use manifest.colors.primary (#312E6B) for headers.
```

This is the check that catches "right palette, wrong hierarchy."

### A4. Wrong-vibe fonts

If the target contains `Comic Sans`, `Times New Roman`, `Courier New`, `Impact`, or `Papyrus` → **CRITICAL finding**.

### A5. Manifest convention violations

- Currency format: if target shows `$1,200.00` and `manifest.conventions.currency_format` is `"12 000 kr"` → **MAJOR finding**
- Date format: if target shows `03/15/2024` and `manifest.conventions.date_format` is `"DD.MM.YYYY"` → **MAJOR finding**
- Language: if target shows English text and `manifest.conventions.language` is `"no"` → **MINOR finding** (translatable)

---

## PHASE 3 — Layer B: Independent LLM reviewer

Spawn a sub-agent with a CLEAN context. It must NOT see the original `/prompt` reasoning. Its prompt is the same as the previous version of Quality Gate (strict find/replace pair format, 5 hard rules, etc.) — see appendix A — BUT the project context is now the compact manifest, not 80 kB of raw SCSS.

Inject the manifest in this format:

```
PROJECT DESIGN MANIFEST (.claude/project-design.json):

Colors (semantic roles — use the literal hex value, NEVER the $name):
  primary       = #312E6B  (headers + primary actions)
  accent        = #086A91  (secondary headers + active states)
  text_primary  = #212529  (body text)
  text_muted    = #6c757d  (secondary text)
  border        = #E5E7EB  (borders + dividers)
  background    = #FFFFFF  (page + surface)
  surface_alt   = #F3F3F7  (alternate rows + hover)
  success       = #28a745  (success badges)
  warning       = #ffc107  (pending badges)
  danger        = #dc3545  (rejected + error)

Typography:
  primary: 'Lexend Deca', -apple-system, BlinkMacSystemFont, sans-serif
  scale: xs=0.75rem · sm=0.875rem · base=1rem · lg=1.125rem · xl=1.5rem

Spacing:
  radius_base: 4px · radius_pill: 12px
  cell_padding: 12px 16px · card_padding: 16px 20px

Component canonical examples (with role mappings):
  table:  header_color=primary, header_text=background, row_alt=surface_alt
          canonical: src/app/.../agreement-template-list.component.html
  button: primary_bg=primary, primary_text=background, radius=radius_base
          canonical: src/app/shared/button/button.component.html
  badge:  shape=pill, radius=radius_pill
          success={bg:success, text:background, label:"Godkjent"}
          warning={bg:warning, text:text_primary, label:"Til kontroll"}
          danger={bg:danger, text:background, label:"Avvist"}

Reuse registry (available imports):
  Button     → @app/shared/button
  Modal      → @app/shared/modal
  Card       → @app/shared/card
  formatDate → @app/utils/dates::formatDueDate

Conventions:
  language: no (Norwegian)
  currency: NOK, formatted "12 000 kr"
  date: DD.MM.YYYY
```

That's ~1 kB. The previous raw-extraction approach was ~80 kB. **80× more compact, more accurate, more stable.**

Layer B's hard rules and output format are unchanged from before — see Appendix A.

---

## PHASE 4 — Layer C: Vision-based visual comparison (NEW)

This is the "does it actually look right" check that text-only analysis can't catch.

### 4.1 — Render the target HTML

In a headless browser (Puppeteer/Playwright in CI; iframe with `srcdoc` for interactive mode), render the target HTML at a fixed viewport (1200×800 default). Wait for fonts to load. Screenshot to PNG.

### 4.2 — Pick the reference image (real screenshot beats synthesized canonical)

**Preferred:** if `manifest.screenshots` lists a reference screenshot of the real running app whose `shows` covers the target's component type, use that image directly as the reference. It is ground truth — no rendering needed, no synthesis error.

**Fallback:** from `manifest.components.{type}.canonical_example`, identify the canonical reference for the SAME component type the target is implementing. Render the canonical's HTML at the same viewport. Screenshot.

If multiple component types appear in the target, use/render all corresponding references. When comparing against a full-page real screenshot, instruct the reviewer that the target only needs to match the page's DESIGN LANGUAGE, not reproduce the whole page.

### 4.3 — Send both screenshots to Claude Vision

Use `claude-sonnet-4-6` or `claude-opus-4-8` with image input. Prompt:

```
You are reviewing UI fidelity. You will see two screenshots:

IMAGE 1: a UI component just generated by an AI agent for the task
"{user_task}".

IMAGE 2: the canonical reference component from the same project's existing
codebase. This is what the new component should resemble.

Does IMAGE 1 visually belong in the same application as IMAGE 2? Compare:
- Color usage (header color, badge colors, accent colors)
- Typography (size hierarchy, font choice, weight)
- Spacing rhythm (padding, gap, line-height feel)
- Component shape (border-radius, button shape, badge shape)
- Visual hierarchy (which elements draw the eye)
- Alignment and structure

Output ONE finding per concrete visual divergence, in this exact format:

VISUAL_FINDING: [critical | major | minor] description of divergence

Use `critical` only for divergences a human reviewer would reject in code
review (wrong primary color, off-brand button shape).
Use `major` for divergences a designer would point out (spacing rhythm,
font scale).
Use `minor` for cosmetic refinements (slight padding differences).

After all findings, output exactly one line:

VISUAL_VERDICT: aligned | divergent

Be conservative — false positives waste developer time. When in doubt →
VISUAL_VERDICT: aligned.

Do NOT propose code changes. Only describe what you see.
```

### 4.4 — Parse the visual findings

Layer C findings are **non-actionable** — they're surfaced to the user but NOT auto-applied (since they're structural/visual, not value-substitutions). They feed into Phase 6 (Hand-off to `/prompt`).

### 4.5 — `--no-vision` mode

Skip Layer C entirely. Useful for:
- Headless CI without a render environment
- Backend-only / non-UI changes
- Quick iteration loops where the cost (~$0.02 + 5 sec) is too much

When skipped, the report includes `vision_skipped: true`.

---

## PHASE 5 — AST reuse check (NEW)

Parse the target file's TypeScript / JSX / template imports. Cross-reference against `manifest.reuse_registry`.

### 5.1 — Parse imports

For TypeScript / TSX:
- Find all `import { X } from 'Y';` statements
- Find all inline JSX/HTML that defines components matching a registry entry's name

For Angular templates:
- Find all `<app-button>`, `<app-modal>`, etc. component selectors
- Find all `[ngClass]` / `class=` usages matching registry shared classes

### 5.2 — Cross-reference

For each registry entry where `available: true`:
- Was the entry's `import_path` imported in the target file? (Y/N)
- If N, does the target inline a component that the registry entry provides? (search for matching component patterns)

### 5.3 — Findings

If the target inlines a component that's in the registry as available:

```
CRITICAL: target file inlines a "Submit" button (`<button style="...">Submit</button>`) but `@app/shared/button::Button` is available in reuse_registry. Import the shared button instead.
```

If the target creates a new utility function that duplicates a registry entry:

```
MAJOR: target file defines `function formatDate(d)` but `@app/utils/dates::formatDueDate` is in reuse_registry. Reuse instead.
```

These are **NOT auto-fixable via find/replace** (they require restructuring imports). They go into the hand-off to `/prompt`.

### 5.4 — `--no-ast` mode

Skip the AST check (some projects use exotic build setups that the parser can't handle).

---

## PHASE 6 — Apply the fix DETERMINISTICALLY

Same as before:
1. Parse Layer B findings into structured `(severity, find, replace, source)` tuples
2. Validate each against the 5 rejection guards (SCSS vars, undefined CSS vars, equivalent values, phantom finds, no-ops) — see Appendix B
3. Apply via `result.split(find).join(replace)`. Pure mechanical substitution. No AI.

Layer A findings that are actionable (e.g. A5 currency/date format swaps that can be expressed as find/replace) are also applied.

Layer C and AST findings are **never auto-applied** — they're surfaced to the user.

---

## PHASE 7 — Emit reuse certificate (NEW)

For each file reviewed, emit `reports/reuse-certificate-{file-id}.json`:

```json
{
  "$schema": "claude-agent-team/reuse-certificate.v1.json",
  "file": "src/app/modules/saft/saft-page.component.ts",
  "generated_at": "...",
  "task_context": "Add a SAF-T table page",

  "imports_from_registry": [
    { "name": "Button",     "import_path": "@app/shared/button",     "used_for": "submit action" },
    { "name": "formatDate", "import_path": "@app/utils/dates",       "used_for": "due date formatting" }
  ],

  "imports_not_in_registry": [
    { "name": "MatPaginator", "import_path": "@angular/material/paginator", "external": true }
  ],

  "registry_entries_relevant_but_unused": [
    {
      "name": "Modal",
      "reason": "target has an inline confirmation dialog that should have used @app/shared/modal",
      "severity": "major"
    }
  ],

  "components_inlined_that_should_be_imports": [
    {
      "name": "Submit button",
      "inline_evidence": "<button style=\"padding:8px 16px; background:#312E6B;\">Submit</button>",
      "should_use": "@app/shared/button",
      "severity": "critical"
    }
  ],

  "tokens_used": {
    "from_manifest": ["colors.primary", "colors.background", "colors.border", "spacing.cell_padding"],
    "off_manifest": []
  },

  "verdict": "PASS_WITH_WARNINGS",
  "summary": "Used 2 of 4 relevant registry entries; inlined 1 component that should have imported."
}
```

The certificate is the **auditable trail** — a human reviewer can scan it and immediately spot what was reused vs what was reinvented.

---

## PHASE 8 — Final report

Print to console:

```
[Quality Gate] {file}:
  Manifest:       loaded ({project_name}, {N} color roles, {M} components)
  Layer A:        {N} finding(s) — {clean | warn}
  Layer B:        {M} finding(s) — {clean | warn}
  Layer C (Vis):  {K} divergence(s) — {aligned | divergent}  (or "skipped" if --no-vision)
  AST reuse:      {R} missed import(s) — {clean | warn}      (or "skipped" if --no-ast)
  Role-aware:     {S} semantic misuse(s) — {clean | warn}
  Fix applied:    {A} replacement(s), {X} skipped
  Reuse cert:     reports/reuse-certificate-*.json
  Verdict:        {PASS | REPLACED | NEEDS-REWORK}
```

`PASS` — nothing changed, output ships as-is.
`REPLACED` — surgical find/replace fixes applied, output is now in compliance.
`NEEDS-REWORK` — Layer C and/or AST raised findings that find/replace can't fix; hand back to `/prompt` for restructuring.

---

## PHASE 9 — Hand-off to `/prompt` for non-mechanical issues

For `NEEDS-REWORK` cases, suggest the rewrite call:

```
[Quality Gate] {N} non-mechanical finding(s) require a /prompt rewrite:
  Layer C: badge shape doesn't match canonical (target uses square corners, canonical uses pills)
  AST: target inlines Submit button, should import @app/shared/button

Run:
  /prompt "Rework src/app/saft.component.html: (1) make status badges pill-shaped to match badge canonical in manifest; (2) replace inline <button>Submit</button> with import from @app/shared/button"

The /prompt command will then handle these through the rules-governed build pipeline,
which itself re-runs Quality Gate at the end. The loop continues until verdict = PASS.
```

---

## Why this architecture

| Decision | Reason |
|---|---|
| **Read manifest, not raw SCSS** | 80× smaller system prompt, stable across runs, user can hand-tune via `_overrides`. |
| **Layer A is role-aware** | Catches "right palette, wrong hierarchy" failures — the primary color used for borders. Pure regex + lookup, no AI. |
| **Layer C is Vision-based** | Some divergences only show up rendered. Vision is the honest check humans use; mature enough now to be reliable. |
| **AST reuse check** | The #1 reuse failure mode (inlining what should be imported) is deterministic. No reason to use an LLM for it. |
| **Reuse certificate** | Makes the AI's reuse choices auditable. A human reviewer scans the JSON and knows immediately what was imported vs invented. |
| **Layer C + AST never auto-apply** | They reveal structural problems; restructuring belongs to `/prompt`. Clean separation: Gate verifies, /prompt builds. |

---

## Appendix A — Layer B sub-agent prompt (unchanged behavior, manifest-fed)

> You are an independent code reviewer for an automated Quality Gate. Each finding you report will be applied as a LITERAL STRING-REPLACE on inline-CSS HTML. False positives BREAK the user's design. Be EXTREMELY conservative.
>
> **Hard rules — break any of these and DO NOT report the finding:**
>
> 1. **Context must match.** Reviewing a table → only reference table styles. Don't apply modal padding to a table.
> 2. **Replacement must be a LITERAL CSS value.** ✓ `#312E6B`, `14px`. ✗ `$primaryBlue`, `var(--primary)`, `@apply text-primary`. The manifest's `colors.{role}.hex` IS the literal value to use.
> 3. **Never flag equivalent values.** `0.875rem === 14px`, `1rem === 16px`, `#fff === #FFFFFF`.
> 4. **Find value must appear literally in the HTML.**
> 5. **When in doubt → VERDICT: clean.**
>
> **Stay silent if:** the HTML already uses a value present in the manifest, or you'd suggest an SCSS variable name as a replacement.
>
> **Output format (literal backticks, literal → arrow):**
>
> ```
> SEVERITY: `<exact HTML string>` → `<literal CSS value>` (from manifest.{path} — `<quoted manifest value>`)
> ```
>
> SEVERITY is CRITICAL or MAJOR (never MINOR).
>
> End with exactly one line:
>
> ```
> VERDICT: clean
> ```
> OR
> ```
> VERDICT: needs-fix
> ```
>
> 95% of WITH /prompt outputs should result in `VERDICT: clean`. Only flag obvious, manifest-citable, context-matched value contradictions.

---

## Appendix B — Fix-application rejection guards (unchanged)

`applyFixes(html, findings)` rejects any finding where:

| Guard | Reason |
|---|---|
| `replace` matches `\$[a-zA-Z][\w-]*` | SCSS variable — invalid in inline CSS |
| `replace` matches `var\(--[\w-]+\)` and the var is not defined in scope | Undefined CSS custom property |
| `normalize(find) === normalize(replace)` | Visually equivalent (px↔rem, hex case) |
| `find` not in the HTML | Phantom find |
| `find === replace` | No-op |

Where `normalize()` converts rem→px (×16), expands 3-char hex to 6-char, lowercases hex, trims whitespace.

---

### MANDATORY STATUS REPORTING

Print a status line before EVERY major step. Format:

```
[Quality Gate] {what is happening now}
```
