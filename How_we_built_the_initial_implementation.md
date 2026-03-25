# From Specification to Working CLI: How `mws` Was Built

> A narrative account of implementing `mws` with Claude Code — from a single prompt to a reviewed and remediated codebase.
> Total elapsed time: approximately 3 hours across two sessions.

---

## Overview

This document picks up where [How we built the spec](How_we_built_the_spec.md) left off. The specification was complete, the reference implementations (`gws` and `m365`) were available as submodules, and the architecture was well-defined. The question was: how do you get from a 40-page spec to a working CLI?

The answer turned out to be not one large implementation pass but a four-phase process: plan, generate, review, remediate. Each phase revealed something different about how AI-assisted development works at this scale, and about the kinds of errors that emerge when an agent builds a complex system from a specification.

---

## Phase 1: Planning the Implementation (~20 minutes)

The implementation did not start with "build this." It started with planning. Claude Code was given the specification, the reference implementations, and an explicit instruction: use `/plan` mode with `ultrathink` (deep reasoning) to create a multi-phased implementation plan before writing any code.

This mirrors the philosophy from the specification phase — understand the full scope before committing to an approach. Claude Code read `SPECIFICATION.md`, studied the `gws` and `m365` reference source code, and produced a phased plan that sequenced the work: project scaffolding and dependencies first, then the schema engine, then auth, then the dynamic command surface, then output formatting, MCP server, tests, and finally skills and documentation.

The plan was reviewed and approved before any code was written. This is a meaningful constraint — it forces the agent to think about dependency ordering (you can't test dynamic commands without the schema engine) and to commit to an architecture before generating code.

---

## Phase 2: Executing the Plan (~45 minutes)

With the plan approved, Claude Code executed it phase by phase, producing the initial commit: **54 files, 6,513 lines of code**.

```
5fc2776 Initial implementation of mws — Microsoft 365 Graph API CLI
```

What arrived in that single commit was structurally complete:

- **24 Python source files** across 7 modules (`cli`, `auth`, `schema`, `engine`, `client`, `mcp`, `output`)
- **114 tests** covering schema parsing, executor dry-run, client retry/pagination, output formatting, auth flows
- Full project scaffolding: `pyproject.toml`, CI workflow, documentation stubs, MCP server, Claude Code skills
- The two hardest subsystems — the OpenAPI schema engine and the dynamic command builder — were architecturally sound

This is the part that feels almost unremarkable in hindsight: an agent reads a spec, reads reference code, and produces a codebase. It took under an hour. The more interesting part is what happened next.

---

## Phase 3: The Review (~30 minutes)

Rather than immediately testing and fixing forward, the next step was a deliberate pause: a full critical review of the codebase, requested "using ultrathink" — Claude Code's deep reasoning mode.

This was a conscious decision. The initial implementation *looked* complete. Tests passed. The file structure matched the spec. But the question was: **does the CLI actually work end-to-end?**

The review examined every module and produced `REVIEW_FINDINGS.md` — 27 findings across four severity levels:

| Severity | Count | Examples |
|---|---|---|
| **Critical** | 4 | Dynamic commands not wired, aliases never resolved, no auth integration, mypy fails |
| **High** | 7 | Phantom dependency, ignored flags, duplicate type definitions, MCP auth missing |
| **Medium** | 8 | Shallow metadata stripping, no integration tests, hardcoded client ID |
| **Low** | 8 | Missing spec features, skill command mismatches, stub README |

### The pattern of failure

The four critical findings told a specific story about how AI-generated code fails. It wasn't that the components were poorly written — individually, each module was well-structured and internally correct. The failure was in **wiring**:

- **F-01:** `LazySchemaGroup` — the dynamic command engine — was defined, implemented, tested... and never connected to the Typer app. The function `register_dynamic_commands()` existed but was never called. The CLI's entire value proposition was inoperable.

- **F-02:** `resolve_alias()` — the alias expansion layer — was defined, had correct logic, had tests... and was never invoked. No code path called it before Typer dispatch.

- **F-03:** `DeviceCodeAuth`, `ClientCredentialAuth`, `MsalAuth` — three auth implementations, all working in isolation — were never integrated into `GraphClient` construction. Every dynamic command would make unauthenticated requests.

- **F-04:** mypy produced 19 errors. The type stubs for PyYAML weren't in dev dependencies. MSAL's untyped returns needed explicit casts. The CI would be red from the first commit.

The pattern: **components were complete but the glue between them was missing.** This is the characteristic failure mode of AI-generated code at the system level. Each module is internally consistent — the schema parser correctly builds a command tree, the auth layer correctly acquires tokens, the HTTP client correctly retries — but the integration points where one module hands off to another are where errors accumulate.

This is also why the review step mattered. Running `mws me messages list` would have surfaced F-01 immediately. But the review caught all four critical issues, plus 23 others, in a single systematic pass — before any debugging cycle started.

---

## Phase 4: Remediation Planning (~15 minutes)

With 27 findings documented, the next step was not "fix them all" but "plan the fix." Using Claude Code's `/plan` mode, the findings were organized into a phased implementation plan:

1. **Phase 1: Critical wiring** — Connect `LazySchemaGroup` to Typer, wire alias resolution, integrate auth
2. **Phase 2: mypy and dependencies** — Fix type errors, remove phantom dependency, add stubs
3. **Phase 3: High-severity fixes** — Duplicate types, ignored flags, MCP auth, metadata stripping
4. **Phase 4: Medium-severity** — `--orderby` flag, schema path shortcuts, integration tests
5. **Phase 5: Polish** — Skill file corrections, documentation updates

The plan was reviewed and approved before any code was changed. This is the specification-first philosophy carried into the fix cycle: understand the full scope before touching code.

---

## Phase 5: Implementation of Fixes (~90 minutes)

The remediation was executed as a single focused session, producing one commit:

```
1075f98 Fix critical wiring issues: dynamic commands, auth, aliases, and mypy
        20 files changed, 573 insertions(+), 366 deletions(-)
```

### The interesting fixes

**Wiring `LazySchemaGroup` (F-01)** required understanding how Typer and Click interact. Typer's constructor accepts a `cls=` parameter for custom Click Group subclasses — but the class must inherit from `TyperGroup`, not `click.Group` directly. The initial implementation had `LazySchemaGroup(click.Group)`, and the broken `register_dynamic_commands()` tried to monkeypatch Typer's internal Click group after the fact. The fix was one line:

```python
app = typer.Typer(cls=LazySchemaGroup, ...)
```

But discovering that Typer supports `cls=` — and that it requires `TyperGroup` specifically — required reading Typer's source code. This is the kind of framework-specific knowledge that specifications can't easily encode.

**Alias resolution (F-02)** turned out to have the simplest possible fix: mutate `sys.argv` before Typer dispatch. Two lines in `cli_main()`:

```python
from mws.engine.aliases import resolve_alias
sys.argv[1:] = resolve_alias(sys.argv[1:])
```

**Auth integration (F-03)** required a new `_resolve_auth()` function in `commander.py` that centralized the auth resolution logic: try client credentials from environment variables first, fall back to device code flow from the user's profile, return `None` for `--dry-run`. This function is called by both dynamic command callbacks and MCP tool handlers.

**Schema path shortcuts (F-23)** — making `mws schema /me/messages` work without the `show` subcommand — went through three design iterations. The first attempt (a callback with an optional path argument) broke the `list` and `refresh` subcommands because Typer treated subcommand names as the path argument. The solution was a custom `SchemaGroup(TyperGroup)` that intercepts path-like arguments (starting with `/`) in `get_command()` and synthesizes Click commands on the fly.

**Investigating F-08 (pagination auth bypass)** was interesting for what it revealed about review accuracy. The finding claimed that `client.send(request)` bypasses the auth flow because the request is pre-built. An investigation of httpx's source confirmed this was wrong — `send()` *does* invoke the auth flow. The finding was downgraded. Reviews aren't infallible either.

### What the fixes looked like in aggregate

The 11 new integration tests were arguably more important than the code fixes. They tested the full CLI path — from `sys.argv` through alias resolution, through Typer dispatch, through `LazySchemaGroup`, through the executor, and back to `--dry-run` output. These are the tests that would have caught F-01 through F-03 in the first place.

Final state:
- **125 tests passing** (114 original + 11 new integration tests)
- **mypy: 0 errors** (down from 19)
- **ruff: clean** (lint + format)

---

## What This Process Illustrates

### AI-generated code fails at integration, not implementation

The initial codebase had correct schema parsing, correct auth flows, correct HTTP retry logic, correct output formatting — and a CLI that couldn't execute a single dynamic command. The components were individually sound; the wiring between them was missing.

This has implications for how you review AI-generated code. Unit test coverage was high (114 tests), but those tests validated individual modules in isolation. The integration tests that would have caught the critical failures didn't exist. **The test gap matched the code gap exactly: both were at the system boundary.**

### Review-before-fix beats fix-forward

The natural temptation after generating a codebase is to start running it, hit errors, and fix them one at a time. The review-first approach — systematically examining every module before touching anything — found 27 issues in 30 minutes, including subtle ones (metadata stripping depth, MCP auth, phantom dependencies) that fix-forward debugging might have missed for days.

The review also provided a complete inventory that could be prioritized and planned. Phase ordering mattered: fixing `LazySchemaGroup` wiring before auth integration made each subsequent fix testable.

### The spec-to-implementation gap is real but manageable

The specification was detailed and implementation-ready. The initial implementation followed it faithfully at the architectural level. But a specification describes *what the system does*, not *how framework X wires component Y to component Z*. The Typer `cls=` parameter, the `TyperGroup` base class requirement, the `sys.argv` mutation timing — these are implementation details that live below the specification's level of abstraction.

This isn't a flaw in the spec or the implementation — it's the inherent gap between design and code. The three-phase process (generate → review → remediate) is a practical way to cross it.

### The cost structure is inverted

In traditional development, the expensive part is writing code. Review and testing are overhead you try to minimize. With AI-assisted development, the cost structure inverts: generating 6,500 lines of code took 45 minutes. The review, planning, and remediation took over twice that long. **The bottleneck is not generation but verification.**

This suggests that the right investment for AI-assisted projects is in review tooling and integration test infrastructure, not in faster generation.

---

## Artifact Summary

| Artifact | Description |
|---|---|
| `5fc2776` | Initial implementation — 54 files, 6,513 lines, 114 tests |
| `docs/REVIEW_FINDINGS.md` | 27 findings across 4 severity levels (archived) |
| `1075f98` | Remediation — 20 files changed, 573 insertions, 366 deletions |
| `e323b1f` | Review findings archived with commit references |
| `CLAUDE.md` | Updated to reflect post-remediation architecture |
