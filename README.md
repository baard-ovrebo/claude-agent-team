# Claude Agent Team

An AI development team built on [Claude Code](https://claude.ai/claude-code) — 26 slash commands that orchestrate specialized AI agents to manage Jira tickets, design UIs, implement features, fix bugs, review code, run tests, audit dependencies, sync branches, onboard repositories, generate changelogs, containerize, and deploy.

No framework. No SDK. No infrastructure. Just Markdown files that become executable pipelines.

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
| **Documentation Lead** | Compiles HTML reports |
| **Merge Conflict Resolver** | Analyzes and resolves Git conflicts |
| **Onboarding Engineer** | Analyzes repos and sets up dev environments |

## Commands

### Project Management
| Command | Description |
|---------|-------------|
| `/jira FO-2847` | Full ticket-to-resolution: fetch, analyze JAM recordings, classify, design, implement, review, report, update Jira |
| `/jira sprint` | Batch process sprint tickets — fetches Scrum teams dynamically, user picks team, processes each ticket |
| `/jira teams` | List all available Scrum teams from Jira |
| `/jira watch FO-2847` | Poll a ticket for new comments — auto-resumes pipeline when reporter replies |
| `/jira resume FO-2847` | Resume a paused ticket from a saved state file (new session) |
| `/jam {url}` | Analyze JAM bug recordings via MCP — video analysis, console logs, network requests, user events |
| `/tempo` | Log time to Jira (`/tempo addTime FO-2847 2h "Bug fix"`) |

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
| `/repo-setup {org} --auto-setup --search "control"` | Auto-setup only repos matching the search |
| `/repo-setup {url} --analyze-only` | Report only, don't install anything |
| `/repo-setup --local-scan D:\Projects` | Scan repos already on disk instead of cloning |

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
- Fetches full ticket details, downloads and resizes image attachments
- **Auto-detects JAM links** in tickets and analyzes bug recordings via MCP (video, console, network, user events)
- **Reads and analyzes comments** — extracts additional requirements, identifies unanswered questions
- **@mentions the reporter** on Jira if info is missing (posted as the authenticated user)
- **Watch mode** — polls for replies every 2 min, auto-resumes when the reporter answers, supports back-and-forth dialogue
- **State persistence** — saves pipeline state to JSON so you can resume from a new session
- **Git branch setup** — asks to create branches for all affected projects before implementation
- **Design in Paper** — creates mockups via MCP, user approval gate before any code is written
- **Parallel implementation** — Frontend + Backend agents work simultaneously

### Repository Onboarding
- **Single repo mode** — detects stack, installs deps, configures env, sets up DB, runs migrations, builds, tests, starts dev server
- **Organization scan** — fetches all repos via GitHub API, analyzes each, maps inter-repo relationships (depends-on, frontend-for, shares-data, shared-library, gateway, deploys-with)
- **Architecture diagram** — CSS visual showing repos as color-coded boxes with connection lines
- **Startup order** — calculates correct order based on dependency graph
- **GitHub account switching** — if current `gh` account can't access the org, lists all authenticated accounts and lets you pick
- **Dependent repo detection** — finds git submodules, Docker Compose refs, local package deps, .NET ProjectReferences, Maven modules
- **HTML setup guide** — 12-section document: prerequisites, quick start, step-by-step, env vars, commands, architecture, testing, troubleshooting

### Git Operations
- **Pre-flight checks** — uncommitted changes detection, stash option, branch existence verification
- **AI conflict resolution** — per-file analysis: both-needed, incoming-preferred, current-preferred, or needs-human-review
- **Lock file regeneration** — auto-regenerates package-lock.json, yarn.lock, poetry.lock, go.sum after merge
- **Multi-project sync** — syncs across frontend + backend repos simultaneously

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

4. **Configure MCP servers** (optional, for JAM + Paper):
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
| `/new-feature` (design phase) | Paper MCP server |
| `/unit-test`, `/deps`, `/dev-team` | Nothing extra — works standalone |
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

### Key Design Principles
- **Always ask for project paths** — never guess which codebase to work in
- **User approval gates** — plan and design must be approved before coding starts
- **Parallel where possible** — Security + Quality scan simultaneously, Frontend + Backend build simultaneously
- **Iterative loops** — scan → fix → re-scan until clean (not single-pass)
- **Stack-agnostic** — runtime detection adapts to Java, C#, JS, Python, Go, Rust, PHP, Ruby
- **State persistence** — paused pipelines can be resumed from new sessions
- **Always generate reports** — every pipeline produces an HTML report as an audit trail

## Documentation

- [Architecture Deep Dive](docs/agent-architecture-confluence.html) — full technical document explaining the system
- [Skills Reference](docs/skills-documentation.html) — detailed docs for every command
- [/new-feature Flow Diagram](docs/new-feature-diagram.html) — visual pipeline flow
- [/full-pipeline Flow Diagram](docs/full-pipeline-diagram.html) — visual pipeline flow
- [Competition Presentation](docs/ai-competition-presentation.html) — overview presentation

## Project Structure

```
.claude/
  commands/
    jira.md              # Jira ticket orchestrator (50KB+ — the biggest pipeline)
    new-feature.md       # Feature development pipeline
    repo-setup.md        # Repository onboarding & org scanner
    unit-test.md         # Unit test engineer
    deps.md              # Dependency health auditor
    git.md               # Git operations (sync, status, conflict resolution)
    dev-team.md          # Iterative quality loop
    full-pipeline.md     # End-to-end delivery
    jam.md               # JAM bug recording analyzer
    tempo.md             # Time tracking
    docker-build.md      # Docker build engineer
    docker-deploy.md     # Docker deploy engineer
    docker-test.md       # Docker integration tests
    docker-teardown.md   # Docker cleanup
    code-analysis.md     # Code change reviewer
    security-audit.md    # Security auditor
    quality-audit.md     # Quality engineer
    fix-all.md           # Backend developer (fix mode)
    test-all.md          # Test engineer
    master-report.md     # Report compiler
    new-feature.md       # Feature pipeline
    playwright-test.md   # E2E test engineer
docs/                    # HTML documentation and diagrams
reports/                 # Generated reports (gitignored)
.env.example             # Credential template
```

## License

MIT

## Author

Bård Øvrebø — Control Team, Finago
