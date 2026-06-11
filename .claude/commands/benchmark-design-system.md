# /benchmark-design-system — Track Quality Gate quality over time

You are the **Design System Benchmark Runner**. Your job: run a fixed suite of standard prompts against a project, score the outputs against the manifest, and produce a regression-trackable score. Use this to know whether changes to `/prompt`, `/quality-gate`, or the manifest are helping or hurting.

**Arguments:** `$ARGUMENTS`

| Pattern | Mode |
|---|---|
| *(empty)* | Run full suite against current project, score against manifest, write report |
| `--baseline` | Run once, save scores as the project's baseline (`.claude/benchmark-baseline.json`) |
| `--compare` | Run, compare against baseline, surface regressions and improvements |
| `--filter <prompt-id>` | Run only the named prompt(s) |
| `--model <model>` | Run against a specific model (default: whatever the project is using) |
| `--no-quality-gate` | Run /prompt only, skip Quality Gate (measures raw /prompt quality) |

---

## PHASE 1 — Load the manifest + baseline

1. Read `.claude/project-design.json`. Abort if missing — direct user to `/init-design-system`.
2. If `--compare`, read `.claude/benchmark-baseline.json`. Warn if missing — suggest `--baseline`.

---

## PHASE 2 — The standard prompts (10 total)

Each prompt exercises a specific failure mode. They're chosen because they tend to catch the issues we care about.

| # | Prompt | Tests |
|---|---|---|
| 1 | "Create a {DOMAIN} table that shows {3-5 columns}" | Table structure, header color, row alt, status pills, currency/date conventions |
| 2 | "Add a Submit button to this form" | Reuse of shared/button (AST check) |
| 3 | "Build a list view of {entities} with a filter bar" | List pattern, filter input styling |
| 4 | "Create a modal dialog for editing {entity}" | Modal canonical match, button reuse inside modal |
| 5 | "Add a status badge column to the existing table" | Badge shape (pill), correct role-color mapping (success/warning/danger) |
| 6 | "Build a card showing {entity} summary with avatar + stats" | Card pattern, typography hierarchy |
| 7 | "Add a primary action button + secondary cancel button" | Variant reuse (primary vs secondary), spacing between |
| 8 | "Show a loading spinner with text 'Loading…'" | Loading state pattern, color from manifest |
| 9 | "Build a sidebar nav with 5 menu items + active state" | Nav pattern, active-color role |
| 10 | "Create an error message banner with retry button" | Danger role color, button reuse, banner pattern |

`{DOMAIN}` is auto-filled from the project (e.g. "SAF-T" for control-frontend, "invoice" for an accounting app). The runner detects the domain from `manifest.project` + `manifest.conventions.language` + a quick LLM call to guess what makes sense.

---

## PHASE 3 — Execute each prompt

For each prompt:

1. Call `/prompt "<prompt>"`. Capture the output.
2. Unless `--no-quality-gate`, call `/quality-gate <output-file>` on the result.
3. Parse the Quality Gate verdict and findings.
4. Score the result (see Phase 4).

Use a **fresh context** for each prompt — don't let one prompt's output bias the next.

---

## PHASE 4 — Score each result

Each prompt scores 0–100. Higher is better. Subtract from 100:

| Penalty | Points |
|---|---|
| Quality Gate verdict = NEEDS-REWORK | −30 |
| Layer A finding (per finding) | −5 |
| Layer B finding (per finding, applied) | −3 |
| Layer C divergence: critical | −15 |
| Layer C divergence: major | −8 |
| Layer C divergence: minor | −2 |
| AST: missed import from registry | −20 (per missed import) |
| Role-aware: semantic color misuse | −10 (per misuse) |
| Output failed to render (invalid HTML) | −50 |
| Took >60 seconds | −5 |

Bonus:

| Bonus | Points |
|---|---|
| Layer B verdict = clean on first try | +5 |
| Layer C verdict = aligned on first try | +10 |
| Reuse certificate has 0 registry_entries_relevant_but_unused | +5 |

Cap final score at 100. Floor at 0.

---

## PHASE 5 — Aggregate and report

Compute:

- **Overall score** = average of 10 prompt scores
- **Layer pass rates**: % of prompts with clean Layer A, B, C
- **Reuse score**: % of prompts that imported all relevant registry entries
- **Cost**: total API spend (tokens × pricing)

Write `reports/benchmark-{timestamp}.json`:

```json
{
  "generated_at": "...",
  "manifest_version": "...",
  "manifest_generated_at": "...",
  "model": "claude-haiku-4-5",
  "results": [
    {
      "prompt_id": 1,
      "prompt": "Create a SAF-T table...",
      "score": 87,
      "quality_gate_verdict": "REPLACED",
      "findings": { "layer_a": 0, "layer_b": 2, "layer_c": 1, "ast": 0, "role_aware": 0 },
      "duration_sec": 18,
      "cost_usd": 0.052
    },
    ...
  ],
  "aggregate": {
    "score": 81.4,
    "layer_a_pass_rate": 0.90,
    "layer_b_pass_rate": 0.70,
    "layer_c_pass_rate": 0.80,
    "ast_pass_rate": 0.85,
    "role_aware_pass_rate": 0.95,
    "total_cost_usd": 0.62,
    "total_duration_sec": 187
  }
}
```

Also write an HTML report at `reports/benchmark-{timestamp}.html` with:

- Score per prompt as a bar chart
- Side-by-side rendered output + canonical reference for each
- Findings detail per prompt (expandable)
- Cost + time totals

---

## PHASE 6 — Compare against baseline

If `--compare`:

```
[Benchmark] Comparison vs baseline (2026-06-08):

  Overall score: 78.2 → 81.4 (+3.2) 📈

  Per-prompt:
  ✓ #1 (SAF-T table):     82 → 87 (+5)
  ✓ #2 (Submit button):   65 → 95 (+30) — AST reuse check landed
  ⚠ #3 (List view):       80 → 72 (-8) — Layer C now flags spacing rhythm
  ✓ #4 (Modal):           75 → 81 (+6)
  ...

  Layer pass rates:
  Layer A:  0.85 → 0.90 (+5%)
  Layer B:  0.60 → 0.70 (+10%)
  Layer C:  0.70 → 0.80 (+10%)
  AST:      0.65 → 0.85 (+20%) ← biggest single-feature gain
  Role-aware: 0.90 → 0.95 (+5%)

  Cost:  $0.48 → $0.62 (+29%) — Vision adds cost; Layer B saves it back via fewer find/replace
  Time:  142s → 187s (+32%) — Vision adds ~5s per prompt
```

Surface any score drops >5 points as REGRESSIONS — these should be investigated before merging the change that caused them.

---

## PHASE 7 — `--baseline` mode

Save current run as the baseline:

```
.claude/benchmark-baseline.json
```

Subsequent `--compare` runs measure against this.

---

## Why this command exists

You can't improve what you don't measure. Without a benchmark:
- You "feel" the demo is better but can't prove it
- A prompt tweak that helps SAF-T tables might quietly hurt status badges
- Vision cost adds up; you need to know if it's earning its keep

10 prompts × 3 reference projects × 1 run per change is ~$3 of API cost and ~5 minutes of wall-clock. **Cheap insurance against silent regressions.**

Run this:
- Before merging any change to `/prompt.md` or `/quality-gate.md`
- After regenerating the manifest with `--refresh`
- Weekly as a cron job to detect drift in Anthropic models' baseline behavior

---

### MANDATORY STATUS REPORTING

```
[Benchmark] {what is happening now}
```
