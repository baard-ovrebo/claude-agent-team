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

## Step 1.5 — Load the project's design manifest (do this BEFORE planning if the task involves UI)

If the task involves building, modifying, or styling any UI (component, page, widget, template, style sheet), you MUST consult the project's design manifest. This is what makes "match the project's style" actually reliable.

Skip this step ONLY if the task is purely non-visual (data migrations, pure logic, backend wiring with no UI surface).

### 1.5a — Prefer the persistent manifest

First check for `.claude/project-design.json` in the project root.

**If it exists:** READ IT. This is your authoritative source for the project's design language. It's compact (~5 kB), stable across runs, and may include user-corrected `_overrides`. Skip 1.5b/1.5c if a valid manifest exists.

**If it does NOT exist:** abort with this message and tell the user to generate one first:

```
[Prompt] No design manifest found at .claude/project-design.json.

The project's design language has not been mapped yet. Run this once, then
re-run your task:

  /init-design-system

This will scan the project, extract its tokens, catalog its UI patterns,
build a reuse registry, and write the manifest. It's a one-time setup
(re-run with --refresh if the design language changes later).

Without the manifest, /prompt would have to re-derive your design language
from raw SCSS on every call — slower, more expensive, less consistent.
```

Do NOT proceed without the manifest. Tell the user to run `/init-design-system`, then stop.

### 1.5b — How to use the manifest in your build

When you write code, lean on these manifest sections:

- **`colors.{role}.hex`** — use the literal hex value for each role (e.g. `colors.primary.hex` for headers). NEVER use the SCSS variable name in inline CSS or HTML preview snippets.
- **`typography.primary.family`** — the font-family string (use literally).
- **`spacing.*`** — radius, padding, gap values.
- **`components.{type}`** — for each component type, the canonical example path + role mappings. When the user asks for a table, mirror `components.table.html_snippet` structure and apply the role-mapped colors.
- **`reuse_registry`** — every entry with `available: true` is something you CAN import. CHECK THIS LIST before creating anything new. If a registry entry exists for what the user asked for, import it instead of building.
- **`conventions`** — language, currency format, date format. Use these literally.

### 1.5b.2 — Screenshot grounding (the strongest style anchor)

Check `.claude/design-screenshots/` for reference screenshots of the real running application (PNG/JPEG, captured by the team or by `/init-design-system --screenshots`). If one exists for the relevant screen/component type:

- **Read it** (you can read images) and treat it as ground truth that OVERRIDES text-derived style. What you see in the screenshot beats what you infer from SCSS.
- Match its design language precisely: header treatment, table/row styling, badge shapes, fonts, spacing rhythm.

Why: models follow visual examples far more faithfully than style descriptions. A screenshot of the real app is worth more than 80 kB of SCSS.

### 1.5b.3 — Template mode (copy, don't reinterpret)

When the manifest's `components.{type}` has a canonical example of the SAME component type you're building:

- Treat the canonical's HTML as your **template**. Copy its tag structure, nesting, and styling approach exactly.
- Change ONLY the data: column names, cell contents, labels.
- Do not "improve" the layout, reorganize it, or modernize it. An exact structural copy with new data is the goal.
- Models drift when they reinterpret; they stay on-brand when they copy. **Copy.**

### 1.5c — Cite the manifest in your plan

In Step 2 (Plan), explicitly cite which manifest entries you'll consume:

```
[Prompt] Manifest references:
  - Color: colors.primary.hex (#312E6B) for table header background
  - Color: colors.background.hex (#FFFFFF) for header text
  - Color: colors.surface_alt.hex (#F3F3F7) for alternate rows
  - Component: components.table.html_snippet structure (from agreement-template-list.component.html)
  - Reuse: importing @app/shared/button for action buttons (reuse_registry["Button"])
  - Conventions: Norwegian labels, "DD.MM.YYYY" dates, "12 000 kr" currency
```

### 1.5d — Skip rules

You may skip Step 1.5 if:
- The task is non-visual (data migrations, backend logic, infrastructure)
- The task is a single-line tweak to an existing file
- You've already cited the manifest in this session and the project state hasn't changed

Otherwise, Step 1.5 is **mandatory** for any UI work. The manifest is small; reading it adds milliseconds. The payoff is on-brand output the first time instead of a build-review-rebuild loop.

---

## Step 2 — Plan against the rules + manifest

Before writing any code, restate the task in your own words and write a short plan that **explicitly references each relevant rule** and, for UI work, **explicitly cites the manifest entries** you'll consume. For every rule that touches the task, state how you will satisfy it.

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

Quality Gate reads the SAME `.claude/project-design.json` you read in Step 1.5 — both sides agree on what "the project's style" is. It will then:

1. **Layer A** — Deterministic static checks against the manifest (off-brand colors, wrong fonts)
2. **Layer B** — Independent LLM reviewer producing strict find/replace pairs
3. **Layer C** — Claude Vision: screenshots your output + the manifest's canonical example, compares them visually, surfaces any divergence
4. **AST reuse check** — parses your output and verifies imports against the manifest's `reuse_registry`. If you wrote a `<button>` inline when `@app/shared/button` exists in the registry → hard fail.
5. **Role-aware color check** — verifies your color usage matches the role-mapping in the manifest (e.g. the primary brand color isn't used for borders).
6. **Fix application** — deterministic find/replace (no AI rewrite) with rejection guards for SCSS vars, equivalent values, phantom finds.

Report Quality Gate's result in the compliance checklist:

```
[Prompt] Quality Gate verdict:
  Layer A: {clean | N findings}
  Layer B: {clean | N findings}
  Layer C (Vision): {clean | N divergences from canonical example}
  AST reuse:        {clean | N missed imports — would have used X from reuse_registry}
  Role-aware:       {clean | N semantic color misuses}
  Fix:              {N replacements applied, M skipped (reasons)}
  Reuse certificate: {emitted | failed}

  Final: PASS | REPLACED | NEEDS-REWORK
```

If Quality Gate returns `REPLACED`, the task is still complete — the gate just trimmed your output to match the project. If it returns `NEEDS-REWORK` (i.e. structural findings that find/replace can't fix, OR missed reuse), address them in a follow-up `/prompt` cycle and re-run Quality Gate until PASS.

### Step 4.6 — Emit a reuse certificate

For every component / function / file you created or modified, emit a **reuse certificate** to `reports/reuse-certificate-{task-id}.json`:

```json
{
  "task": "Add a SAF-T table page",
  "timestamp": "...",
  "components_created": [
    {
      "path": "src/app/modules/saft/saft-page.component.ts",
      "imports_from_registry": ["@app/shared/table", "@app/shared/button", "@app/utils/dates"],
      "imports_new": [],
      "scss_classes_used": ["agreement-table", "status-pill"],
      "tokens_referenced": ["$primaryBlue", "$lightGrey", "$tableHeaderText"]
    }
  ],
  "registry_entries_unused_but_relevant": [],
  "reviewer_notes": "..."
}
```

If `registry_entries_unused_but_relevant` is non-empty, Quality Gate would have flagged this in step 4.5 — but the certificate serves as the auditable record. Paste a summary of the certificate into the PR description (the user can copy it from the file).

---

### Notes
- This command is installed **globally** (`~/.claude/commands/prompt.md`) so it works in every project, and is also versioned in this repo (`.claude/commands/prompt.md`).
- Rules come from **both** the global file (`~/.claude/prompt-rules.env`) and the project-local file (`.claude/prompt-rules.env`), combined. Global untagged rules apply everywhere; `[project: <name>]` sections apply only in the matching project; local rules win on conflict.
- Treat the rules as overriding your defaults. The whole point of `/prompt` is that the user has pre-committed you to these constraints.
