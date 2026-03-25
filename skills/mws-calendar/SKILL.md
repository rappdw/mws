---
name: mws-calendar
description: "mws CLI: Manage Microsoft 365 calendar events via Graph API."
metadata:
  version: 0.1.0
  openclaw:
    category: "productivity"
    requires:
      bins:
        - mws
    cliHelp: "mws schema show /me/calendar/events"
---

# mws — Calendar

> PREREQUISITE: Read ../mws-shared/SKILL.md for auth setup and global flags.

## Required Scopes

`Calendars.Read`, `Calendars.ReadWrite`

## Key Commands

```bash
# List upcoming events
mws cal list --top 10

# Get a specific event
mws me calendar events get --params '{"event-id": "<ID>"}'

# Create an event
mws cal create --body '{
  "subject": "Team Standup",
  "start": {"dateTime": "2024-01-15T09:00:00", "timeZone": "UTC"},
  "end": {"dateTime": "2024-01-15T09:30:00", "timeZone": "UTC"},
  "attendees": [
    {"emailAddress": {"address": "user@example.com"}, "type": "required"}
  ]
}'

# Update an event
mws me calendar events update --params '{"event-id": "<ID>"}' --body '{"subject": "Updated Title"}'

# Delete an event
mws me calendar events delete --params '{"event-id": "<ID>"}'
```

## Common OData Filters

```bash
# Events today
--filter "start/dateTime ge '2024-01-15T00:00:00Z' and start/dateTime lt '2024-01-16T00:00:00Z'"

# Events this week
--filter "start/dateTime ge '2024-01-15T00:00:00Z' and end/dateTime le '2024-01-22T00:00:00Z'"

# Recurring events only
--filter "type eq 'seriesMaster'"
```

## Recipes

### 1. List today's schedule

```bash
mws cal list --filter "start/dateTime ge '$(date -u +%Y-%m-%dT00:00:00Z)'" --select "subject,start,end,location" --top 20 --format table
```

### 2. Create a recurring weekly meeting

```bash
mws cal create --body '{
  "subject": "Weekly Sync",
  "start": {"dateTime": "2024-01-15T10:00:00", "timeZone": "UTC"},
  "end": {"dateTime": "2024-01-15T10:30:00", "timeZone": "UTC"},
  "recurrence": {
    "pattern": {"type": "weekly", "interval": 1, "daysOfWeek": ["monday"]},
    "range": {"type": "noEnd", "startDate": "2024-01-15"}
  }
}'
```

### 3. Check free/busy time

```bash
mws me calendar events list --filter "start/dateTime ge '2024-01-15T08:00:00Z' and end/dateTime le '2024-01-15T18:00:00Z'" --select "subject,start,end"
```

## Tips

- Always include `timeZone` in start/end objects
- Use `--dry-run` before creating or updating events
- Use `--select` to reduce payload size for list operations
