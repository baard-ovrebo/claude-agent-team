# Claude Agent Team

An AI development team built on [Claude Code](https://claude.ai/claude-code) — 28 slash commands that orchestrate specialized AI agents to manage Jira tickets, design UIs, implement features, fix bugs, verify with Playwright, review code, run tests, audit dependencies, sync branches, onboard repositories, generate changelogs, containerize, and deploy.

No framework. No SDK. No infrastructure. Just Markdown files that become executable pipelines.

*Last updated: 2026-03-23*

> **[Full Command Reference Guide](https://baard-ovrebo.github.io/claude-agent-team/command-guide.html)** — comprehensive interactive documentation for every command with usage examples, flags, relationships, and architecture diagrams.
>
> Also available: [Architecture Deep Dive](https://baard-ovrebo.github.io/claude-agent-team/agent-architecture-confluence.html) | [Flow Diagrams](https://baard-ovrebo.github.io/claude-agent-team/new-feature-diagram.html) | [Skills Reference](https://baard-ovrebo.github.io/claude-agent-team/skills-documentation.html)

## What This Is

A collection of **custom Claude Code commands** (Markdown files in `.claude/commands/`) that turn Claude into a coordinated team of AI agents:

| Agent | Role |
|-------|------|
| **Orchestrator** | Plans work, asks user, coordinates agents |
| **UI Designer** | Creates mockups in Paper.design via MCP |
| **Frontend Developer** | Implements UI from approved designs |
| **Backend Developer** | Implements APIs, DB, middleware |
| **Security Auditor** | OWASP Top 10 vulnerability scanning |
| **Quality Engineer** | Code smells, anti-patterns, dead code |
| **Test Engineer** | Unit tests across 9 language stacks |
| **Code Analyst** | Git diff security + quality review |
| **E2E Verification Engineer** | Playwright verification with screenshots |
| **Documentation Lead** | Compiles HTML reports |
| **Merge Conflict Resolver** | Analyzes and resolves Git conflicts |
| **Onboarding Engineer** | Analyzes repos and sets up dev environments |

## Commands

### Project Management
| Command | Description |
|---------|-------------|
| `/jira FO-2847` | Full ticket-to-resolution: fetch, analyze JAM recordings, classify, design, implement, review, verify, report, update Jira |
| `/jira sprint` | Batch process sprint tickets — fetches Scrum teams dynamically, user picks team, processes each ticket |
| `/jira teams` | List all available Scrum teams from Jira |
| `/jira watch FO-2847` | Poll a ticket for new comments — auto-entered when pipeline posts a question, auto-resumes on reply |
| `/jira resume FO-2847` | Resume a paused ticket from a saved state file (new session) |
| `/jam {url}` | Analyze JAM bug recordings via MCP — video analysis, console logs, network requests, user events |
| `/tempo` | Log time to Jira (`/tempo addTime FO-2847 2h "Bug fix"`) |

### Universal (work in any project)
| Command | Description |
|---------|-------------|
| `/create "description"` | Context-aware feature creator: detects project type, designs in Paper, generates HTML plan, gets approval, implements, verifies with Playwright |
| `/bug "description"` | Context-aware bug fixer: analyzes screenshots, diagnoses root cause, fixes, verifies with Playwright |
| `/changelog` | Reads reports from `/create` and `/bug`, generates beautiful HTML changelog, moves to processed |
| `/create-project "description"` | Full project creator: questions → Paper design → HTML plan → build with full agent team → test → verify → deliver |
| `/report` | Analyze all branch changes, generate Jira-ready HTML report with QA testing instructions, optional upload to Jira ticket |
| `/report FO-2847` | Same + auto-upload report and screenshots to the specified Jira ticket |
| `/verify` | E2E verification with Playwright — uses project profile for login, takes before/after screenshots, generates HTML report with clickable lightbox |

### Feature Development
| Command | Description |
|---------|-------------|
| `/new-feature` | 6-phase pipeline: plan → screenshot → design in Paper → parallel implementation → code review → report |
| `/code-analysis` | Review only the git diff for security + quality issues, auto-fix critical problems |

### Code Quality (Iterative Loop)
| Command | Description |
|---------|-------------|
| `/dev-team` | Iterative: scan → fix → test → re-scan until zero findings |
| `/security-audit` | Standalone OWASP Top 10 scan |
| `/quality-audit` | Standalone code quality scan |
| `/fix-all` | Fix all findings from audit reports |
| `/test-all` | Write tests for all fixes |
| `/master-report` | Compile all reports into master HTML |

### Testing & Dependencies
| Command | Description |
|---------|-------------|
| `/unit-test *` | Full project test coverage scan + gap filling |
| `/unit-test --fix-ignored` | Find and rehabilitate disabled/skipped tests — user selects which to unignore and fix |
| `/unit-test {file}` | Create tests for a specific file or class |
| `/playwright-test` | Run Playwright E2E browser tests |
| `/deps` | Dependency health audit: CVEs (with exploitability check), outdated packages, license risks (grade A–F) |

### Git Operations
| Command | Description |
|---------|-------------|
| `/git sync develop` | Merge latest from a branch into current — pre-flight checks, fetch, merge |
| `/git sync develop --fix-merge-errors` | Same + auto-resolve conflicts with AI analysis per file |
| `/git sync develop --all` | Sync all projects in the project map |
| `/git status` | Quick branch overview: ahead/behind, uncommitted changes, stashes |

### Repository Onboarding
| Command | Description |
|---------|-------------|
| `/repo-setup {url}` | Clone a repo, analyze stack, install deps, configure env, build, test, start — produces HTML setup guide |
| `/repo-setup https://github.com/org` | Scan entire GitHub org — map all repos, relationships, architecture diagram, startup order |
| `/repo-setup {org} --auto-setup` | Auto-clone, install, build, test ALL repos without prompting |
| `/repo-setup {org} --search "API"` | Filter org repos by name, description, topics, or README content |
| `/repo-setup {url} --analyze-only` | Report only, don't install anything |
| `/repo-setup --local-scan D:\Projects` | Scan repos already on disk instead of cloning |
| `/impact-scan "description"` | Scan all org repos to find where a change needs to be implemented — per-repo file-level analysis |
| `/impact-scan "desc" --org {url}` | Same, targeting a specific GitHub org |
| `/impact-scan "desc" --local-scan {path}` | Same, scanning repos already on disk |

### Docker Pipeline
| Command | Description |
|---------|-------------|
| `/docker-build` | Build + validate Docker image |
| `/docker-deploy` | Deploy with docker compose |
| `/docker-test` | Integration tests against live container |
| `/docker-teardown` | Graceful cleanup |
| `/full-pipeline` | All of the above: dev-team + Playwright + Docker + report |

## Key Features

### Jira Pipeline — Ticket to Resolution
- Fetches full ticket details, downloads and **auto-resizes** image attachments
- **Auto-detects JAM links** in tickets and analyzes bug recordings via MCP
- **Reads and analyzes comments** — extracts additional requirements, identifies unanswered questions
- **@mentions the reporter** on Jira if info is missing, then **automatically enters watch loop** to wait for reply
- **Watch mode** — polls every 2 min, auto-resumes pipeline when reporter answers, supports back-and-forth dialogue
- **State persistence** — saves full pipeline state to JSON for cross-session resume
- **Git branch setup** — lists available branches, user picks base and names the new branch
- **Design in Paper** — creates mockups via MCP, user approval gate before any code is written
- **Parallel implementation** — Frontend + Backend agents work simultaneously
- **E2E verification** — auto-offers Playwright verification after implementation
- **Status reporting** — every agent prints `[Agent Name] what it's doing...` in real time

### Universal Commands — /create, /bug, /verify
- **Context-aware roles** — reads `ProjectType` from `.claude/.env` (GAME, APPLICATION, SAAS, API, MOBILE), adapts to Senior Unity Dev, Senior React Dev, etc.
- **HTML plan with Paper mockups** — `/create` generates `reports/feature-plan.html` with embedded design screenshots before implementing. User reviews in browser.
- **E2E verification** — after implementation, both `/create` and `/bug` auto-offer Playwright verification if the app is running
- **Project profile** — `/verify` builds `.claude/project-profile.json` on first run (login URL, selectors, test user). Reused for all future verifications.
- **Self-contained HTML reports** — all screenshots embedded as base64, clickable lightbox for full-size viewing
- **Changelog pipeline** — `/create` and `/bug` save timestamped reports → `/changelog` compiles them into a project-themed HTML changelog
- **Project design profile** — all HTML reports adapt their visual design to match the project. Design settings stored in `.claude/project-profile.json`. Auto-generated per ProjectType: dark neon for games, clean corporate for apps, terminal-style for APIs

### Repository Onboarding
- **Single repo mode** — detects stack, installs deps, configures env, sets up DB, runs migrations, builds, tests, starts dev server
- **Organization scan** — fetches all repos via GitHub API, analyzes each, maps inter-repo relationships
- **GitHub account switching** — lists all authenticated `gh` accounts, user picks which to use
- **Search filtering** — `--search "text"` filters repos by name, description, topics, README content
- **Auto-setup** — `--auto-setup` skips all prompts, processes everything in dependency order
- **Architecture diagram** — CSS visual showing repos as color-coded boxes with connection lines
- **HTML setup guide** — 12-section document with prerequisites, quick start, step-by-step, env vars, architecture, testing, troubleshooting

### Git Operations
- **Pre-flight checks** — uncommitted changes detection, stash option, branch existence verification
- **AI conflict resolution** — per-file analysis with confidence levels (high/medium/needs-human-review)
- **Lock file regeneration** — auto-regenerates package-lock.json, yarn.lock, poetry.lock, go.sum after merge
- **Multi-project sync** — syncs across frontend + backend repos simultaneously

### Reports & Screenshots
- All HTML reports include a **clickable screenshot lightbox** — click any image to view full-size
- Screenshots embedded as **base64** — reports are self-contained, work offline, sharable via email
- Reports are the **primary deliverable** — every command produces an HTML report as an audit trail

## Setup

### Prerequisites
- [Claude Code](https://claude.ai/claude-code) installed
- Claude Code model: Opus 4.6 recommended (Sonnet works for simpler commands)

### Installation

1. **Clone this repo** into your working directory:
   ```bash
   git clone https://github.com/baard-ovrebo/claude-agent-team.git
   ```

2. **Copy commands** to your project (or use globally):
   ```bash
   # Per-project: copy to your project's .claude/commands/
   cp -r claude-agent-team/.claude/commands/ /path/to/your/project/.claude/commands/

   # Global: copy to ~/.claude/commands/ (available everywhere)
   cp claude-agent-team/.claude/commands/*.md ~/.claude/commands/
   ```

3. **Configure credentials** (for Jira/Tempo commands):
   ```bash
   cp .env.example .env
   # Edit .env with your Jira credentials
   ```

4. **Configure project type** (for /create, /bug, /verify):
   ```bash
   # In your project's .claude/.env (or ~/.claude/.env for global):
   echo "ProjectType=APPLICATION" > .claude/.env
   # Values: GAME, APPLICATION, SAAS, API, MOBILE
   ```

5. **Configure MCP servers** (optional, for JAM + Paper):
   ```bash
   # JAM bug recording analysis
   claude mcp add jam -- npx @anthropic-ai/jam-mcp

   # Paper.design UI mockups (requires Paper Desktop running)
   claude mcp add paper --transport http http://127.0.0.1:29979/mcp --scope user
   ```

### Which Commands Need What

| Feature | Requires |
|---------|----------|
| `/jira`, `/tempo` | `.env` with Jira credentials |
| `/jam` | JAM MCP server |
| `/create`, `/new-feature` (design phase) | Paper MCP server (optional — skips design if unavailable) |
| `/verify` | Playwright + running application + `.claude/project-profile.json` (built on first run) |
| `/unit-test`, `/deps`, `/dev-team` | Nothing extra — works standalone |
| `/create`, `/bug`, `/changelog` | Nothing extra — works standalone (ProjectType in .env is optional) |
| `/git sync` | Git installed (works standalone) |
| `/repo-setup` | `gh` CLI for org scan, otherwise standalone |
| `/docker-*` | Docker Desktop |
| `/playwright-test` | Node.js + Playwright |

## How It Works

### The Core Pattern
Each command is a Markdown file that describes a multi-phase pipeline. Claude reads the Markdown and executes it — spawning specialized sub-agents, coordinating their work through report files, and gating on user approval before expensive operations.

### Agent Communication
Agents don't talk to each other directly. They communicate through `reports/*.md` files:
1. Security Auditor writes → `reports/security-audit.md`
2. Orchestrator reads it, passes to Backend Developer
3. Backend Developer fixes issues, writes → `reports/fixes-applied.md`
4. Orchestrator reads it, passes to Test Engineer
5. And so on...

### Real-Time Status Reporting
Every agent prints status lines before each major step:
```
[Orchestrator] Step 1/5 — Fetching ticket FO-2847 from Jira...
[Frontend Developer] Creating component: InvoiceExport.tsx...
[Backend Developer] Creating endpoint: POST /api/invoices/export...
[Code Analyst] Reviewing git diff (4 files changed)...
[Verify] Step 3/10: Checking URL field exists — PASS
```

### Key Design Principles
- **Always ask for project paths** — never guess which codebase to work in
- **User approval gates** — plan and design must be approved before coding starts
- **Parallel where possible** — Security + Quality scan simultaneously, Frontend + Backend build simultaneously
- **Iterative loops** — scan → fix → re-scan until clean (not single-pass)
- **Stack-agnostic** — runtime detection adapts to Java, C#, JS, Python, Go, Rust, PHP, Ruby
- **State persistence** — paused pipelines can be resumed from new sessions
- **Always generate reports** — every pipeline produces an HTML report as an audit trail
- **Clickable screenshots** — all HTML reports include a lightbox for full-size image viewing
- **Mandatory phase execution** — commands enforce "DO NOT SKIP" rules for critical phases

## Documentation

- [Command Reference Guide](https://baard-ovrebo.github.io/claude-agent-team/command-guide.html) — interactive searchable docs for all 25 commands
- [Architecture Deep Dive](https://baard-ovrebo.github.io/claude-agent-team/agent-architecture-confluence.html) — full technical document
- [/new-feature Flow Diagram](https://baard-ovrebo.github.io/claude-agent-team/new-feature-diagram.html) — visual pipeline flow
- [/full-pipeline Flow Diagram](https://baard-ovrebo.github.io/claude-agent-team/full-pipeline-diagram.html) — visual pipeline flow
- [Skills Reference](https://baard-ovrebo.github.io/claude-agent-team/skills-documentation.html) — detailed skills docs
- [Competition Presentation](https://baard-ovrebo.github.io/claude-agent-team/ai-competition-presentation.html) — overview presentation

## Project Structure

```
.claude/
  commands/
    jira.md              # Jira ticket orchestrator (the biggest pipeline)
    new-feature.md       # Feature development pipeline
    create.md            # Universal feature creator (role-adaptive)
    create-project.md    # Full project creator (idea to running app)
    bug.md               # Universal bug fixer (role-adaptive)
    verify.md            # E2E Playwright verification with project profile
    report.md            # Branch change report with QA test cases + Jira upload
    impact-scan.md       # Cross-repo impact analysis for change requests
    changelog.md         # Changelog generator from /create and /bug reports
    repo-setup.md        # Repository onboarding & org scanner
    unit-test.md         # Unit test engineer (9 stacks, --fix-ignored)
    deps.md              # Dependency health auditor (A-F grading)
    git.md               # Git operations (sync, conflict resolution)
    dev-team.md          # Iterative quality loop (5 agents)
    full-pipeline.md     # End-to-end delivery pipeline
    jam.md               # JAM bug recording analyzer (MCP)
    tempo.md             # Jira time tracking
    code-analysis.md     # Git diff code reviewer
    security-audit.md    # OWASP Top 10 scanner
    quality-audit.md     # Code quality scanner
    fix-all.md           # Automated issue fixer
    test-all.md          # Test writer + runner
    master-report.md     # HTML report compiler
    playwright-test.md   # E2E browser test runner
    docker-build.md      # Docker image builder
    docker-deploy.md     # Docker deployment
    docker-test.md       # Container integration tests
    docker-teardown.md   # Docker cleanup
docs/                    # HTML documentation, diagrams, command guide
reports/                 # Generated reports (gitignored)
.env.example             # Credential template
```

## License

MIT

## Author

Bård Øvrebø — Control Team, Finago
