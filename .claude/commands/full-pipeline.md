# Full Pipeline Orchestrator — Dev Team + Docker

You are the **Pipeline Orchestrator** — the ultimate team lead. You coordinate the ENTIRE software delivery pipeline: code quality, security, fixes, unit testing, Playwright E2E testing, Docker build, deployment, integration testing, and final reporting.

This is a four-phase pipeline:
- Phase 1: Code quality loop (scan, fix, test, repeat)
- Phase 2: Playwright E2E testing against the web UI
- Phase 3: Docker containerization, deployment, and integration testing
- Phase 4: Master report compilation

---

## PHASE 1: Code Quality Loop

Execute this iterative loop until the code is clean:

### Step 1.1 — Parallel Scan
Launch TWO agents in parallel (using the Agent tool):

**Agent A: Security Auditor**
- Scan every source file for OWASP Top 10 vulnerabilities
- Check for: injection, broken auth, data exposure, XSS, access control, misconfig
- Categorize: CRITICAL / WARNING / INFO
- Write findings to `reports/security-audit.md`

**Agent B: Code Quality Engineer**
- Scan every source file for code smells, bugs, anti-patterns
- Check for: type safety, error handling, performance, dead code, API design
- Categorize: CRITICAL / WARNING / INFO
- Write findings to `reports/quality-audit.md`

### Step 1.2 — Fix
Launch a **Backend Developer** agent:
- Read findings from `reports/security-audit.md` and `reports/quality-audit.md`
- Fix ALL issues, prioritized: CRITICAL → WARNING → INFO
- Write summary to `reports/fixes-applied.md`

### Step 1.3 — Test
Launch a **Test Engineer** agent:
- Write tests for every fix
- Write edge case and security regression tests
- Run ALL tests, iterate until 100% pass
- Write results to `reports/test-report.md`

### Step 1.4 — Regression Check
Re-run Security Auditor + Code Quality Engineer on the modified code. If NEW issues are found, repeat from Step 1.2. Continue until a scan produces ZERO new findings.

---

## PHASE 2: Playwright E2E Testing

Only begin Phase 2 after Phase 1 completes with zero findings and all unit tests passing.

### Step 2.1 — Run Playwright E2E Tests
Launch a **Playwright E2E Test Engineer** agent:
- Verify Playwright is installed (`node_modules/@playwright/test` exists); if not, install it
- Run the full Playwright test suite: `cd demo-api && npx playwright test`
- The suite tests: authentication flows, product CRUD, user management, order lifecycle, and security (XSS, data leaks, auth bypass)
- If any tests fail, determine if it's a test bug or an app bug:
  - **App bug:** fix the source code, re-run unit tests, then re-run Playwright tests
  - **Test bug:** fix the test, re-run
- Loop until all E2E tests pass
- The Playwright HTML report is auto-generated at `reports/playwright-report/index.html`
- Write summary to `reports/playwright-test-report.md`

### Step 2.2 — Coverage Check
After all tests pass, check for untested user flows:
- Are all views tested (login, dashboard)?
- Are all CRUD operations covered?
- Are error states tested (invalid input, unauthorized access)?
- Write any additional tests for gaps found
- Re-run and verify

---

## PHASE 3: Docker Pipeline

Only begin Phase 3 after Phase 2 completes with all E2E tests passing.

### Step 3.1 — Docker Build
Launch a **Docker Build** agent:
- Build the Docker image using `docker compose build` in `demo-api/`
- Validate: image size, non-root user, health check, no secrets in layers
- Run security scan if available
- Write report to `reports/docker-build-report.md`
- If build fails, fix the Dockerfile and retry

### Step 3.2 — Docker Deploy
Launch a **Docker Deploy** agent:
- Clean up any previous deployment
- Run `docker compose up -d` in `demo-api/`
- Wait for health check to pass
- Test key endpoints with curl
- Collect ALL deployment info: container ID, IP, ports, network, resource usage
- Write report to `reports/docker-deploy-report.md`

### Step 3.3 — Docker Integration Tests
Launch a **Docker QA** agent:
- Run full integration test suite against the live container
- Test: auth flow, CRUD, orders, security, edge cases, container health
- Record every request/response
- Write report to `reports/docker-integration-test-report.md`

### Step 3.4 — Cleanup Decision
After integration tests complete:
- If all tests pass: proceed to master report (leave container running for demo)
- If tests fail: fix issues, rebuild, redeploy, retest (loop)

---

## PHASE 4: Master Report

Launch a **Documentation Lead** agent to compile ALL reports into a single master HTML report at `reports/master-report.html`.

The report MUST include:

### Executive Summary
- Pipeline status: PASSED / FAILED
- Total issues found and fixed (by category)
- Tests written and pass rate
- Rounds needed in Phase 1
- Docker build and deployment status

### Section 1: Security Audit
- All findings with severity badges
- Before/after code snippets for critical fixes
- OWASP category mapping

### Section 2: Code Quality
- All findings with improvements made
- Patterns identified

### Section 3: Fixes Applied
- Every change, grouped by file
- Rationale for each fix

### Section 4: Test Results
- Unit test results table
- Security regression test results
- Coverage analysis

### Section 5: Docker Build
- Image details: name, size, base image, layers
- Security scan results
- Optimization notes

### Section 6: Docker Deployment
- **Full access information table:**

| Item | Value |
|------|-------|
| API Base URL | http://localhost:3000 |
| Container Name | demo-api |
| Container ID | [ID] |
| Container IP | [IP] |
| Network | [name] ([subnet]) |
| Port Mapping | 3000:3000 |
| Health Status | healthy |
| Memory Usage | [usage] |

- All endpoint verification results with URLs and response summaries

### Section 7: Integration Test Results
- Full test matrix with pass/fail
- Failed test details with curl commands and responses
- Container health during testing

### Section 8: Recommendations
- Remaining concerns
- Production readiness assessment
- Next steps

### Styling
- Dark theme: bg #0f172a, cards #1e293b, accent #6366f1
- Severity badges: Critical (red), Warning (amber), Info (cyan), Success (green)
- Collapsible sections with `<details><summary>`
- Sticky top navigation
- Responsive layout
- Print-friendly `@media print` styles
- Monospace code blocks

---


### MANDATORY — CLICKABLE SCREENSHOTS IN HTML REPORTS
Any HTML report that contains screenshots MUST include a JavaScript lightbox so users can click any screenshot to view it full-size. Include this in every generated HTML report that has images:
- Every screenshot `<img>` must have `cursor: pointer` and an `onclick` handler
- Clicking opens a dark overlay with the image at full viewport size (95vw/95vh max)
- Clicking the overlay or pressing Escape closes it
- This applies to: verification reports, feature plans, Jira reports, master reports, org documentation, before/after comparisons


### MANDATORY — UNDERSTAND EXISTING CODE BEFORE WRITING
**Before writing ANY code, you MUST first read and understand the existing codebase.** This applies to every agent that creates or modifies code. Specifically:

1. **Read existing files first** — before creating a new file, read similar existing files to understand patterns
2. **Reuse existing classes, methods, utilities** — search for existing implementations before writing new ones. Do NOT duplicate functionality that already exists.
3. **Match naming conventions** — variable names, function names, class names, file names must follow the project's existing conventions (camelCase, snake_case, PascalCase, etc.)
4. **Match code style** — indentation (tabs vs spaces), bracket placement, quote style (single vs double), semicolons, line length
5. **Match architecture patterns** — where things are placed (controllers/, services/, utils/), how imports are structured, how errors are handled, how logging is done
6. **Match existing API patterns** — if the project uses a specific response format, error format, or middleware pattern, follow it exactly
7. **Use existing dependencies** — do NOT add new packages if an existing dependency can do the job
8. **Follow existing test patterns** — if tests use a specific setup/teardown pattern, mocking approach, or assertion style, match it
9. **Read configuration files** — understand the project's build config, linting rules, TypeScript settings, etc.

**When spawning sub-agents**, include this instruction in their prompt:
> "Before writing any code, read at least 3-5 existing files in the area you are working on. Identify: naming conventions, code style, architecture patterns, existing utilities you can reuse, and how similar features are implemented. Your code MUST look like it was written by the same developer who wrote the existing code."

### MANDATORY STATUS REPORTING
**Print a status line before EVERY major step.** Format:
```
[{Agent_Name}] {what is happening now}
```
The user must see what you are doing in real time. Print status BEFORE starting each step, not after. When spawning sub-agents, include this instruction in their prompt so they also report status with their agent name (e.g., [Security Auditor], [Frontend Developer], [Backend Developer], [Code Analyst], [Test Engineer], [UI Designer], [Documentation Lead]).


## Rules
- ALWAYS use the Agent tool to spawn sub-agents — never do the work inline
- Launch independent agents in PARALLEL (Security + Quality, Build while writing report)
- Each agent gets a COMPLETE prompt — they have no memory of other agents
- Pass findings between agents explicitly via the report files
- The loop MUST continue until verification finds zero issues
- Track round numbers and total findings across rounds
- If an agent fails, note it and continue with others
- ALL docker commands must run in the `demo-api/` directory

## Final Output
After everything completes, provide a summary:
- Pipeline result: PASSED / FAILED
- Rounds in Phase 1
- Docker build/deploy status
- Integration test pass rate
- Link to master report: `reports/master-report.html`
- How to access the running API: `http://localhost:3000`
- How to tear down: run `/docker-teardown`
