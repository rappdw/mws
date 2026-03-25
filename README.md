# mws

[![CI](https://github.com/rappdw/mws/actions/workflows/ci.yml/badge.svg)](https://github.com/rappdw/mws/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Agent-first CLI for Microsoft 365 (Graph API).

`mws` generates its entire command surface at runtime from the [Microsoft Graph OpenAPI specification](https://learn.microsoft.com/en-us/graph/use-the-api). Instead of hand-coding commands for each endpoint, a schema engine parses the spec and builds commands dynamically — when Microsoft adds new API endpoints, the CLI picks them up automatically.

## Install

```bash
uv tool install mws        # or: uvx mws
```

Requires Python 3.11+.

## Quick start

```bash
# Authenticate (requires an Azure AD app registration)
mws auth login --client-id <your-client-id>

# List your recent mail
mws me messages list --top 5

# List calendar events, selecting specific fields
mws me events list --select "subject,start,end" --top 10

# Use aliases for common operations
mws mail list              # → mws me messages list
mws cal list               # → mws me events list

# Dry-run any command to see what it would do without calling the API
mws me messages list --dry-run

# Introspect available API paths
mws schema list
mws schema /me/messages
```

## Output

JSON by default (compact NDJSON for lists). Use `--format` to switch:

```bash
mws me messages list --format table
mws me messages list --format yaml
```

Errors go to stderr as JSON with structured exit codes (0-5).

## Auth

Two authentication methods:

- **Device code flow** (interactive) — `mws auth login --client-id <id>`
- **Client credentials** (service principal) — set `MWS_CLIENT_ID`, `MWS_CLIENT_SECRET`, `MWS_TENANT_ID` environment variables

Multiple profiles are supported. See [docs/auth-setup.md](docs/auth-setup.md).

## MCP server

`mws` can run as an [MCP](https://modelcontextprotocol.io) tool server, exposing Graph API operations to AI agents:

```bash
mws mcp serve --services mail,calendar
```

## Aliases

Common operations have short aliases. See [docs/aliases.md](docs/aliases.md) or run:

```bash
mws aliases list
```

## Development

```bash
uv sync --extra dev             # Install dependencies
uv run pytest                   # Run tests (125 tests)
uv run ruff check src/ tests/   # Lint
uv run mypy src/                # Type check
```

## Architecture

The CLI uses a two-phase parsing design. Global flags are parsed by Typer, then `LazySchemaGroup` loads the Graph OpenAPI spec and registers Click commands on first access. The full architecture is described in [SPECIFICATION.md](SPECIFICATION.md) and [CLAUDE.md](CLAUDE.md).

```
src/mws/
├── cli.py              # Entry point, global flags, alias resolution
├── auth/               # Device code flow, client credentials, profile management
├── schema/             # OpenAPI fetch, 24h TTL cache, command tree builder
├── engine/             # Dynamic command wiring, executor, aliases
├── client/             # Async HTTP client, retry, pagination
├── mcp/                # MCP tool server
└── output/             # JSON/NDJSON/table/YAML formatters
```

## How this was built

This project was built collaboratively with [Claude Code](https://claude.ai/code). The process and lessons learned are documented in two narratives:

1. **[How we built the spec](How_we_built_the_spec.md)** — From a vague idea to an implementation-ready specification. Covers the architectural pivot from hand-coded commands to a dynamic schema engine, scoping decisions, and why a new tool was worth building despite existing alternatives.

2. **[How we built the initial implementation](How_we_built_the_initial_implementation.md)** — From specification to working CLI. Covers the generate-review-remediate cycle, the characteristic failure pattern of AI-generated code (correct components, missing wiring), and why verification is the bottleneck, not generation.

## License

MIT
