---
name: mws-mail
description: "mws CLI: Read, send, and manage Microsoft 365 email via Graph API."
metadata:
  version: 0.1.0
  openclaw:
    category: "productivity"
    requires:
      bins:
        - mws
    cliHelp: "mws schema show /me/messages"
---

# mws — Mail

> PREREQUISITE: Read ../mws-shared/SKILL.md for auth setup and global flags.

## Required Scopes

`Mail.Read`, `Mail.Send`, `Mail.ReadWrite`

## Key Commands

```bash
# List recent messages
mws mail list --top 10

# List unread messages
mws mail list --filter "isRead eq false" --select "subject,from,receivedDateTime"

# Get a specific message
mws me messages get --params '{"message-id": "<ID>"}'

# Send an email
mws me send-mail --body '{
  "message": {
    "subject": "Hello",
    "body": {"contentType": "Text", "content": "Hi there"},
    "toRecipients": [{"emailAddress": {"address": "user@example.com"}}]
  }
}'

# Delete a message
mws me messages delete --params '{"message-id": "<ID>"}'
```

## Common OData Filters

```bash
# Unread messages
--filter "isRead eq false"

# Messages from a specific sender
--filter "from/emailAddress/address eq 'sender@example.com'"

# Messages received today
--filter "receivedDateTime ge 2024-01-15T00:00:00Z"

# Messages with attachments
--filter "hasAttachments eq true"

# Subject contains text
--filter "contains(subject, 'meeting')"
```

## Recipes

### 1. Triage unread inbox

```bash
mws mail list --filter "isRead eq false" --select "id,subject,from,receivedDateTime" --top 20
```

### 2. Send a reply

```bash
mws me messages get --params '{"message-id": "<ID>"}'
# Then use the reply endpoint
mws me messages reply --params '{"message-id": "<ID>"}' --body '{"comment": "Thanks!"}'
```

### 3. Search across mailbox

```bash
mws me messages list --filter "contains(subject, 'quarterly report')" --top 5
```

### 4. Get messages with specific fields only

```bash
mws mail list --select "subject,from,receivedDateTime,isRead" --top 10 --format table
```

## Tips

- Use `--select` to minimize response size — Graph API returns all fields by default
- Use `--dry-run` before `send-mail` to verify the request payload
- Page through large mailboxes with `--page-all --page-limit 5`
