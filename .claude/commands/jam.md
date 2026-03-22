# JAM Session Analyzer

Analyze JAM (jam.dev) recordings to understand bugs, issues, and feature requests captured in video sessions.

**Arguments:** $ARGUMENTS

---

## Step 1 — Parse the JAM Reference

The argument can be:
- A full JAM URL: `https://jam.dev/c/abc123`
- A JAM ID: `abc123`
- A Jira ticket key: `FO-2847` (will search the ticket for JAM links)

**If it's a Jira ticket key** (matches pattern like `FO-1234`, `PROJ-567`):
1. Fetch the Jira ticket to find JAM links:
```bash
source .env && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" "${JIRA_BASE_URL}/rest/api/3/issue/{TICKET_KEY}" | python -c "
import json, sys, re
data = json.load(sys.stdin)
# Search description and comments for JAM URLs
def extract_text(node):
    t = ''
    if isinstance(node, dict):
        if node.get('type') == 'text':
            t += node.get('text', '')
        for c in node.get('content', []):
            t += extract_text(c)
    return t

texts = []
desc = data.get('fields', {}).get('description')
if desc:
    texts.append(extract_text(desc))
for c in data.get('fields', {}).get('comment', {}).get('comments', []):
    if c.get('body'):
        texts.append(extract_text(c['body']))

all_text = ' '.join(texts)
urls = re.findall(r'https?://jam\.dev/c/[\w-]+', all_text)
if urls:
    for u in urls:
        print(u)
else:
    print('NO_JAM_LINKS_FOUND')
"
```

If no JAM links found, inform the user and stop.

**If it's a URL or ID**, construct the full URL: `https://jam.dev/c/{id}`

## Step 2 — Fetch JAM Session Data

Try multiple approaches to get the JAM data:

**Approach A: Jam MCP tools (if available)**
Check if `mcp__Jam__*` tools are available. If so, use them to fetch the JAM session details.

**Approach B: Use the jam-issue-resolver agent**
Launch a `jam-issue-resolver` agent using the Agent tool with `subagent_type: "jam-issue-resolver"`:

> Analyze this JAM recording: {JAM_URL}
>
> Extract and report:
> 1. What is the bug/issue/feature being shown?
> 2. What steps does the user take in the recording?
> 3. What is the expected behavior vs actual behavior?
> 4. What error messages or visual glitches are visible?
> 5. What pages/components/URLs are involved?
> 6. What browser/device info is available?
>
> Write your analysis to `reports/jam-analysis.md`

**Approach C: WebFetch fallback**
If the above approaches don't work, use WebFetch to analyze the JAM page:

```
WebFetch URL: {JAM_URL}
Prompt: "Analyze this JAM bug recording page. Extract: the bug description, steps to reproduce, expected vs actual behavior, any error messages, console logs, network requests, browser info, and screenshots/frames from the recording. Be as detailed as possible."
```

## Step 3 — Present Analysis

Present the JAM analysis to the user:

```
## JAM Analysis: {JAM_URL}

### Bug/Issue Summary
{one-paragraph summary}

### Steps to Reproduce
1. {step}
2. {step}
3. {step}

### Expected Behavior
{what should happen}

### Actual Behavior
{what actually happens}

### Error Details
- Console errors: {if any}
- Network failures: {if any}
- Visual glitches: {description}

### Environment
- Browser: {detected}
- OS: {detected}
- Page URL: {the URL in the recording}

### Affected Components
- {list of UI components/pages involved}
- {relevant file paths if identifiable}

### Suggested Fix
{brief technical suggestion based on the analysis}
```

## Step 4 — Ask What to Do Next

Ask using `AskUserQuestion`:

> "JAM analysis complete. What would you like to do?"

Options:
1. **Create Jira ticket** — Create a new ticket with this analysis pre-filled
2. **Link to existing ticket** — Add this analysis as a comment on an existing Jira ticket
3. **Fix it now** — Start implementing a fix based on this analysis (will run the /jira pipeline)
4. **Just the analysis** — Done, I only needed the analysis

**If "Create Jira ticket":**
```bash
source .env && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  "${JIRA_BASE_URL}/rest/api/3/issue" \
  -d '{
    "fields": {
      "project": {"key": "FO"},
      "summary": "{bug_summary}",
      "description": {
        "type": "doc",
        "version": 1,
        "content": [
          {"type": "paragraph", "content": [{"type": "text", "text": "JAM Recording: {JAM_URL}", "marks": [{"type": "link", "attrs": {"href": "{JAM_URL}"}}]}]},
          {"type": "paragraph", "content": [{"type": "text", "text": "{formatted_analysis}"}]}
        ]
      },
      "issuetype": {"name": "DevBug"}
    }
  }'
```

**If "Link to existing ticket":**
Ask for the ticket key, then post the analysis as a comment.

**If "Fix it now":**
Proceed to run the full `/jira` pipeline with the analysis as context.

---

### MANDATORY STATUS REPORTING
**Print a status line before EVERY major step.** Format:
```
[{Agent_Name}] {what is happening now}
```
The user must see what you are doing in real time. Print status BEFORE starting each step, not after. When spawning sub-agents, include this instruction in their prompt so they also report status with their agent name (e.g., [Security Auditor], [Frontend Developer], [Backend Developer], [Code Analyst], [Test Engineer], [UI Designer], [Documentation Lead]).


## Rules
- Always use `source .env` for credentials
- Try Jam MCP tools first, then jam-issue-resolver agent, then WebFetch as fallback
- The JAM token is stored in `.env` as `JAM_API_TOKEN`
- Keep the analysis structured and actionable
- If the JAM recording shows a clear bug, suggest specific files/code that might need fixing
