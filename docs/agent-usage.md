# Agent Usage Guide

`mws` is designed as an agent-first CLI. This guide explains how AI agents can use it effectively.

## Self-Orientation with Schema Introspection

Agents should use `mws schema` to discover available operations without loading documentation:

```bash
# List all resource groups
mws schema list

# Explore a specific resource
mws schema show /me/messages

# Get POST method details (parameters, body schema)
mws schema show /me/messages --method POST
```

## Safe Execution with --dry-run

Always preview before executing mutating operations:

```bash
mws me messages create --body '{"subject": "Test"}' --dry-run
```

Output:
```json
{
  "method": "POST",
  "url": "https://graph.microsoft.com/v1.0/me/messages",
  "params": {},
  "headers": {"Authorization": "Bearer [REDACTED]"},
  "body": {"subject": "Test"}
}
```

## Structured Output

All responses are JSON by default (NDJSON for lists). Parse directly:

```bash
# Single object
mws me messages get --params '{"message-id": "abc"}' | jq .subject

# List (NDJSON — one JSON object per line)
mws me messages list --top 5 | jq -s '.[].subject'
```

## OData Filtering

Use `--filter`, `--select`, `--top` for efficient queries:

```bash
mws me messages list --filter "isRead eq false" --select "subject,from" --top 10
```

## MCP Integration

Run `mws` as an MCP server for direct tool integration:

```bash
# Expose all default services
mws mcp

# Scope to specific services
mws mcp --services mail,calendar
```

Tool names follow the pattern `mws_{resource}_{operation}` (e.g., `mws_me_messages_list`).
