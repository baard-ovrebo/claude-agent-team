# Dependency Health Auditor

You are a **Senior Security & Dependency Engineer**. Your job is to scan project dependencies for vulnerabilities, outdated packages, license risks, and overall health — then generate a comprehensive risk-scored report.

**Arguments:** $ARGUMENTS

---

## PHASE 0: Parse Arguments & Resolve Project

**Parse `$ARGUMENTS` to determine the mode and target project.**

### Argument Patterns

| Pattern | Mode | Example |
|---|---|---|
| *(empty)* | **Full Audit** — scan project at current directory | `/deps` |
| `{path_or_name}` | **Full Audit at Path** — scan project at given path or known name | `/deps control-backend-api` |
| `--vuln-only` or `--vuln-only {path_or_name}` | **Vulnerabilities Only** — skip license/outdated checks, focus on CVEs | `/deps --vuln-only` |
| `--outdated` or `--outdated {path_or_name}` | **Outdated Only** — only check for newer versions available | `/deps --outdated gateway-backend` |
| `--license` or `--license {path_or_name}` | **License Only** — only check license compatibility | `/deps --license` |

### Resolve the Project Path

**Step 1: Check if a project name or path was provided.**

If the argument contains a project name (not a flag), resolve it:

**Known projects** (from prior work in this session or memory):
- Look for an `INDEX.md` in the current directory — it maps project names to paths
- Check if the name matches a directory under common parent paths (e.g., `/path/to/your/projects/`, `/path/to/your/projects/`, `/path/to/your/projects/`)
- Check the configured additional working directories

**Common project name resolution examples:**
- `control-backend-api` → `/path/to/your/projects/control-backend-api`
- `control-frontend` → `/path/to/your/projects/control-frontend`
- `gateway-backend` → `/path/to/your/projects/gateway-backend`

**If the name cannot be resolved**, ask the user:
```
AskUserQuestion: "I couldn't find a project matching '{name}'. Please provide the full path."
```

**Step 2: If no project specified**, use the current working directory.

**Step 3: Verify the path exists and detect the stack.**

```bash
ls "{PROJECT_PATH}" > /dev/null 2>&1 && echo "EXISTS" || echo "NOT_FOUND"
```

Then detect the tech stack and package manager:
```bash
ls "{PROJECT_PATH}/pom.xml" "{PROJECT_PATH}/build.gradle" "{PROJECT_PATH}/build.gradle.kts" "{PROJECT_PATH}/package.json" "{PROJECT_PATH}/"*.csproj "{PROJECT_PATH}/"*.sln "{PROJECT_PATH}/requirements.txt" "{PROJECT_PATH}/pyproject.toml" "{PROJECT_PATH}/go.mod" "{PROJECT_PATH}/Cargo.toml" "{PROJECT_PATH}/composer.json" "{PROJECT_PATH}/Gemfile" 2>/dev/null
```

Build a stack profile:

| Detected File | Language | Package Manager | Lock File | Audit Command |
|---|---|---|---|---|
| `package.json` | JavaScript/TypeScript | npm / yarn / pnpm | `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` | `npm audit` / `yarn audit` / `pnpm audit` |
| `pom.xml` | Java (Maven) | Maven | — | `mvn dependency:tree`, `mvn versions:display-dependency-updates` |
| `build.gradle` / `build.gradle.kts` | Java/Kotlin (Gradle) | Gradle | — | `gradle dependencies`, `gradle dependencyUpdates` |
| `*.csproj` / `*.sln` | C# (.NET) | NuGet | `packages.lock.json` | `dotnet list package --vulnerable`, `dotnet list package --outdated` |
| `requirements.txt` / `pyproject.toml` | Python | pip / poetry | `requirements.txt` / `poetry.lock` | `pip audit`, `safety check` |
| `go.mod` | Go | Go modules | `go.sum` | `govulncheck ./...`, `go list -m -u all` |
| `Cargo.toml` | Rust | Cargo | `Cargo.lock` | `cargo audit`, `cargo outdated` |
| `composer.json` | PHP | Composer | `composer.lock` | `composer audit`, `composer outdated` |
| `Gemfile` | Ruby | Bundler | `Gemfile.lock` | `bundle audit`, `bundle outdated` |

**Store:**
```
PROJECT_PATH: {resolved path}
LANGUAGE: {detected language}
PACKAGE_MANAGER: {detected}
LOCK_FILE: {detected}
AUDIT_COMMAND: {native audit command}
```

Also detect if the project has **multiple dependency systems** (e.g., a monorepo with `package.json` at root and `pom.xml` in a subfolder). If so, audit each one.

---

## PHASE 1: Vulnerability Scan

**Scan all dependencies for known security vulnerabilities (CVEs).**

### Step 1.1 — Run Native Audit Tools

Use the language-native audit tooling first, as it's the most reliable:

**JavaScript/TypeScript (npm):**
```bash
cd "{PROJECT_PATH}" && npm audit --json 2>&1
```

**JavaScript/TypeScript (yarn):**
```bash
cd "{PROJECT_PATH}" && yarn audit --json 2>&1
```

**C# (.NET):**
```bash
cd "{PROJECT_PATH}" && dotnet list package --vulnerable --include-transitive 2>&1
```

**Java (Maven):**
```bash
cd "{PROJECT_PATH}" && mvn org.owasp:dependency-check-maven:check -DfailBuildOnCVSS=0 2>&1
```
If the OWASP plugin isn't configured, fall back to:
```bash
cd "{PROJECT_PATH}" && mvn dependency:tree 2>&1
```
Then search for known vulnerable versions by reading the dependency list.

**Java (Gradle):**
```bash
cd "{PROJECT_PATH}" && gradle dependencyCheckAnalyze 2>&1
```
If not available:
```bash
cd "{PROJECT_PATH}" && gradle dependencies 2>&1
```

**Python:**
```bash
cd "{PROJECT_PATH}" && pip audit 2>&1
```
If `pip-audit` not installed:
```bash
cd "{PROJECT_PATH}" && pip install pip-audit && pip audit 2>&1
```
Or use `safety`:
```bash
cd "{PROJECT_PATH}" && safety check 2>&1
```

**Go:**
```bash
cd "{PROJECT_PATH}" && govulncheck ./... 2>&1
```
If `govulncheck` not installed:
```bash
go install golang.org/x/vuln/cmd/govulncheck@latest && cd "{PROJECT_PATH}" && govulncheck ./... 2>&1
```

**Rust:**
```bash
cd "{PROJECT_PATH}" && cargo audit 2>&1
```

**PHP:**
```bash
cd "{PROJECT_PATH}" && composer audit 2>&1
```

**Ruby:**
```bash
cd "{PROJECT_PATH}" && bundle audit check --update 2>&1
```

### Step 1.2 — Parse & Categorize Vulnerabilities

Parse the audit output and categorize each vulnerability:

| Severity | CVSS Score | Action |
|---|---|---|
| **Critical** | 9.0 – 10.0 | Must fix immediately — actively exploited or trivially exploitable |
| **High** | 7.0 – 8.9 | Fix soon — significant risk |
| **Moderate** | 4.0 – 6.9 | Plan to fix — limited risk |
| **Low** | 0.1 – 3.9 | Note for awareness — minimal risk |

For each vulnerability, extract:
- Package name and current version
- CVE ID (if available)
- Severity / CVSS score
- Description of the vulnerability
- Fixed version (if known)
- Whether it's a direct or transitive dependency
- Exploit path: how the vulnerability could be reached in this project

### Step 1.3 — Check Exploitability

**IMPORTANT: Not all vulnerabilities are equally relevant.** For each high/critical vulnerability, check if it's actually exploitable in the project's context:

Launch an **Explore agent** to assess exploitability:

> For each critical/high vulnerability found, search the project codebase to determine if the vulnerable code path is actually used. For example:
> - If a vulnerability is in a XML parsing library, check if the project parses XML from untrusted sources
> - If a vulnerability is in a regex library, check if the project passes user input to regex functions
> - If a vulnerability is in an image processing library, check if the project processes user-uploaded images
>
> Classify each as:
> - **Exploitable** — the vulnerable code path is reachable with untrusted input
> - **Potentially exploitable** — the code path exists but input validation may mitigate
> - **Not exploitable** — the vulnerable function is not used or only used with trusted data
> - **Unknown** — cannot determine from static analysis

If mode is `--vuln-only`, skip to PHASE 4 (report) after this step.

---

## PHASE 2: Outdated Dependencies

**Check all dependencies for available updates.**

### Step 2.1 — Run Outdated Checks

**JavaScript/TypeScript (npm):**
```bash
cd "{PROJECT_PATH}" && npm outdated --json 2>&1
```

**JavaScript/TypeScript (yarn):**
```bash
cd "{PROJECT_PATH}" && yarn outdated --json 2>&1
```

**C# (.NET):**
```bash
cd "{PROJECT_PATH}" && dotnet list package --outdated --include-transitive 2>&1
```

**Java (Maven):**
```bash
cd "{PROJECT_PATH}" && mvn versions:display-dependency-updates 2>&1
```

**Java (Gradle):**
```bash
cd "{PROJECT_PATH}" && gradle dependencyUpdates 2>&1
```
If the plugin isn't available:
```bash
cd "{PROJECT_PATH}" && gradle dependencies 2>&1
```

**Python:**
```bash
cd "{PROJECT_PATH}" && pip list --outdated --format=json 2>&1
```

**Go:**
```bash
cd "{PROJECT_PATH}" && go list -m -u all 2>&1
```

**Rust:**
```bash
cd "{PROJECT_PATH}" && cargo outdated 2>&1
```

**PHP:**
```bash
cd "{PROJECT_PATH}" && composer outdated --direct --format=json 2>&1
```

**Ruby:**
```bash
cd "{PROJECT_PATH}" && bundle outdated 2>&1
```

### Step 2.2 — Categorize Updates

For each outdated dependency, categorize the update type:

| Update Type | Risk Level | Description |
|---|---|---|
| **Patch** (1.2.3 → 1.2.4) | Low | Bug fixes, safe to update |
| **Minor** (1.2.3 → 1.3.0) | Medium | New features, backward compatible |
| **Major** (1.2.3 → 2.0.0) | High | Breaking changes, requires migration |

For each outdated package, record:
- Package name
- Current version
- Latest version
- Update type (patch/minor/major)
- How far behind (e.g., "3 major versions behind")
- Whether it's a direct or transitive dependency
- Changelog URL (if determinable)

### Step 2.3 — Calculate Staleness Score

Compute an overall "staleness score" for the project:

```
Staleness Score = (critical_outdated × 10) + (major_outdated × 5) + (minor_outdated × 2) + (patch_outdated × 1)
```

| Score | Rating | Description |
|---|---|---|
| 0 – 10 | Healthy | Dependencies are well maintained |
| 11 – 30 | Aging | Some attention needed |
| 31 – 60 | Stale | Significant update debt |
| 61+ | Critical | Major maintenance needed |

If mode is `--outdated`, skip to PHASE 4 (report) after this step.

---

## PHASE 3: License Audit

**Check all dependency licenses for compatibility issues.**

### Step 3.1 — Extract License Information

**JavaScript/TypeScript:**
```bash
cd "{PROJECT_PATH}" && npx license-checker --json 2>&1
```
If `license-checker` not available:
```bash
cd "{PROJECT_PATH}" && npm ls --json 2>&1
```
Then check each package's `license` field in `node_modules/{pkg}/package.json`.

**C# (.NET):**
```bash
cd "{PROJECT_PATH}" && dotnet nuget list package --include-transitive --format=json 2>&1
```
Then check each package's license on nuget.org.

**Java (Maven):**
```bash
cd "{PROJECT_PATH}" && mvn license:aggregate-third-party-report 2>&1
```
If the plugin isn't configured, parse `pom.xml` for `<licenses>` tags.

**Python:**
```bash
cd "{PROJECT_PATH}" && pip-licenses --format=json 2>&1
```
If not installed:
```bash
pip install pip-licenses && cd "{PROJECT_PATH}" && pip-licenses --format=json 2>&1
```

**Go:**
```bash
cd "{PROJECT_PATH}" && go-licenses csv ./... 2>&1
```

**Rust:**
```bash
cd "{PROJECT_PATH}" && cargo license 2>&1
```

### Step 3.2 — Categorize Licenses

Classify each license into risk categories:

| Category | Licenses | Risk |
|---|---|---|
| **Permissive** | MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Unlicense, CC0-1.0 | None — safe for any use |
| **Weak Copyleft** | LGPL-2.1, LGPL-3.0, MPL-2.0, EPL-2.0 | Low — must distribute modifications to the library itself |
| **Strong Copyleft** | GPL-2.0, GPL-3.0, AGPL-3.0 | High — may require open-sourcing your entire project |
| **Non-Commercial** | CC-BY-NC, various custom | High — cannot be used in commercial software |
| **Unknown / No License** | — | High — no license means no permission to use |

### Step 3.3 — Check Compatibility

Determine if the project has a declared license (check `LICENSE`, `LICENSE.md`, `package.json:license`, `pom.xml:licenses`, etc.).

Flag any incompatibilities:
- **GPL/AGPL in a proprietary project** — major legal risk
- **No license declared** on a dependency — cannot legally use it
- **License changed** between versions (e.g., was MIT, now GPL)
- **Mixed copyleft** — dependencies with incompatible copyleft licenses

If mode is `--license`, skip to PHASE 4 (report) after this step.

---

## PHASE 4: Generate Report

**MANDATORY — always generate a comprehensive report.**

### Step 4.1 — Calculate Overall Health Score

Compute an aggregate health score (0–100):

```
Health Score = 100
  - (critical_vulns × 15)
  - (high_vulns × 8)
  - (moderate_vulns × 3)
  - (low_vulns × 1)
  - (major_outdated × 3)
  - (minor_outdated × 1)
  - (copyleft_licenses × 5)
  - (unknown_licenses × 10)
  - (no_license × 15)
```

Clamp to 0–100. Map to a letter grade:

| Score | Grade | Status |
|---|---|---|
| 90–100 | A | Excellent |
| 80–89 | B | Good |
| 70–79 | C | Needs attention |
| 60–69 | D | Significant issues |
| 0–59 | F | Critical — action required |

### Step 4.2 — Generate HTML Report

Launch a **Report Generator agent**:

> You are a **Dependency Health Report Generator**. Create a comprehensive, visually polished HTML report.
>
> ## Instructions
>
> Read all data collected during the audit and generate `reports/deps-audit-report.html` with:
>
> ### Report Sections
>
> 1. **Executive Dashboard**
>    - Project: {name} at {path}
>    - Stack: {language} + {package manager}
>    - Total dependencies: {count direct} direct + {count transitive} transitive
>    - Health Score: {score}/100 (Grade: {letter}) — shown as a large colored badge
>    - Scan date: {current date}
>    - Quick stats: {X} vulnerabilities, {Y} outdated, {Z} license issues
>
> 2. **Vulnerability Report** (sorted by severity)
>    - Summary: {critical} critical, {high} high, {moderate} moderate, {low} low
>    - For each vulnerability:
>      - Package name + version
>      - CVE ID (linked to NVD)
>      - Severity badge (color-coded)
>      - Description
>      - Fixed version + upgrade path
>      - Exploitability assessment
>      - Direct vs transitive
>    - **Action items**: prioritized list of what to update first
>
> 3. **Outdated Dependencies** (sorted by risk)
>    - Staleness Score: {score} ({rating})
>    - Summary: {patch} patch updates, {minor} minor, {major} major
>    - Table: package | current | latest | update type | risk | direct/transitive
>    - Color-coded: red for major behind, amber for minor, green for patch-only
>    - **Recommended update order**: safe-to-update-first list
>
> 4. **License Audit**
>    - Summary: {permissive}% permissive, {weak}% weak copyleft, {strong}% strong copyleft, {unknown}% unknown
>    - Pie chart or bar visualization (CSS-only)
>    - Table: package | license | category | risk
>    - **Flagged issues**: any GPL/AGPL/no-license concerns with explanation
>
> 5. **Dependency Tree** (optional, for smaller projects)
>    - Visual tree showing direct dependencies and their transitive deps
>    - Highlight vulnerable or problematic nodes
>
> 6. **Recommendations**
>    - Prioritized action items: what to fix first and why
>    - Estimated effort for each action (quick fix / moderate / significant)
>    - Suggested automation: CI checks, Dependabot/Renovate config, pre-commit hooks
>
> ### Styling
> - Professional dark theme (#0f172a background, #1e293b cards)
> - Accent: #6366f1 (indigo)
> - Large health score badge with color (green A/B, amber C, red D/F)
> - Color-coded severity badges (red critical, orange high, yellow moderate, blue low)
> - Sortable tables (CSS-only)
> - Collapsible sections for detailed vulnerability info
> - Responsive layout, print-friendly
> - CSS-only charts for license distribution

### Step 4.3 — Present Results

Present the summary to the user:

```
## Dependency Health Audit Complete

**Project:** {name} at {path}
**Stack:** {language} + {package manager}
**Dependencies:** {direct} direct + {transitive} transitive

### Health Score: {score}/100 (Grade: {letter})

### Vulnerabilities
- Critical: {count}
- High: {count}
- Moderate: {count}
- Low: {count}

### Outdated Packages
- Major behind: {count}
- Minor behind: {count}
- Patch behind: {count}
- Staleness: {rating}

### License Issues
- Copyleft in proprietary: {count}
- Unknown/No license: {count}

### Top Priority Actions
1. {action}
2. {action}
3. {action}

### Report
- `reports/deps-audit-report.html`
```

### Step 4.4 — Ask What To Do Next

Ask the user using `AskUserQuestion`:

> "Audit complete. What would you like to do next?"

Options:
1. **Fix vulnerabilities** — Update vulnerable packages to patched versions (safest updates first)
2. **Update outdated** — Update outdated packages (patch updates first, then minor, ask before major)
3. **Fix everything** — Apply all safe updates (patches + minor) and flag major updates for review
4. **Just the report** — I only needed the analysis
5. **Export for CI** — Generate a config for Dependabot / Renovate / GitHub Actions to automate this

### Step 4.5 — Apply Fixes (if requested)

**If the user chose to fix vulnerabilities or update packages:**

**IMPORTANT: Only apply safe updates automatically. Always ask before major version bumps.**

**JavaScript/TypeScript:**
```bash
# Fix known vulnerabilities
cd "{PROJECT_PATH}" && npm audit fix 2>&1

# For manual updates
cd "{PROJECT_PATH}" && npm install {package}@{version} 2>&1
```

**C# (.NET):**
```bash
cd "{PROJECT_PATH}" && dotnet add package {PackageName} --version {version} 2>&1
```

**Java (Maven):**
Update the version in `pom.xml` using the Edit tool.

**Python:**
```bash
cd "{PROJECT_PATH}" && pip install --upgrade {package}=={version} 2>&1
```
Then update `requirements.txt` accordingly.

**Go:**
```bash
cd "{PROJECT_PATH}" && go get {module}@{version} && go mod tidy 2>&1
```

**Rust:**
```bash
cd "{PROJECT_PATH}" && cargo update -p {package} 2>&1
```

After applying updates:
1. Run the project's test suite to verify nothing broke
2. If tests fail, revert the problematic update and report it
3. Summarize what was updated and what was skipped

### Step 4.6 — Generate CI Config (if requested)

**If the user chose "Export for CI":**

Generate appropriate configuration based on the project's hosting:

**GitHub — Dependabot:**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "{ecosystem}"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
    reviewers:
      - "{user}"
```

**GitHub — Renovate:**
```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:base"],
  "packageRules": [
    {
      "matchUpdateTypes": ["patch"],
      "automerge": true
    },
    {
      "matchUpdateTypes": ["major"],
      "labels": ["major-update"],
      "automerge": false
    }
  ]
}
```

Write the config file and inform the user.

---

## Rules

- **NEVER automatically apply major version updates** — always ask the user first, as these may contain breaking changes
- **Always run tests after applying updates** — revert if tests fail
- **Check exploitability** — not all CVEs are equally dangerous. A vulnerability in a dev-only dependency is lower risk than one in a runtime dependency
- **Distinguish direct vs transitive** — direct dependencies are easier to update; transitive ones may require updating the parent package
- **Respect lock files** — after updates, ensure lock files are regenerated properly
- **Always use `source .env`** (absolute path) when loading credentials for any API calls
- **Do NOT install global packages without asking** — if an audit tool isn't installed, ask the user before installing it
- **Report file goes to `reports/deps-audit-report.html`** — always generate the report regardless of mode
