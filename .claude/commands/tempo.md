# Tempo — Jira Time Tracking

Quick time tracking for Jira tickets without opening the browser.

**Arguments:** $ARGUMENTS

---

## Parse the Command

The arguments follow this format:

**addTime**: `/tempo addTime {TICKET} {START_TIME} {END_TIME} "{DESCRIPTION}"`
- Example: `/tempo addTime FO-2872 14:00 16:00 "Implemented invoice reference fix"`
- Example: `/tempo addTime FO-2872 09:30 11:00 "Code review and testing"`
- Example: `/tempo addTime FO-2872 2h "Quick bug fix"` (shorthand — logs 2h starting now)
- Example: `/tempo addTime FO-2872 45m "Standup and planning"` (shorthand — logs 45m starting now)

**getTime**: `/tempo getTime {TICKET}`
- Example: `/tempo getTime FO-2872`

Parse the arguments to determine which action to take.

---

## Action: addTime

### Step 1 — Parse Arguments

Extract from the arguments:
- **TICKET**: The Jira ticket key (e.g., FO-2872)
- **START_TIME**: Either a time like "14:00" or a duration like "2h", "45m", "1h30m"
- **END_TIME**: A time like "16:00" (only present if START_TIME is a clock time)
- **DESCRIPTION**: The quoted text at the end

**If START_TIME and END_TIME are clock times (HH:MM format):**
- Calculate duration in seconds: (END_TIME - START_TIME) in seconds
- Use today's date combined with START_TIME as the "started" timestamp
- Format started as ISO 8601: `YYYY-MM-DDTHH:MM:00.000+0100` (use Europe/Berlin timezone +0100 or +0200 depending on DST)

**If START_TIME is a duration (e.g., "2h", "45m", "1h30m"):**
- Parse the duration into seconds (1h = 3600s, 1m = 60s)
- Use current time minus the duration as the "started" timestamp
- No END_TIME expected

### Step 2 — Determine Timezone Offset

Get the current timezone offset:
```bash
date +%z
```

### Step 3 — Post Worklog

```bash
source .env && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  "${JIRA_BASE_URL}/rest/api/3/issue/{TICKET}/worklog" \
  -d '{
    "timeSpentSeconds": {duration_in_seconds},
    "started": "{started_iso_timestamp}",
    "comment": {
      "type": "doc",
      "version": 1,
      "content": [
        {
          "type": "paragraph",
          "content": [
            {
              "type": "text",
              "text": "{DESCRIPTION}"
            }
          ]
        }
      ]
    }
  }'
```

### Step 4 — Confirm

Parse the response and present a clean confirmation:

```
Time logged on {TICKET}:
  Date:     {today's date}
  Time:     {START_TIME} — {END_TIME}
  Duration: {hours}h {minutes}m
  Comment:  {DESCRIPTION}
```

If the API returns an error, show the error message clearly.

---

## Action: getTime

### Step 1 — Fetch Worklogs

```bash
source .env && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  "${JIRA_BASE_URL}/rest/api/3/issue/{TICKET}/worklog"
```

### Step 2 — Also Fetch Ticket Summary

```bash
source .env && curl -s -u "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  "${JIRA_BASE_URL}/rest/api/3/issue/{TICKET}?fields=summary,timetracking"
```

### Step 3 — Format and Display

Parse the worklog entries and present them in a clean table:

```
## Time Tracking: {TICKET}
**{Ticket Summary}**

### Logged Time

| Date       | Day | Start | End   | Duration | Author         | Description              |
|------------|-----|-------|-------|----------|----------------|--------------------------|
| 2026-03-18 | Wed | 14:00 | 16:00 | 2h 0m    | Bård Øvrebø    | Implemented invoice fix  |
| 2026-03-17 | Tue | 09:00 | 10:30 | 1h 30m   | Bård Øvrebø    | Code review              |

### Summary
- **Total logged:** {sum of all hours}h {minutes}m
- **Estimated:** {original estimate from timetracking field, or "Not set"}
- **Remaining:** {remaining estimate from timetracking field, or "Not set"}
- **Entries:** {count}
```

For each worklog entry, extract:
- `started` — parse to get date, day of week, and start time
- `timeSpentSeconds` — convert to hours and minutes, calculate end time from started + duration
- `author.displayName` — who logged it
- `comment` — parse the Atlassian Document Format to get plain text

Sort entries by date (newest first).

Parse the `started` field (ISO 8601 format like `2026-03-18T14:00:00.000+0100`) using Python:
```bash
python -c "
import json, sys
from datetime import datetime, timedelta

with sys.stdin as f:
    data = json.load(f)

worklogs = data.get('worklogs', [])
if not worklogs:
    print('No time logged on this ticket.')
    sys.exit(0)

total_seconds = 0
entries = []
for w in worklogs:
    started = w['started']
    # Parse ISO timestamp
    dt = datetime.fromisoformat(started.replace('+', '+').rstrip('Z'))
    seconds = w['timeSpentSeconds']
    total_seconds += seconds
    end_dt = dt + timedelta(seconds=seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    author = w.get('author', {}).get('displayName', 'Unknown')

    comment = ''
    body = w.get('comment')
    if body:
        def extract_text(node):
            t = ''
            if isinstance(node, dict):
                if node.get('type') == 'text':
                    t += node.get('text', '')
                for c in node.get('content', []):
                    t += extract_text(c)
            return t
        comment = extract_text(body)

    entries.append({
        'date': dt.strftime('%Y-%m-%d'),
        'day': dt.strftime('%a'),
        'start': dt.strftime('%H:%M'),
        'end': end_dt.strftime('%H:%M'),
        'duration': f'{hours}h {minutes}m',
        'author': author,
        'comment': comment[:60]
    })

# Sort newest first
entries.sort(key=lambda x: x['date'], reverse=True)

print('| Date       | Day | Start | End   | Duration | Author         | Description              |')
print('|------------|-----|-------|-------|----------|----------------|--------------------------|')
for e in entries:
    print(f'| {e[\"date\"]} | {e[\"day\"]} | {e[\"start\"]} | {e[\"end\"]}  | {e[\"duration\"]:8s} | {e[\"author\"]:14s} | {e[\"comment\"]:24s} |')

th = total_seconds // 3600
tm = (total_seconds % 3600) // 60
print(f'\nTotal: {th}h {tm}m ({len(entries)} entries)')
"
```

---

## Rules

- Always use `source .env` for credentials
- Use today's date if no date is specified
- Use Europe/Berlin timezone for timestamps (check DST with `date +%z`)
- If the ticket key is invalid or the API returns an error, show a clear error message
- Keep output concise and formatted — this is a quick utility, not a report
- Do NOT open Jira in the browser or suggest the user does so
