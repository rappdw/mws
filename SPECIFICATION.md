# `mws` — Microsoft 365 CLI Specification

> Binary name: `mws` | Language: Python 3.11+ | Distribution: `uv tool install mws` / `uvx mws`

---

## Reference Implementations

This repo includes two submodules in `research/` that serve as primary references during implementation. **Read their source before writing any corresponding `mws` code.**

```
research/
├── gws/    # Primary style reference (googleworkspace/cli)
└── m365/   # Secondary reference (pnp/cli-microsoft365)
```

### `research/gws` — Primary Style Reference

`gws` is the architectural and stylistic model for `mws`. It solves the same problem (unified CLI over a cloud productivity suite) with the same agent-first design philosophy. Follow it closely for:

- **Overall architecture** — two-phase parsing, dynamic command tree built from OpenAPI spec at runtime
- **Command surface shape** — how resource groups, resources, and operations are named and nested
- **Output format** — NDJSON default, `--format` flag behavior, error serialization to stderr
- **Global flag design** — `--dry-run`, `--page-all`, `--page-limit`, `--params`, `--body`, `--select`, `--filter`
- **Schema introspection** — `mws schema <path>` modeled directly on `gws schema`
- **Skill file format and content** — copy the SKILL.md structure from `research/gws/skills/` exactly; adapt content for Graph API
- **MCP server mode** — model `mws mcp` on `gws mcp`
- **First-run and auth setup UX** — silent when things work, minimal output, no banners

The primary difference: `gws` is written in Rust and distributed via npm. `mws` is Python. Translate patterns, not code.

### `research/m365` — Secondary Reference

`m365` is a mature, production CLI targeting the same Graph API. Consult it for:

- **Graph API auth patterns** — device code flow, token cache structure, MSAL integration, refresh handling
- **Azure AD app registration** — the auth setup guide in `research/m365/docs/` covers the exact portal steps and required permission scopes
- **OData query patterns** — `$filter`, `$select`, `$top`, `$orderby` usage against real Graph endpoints
- **Graph API edge cases** — pagination quirks, throttling behavior, error codes, endpoint-specific gotchas
- **Permission scope inventory** — what delegated scopes are needed for which operations
- **Command taxonomy** — how Graph resources map to human-readable CLI nouns (useful for the alias layer)

Do not follow `m365` for architecture, output format, or UX — it is human-first and Node-based. Use it as a field guide to the Graph API, not a design template.

---

## Design Philosophy

`mws` is built for two audiences: humans who want scriptable access to M365 without writing Graph API `curl` calls, and AI agents that need structured, predictable, introspectable tool interfaces.

### Agent-first principles

- **Every response is structured JSON by default.** Tables and color are opt-in via `--format table`.
- **Every command is introspectable.** `mws schema <resource>` returns the full JSON schema for any operation. Agents query this instead of loading documentation into context.
- **The command surface is always current.** Commands are generated at runtime from the Microsoft Graph OpenAPI spec. When Microsoft adds an API endpoint, `mws` picks it up automatically.
- **`--dry-run` on everything.** Agents preview before they act.
- **Minimal token overhead.** Compact output by default. No banners, no progress spinners, no confirmations unless `--verbose`.
- **Skills ship with the CLI.** SKILL.md files for each service teach LLMs how to use `mws` correctly.

---

## Architecture

Model the overall architecture on `research/gws/` — specifically its two-phase parsing strategy where a static CLI parser (Typer, in our case) is combined with a dynamic command surface built from the live API spec. Read `research/gws/src/main.rs` and the surrounding modules to understand the flow before writing any engine code.

```
┌─────────────────────────────────────────────────────┐
│                    mws CLI                          │
│                                                     │
│  ┌─────────────┐    ┌──────────────────────────┐   │
│  │  Auth layer │    │   Schema Engine          │   │
│  │  (MSAL)     │    │   - Fetch OpenAPI spec   │   │
│  │             │    │   - Local cache (TTL)    │   │
│  └──────┬──────┘    │   - Build command tree   │   │
│         │           └────────────┬─────────────┘   │
│         │                        │                  │
│         ▼                        ▼                  │
│  ┌──────────────────────────────────────────────┐  │
│  │           Dynamic Command Builder            │  │
│  │  Typer app built at import time from schema  │  │
│  └──────────────────┬───────────────────────────┘  │
│                     │                               │
│         ┌───────────┴──────────┐                   │
│         ▼                      ▼                   │
│  ┌─────────────┐      ┌────────────────┐           │
│  │  Alias layer│      │   MCP server   │           │
│  │  (well-known│      │   (mws mcp)    │           │
│  │   shortcuts)│      └────────────────┘           │
│  └─────────────┘                                   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │           Graph HTTP Client                 │   │
│  │   httpx async, pagination, retry, auth      │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Repository Layout

```
mws/
├── SPECIFICATION.md
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── research/                         # Submodules — read before implementing
│   ├── gws/                          # github.com/googleworkspace/cli
│   └── m365/                         # github.com/pnp/cli-microsoft365
├── src/
│   └── mws/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py                    # Root Typer app + dynamic command registration
│       ├── auth/
│       │   ├── config.py             # ~/.config/mws/config.json
│       │   ├── device_flow.py        # MSAL device code flow
│       │   └── client_creds.py       # Service principal / client credentials
│       ├── schema/
│       │   ├── fetch.py              # Download & cache Graph OpenAPI spec
│       │   ├── cache.py              # ~/.cache/mws/graph-openapi-{version}.yaml
│       │   ├── build.py              # Parse spec → internal command tree
│       │   └── introspect.py         # mws schema <resource>
│       ├── engine/
│       │   ├── commander.py          # Dynamically register Typer commands from tree
│       │   ├── executor.py           # Translate CLI invocation → Graph HTTP request
│       │   └── aliases.py            # Well-known shorthand routes
│       ├── client/
│       │   └── graph.py              # httpx async: auth, pagination, retry
│       ├── mcp/
│       │   └── server.py             # MCP server mode
│       ├── output/
│       │   └── format.py             # json / table / yaml renderers
│       └── errors.py
├── skills/                           # Agent skill files — model on research/gws/skills/
│   ├── mws-shared/SKILL.md
│   ├── mws-mail/SKILL.md
│   ├── mws-calendar/SKILL.md
│   ├── mws-teams/SKILL.md
│   └── mws-drive/SKILL.md
├── tests/
│   ├── conftest.py
│   ├── test_schema.py
│   ├── test_engine.py
│   ├── test_executor.py
│   ├── test_auth.py
│   └── test_mcp.py
└── docs/
    ├── auth-setup.md                 # Adapt from research/m365/docs/ auth guides
    ├── agent-usage.md
    └── aliases.md
```

---

## Toolchain & Dependencies

| Purpose | Library |
|---|---|
| CLI framework | `typer[all]` |
| Rich terminal output | `rich` |
| HTTP client | `httpx[http2]` (async) |
| Auth / MSAL | `msal` |
| YAML output | `pyyaml` |
| Config/cache dirs | `platformdirs` |
| OpenAPI parsing | `openapi-core` or `jsonschema` |
| MCP server | `mcp` (Anthropic MCP Python SDK) |
| Testing | `pytest`, `pytest-asyncio`, `respx` |

```toml
[project]
name = "mws"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "typer[all]>=0.12",
  "rich>=13",
  "httpx[http2]>=0.27",
  "msal>=1.28",
  "pyyaml>=6",
  "platformdirs>=4",
  "openapi-core>=0.19",
  "mcp>=1.0",
]

[project.scripts]
mws = "mws.cli:app"
```

---

## Schema Engine

The schema engine is the core of `mws`. Everything else depends on it. Model it on the equivalent component in `research/gws/` — the discovery service fetcher, cache, and command tree builder — translated into Python.

### OpenAPI Spec URLs

Microsoft publishes full OpenAPI 3 specs at Microsoft-hosted URLs:

```
v1.0 (default):  https://aka.ms/graph/v1.0/openapi.yaml
beta:            https://aka.ms/graph/beta/openapi.yaml
```

### Cache

- Location: `~/.cache/mws/graph-openapi-v1.0.yaml` and `~/.cache/mws/graph-openapi-beta.yaml`
- TTL: 24 hours (configurable via `MWS_SCHEMA_TTL_HOURS`)
- Refreshed on TTL expiry or `mws schema refresh`
- Store both the raw spec and a parsed index (`graph-index-{version}.json`) for fast warm starts

### Schema Introspection

Model `mws schema` directly on `gws schema`. Output is always JSON. This is the primary mechanism for agents to self-orient without loading documentation into context.

```bash
mws schema /me/messages
mws schema /me/calendar/events --method POST
mws schema list
mws schema refresh
```

---

## Command Surface

### Dynamic Commands (Primary)

All commands are generated from the Graph OpenAPI spec at runtime. Follow the `gws` two-phase parsing strategy from `research/gws/src/` — static Typer arg parsing combined with dynamic dispatch against the live schema.

General form:
```
mws <resource-group> <resource> <operation> [--params <json>] [--body <json>] [flags]
```

Examples:
```bash
mws me messages list --params '{"$top": 10, "$filter": "isRead eq false"}'
mws me calendar events create --body '{"subject": "Standup", "start": {...}, "end": {...}}'
mws me sendMail --body '{"message": {"subject": "Hello", "toRecipients": [...]}}'
mws me joinedTeams list
mws me drive root children create --body '{"name": "report.pdf"}' --upload ./report.pdf
```

For OData filter syntax and which params each endpoint accepts, consult `research/m365/` source and docs.

### Alias Layer

A thin alias layer provides shorter routes to common operations. Aliases resolve to identical dynamic commands underneath and produce identical output. For alias vocabulary, use `research/m365/`'s command taxonomy as a reference for what human operators expect.

```bash
mws mail list       → mws me messages list
mws mail get <id>   → mws me messages get --id <id>
mws mail send       → mws me sendMail --body <...>
mws cal list        → mws me calendar events list
mws cal create      → mws me calendar events create --body <...>
mws teams list      → mws me joinedTeams list
mws drive ls        → mws me drive root children list
mws drive get <p>   → mws me drive root:/{p}: get
```

Full alias list documented in `docs/aliases.md` and via `mws aliases list`.

### Built-in Commands (Static)

```
mws auth login [--profile <n>] [--tenant-id <tid>] [--client-id <cid>]
mws auth logout [--profile <n>]
mws auth status
mws auth switch <profile>

mws schema list
mws schema <path> [--method <verb>]
mws schema refresh

mws aliases list

mws mcp [--services <svc,...>]

mws --version
mws --help
```

---

## Global Flags

Model flag naming and behavior on `research/gws/`. Specifically mirror `--dry-run`, `--page-all`, `--page-limit`, `--params`, `--body`, `--select`, `--filter`, `--top` from the gws README and source.

| Flag | Default | Description |
|---|---|---|
| `--format` | `json` | Output format: `json`, `table`, `yaml` |
| `--api-version` | `v1.0` | Graph API version: `v1.0` or `beta` |
| `--profile` | `default` | Auth profile to use |
| `--dry-run` | `false` | Print the Graph request that would be made; do not execute |
| `--params <json>` | — | OData query parameters as JSON object |
| `--body <json>` | — | Request body as JSON (or `-` to read from stdin) |
| `--select <fields>` | — | Shorthand for `$select` |
| `--filter <expr>` | — | Shorthand for `$filter` |
| `--top <n>` | — | Shorthand for `$top` |
| `--page-all` | `false` | Follow all `@odata.nextLink` pages; emit NDJSON |
| `--page-limit <n>` | `10` | Max pages when `--page-all` is set |
| `--no-color` | `false` | Disable Rich color output |
| `--quiet` / `-q` | `false` | Suppress all output except data |
| `--verbose` / `-v` | `false` | Emit HTTP debug info to stderr |

`--dry-run` output:
```json
{
  "method": "GET",
  "url": "https://graph.microsoft.com/v1.0/me/messages",
  "params": {"$top": 10, "$filter": "isRead eq false"},
  "headers": {"Authorization": "Bearer [REDACTED]"}
}
```

---

## Authentication

### Azure AD App Registration

Write `docs/auth-setup.md` by adapting the auth setup documentation from `research/m365/docs/`. The portal steps, required permission scopes, and token flow are well-documented there; do not reinvent them. Key scopes needed:

- Mail: `Mail.Read`, `Mail.Send`, `Mail.ReadWrite`
- Calendar: `Calendars.Read`, `Calendars.ReadWrite`
- Teams: `Team.ReadBasic.All`, `ChannelMessage.Read.All`, `Chat.Read`
- Drive: `Files.Read.All`, `Files.ReadWrite.All`

### Auth Flows

For implementation, consult `research/m365/src/` auth modules for MSAL integration patterns, token cache structure, and refresh handling. These are Graph-specific concerns where m365 is the better reference than gws.

**Device Code Flow** (interactive, default) — `mws auth login` triggers MSAL device code, caches token at `~/.config/mws/tokens/<profile>.json` (mode `0600`).

**Client Credentials Flow** (unattended) — activated by `--auth-type sp` or env vars `MWS_TENANT_ID`, `MWS_CLIENT_ID`, `MWS_CLIENT_SECRET`. Token not persisted.

### Configuration File

`~/.config/mws/config.json`:

```json
{
  "default_profile": "work",
  "profiles": {
    "work": {
      "tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "auth_type": "device_code",
      "token_cache_path": "~/.config/mws/tokens/work.json"
    }
  }
}
```

---

## Output

Model output behavior exactly on `research/gws/` — specifically its NDJSON default, error serialization, and `--format` flag handling. Do not follow m365 output patterns.

- **JSON (default):** Compact NDJSON for lists, single object for singular operations. Strip `@odata.context` and Graph metadata fields unless `--verbose`.
- **Table (`--format table`):** `rich.table.Table`, first 5 schema fields or `--select` fields, truncate long values to 40 chars.
- **YAML (`--format yaml`):** `pyyaml` default_flow_style=False.
- **Errors:** Always to stderr as JSON: `{"error": "<code>", "message": "<msg>", "status": 404}`. Exit codes: `0` success, `1` general, `2` auth, `3` not found, `4` permission denied, `5` throttled.

---

## Graph API Client

- `httpx.AsyncClient` with `http2=True`, base URL `https://graph.microsoft.com/{api-version}`
- Auth injected via httpx auth class
- Retry: 3 attempts, exponential backoff on `429` (respect `Retry-After`) and `503`
- Pagination: async generator following `@odata.nextLink`
- File upload: chunked upload session for files >4MB

For Graph-specific retry and pagination edge cases, consult `research/m365/src/` implementations.

---

## MCP Server Mode

Model `mws mcp` on `gws mcp` from `research/gws/`. Tool names follow `mws_<service>_<operation>`. Runs over stdio (default) or SSE (`--transport sse --port <n>`). Tool schemas generated from Graph OpenAPI response schemas.

```bash
mws mcp                           # all services
mws mcp --services mail,calendar  # scoped
```

Keep `--services` scoped to control tool count (clients typically support 50–128 tools).

---

## Agent Skills

Copy the SKILL.md structure and format exactly from `research/gws/skills/`. Adapt content for Graph API and Microsoft auth. One file per service plus a shared file.

Each SKILL.md covers: auth setup, key commands with example payloads, common OData filter patterns, how to use `mws schema` to self-orient, error recovery patterns, and 5–10 end-to-end recipes.

Skills are installable into Claude Code or any skill-aware agent runner:

```bash
npx skills add https://github.com/<org>/mws
npx skills add https://github.com/<org>/mws/tree/main/skills/mws-mail
```

---

## Configuration Precedence

1. CLI flag
2. Environment variable (`MWS_FORMAT`, `MWS_PROFILE`, `MWS_API_VERSION`, `MWS_TENANT_ID`, `MWS_CLIENT_ID`, `MWS_CLIENT_SECRET`, `MWS_SCHEMA_TTL_HOURS`)
3. Config file (`~/.config/mws/config.json`)
4. Built-in default

---

## Testing

- `pytest` + `pytest-asyncio`, `respx` for httpx mocking
- Use `--dry-run` output as the primary assertion surface for executor tests
- Target: >80% line coverage on `engine/`, `schema/`, `client/`
- Schema tests: OpenAPI spec parses into correct command tree
- Engine tests: CLI invocations produce correct Graph HTTP requests
- MCP tests: tool schema generation from OpenAPI

---

## First-Run Experience

```bash
$ mws mail list
# cold, no config:
No profile configured. Run 'mws auth login' to get started.

# cold schema cache:
Fetching Graph API schema... done (cached at ~/.cache/mws/graph-openapi-v1.0.yaml)
[...NDJSON results...]
```

No banners, no ASCII art. Silent when things work. Model on gws first-run behavior.

---

## Version & Release

- Version in `pyproject.toml`, mirrored to `mws/__init__.py` as `__version__`
- `uv tool install mws` and `uvx mws` compatible
- CI: `ruff`, `mypy`, `pytest` on Python 3.11 and 3.12
- Release: tag `v*` → PyPI via OIDC trusted publisher
- Changelog: Keep a Changelog format

---

## Implementation Order

Before starting any phase, read the corresponding `research/gws/` source for that component.

1. **Scaffold** — `pyproject.toml`, root `cli.py`, global flags, uv/uvx entry point
2. **Auth** — config file, device code flow (MSAL), token cache, `mws auth` commands. Reference: `research/m365/src/auth/`
3. **Graph client** — httpx async, token injection, pagination, retry. Reference: `research/m365/src/` for Graph-specific edge cases
4. **Schema fetch & cache** — download spec from `aka.ms` URLs, TTL cache, `mws schema refresh`. Reference: `research/gws/src/` discovery fetcher
5. **Schema parser** — parse OpenAPI into command tree, `mws schema list` and `mws schema <path>`. Reference: `research/gws/src/` command tree builder
6. **Dynamic command builder** — Typer subcommands from parsed tree, two-phase parsing. Reference: `research/gws/src/main.rs`
7. **Executor** — CLI invocation → Graph HTTP request, `--dry-run`. Reference: `research/gws/src/` executor
8. **Output formatting** — NDJSON default, `--format table/yaml`, error serialization. Reference: `research/gws/` output modules
9. **Alias layer** — well-known shortcuts, `mws aliases list`. Reference: `research/m365/` for vocabulary
10. **MCP server mode** — `mws mcp`, tool schema generation, stdio transport. Reference: `research/gws/` MCP implementation
11. **Skills** — SKILL.md files for each service. Reference: `research/gws/skills/` for structure and format
12. **Tests** — schema, engine, executor, auth, MCP
13. **Docs** — `auth-setup.md` (adapt from `research/m365/docs/`), `agent-usage.md`, `aliases.md`
14. **CI/CD** — GitHub Actions lint/test/release
