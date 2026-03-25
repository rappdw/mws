---
name: mws-shared
description: "mws CLI: Shared patterns, auth setup, global flags, and schema introspection for Microsoft 365."
metadata:
  version: 0.1.0
  openclaw:
    category: "productivity"
    requires:
      bins:
        - mws
---

# mws — Shared Patterns

> Use this skill file for general mws CLI usage. Service-specific skills (mail, calendar, teams, drive) build on these patterns.

## Authentication

```bash
# Interactive login (device code flow)
mws auth login --tenant-id <TENANT_ID> --client-id <CLIENT_ID>

# Check status
mws auth status

# Switch profiles
mws auth switch work
```

For unattended use, set `MWS_TENANT_ID`, `MWS_CLIENT_ID`, `MWS_CLIENT_SECRET` environment variables.

## Global Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--format {json\|table\|yaml}` | `json` | Output format |
| `--api-version {v1.0\|beta}` | `v1.0` | Graph API version |
| `--profile <name>` | `default` | Auth profile |
| `--dry-run` | `false` | Preview request without executing |
| `--params <json>` | — | OData query parameters as JSON |
| `--body <json>` | — | Request body (or `-` for stdin) |
| `--select <fields>` | — | Shorthand for `$select` |
| `--filter <expr>` | — | Shorthand for `$filter` |
| `--top <n>` | — | Shorthand for `$top` |
| `--page-all` | `false` | Follow all pagination pages |
| `--page-limit <n>` | `10` | Max pages with `--page-all` |
| `--verbose` / `-v` | `false` | HTTP debug output to stderr |
| `--quiet` / `-q` | `false` | Suppress non-data output |

## Schema Introspection

Use `mws schema` to discover API operations without external documentation:

```bash
mws schema list                            # All resource groups
mws schema show /me/messages               # All methods on a resource
mws schema show /me/messages --method POST # Specific method details
mws schema refresh                         # Force re-download schema
```

## Command Syntax

```
mws <resource-group> <resource> <operation> [flags]
```

## Output

- **JSON (default):** NDJSON for lists (one object per line), pretty-printed for single objects
- **Table:** `--format table` for human-readable output
- **YAML:** `--format yaml`
- **Errors:** Always JSON to stderr with exit codes: 0=ok, 1=api, 2=auth, 3=notfound, 4=permission, 5=throttled

## Error Recovery

1. **Auth errors (exit 2):** Run `mws auth login` to re-authenticate
2. **Not found (exit 3):** Verify resource ID with `mws schema show <path>`
3. **Permission denied (exit 4):** Check required scopes in Azure AD app registration
4. **Throttled (exit 5):** Wait and retry; use `--top` to reduce result size

## Tips

- Always use `--dry-run` before mutating operations
- Use `mws schema show` to discover parameters instead of guessing
- Pipe `--body -` from stdin for complex request bodies
- Use `--select` to reduce response size and improve performance
