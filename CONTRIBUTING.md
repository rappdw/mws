# Contributing to mws

## Setup

```bash
git clone <repo-url>
cd mws
git submodule update --init
uv sync --extra dev
```

## Development workflow

```bash
uv run mws --version            # Verify install
uv run pytest                   # Run tests (125 tests)
uv run ruff check src/ tests/   # Lint
uv run ruff format src/ tests/  # Format
uv run mypy src/                # Type check
```

All four checks (tests, ruff check, ruff format, mypy) must pass before submitting a PR. CI runs them automatically.

## Code style

- **Formatter/linter:** ruff, line length 100
- **Type checking:** mypy in strict mode
- **Imports:** sorted by ruff, one import per line for multi-imports
- **Output:** JSON to stdout, errors to stderr as JSON — never print unstructured text

## Testing

- Mock HTTP with `respx`, never make real API calls
- Use `--dry-run` output as the primary assertion surface for executor tests
- Use the `MINIMAL_OPENAPI` fixture from `tests/test_schema.py` for schema-dependent tests
- Integration tests that exercise the full CLI path (alias resolution → Typer dispatch → executor) go in `tests/test_integration.py`

## Architecture

Read [SPECIFICATION.md](SPECIFICATION.md) before making architectural decisions. The key design patterns are documented in [CLAUDE.md](CLAUDE.md).

Reference implementations in `research/` are available as submodules:
- `research/gws/` — primary reference for architecture and output format
- `research/m365/` — reference for Graph API auth and OData patterns

## Commit messages

- Lead with what changed and why, not how
- Keep the first line under 72 characters
- Use the body for detail when the change is non-obvious

## Reporting issues

Open an issue with:
- What you expected to happen
- What actually happened
- The command you ran (use `--dry-run` output if relevant)
- Your Python version and OS
