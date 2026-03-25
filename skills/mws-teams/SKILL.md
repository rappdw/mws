---
name: mws-teams
description: "mws CLI: Interact with Microsoft Teams — list teams, channels, and messages."
metadata:
  version: 0.1.0
  openclaw:
    category: "productivity"
    requires:
      bins:
        - mws
    cliHelp: "mws schema show /me/joinedTeams"
---

# mws — Teams

> PREREQUISITE: Read ../mws-shared/SKILL.md for auth setup and global flags.

## Required Scopes

`Team.ReadBasic.All`, `ChannelMessage.Read.All`, `Chat.Read`

## Key Commands

```bash
# List joined teams
mws teams list

# List channels in a team
mws teams channels list --params '{"team-id": "<TEAM_ID>"}'

# List messages in a channel
mws teams channels messages list --params '{"team-id": "<TEAM_ID>", "channel-id": "<CHANNEL_ID>"}' --top 10

# Send a message to a channel
mws teams channels messages create --params '{"team-id": "<TEAM_ID>", "channel-id": "<CHANNEL_ID>"}' --body '{
  "body": {"content": "Hello from mws!"}
}'

# List chats
mws me chats list --top 10
```

## Recipes

### 1. Find a team and its channels

```bash
# List all teams
mws teams list --select "id,displayName" --format table

# List channels for a specific team
mws teams channels list --params '{"team-id": "<ID>"}' --select "id,displayName"
```

### 2. Read recent channel messages

```bash
mws teams channels messages list --params '{"team-id": "<ID>", "channel-id": "<ID>"}' --top 5 --select "id,from,body,createdDateTime"
```

## Tips

- Teams API has strict throttling limits — use `--top` to limit results
- Channel messages require `ChannelMessage.Read.All` scope
- Use `--dry-run` before posting messages
