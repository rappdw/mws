# Review Findings

Critical review of the `mws` repository covering code completeness, correctness, architecture, and overall viability.

---

## Critical: Must Fix

### F-01: Dynamic commands are never wired into the CLI

`register_dynamic_commands()` in `commander.py` is defined but **never called** from `cli.py` or `__main__.py`. The `LazySchemaGroup` that loads OpenAPI-driven commands is never installed on the Typer app. This means the entire dynamic command surface (`mws me messages list`, `mws users list`, etc.) — the core value proposition — is inoperable.

The function also has a type-annotated return of `None` but actually returns a `LazySchemaGroup`, with a `# type: ignore` suppressing the error. The replacement strategy (swapping Typer's underlying Click group) is incomplete — the returned group is discarded.

**Files:** `src/mws/engine/commander.py:143-162`, `src/mws/cli.py`

### F-02: Aliases are never resolved

`resolve_alias()` is defined in `engine/aliases.py` but never called. The alias layer (`mws mail list` -> `mws me messages list`) does not function. There is no argv interception point in `cli.py` or `__main__.py` that invokes alias resolution before Click/Typer dispatch.

**Files:** `src/mws/engine/aliases.py:57`, `src/mws/cli.py`, `src/mws/__main__.py`

### F-03: No auth integration in command execution

`_make_method_callback()` in `commander.py` creates a `GraphClient(api_version=..., verbose=...)` with **no auth parameter**. The client will make unauthenticated requests to Graph API, which will fail with 401 on every real endpoint. There is no code path that reads the profile config, instantiates `DeviceCodeAuth` or `ClientCredentialAuth`, creates an `MsalAuth` wrapper, and passes it to the `GraphClient`.

**Files:** `src/mws/engine/commander.py:29`, `src/mws/client/graph.py`

### F-04: mypy fails with 19 errors — CI will never pass

`ci.yml` runs `uv run mypy src/mws/` which currently produces 19 errors including:
- Missing `types-PyYAML` stub dependency
- `no-any-return` errors across multiple modules
- Invalid `port` kwarg to `FastMCP.run()` (API mismatch)
- `pass_context` type incompatibility

Since CI runs mypy and the pipeline has no `|| true`, every PR will fail.

**Files:** `pyproject.toml` (missing `types-PyYAML` in dev deps), multiple source files

---

## High: Should Fix

### F-05: `openapi-core` is a phantom dependency

`openapi-core>=0.19` is listed in `pyproject.toml` dependencies but is never imported anywhere in the codebase. It pulls in a large transitive dependency tree for no reason. The schema parsing is handled by custom code in `schema/build.py` (which is fine — the Graph OpenAPI spec is too large for validation-style libraries anyway).

**Files:** `pyproject.toml:19`

### F-06: `--no-color` flag is accepted but ignored

The global `--no-color` flag is parsed and stored in `GlobalOptions` but never plumbed to the Rich `Console` in `format.py`. The table formatter hardcodes `no_color=False`.

**Files:** `src/mws/output/format.py:81`, `src/mws/cli.py:130-133`

### F-07: `--verbose` flag is not passed to output formatter

Metadata stripping depends on `GraphClient.verbose`, but the formatter doesn't know about verbose mode. More critically, the spec says verbose mode should "emit HTTP debug info to stderr" — the client does print to stderr, but there's no structured approach; it just prints raw strings.

### F-08: `_raw_request_full_url` bypasses auth

In `graph.py:234`, `_raw_request_full_url()` constructs an `httpx.Request` manually with `headers=dict(client.headers)` — but this copies the *client's default headers*, not the auth headers injected by `MsalAuth.auth_flow()`. Pagination requests to `@odata.nextLink` will be unauthenticated. The `client.send(req)` call also bypasses the auth flow because the request is pre-built.

**Files:** `src/mws/client/graph.py:223-263`

### F-09: Duplicate `OutputFormat` definition

`OutputFormat` is defined identically in both `cli.py` and `output/format.py`. They are separate classes that happen to have the same values. The `format_and_print` function works around this with `hasattr(fmt, "value")` instead of type-checking, which is fragile.

**Files:** `src/mws/cli.py:17-20`, `src/mws/output/format.py:11-14`

### F-10: MCP tool handlers have no auth

In `mcp/server.py:119`, the tool handler creates `GraphClient(api_version="v1.0")` with no auth. Every MCP tool invocation will fail against real Graph API. There's also no way to pass the user's profile or API version preference to MCP tools.

**Files:** `src/mws/mcp/server.py:115-137`

### F-11: Schema show path is `/me/messages` not `me messages`

`mws schema show /me/messages` works, but the dynamic commands (if they were wired up) would be `mws me messages list`. The schema introspection uses slash-separated paths while the CLI uses space-separated segments. The spec says `mws schema <path>` should accept the slash form — this is fine, but the mapping between the two forms for the user is undocumented and could be confusing.

---

## Medium: Quality & Robustness

### F-12: `asyncio.run()` called in multiple sync contexts

`asyncio.run()` is called in `_make_method_callback`, `_ensure_schema`, `mcp` command, and `_get_tree`. If any of these run inside an existing event loop (e.g., Jupyter, some test runners, or nested MCP server scenarios), they will raise `RuntimeError: This event loop is already running`. Consider a helper that detects an existing loop and uses `loop.run_until_complete()` or `nest_asyncio`.

**Files:** `src/mws/engine/commander.py:32,60,120`, `src/mws/cli.py:187`, `src/mws/schema/introspect.py:26`

### F-13: GraphClient is not used as an async context manager

The client creates `httpx.AsyncClient` but relies on manual `close()` calls. Several error paths in `_make_method_callback` could skip the `finally:` block if `asyncio.run()` itself fails. Should use `async with` pattern.

### F-14: `_classify_error` returns a type, compared with `==`

In `graph.py:165`, `error_cls == ThrottledError` uses identity comparison on types. This works but `is` would be more idiomatic and explicit. More importantly, `_classify_error` takes a `body` parameter it never uses — dead parameter.

**Files:** `src/mws/client/graph.py:39-47,165`

### F-15: Schema parsing drops `$ref` — no deep resolution

`build_command_tree` handles inline schemas but doesn't resolve `$ref` references. The real Graph OpenAPI spec uses `$ref` extensively. Request body schemas and response schemas will be `None` or contain unresolved `{"$ref": "#/components/schemas/..."}` objects, making `mws schema show` output incomplete and MCP tool schemas broken for any non-trivial endpoint.

**Files:** `src/mws/schema/build.py:220-231`

### F-16: Schema parsing performance with real spec

The Graph OpenAPI spec is ~50MB of YAML. `yaml.safe_load()` on a 50MB file can take 30-60 seconds and consume significant memory. The JSON index cache mitigates warm starts, but first-run and refresh will be very slow. Consider downloading the JSON version of the spec if available, or streaming the YAML parse.

### F-17: Hardcoded default client ID

`device_flow.py:15` hardcodes `DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"`. This appears to be a fabricated UUID. A real Azure AD app registration is needed, or the README/docs should clearly state users must register their own app and always pass `--client-id`.

**Files:** `src/mws/auth/device_flow.py:15`

### F-18: Tests don't test the actual CLI end-to-end

The executor and client tests are solid unit tests, but there are no integration tests that invoke `mws me messages list --dry-run` through the actual CLI entry point with a mocked schema. Since the dynamic command wiring is broken (F-01), such tests would have caught it immediately.

### F-19: `strip_metadata_recursive` only strips one level of nesting

The function strips OData keys from the top-level dict and from items in a `value` array, but Graph API responses can have deeper nesting (e.g., `value[].attachments[].@odata.type`). The function name says "recursive" but it's only two levels deep.

**Files:** `src/mws/client/graph.py:55-65`

---

## Low: Polish & Spec Compliance

### F-20: `--upload` flag from spec not implemented

The spec mentions `--upload ./report.pdf` for file upload and "chunked upload session for files >4MB" but neither the flag nor the upload session logic exists.

### F-21: `CONTRIBUTING.md` mentioned in spec layout but not created

### F-22: `--auth-type sp` flag not implemented

The spec mentions `--auth-type sp` to select client credentials flow, but no such flag exists on any command. Client credentials are only available via env vars.

### F-23: `mws schema <path>` spec syntax vs `mws schema show <path>`

The spec says `mws schema /me/messages` (no `show` subcommand), but the implementation requires `mws schema show /me/messages`. This breaks agent expectations documented in the skills.

### F-24: Aliases use `send-mail` but Graph API uses `sendMail`

`aliases.py:31` maps `("mail", "send")` to `["me", "send-mail"]` — but the `_normalize_segment` function would produce `send-mail` from `sendMail`, which is correct for internal consistency. However, this means the alias path segments must match the *normalized* names, which are not validated against the actual command tree.

### F-25: README is a stub

Three lines. No installation instructions, usage examples, or links to docs.

### F-26: Skills reference commands that don't work

The mail skill shows `mws me sendMail` — but `sendMail` would be normalized to `send-mail` by the schema engine. Skills need to match the actual CLI surface after normalization.

### F-27: No `--orderby` OData shorthand

The spec and gws reference include `$orderby` as a common OData parameter, but there's no `--orderby` shorthand flag alongside `--select`, `--filter`, `--top`.

---

## Overall Assessment

### What works well
- **Architecture is sound.** The two-phase parsing design, lazy schema loading, and dataclass-based command tree are well-structured and appropriate for the problem.
- **Test coverage on units.** Schema parsing, executor dry-run, client retry/pagination, and output formatting are thoroughly tested.
- **Error model is clean.** Dataclass-based error hierarchy with JSON serialization and distinct exit codes follows the spec well.
- **Cache design is smart.** Three-tier loading (JSON index -> raw YAML -> network) is the right approach for a 50MB spec.

### What doesn't work
- **The CLI doesn't actually do anything dynamic.** The core value proposition — run any Graph API command from the OpenAPI spec — is not wired up. Static commands (auth, schema, aliases list) work, but `mws me messages list` would fail with "No such command."
- **Auth is not integrated with execution.** Even if dynamic commands were wired, they'd make unauthenticated requests.
- **mypy fails**, making CI red from day one.

### Approach concerns
- **50MB YAML parse on first run** is a significant UX problem. The Graph OpenAPI spec is enormous. First-run experience will be painful (30-60s of parsing with high memory use). Consider whether a pre-built index can ship with the package, or whether the spec can be fetched as JSON.
- **All commands are `asyncio.run()` wrappers around async code.** Since the CLI is synchronous by nature (Typer/Click), the async layer adds complexity without benefit. The only justification would be if httpx's async API offered something sync doesn't — but `httpx` has a perfectly good sync API. Consider whether the async layer is earning its keep.
- **`$ref` resolution** is the elephant in the room. Without it, schema introspection and MCP tool schemas will be incomplete for most real endpoints.
