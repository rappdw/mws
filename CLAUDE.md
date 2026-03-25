# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mws** is a Python CLI for Microsoft 365 (Graph API). It is agent-first, producing structured JSON output by default, with commands generated at runtime from the Microsoft Graph OpenAPI specification. The design mirrors the architecture of the Google Workspace CLI (`research/gws/`).

The full design is in `SPECIFICATION.md` — read it before making architectural decisions.

## Toolchain

- **Python 3.11+** with **uv** as the package manager
- **CLI framework:** typer (with Click underneath for dynamic commands)
- **HTTP client:** httpx (async, http2)
- **Auth:** msal (Azure AD)
- **Output:** rich (tables), pyyaml (YAML)
- **MCP server:** mcp (Anthropic MCP Python SDK)
- **Testing:** pytest, pytest-asyncio, respx (httpx mocking)
- **Linting:** ruff (line-length=100), mypy (strict)

## Common Commands

```bash
uv sync --extra dev             # Install all dependencies including dev
uv run mws                      # Run the CLI
uv run mws --version            # Show version
uv run mws auth --help          # Auth subcommands
uv run mws schema list          # List API resource groups
uv run mws aliases list         # Show alias shortcuts
uv run pytest                   # Run all tests (125 tests)
uv run pytest tests/test_foo.py # Run a single test file
uv run pytest -k "test_name"   # Run a single test by name
uv run ruff check src/ tests/  # Lint
uv run ruff format src/ tests/ # Format
uv run mypy src/                # Type check
```

## Architecture

```
src/mws/
├── cli.py           # Typer app entry point, global flags, cli_main() entry point with alias resolution
├── errors.py        # MwsError hierarchy, exit codes (0-5), JSON stderr serialization
├── auth/
│   ├── commands.py  # mws auth login/logout/status/switch CLI commands
│   ├── config.py    # Multi-profile config at ~/.config/mws/config.json
│   ├── device_flow.py # MSAL device code flow with SerializableTokenCache
│   └── client_creds.py # Service principal auth via env vars
├── schema/
│   ├── fetch.py     # Download OpenAPI spec from aka.ms URLs
│   ├── cache.py     # 24h TTL cache at ~/.cache/mws/, JSON index for fast starts
│   ├── build.py     # Parse OpenAPI → CommandTree (ResourceNode/MethodNode dataclasses)
│   └── introspect.py # mws schema list/show/refresh commands, SchemaGroup for path shortcuts
├── engine/
│   ├── commander.py # LazySchemaGroup (TyperGroup subclass) for dynamic command loading, auth resolution
│   ├── executor.py  # CLI invocation → Graph HTTP request, --dry-run, path param substitution
│   └── aliases.py   # Flat alias table + mws aliases list command
├── client/
│   └── graph.py     # GraphClient: httpx async, MsalAuth, retry (429/503), pagination
├── mcp/
│   └── server.py    # FastMCP server, tools from CommandTree, --services filter
└── output/
    └── format.py    # JSON/NDJSON/table/YAML formatters
```

**Key design patterns:**
- **Two-phase parsing:** Global flags parsed by Typer callback, then `LazySchemaGroup` (wired via `cls=LazySchemaGroup` on the root Typer app) loads OpenAPI schema and registers Click commands on first access
- **Alias resolution:** `sys.argv` is mutated before Typer dispatch (in both `cli_main()` and `__main__.py`) to expand alias shortcuts like `mail list` → `me messages list`
- **Auth resolution:** `_resolve_auth()` in `commander.py` tries client credentials (env vars) first, falls back to device code flow, returns `None` for `--dry-run`
- **Schema engine:** Fetches OpenAPI spec from `https://aka.ms/graph/{v1.0|beta}/openapi.yaml`, caches raw YAML + compact JSON index to `~/.cache/mws/` with 24h TTL
- **Command tree:** `CommandTree` → `ResourceNode` → `MethodNode` dataclasses with serialization for index caching
- **Aliases:** Flat `dict[tuple[str,...], AliasTarget]` mapping in `engine/aliases.py`
- **Output:** JSON (compact NDJSON for lists) is the default; errors always go to stderr as JSON
- **Metadata stripping:** `@odata.context`, `@odata.type` etc. stripped from responses unless `--verbose`; `@odata.nextLink` preserved internally for pagination

## Reference Implementations

- `research/gws/` — **Primary reference** for architecture, output format, global flags, schema introspection, MCP server (Rust)
- `research/m365/` — **Secondary reference** for Graph API auth patterns, OData queries, permission scopes (Node.js/TypeScript)

These are git submodules. Use `git submodule update --init` to populate them.

## Testing

- Mock HTTP with `respx`, not real API calls
- Use `--dry-run` output as the primary assertion surface for executor tests
- Use the `MINIMAL_OPENAPI` fixture from `tests/test_schema.py` for schema-dependent tests
- Target >80% coverage on `engine/`, `schema/`, `client/`
