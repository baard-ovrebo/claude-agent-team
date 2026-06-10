# Rules-Governed Prompt

You are a **disciplined engineering agent**. The user is giving you a task, but **before and while** you carry it out you MUST obey a set of project-specific rules defined in a rules file. These rules are non-negotiable constraints, not suggestions.

**Input:** $ARGUMENTS

---

## Step 0 — Detect the mode

Look at the input. It is one of two modes:

- **Manage-rules mode** — the input begins with a flag like `--add-rule`. Go to the "Managing rules" section below, do that, and **stop** (do not run a task).
- **Task mode** — anything else. The input is a task to perform; continue with Step 1.

### Managing rules

**`--add-rule "<rule text>"`** (optionally with `--global` and/or `--project <name>`):

1. Determine the target rules file:
   - If `--global` is present → `~/.claude/prompt-rules.env` (home `.claude`, e.g. `C:\Users\<you>\.claude\prompt-rules.env`).
   - Otherwise → the project file `.claude/prompt-rules.env` if it exists; if it does **not** exist, fall back to the global file.
   - If the target file does not exist yet, create it with a short `#` header explaining the one-rule-per-line / project-tag format.
2. Determine the target **scope**:
   - If `--project <name>` is given → the rule goes under a `[project: <name>]` section. If that section header doesn't exist in the file yet, add it. Append the rule as the last line of that section.
   - If no `--project` → the rule is global; append it in the global (untagged) area, before the first `[project: ...]` header.
3. Extract the rule text from inside the quotes. Trim it. If it is empty, tell the user and stop.
4. **Deduplicate:** if an identical (case-insensitive, trimmed) rule line already exists **in the same scope**, tell the user it's already there and stop — do not add a duplicate.
5. Insert the rule as a **new line** in the right place (ensure proper newlines so rules never concatenate onto a comment, header, or another rule). Write it verbatim, no `#` prefix.
6. Confirm to the user:

```
[Prompt] Added rule to <project|global> file: <path>
  scope: <global | project: name>
  + <rule text>
Now active for the next /prompt run in that scope.
```

Other manage flags you should also handle:
- **`--list-rules`** — print the currently active rules (resolved project-first) with their numbers and which file they came from. Then stop.

Then **stop** — managing rules never also runs a task in the same invocation.

---

## Step 1 — Load the rules (MANDATORY, do this first)

### 1a. Identify the current project

Determine the current project's name = the folder name of the git repo root (run `git rev-parse --show-toplevel` and take its basename), or, if not in a git repo, the basename of the current working directory. Also keep the full project root path. Example: `control-frontend`, `gateway-backend`, `AIComp`.

### 1b. Read the rules files

Read **both** of these if they exist (you combine them, you do NOT pick just one):

1. **Global:** `~/.claude/prompt-rules.env` (home `.claude`, e.g. `C:\Users\<you>\.claude\prompt-rules.env`).
2. **Project-local:** `.claude/prompt-rules.env` in the current project root.

If **neither** exists, tell the user, show both paths, and stop — do not proceed without rules.

### 1c. Parse rules and project tags

Parse each file top to bottom:
- Lines starting with `#` are comments → ignore. Blank lines → ignore.
- A line of the form `[project: <name>]` (or `[project: a, b]`, or `[all]` / `[project: all]`) is a **section header**, not a rule. It sets the scope for the rules that follow it, until the next header.
- Any other non-empty line is **one rule**, belonging to the current section scope.

**Which rules apply:**
- Rules before any header, or under an `[all]` / `[project: all]` section → **always apply** (global scope).
- Rules under `[project: <name>]` → apply **only if** `<name>` matches the current project. A name matches when it equals the current project's folder/repo name (case-insensitive) **or** appears as a path segment in the project root path. Multiple names in one header → matches if any one matches.
- Rules under a section that does NOT match the current project → **ignored** for this run.

The project-local file's rules are inherently for this project; apply all of them (they may also use tags). If a local rule conflicts with a global one, the **local rule wins**.

### 1d. Report what you loaded

```
[Prompt] Project: <name>  (<project root path>)
[Prompt] Loaded N applicable rule(s):
  global  1. <rule text>
  global  2. <rule text>
  [control-frontend] 3. <rule text>
  ...
(skipped M rule(s) tagged for other projects)
```

## Step 1.5 — Map the project's design system (do this BEFORE planning if the task involves UI)

If the task involves building, modifying, or styling any UI (component, page, widget, template, style sheet), you MUST first build a snapshot of the project's actual design system. This is what makes "match the project's style" actually reliable — without it, "use the project's colors" degrades to best-effort guessing.

Skip this step ONLY if the task is purely non-visual (data migrations, pure logic, backend wiring with no UI surface).

### 1.5a — Auto-extract design tokens (synthesize the project's `_variables.scss`)

Walk the project's SCSS / SASS / CSS / Less files (skip `node_modules`, `dist`, `build`, `.git`, `.angular`) and extract:

| Token type | Regex |
|---|---|
| SCSS variable definitions | `\$([a-zA-Z][\w-]*)\s*:\s*([^;{}\n]+?)\s*(?:!default\s*)?;` |
| CSS custom properties | `--([a-zA-Z][\w-]*)\s*:\s*([^;{}\n]+?)\s*;` |
| Hex color usage frequency | `#([0-9a-f]{3}|[0-9a-f]{6})\b` |
| `font-family` declarations | `font-family\s*:\s*([^;{}\n]+?);` |
| `border-radius` declarations | `border-radius\s*:\s*([^;{}\n]+?);` |

Then **resolve one level of variable indirection**: if `$tableHeaderBg: $primaryBlue;` and `$primaryBlue: #312E6B;`, record `$tableHeaderBg = #312E6B (originally $primaryBlue)`.

Report what you found:

```
[Prompt] Design tokens extracted from {project_name}:
  - {N} SCSS variables (top color vars: $primaryBlue=#312E6B, $lighterBlue=#086A91, ...)
  - {M} CSS custom properties
  - Top palette: #312E6B (47×), #F3F3F7 (23×), #FFFFFF (89×), ...
  - Font: {literal font-family declaration}
  - Border-radius scale: 4px (38×), 12px (4×)
```

When you write inline styles or CSS, use the **resolved literal values** (e.g. `background:#312E6B`), NEVER the variable name (`$primaryBlue` does NOT work in inline CSS / preview HTML).

### 1.5b — Scan for existing UI patterns (build the project's pattern catalog)

Walk every `.html` (Angular) / `.tsx`/`.jsx` (React) / `.vue` (Vue) / `.svelte` file in the project. Use regex to detect existing UI patterns and pair each match with its companion stylesheet (Angular convention: `foo.component.html` + `foo.component.scss`; React: same file).

Patterns to catalog (detect-regex / max-snippet-size):

| Type | Detect regex | Snippet |
|---|---|---|
| Tables | `<table\b\|<mat-table\b\|<p-table\b\|<cdk-table\b` | 1800 chars |
| Lists | `<ul\b[^>]*class=\|<mat-list\b\|<p-listbox\b\|<li\b[^>]*\*ngFor` | 1200 chars |
| Cards | `<mat-card\b\|<p-card\b\|class="[^"]*\bcard\b` | 1200 chars |
| Modals / dialogs | `<mat-dialog\b\|<p-dialog\b\|class="[^"]*\b(modal\|dialog)\b` | 1500 chars |
| Forms | `<form\b\|<mat-form-field\b\|formControlName=` | 1200 chars |
| Badges / chips / pills | `<mat-chip\b\|<p-chip\b\|<p-tag\b\|class="[^"]*\b(badge\|chip\|pill\|tag\|status-?\w*)\b` | 700 chars |
| Styled buttons | `<button\b[^>]*class="[^"]*\b(primary\|secondary\|outlined\|raised\|fab\|btn-[\w-]+)\b\|<mat-button\b\|<p-button\b` | 500 chars |

For each pattern type, keep the top 2 examples ranked by richness (snippet length + paired-SCSS length).

Report what you found:

```
[Prompt] UI patterns catalogued:
  - Tables: {N} found (top: src/app/modules/.../some-list.component.html)
  - Lists: {M} found
  - Cards: ...
  - Modals: ...
  - Forms: ...
  - Badges: ...
  - Buttons: ...
```

### 1.5c — When you build, MIRROR the catalog

When the task asks for one of these component types, you MUST first reference the catalog and MIRROR the closest existing example:

- Same tag structure (e.g. if existing tables use `<table>` with `<thead>` + `<tbody>` and not `<mat-table>`, do the same)
- Same class names where shared
- Same row / cell shape
- Same badge / pill shape
- Same paired-SCSS color references (using the resolved literal hex values from 1.5a)

If the catalog has zero examples of the requested type (e.g. user asks for a "calendar" and you find none) → say so explicitly and create new, building it in the project's shared location. Reference 1.5a for colors/fonts/spacing.

### 1.5d — Skip rules

You may skip Step 1.5 if:
- The task is non-visual (data migrations, backend logic, infrastructure)
- The task is a single-line tweak to an existing file (don't waste a scan for `change padding by 2px`)
- You've already run Step 1.5 in the same session and the project state hasn't materially changed

Otherwise, Step 1.5 is **mandatory** for any UI work. The cost is a few seconds; the payoff is on-brand output the first time instead of a build–review–rebuild loop.

---

## Step 2 — Plan against the rules

Before writing any code, restate the task in your own words and write a short plan that **explicitly references each relevant rule**. For every rule that touches the task, state how you will satisfy it.

If Step 1.5 was run, the plan must also reference:
- Which catalog example(s) you will mirror (cite the file path)
- Which token values you will use (cite the SCSS variable and its resolved hex)

In particular, for reuse/DRY-type rules you MUST actually search the codebase first:
- Search for existing classes, components, functions, variables, types, constants, styles, and utilities that already do what the task needs (use Grep/Glob/Explore across the project).
- If a suitable thing exists → reuse it.
- If it exists but is local/duplicated → refactor it into a shared location and update **all** existing usages to consume the shared version.
- Only create something new when you have confirmed nothing reusable exists, and say so explicitly.

Report findings before editing:

```
[Prompt] Reuse scan: searched for "<thing>" → found <X> / found none.
[Prompt] Decision: reuse <file:symbol> / promote <file:symbol> to shared / create new (justification: ...).
```

## Step 3 — Execute the task

Carry out the task, honoring every loaded rule at all times. If two rules conflict, or a rule makes the task impossible, stop and ask the user instead of silently breaking a rule.

When you modify a shared piece, update every existing caller of it (don't leave forks behind), per the reuse rules.

## Step 4 — Verify against the rules

After finishing:
- Run the project's existing tests/linters if available and report the result.
- Produce a **compliance checklist**: list each loaded rule and mark it ✅ satisfied / ⚠️ not applicable / ❌ violated (with reason). You must not finish with any ❌ unless the user approved it.

```
[Prompt] Rule compliance:
  ✅ Rule 1 — reused existing <X> instead of creating new
  ✅ Rule 2 — matched existing style
  ⚠️ Rule 3 — not applicable (no external API touched)
```

### Step 4.5 — Auto-invoke Quality Gate for UI work

If Step 1.5 was run (i.e. this was UI work), automatically invoke `/quality-gate` on the changed file(s) before declaring the task done:

```
/quality-gate <changed-file> --apply
```

Quality Gate will:
1. Build the same design context you built in Step 1.5 (token palette + pattern catalog) — both sides agree on what "the project's style" is
2. Run an independent reviewer with a clean context that has never seen your reasoning
3. Surface any find/replace pairs as deterministic corrections
4. Apply only the corrections that survive its validation guards (rejects SCSS variables, rejects equivalent-value swaps, rejects phantom finds)
5. Hand back any structural findings that can't be expressed as find/replace — those come back to YOU as a new `/prompt` cycle

Report Quality Gate's result in the compliance checklist:

```
[Prompt] Quality Gate: PASS | REPLACED ({N} fixes applied) | INFORMATIONAL ({M} notes)
```

If Quality Gate returns `REPLACED`, the task is still complete — the gate just trimmed your output to match the project. If it returns structural findings, address them in a follow-up `/prompt` cycle and re-run Quality Gate until clean.

---

### Notes
- This command is installed **globally** (`~/.claude/commands/prompt.md`) so it works in every project, and is also versioned in this repo (`.claude/commands/prompt.md`).
- Rules come from **both** the global file (`~/.claude/prompt-rules.env`) and the project-local file (`.claude/prompt-rules.env`), combined. Global untagged rules apply everywhere; `[project: <name>]` sections apply only in the matching project; local rules win on conflict.
- Treat the rules as overriding your defaults. The whole point of `/prompt` is that the user has pre-committed you to these constraints.
