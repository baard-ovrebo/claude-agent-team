# Claude Agent Team

An AI development team built on [Claude Code](https://claude.ai/claude-code) — 21 slash commands that orchestrate specialized AI agents to manage Jira tickets, design UIs, implement features, review code, run tests, audit dependencies, containerize, and deploy.

No framework. No SDK. No infrastructure. Just Markdown files that become executable pipelines.

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

## Commands

### Project Management
| Command | Description |
|---------|-------------|
| `/jira FO-2847` | Full ticket-to-resolution: fetch, analyze, design, implement, review, report, update Jira |
| `/jira sprint` | Batch process sprint tickets with team filtering |
| `/jira teams` | List available Scrum teams |
| `/jam {url}` | Analyze JAM bug recordings via MCP |
| `/tempo` | Log time to Jira (`/tempo addTime FO-2847 2h "Bug fix"`) |

### Feature Development
| Command | Description |
|---------|-------------|
| `/new-feature` | 6-phase pipeline: plan → screenshot → design in Paper → parallel implementation → code review → report |
| `/code-analysis` | Review only the git diff for security + quality issues |

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
| `/unit-test --fix-ignored` | Find and rehabilitate disabled/skipped tests |
| `/unit-test {file}` | Create tests for a specific file |
| `/playwright-test` | Run Playwright E2E browser tests |
| `/deps` | Dependency health audit: CVEs, outdated, licenses (grade A–F) |

### Docker Pipeline
| Command | Description |
|---------|-------------|
| `/docker-build` | Build + validate Docker image |
| `/docker-deploy` | Deploy with docker compose |
| `/docker-test` | Integration tests against live container |
| `/docker-teardown` | Graceful cleanup |
| `/full-pipeline` | All of the above: dev-team + Playwright + Docker + report |

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
    jira.md              # Jira ticket orchestrator (46KB — the biggest pipeline)
    new-feature.md       # Feature development pipeline
    unit-test.md         # Unit test engineer
    deps.md              # Dependency health auditor
    dev-team.md          # Iterative quality loop
    full-pipeline.md     # End-to-end delivery
    jam.md               # JAM bug recording analyzer
    tempo.md             # Time tracking
    ... (21 commands total)
docs/                    # HTML documentation and diagrams
reports/                 # Generated reports (gitignored)
.env.example             # Credential template
```

## License

MIT

## Author

Bård Øvrebø — Control Team, Finago
