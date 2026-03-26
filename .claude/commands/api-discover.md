# API Endpoint Discovery & Documentation

You are a **Senior API Architect**. Your job is to discover all API endpoints hosted on a domain by scanning the organization's source code, then generate a Swagger-like HTML documentation page.

**Arguments:** $ARGUMENTS

---

## PHASE 0: Parse Arguments

### Argument Patterns

| Pattern | Mode | Example |
|---|---|---|
| `{endpoint_url}` | **Discover from URL** — extract domain pattern, find matching repos, scan for all endpoints | `/api-discover https://orderslip.api.24sevenoffice.com/orderslips/33/lines` |
| `{domain_pattern}` | **Discover from pattern** — scan repos matching a domain wildcard | `/api-discover *.api.24sevenoffice.com` |
| `{endpoint_url} --org {url}` | **Scan GitHub org** — search org repos for the domain | `/api-discover https://crm.api.example.com/contacts --org https://github.com/nexum-fo` |
| `{endpoint_url} --local-scan {path}` | **Scan local repos** — find repos on disk hosting this domain | `/api-discover https://api.example.com/users --local-scan D:\Projects` |
| `{endpoint_url} --repo {path}` | **Single repo** — scan one specific repo for all endpoints | `/api-discover https://api.example.com --repo D:\Projects\my-api` |
| `--report {html_path}` | **View mode** — re-open a previously generated report | `/api-discover --report reports/api-docs-crm.html` |

**Route:**
- If `--report` is present → Open the HTML file in browser and stop
- Otherwise → Continue to PHASE 1

Extract:
- `{ENDPOINT_URL}` — the API endpoint URL or domain pattern
- `--org {url}` — GitHub org URL (triggers org scan via GitHub API)
- `--local-scan {path}` — path to scan for local repos
- `--repo {path}` — single repo path
- `--gh-user {account}` — use a specific GitHub account
- `--search {text}` — additional search filter for repo names/READMEs
- `--include-private` — include private/internal endpoints (not just public)
- `--output {path}` — custom output path for the report

### Step 0.1 — Extract Domain Pattern

From the provided URL, extract the domain pattern:

```bash
python -c "
from urllib.parse import urlparse
url = '{ENDPOINT_URL}'
if '://' not in url and '*' in url:
    # It's already a pattern like *.api.24sevenoffice.com
    print('PATTERN:' + url)
else:
    parsed = urlparse(url if '://' in url else 'https://' + url)
    host = parsed.hostname or url
    # Extract the base domain pattern
    parts = host.split('.')
    if len(parts) >= 3:
        # e.g., orderslip.api.24sevenoffice.com → *.api.24sevenoffice.com
        base = '.'.join(parts[1:])
        print('PATTERN:*.' + base)
        print('SPECIFIC:' + host)
    else:
        print('PATTERN:' + host)
        print('SPECIFIC:' + host)
    print('PATH:' + parsed.path)
"
```

Store:
- `{DOMAIN_PATTERN}` — the wildcard pattern (e.g., `*.api.24sevenoffice.com`)
- `{SPECIFIC_HOST}` — the exact host from the URL (e.g., `orderslip.api.24sevenoffice.com`)
- `{SAMPLE_PATH}` — the path from the URL (e.g., `/orderslips/33/lines`)

Announce:
```
[API Discovery] Scanning for endpoints matching: {DOMAIN_PATTERN}
[API Discovery] Starting from: {SPECIFIC_HOST}{SAMPLE_PATH}
```

---

## PHASE 1: Find Repositories

### Step 1.1 — Discover Repos Hosting This Domain

**If `--repo` was provided:** Use that single repo. Skip to PHASE 2.

**If `--local-scan` was provided:**
```bash
find "{LOCAL_SCAN_PATH}" -maxdepth 3 \( -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.ts" -o -name "*.js" -o -name "*.java" -o -name "*.cs" -o -name "*.go" -o -name "*.py" -o -name "*.env*" -o -name "*.config*" \) -exec grep -li "{DOMAIN_PATTERN_BASE}" {} \; 2>/dev/null | head -50
```

Where `{DOMAIN_PATTERN_BASE}` is the non-wildcard part (e.g., `api.24sevenoffice.com`).

Also search for the specific subdomain:
```bash
find "{LOCAL_SCAN_PATH}" -maxdepth 3 \( -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.env*" -o -name "docker-compose*" -o -name "*.config*" \) -exec grep -li "{SPECIFIC_HOST}" {} \; 2>/dev/null | head -30
```

Group results by repo root (the parent directory containing .git/):
```bash
for f in {matched_files}; do
  dir=$(dirname "$f")
  while [ "$dir" != "/" ] && [ ! -d "$dir/.git" ]; do dir=$(dirname "$dir"); done
  [ -d "$dir/.git" ] && echo "$dir"
done | sort -u
```

**If `--org` was provided:**
```bash
gh api orgs/{ORG_NAME}/repos --paginate --jq '.[].full_name' | head -100
```

Then for each repo, check if it references the domain:
```bash
gh api search/code -X GET -f "q={DOMAIN_PATTERN_BASE}+org:{ORG_NAME}" --jq '.items[].repository.full_name' | sort -u
```

**If no source specified:** Try local scan at common paths, then fall back to asking the user.

### Step 1.2 — Present Discovered Repos

```
[API Discovery] Found {count} repositories referencing {DOMAIN_PATTERN}:

| # | Repository | Path/URL | Relevance |
|---|-----------|----------|-----------|
| 1 | api-orderslip | D:\Projects\api-orderslip | Direct: hosts orderslip.api.* |
| 2 | api-gateway | D:\Projects\api-gateway | Gateway: routes to *.api.* |
| 3 | api-crm-2 | D:\Projects\api-crm-2 | Direct: hosts crm.api.* |
```

Ask the user:
> "I found {count} repos that reference {DOMAIN_PATTERN}. Scan all of them for endpoints?"

Options:
1. **Scan all** — Check every repo
2. **Select specific** — I'll pick which ones
3. **Add more** — I know other repos that should be included

---

## PHASE 2: Deep Scan for API Endpoints

### Step 2.1 — Detect API Framework Per Repo

For each repo, detect what API framework is used:

```bash
# Check for common API frameworks
ls "{REPO_PATH}/pom.xml" 2>/dev/null && echo "JAVA_MAVEN"
ls "{REPO_PATH}/build.gradle"* 2>/dev/null && echo "JAVA_GRADLE"
ls "{REPO_PATH}/"*.csproj 2>/dev/null && echo "DOTNET"
ls "{REPO_PATH}/package.json" 2>/dev/null && echo "NODE"
ls "{REPO_PATH}/go.mod" 2>/dev/null && echo "GO"
ls "{REPO_PATH}/requirements.txt" "{REPO_PATH}/pyproject.toml" 2>/dev/null && echo "PYTHON"
```

Also look for OpenAPI/Swagger specs:
```bash
find "{REPO_PATH}" -maxdepth 4 \( -name "swagger*" -o -name "openapi*" -o -name "*.swagger.*" -o -name "*.openapi.*" \) -type f 2>/dev/null
```

And look for route definitions:
```bash
# Express.js routes
grep -rn "router\.\(get\|post\|put\|patch\|delete\)\|app\.\(get\|post\|put\|patch\|delete\)" "{REPO_PATH}/src" --include="*.ts" --include="*.js" 2>/dev/null | head -50

# Spring Boot
grep -rn "@\(GetMapping\|PostMapping\|PutMapping\|PatchMapping\|DeleteMapping\|RequestMapping\)" "{REPO_PATH}/src" --include="*.java" 2>/dev/null | head -50

# ASP.NET
grep -rn "\[Http\(Get\|Post\|Put\|Patch\|Delete\)\]\|\[Route\(" "{REPO_PATH}" --include="*.cs" 2>/dev/null | head -50

# Go (net/http, gin, echo, chi)
grep -rn "\.GET\|\.POST\|\.PUT\|\.PATCH\|\.DELETE\|HandleFunc\|r\.Route\|e\.GET\|e\.POST" "{REPO_PATH}" --include="*.go" 2>/dev/null | head -50

# Python (Flask, FastAPI, Django)
grep -rn "@app\.\(get\|post\|put\|patch\|delete\)\|@router\.\|path(\|re_path(" "{REPO_PATH}" --include="*.py" 2>/dev/null | head -50

# OpenAPI YAML specs
grep -rn "paths:" "{REPO_PATH}" --include="*.yml" --include="*.yaml" 2>/dev/null | head -20
```

### Step 2.2 — Extract Endpoints (Per Repo)

Launch an **Explore agent** per repo (up to 3 in parallel):

> You are an **API Endpoint Extractor**. Scan the repository at `{REPO_PATH}` and extract every HTTP API endpoint.
>
> ## What to Find
>
> For EACH endpoint, extract:
> 1. **HTTP Method** — GET, POST, PUT, PATCH, DELETE
> 2. **Path** — the URL path (e.g., `/orderslips/{id}/lines/{lineId}`)
> 3. **Full URL** — if discoverable from config (e.g., `orderslip.api.24sevenoffice.com/orderslips/...`)
> 4. **Handler** — file path and function/method name that handles this endpoint
> 5. **Request Schema** — request body type/interface/DTO (if POST/PUT/PATCH)
> 6. **Response Schema** — response type/interface/DTO
> 7. **Path Parameters** — list of path params with types
> 8. **Query Parameters** — list of query params with types and descriptions
> 9. **Headers** — any custom required headers
> 10. **Auth** — what authentication is required (JWT, API key, OAuth, none)
> 11. **Description** — from comments, JSDoc, Swagger annotations, or method name
> 12. **Status Codes** — documented or inferable response codes
> 13. **Tags/Groups** — controller name, route group, or API version
>
> ## Where to Look
>
> **Priority order:**
> 1. **OpenAPI/Swagger specs** (`.yml`, `.yaml`, `.json`) — most authoritative, parse these first
> 2. **Route definitions** — controllers, routers, route files
> 3. **Middleware** — auth middleware, validation middleware (tells you about required headers/auth)
> 4. **DTO/Model files** — request/response types
> 5. **Config files** — domain mappings, base URLs, API versioning
> 6. **Test files** — often reveal endpoints, expected payloads, and response shapes
>
> ## For Request/Response Schemas
> - Follow the type chain: route handler → service method → DTO/interface/model
> - Extract ALL fields with types, required/optional, descriptions if annotated
> - Include nested objects and arrays with their full structure
> - If TypeScript/Java/C#/Go: extract from type definitions
> - If Python: extract from Pydantic models, dataclasses, or type hints
> - If OpenAPI spec: extract directly from the schema definitions
>
> ## Output
> Write results to `reports/api-endpoints-{repo_name}.json` using this structure:
> ```json
> {
>   "repo": "{repo_name}",
>   "path": "{REPO_PATH}",
>   "framework": "{detected_framework}",
>   "baseUrl": "{detected_base_url_or_null}",
>   "domain": "{subdomain}.api.24sevenoffice.com",
>   "apiVersion": "{v1, v2, etc or null}",
>   "auth": { "type": "JWT|ApiKey|OAuth|None", "details": "..." },
>   "endpoints": [
>     {
>       "method": "GET",
>       "path": "/orderslips/{id}",
>       "fullUrl": "https://orderslip.api.24sevenoffice.com/orderslips/{id}",
>       "handler": { "file": "src/controllers/OrderSlipController.ts", "function": "getById", "line": 42 },
>       "description": "Get a single order slip by ID",
>       "tags": ["OrderSlips"],
>       "auth": "Required (JWT)",
>       "pathParams": [{ "name": "id", "type": "number", "description": "Order slip ID" }],
>       "queryParams": [{ "name": "include", "type": "string", "required": false, "description": "Comma-separated relations to include" }],
>       "requestBody": null,
>       "responseBody": {
>         "type": "OrderSlipDto",
>         "schema": {
>           "id": { "type": "number", "description": "Unique identifier" },
>           "customerId": { "type": "number" },
>           "lines": { "type": "OrderSlipLineDto[]", "description": "Order lines" }
>         }
>       },
>       "statusCodes": [
>         { "code": 200, "description": "Success" },
>         { "code": 404, "description": "Order slip not found" }
>       ]
>     }
>   ]
> }
> ```

### Step 2.3 — Scan for Gateway/Proxy Routes

If a gateway or proxy repo was found, extract its route mappings to understand which subdomains route to which backend services:

```bash
# Look for proxy/gateway config
find "{GATEWAY_REPO}" -name "*.yml" -o -name "*.yaml" -o -name "*.json" -o -name "*.ts" -o -name "*.js" | xargs grep -l "proxy\|upstream\|target\|service\|route" 2>/dev/null | head -10
```

This gives context: `orderslip.api.* → api-orderslip service`, `crm.api.* → api-crm-2 service`, etc.

---

## PHASE 3: Compile & Generate Documentation

### Step 3.1 — Merge All Endpoint Data

Read all `reports/api-endpoints-*.json` files and merge them into a unified API map:

```bash
python -c "
import json, glob, os

all_endpoints = []
repos = []

for f in sorted(glob.glob('reports/api-endpoints-*.json')):
    with open(f) as fh:
        data = json.load(fh)
    repos.append({
        'name': data['repo'],
        'framework': data['framework'],
        'baseUrl': data.get('baseUrl'),
        'domain': data.get('domain'),
        'endpointCount': len(data['endpoints'])
    })
    for ep in data['endpoints']:
        ep['_repo'] = data['repo']
        ep['_domain'] = data.get('domain', '')
        all_endpoints.append(ep)

# Group by domain/subdomain
domains = {}
for ep in all_endpoints:
    domain = ep.get('_domain', 'unknown')
    if domain not in domains:
        domains[domain] = []
    domains[domain].append(ep)

# Group by tag within each domain
for domain in domains:
    tags = {}
    for ep in domains[domain]:
        for tag in ep.get('tags', ['Untagged']):
            if tag not in tags:
                tags[tag] = []
            tags[tag].append(ep)
    domains[domain] = tags

summary = {
    'repos': repos,
    'totalEndpoints': len(all_endpoints),
    'domains': {d: {t: len(eps) for t, eps in tags.items()} for d, tags in domains.items()}
}

with open('reports/api-discovery-summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(json.dumps(summary, indent=2))
"
```

### Step 3.2 — Generate Swagger-Style HTML

Launch a **backend-developer agent** to generate the HTML:

> You are a **Technical Documentation Engineer**. Generate a Swagger-like interactive HTML documentation page from the endpoint data.
>
> ## Input
> Read all files matching `reports/api-endpoints-*.json` to get the endpoint data.
>
> ## HTML Design Requirements
>
> The output should look and feel like **Swagger UI** but with a cleaner, modern design:
>
> ### Layout
> - **Fixed top header:** Domain pattern, total endpoints count, generated date
> - **Left sidebar (280px):** Grouped navigation by domain → tag/controller → endpoints. Each endpoint shows method badge + path. Collapsible groups. Search/filter box at top.
> - **Main content area:** Endpoint detail cards
>
> ### Per Endpoint Card
> Each endpoint should be an expandable card (collapsed by default) showing:
>
> **Collapsed view (one line):**
> ```
> [GET] /orderslips/{id}    Get a single order slip    api-orderslip
> ```
> - Method badge: GET=green, POST=blue, PUT=amber, PATCH=purple, DELETE=red
> - Path with param highlights
> - Description (truncated)
> - Source repo badge
>
> **Expanded view (click to expand):**
> - Full description
> - **Source:** repo name, file path, line number
> - **Authentication:** type + details
> - **Path Parameters:** table with name, type, required, description
> - **Query Parameters:** table with name, type, required, default, description
> - **Request Headers:** table (if any custom headers)
> - **Request Body:** (for POST/PUT/PATCH)
>   - Content-Type
>   - Schema displayed as a syntax-highlighted JSON example with field descriptions
>   - "Copy as cURL" button (generates a cURL command)
> - **Response:** (per status code)
>   - Status code badge (200=green, 4xx=amber, 5xx=red)
>   - Description
>   - Response body schema as syntax-highlighted JSON example
> - **Try It** section (optional): pre-filled request with editable fields (purely client-side, generates cURL)
>
> ### Grouping
> - Group endpoints by **domain** first (e.g., `orderslip.api.24sevenoffice.com`, `crm.api.24sevenoffice.com`)
> - Within each domain, group by **tag/controller** (e.g., "OrderSlips", "Lines", "Contacts")
> - Each group is collapsible with endpoint count badge
>
> ### Search & Filter
> - Filter box in sidebar: filters endpoints by path, method, description, tag
> - Method filter toggles: [GET] [POST] [PUT] [PATCH] [DELETE] — click to show/hide
> - Domain filter: dropdown or toggle pills for each discovered domain
>
> ### Styling
> - Clean light theme (white background, subtle borders)
> - Method colors: GET=#22c55e, POST=#3b82f6, PUT=#f59e0b, PATCH=#7c3aed, DELETE=#ef4444
> - Monospace code blocks with syntax highlighting (JSON)
> - Responsive layout (sidebar collapses on mobile)
> - Print-friendly
> - Sticky header
>
> ### Additional Sections
> - **Overview** at top: domain map showing which subdomains exist and which repos serve them
> - **Authentication** section: describes auth methods found across all endpoints
> - **Models/Schemas** section at bottom: all unique DTOs/types referenced by endpoints, with full schema. Endpoint references link to these.
> - **Coverage Stats:** how many endpoints per domain, per method, per repo
>
> ## Output
> Write to `reports/api-docs-{domain_slug}.html` where `{domain_slug}` is derived from the base domain (e.g., `api-24sevenoffice-com`).
>
> The file must be self-contained (all CSS/JS inline) and work when opened directly in a browser.

### Step 3.3 — Auto-Open in Browser

```bash
start "" "reports/api-docs-{domain_slug}.html" 2>/dev/null || xdg-open "reports/api-docs-{domain_slug}.html" 2>/dev/null || open "reports/api-docs-{domain_slug}.html" 2>/dev/null || echo "Open manually: reports/api-docs-{domain_slug}.html"
```

---

## PHASE 4: Present Results

```
[API Discovery] Complete!

**Domain Pattern:** {DOMAIN_PATTERN}
**Repos Scanned:** {count}
**Endpoints Found:** {total_count}

| Domain | Endpoints | Repo | Framework |
|--------|-----------|------|-----------|
| orderslip.api.24sevenoffice.com | 12 | api-orderslip | Express.js |
| crm.api.24sevenoffice.com | 28 | api-crm-2 | Express.js |
| gateway.api.24sevenoffice.com | 45 | api-gateway | Node.js |

**Report:** reports/api-docs-{slug}.html (opened in browser)
**Endpoint data:** reports/api-endpoints-*.json (per repo)
```

Ask the user:
> "API documentation generated with {count} endpoints across {domain_count} domains. What would you like to do?"

Options:
1. **Done** — I have what I need
2. **Scan more repos** — I know other repos to include
3. **Export OpenAPI spec** — Generate a standard OpenAPI 3.0 YAML from the discovered endpoints
4. **Compare with live** — Test the discovered endpoints against the live API to check which are active

---

### MANDATORY — UNDERSTAND EXISTING CODE BEFORE WRITING
**Before writing ANY code, you MUST first read and understand the existing codebase.** This applies to every agent that creates or modifies code. Specifically:

1. **Read existing files first** — before creating a new file, read similar existing files to understand patterns
2. **Reuse existing classes, methods, utilities** — search for existing implementations before writing new ones
3. **Match naming conventions** — variable names, function names, class names, file names must follow the project's existing conventions
4. **Match code style** — indentation, bracket placement, quote style, semicolons, line length
5. **Match architecture patterns** — where things are placed, how imports are structured, how errors are handled

### MANDATORY STATUS REPORTING
**Print a status line before EVERY major step.** Format:
```
[{Agent_Name}] {what is happening now}
```
The user must see what you are doing in real time. Print status BEFORE starting each step, not after. When spawning sub-agents, include this instruction in their prompt so they also report status with their agent name (e.g., [API Extractor], [Doc Generator], [Gateway Scanner]).

## Rules

- **Never modify source code** — this command only reads and documents, never changes anything
- **Follow OpenAPI 3.0 conventions** for schema representation where possible
- **Include all endpoints** — don't skip internal/admin endpoints unless `--include-private` is not set and the endpoint is clearly marked internal
- **Schema depth** — follow type references up to 3 levels deep (avoid infinite recursion on circular references)
- **Large repos** — if a repo has 100+ endpoints, batch the extraction and paginate the HTML output
- **Auth detection** — always check for auth middleware/decorators/annotations to document auth requirements
- **Always auto-open** the HTML report in the browser when done
- **Always use `source .env`** (absolute path) when loading credentials for any API calls
- **Reports go to `reports/`** in the working directory where the command was invoked
