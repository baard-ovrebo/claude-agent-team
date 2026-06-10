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

## Step 2 — Plan against the rules

Before writing any code, restate the task in your own words and write a short plan that **explicitly references each relevant rule**. For every rule that touches the task, state how you will satisfy it.

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

---

### Notes
- This command is installed **globally** (`~/.claude/commands/prompt.md`) so it works in every project, and is also versioned in this repo (`.claude/commands/prompt.md`).
- Rules come from **both** the global file (`~/.claude/prompt-rules.env`) and the project-local file (`.claude/prompt-rules.env`), combined. Global untagged rules apply everywhere; `[project: <name>]` sections apply only in the matching project; local rules win on conflict.
- Treat the rules as overriding your defaults. The whole point of `/prompt` is that the user has pre-committed you to these constraints.
