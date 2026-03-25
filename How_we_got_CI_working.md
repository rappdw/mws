# How We Got CI Working

> Debugging two test failures that only appeared in GitHub Actions.
> Total elapsed time: approximately 30 minutes.

---

## Overview

After pushing the initial implementation and remediation, CI failed on every run. All 125 tests passed locally, but two tests consistently failed in GitHub Actions. This document captures what went wrong and why — both failures illustrate the gap between local development and CI environments.

---

## The Failures

CI reported two test failures on both Python 3.11 and 3.12:

```
FAILED tests/test_aliases.py::TestAliasesCommand::test_aliases_list
  - json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

FAILED tests/test_scaffold.py::test_help_shows_global_flags
  - AssertionError: Missing flag --format in help output
```

Both tests passed locally every time. 125 tests total, 123 passing on CI.

---

## Failure 1: The 2-Minute Alias Test

### Symptom

`test_aliases_list` took **over 2 minutes** before failing with a `JSONDecodeError` — the command output was empty instead of the expected JSON array of aliases.

### Root cause

The test invokes `app` with `["aliases", "list"]`. The root Typer app uses `cls=LazySchemaGroup`, which overrides `get_command()`:

```python
def get_command(self, ctx, cmd_name):
    self._ensure_schema()           # ← triggers schema fetch BEFORE checking static commands
    return super().get_command(ctx, cmd_name)
```

`_ensure_schema()` downloads the Microsoft Graph OpenAPI spec (~50MB YAML) from `https://aka.ms/graph/v1.0/openapi.yaml`. Locally, this is cached at `~/.cache/mws/`. On CI, there's no cache — every run starts fresh.

The `aliases` command is a static Typer subcommand that doesn't need the schema at all. But because `get_command()` unconditionally called `_ensure_schema()` before checking whether the command was already registered, even static commands paid the full schema fetch cost.

On CI, this fetch either timed out or produced an error that left the command output empty, causing `json.loads()` to fail on an empty string.

### Fix

Check static (Typer-registered) commands first. Only load the schema for unknown commands that might be dynamic API commands:

```python
def get_command(self, ctx, cmd_name):
    cmd = super().get_command(ctx, cmd_name)   # ← try static commands first
    if cmd is not None:
        return cmd
    self._ensure_schema()                       # ← only fetch schema for unknown commands
    return super().get_command(ctx, cmd_name)
```

This means `mws aliases list`, `mws auth login`, `mws schema list`, and other static commands never trigger schema loading. Only actual dynamic API commands (`mws me messages list`, `mws users list`, etc.) trigger the fetch.

### Lesson

**Lazy loading should be truly lazy.** The original implementation deferred schema loading from import time to first command access — but then loaded it unconditionally for *every* command access, including commands that don't need it. The correct boundary is: load the schema only when a command is requested that isn't already registered.

---

## Failure 2: The ANSI Escape Code Test

### Symptom

`test_help_shows_global_flags` asserted `"--format" in result.output` and failed, even though `--format` was clearly visible in the help output.

### Root cause

Rich (Typer's default output library) renders help text with ANSI escape codes for color and styling. The flag `--format` was rendered as:

```
\x1b[1;36m-\x1b[0m\x1b[1;36m-format\x1b[0m
```

That's `-` (cyan, bold) + `-format` (cyan, bold) — visually `--format`, but the literal string `--format` doesn't appear as a contiguous substring because ANSI codes are inserted between the two dashes.

Locally, this test passed because the terminal configuration happened to produce output where `--format` appeared as a contiguous string (possibly due to different terminal width or color settings).

### Fix

Strip ANSI escape codes before asserting:

```python
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

def test_help_shows_global_flags(cli_runner):
    result = cli_runner.invoke(app, ["--help"])
    output = _strip_ansi(result.output)
    for flag in ["--format", "--dry-run", ...]:
        assert flag in output, f"Missing flag {flag} in help output"
```

### Lesson

**Never assert on raw Rich/Typer output without stripping ANSI codes.** The presence and placement of escape codes depends on terminal capabilities, width, and color configuration — all of which differ between local development and CI. Either strip ANSI codes before matching, or use a CLI runner configured with `color_system=None`.

---

## What This Illustrates

### CI is a different environment in ways you don't expect

Both failures were invisible locally:
- The schema cache masked the lazy-loading bug — the fetch completed instantly from disk
- The terminal configuration masked the ANSI bug — escape codes happened to not split flag names

Neither failure was a logic error in the application code. Both were environment-dependent test issues that only surfaced in the clean, cacheless, headless CI environment.

### Static vs. dynamic command boundaries matter

The `LazySchemaGroup` design is correct — dynamic commands should be loaded lazily from the schema. But the boundary between "static commands that are always available" and "dynamic commands that require schema loading" was not enforced in `get_command()`. This is a common pattern in CLIs with plugin systems: the plugin loader should not activate until a plugin command is actually requested.

---

## Artifact Summary

| Artifact | Description |
|---|---|
| `src/mws/engine/commander.py` | `get_command()` now checks static commands before loading schema |
| `tests/test_scaffold.py` | ANSI stripping for help output assertions |
