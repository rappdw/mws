"""Phase A scaffold tests: version, help, global flags, error types."""

from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from mws.cli import app
from mws.errors import (
    ApiError,
    AuthError,
    NotFoundError,
    PermissionDeniedError,
    ThrottledError,
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def test_version_output(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--version"])
    assert "0.1.0" in result.output
    assert result.exit_code == 0


def test_help_shows_global_flags(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    for flag in [
        "--format",
        "--dry-run",
        "--api-version",
        "--profile",
        "--params",
        "--body",
        "--select",
        "--filter",
        "--top",
        "--page-all",
        "--page-limit",
        "--verbose",
        "--quiet",
        "--no-color",
    ]:
        assert flag in output, f"Missing flag {flag} in help output"


def test_no_args_shows_help(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, [])
    # Typer's no_args_is_help returns exit code 2
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output


def test_api_error_json() -> None:
    err = ApiError(message="Resource not found", status=404)
    j = err.to_json()
    assert j["error"] == "api_error"
    assert j["message"] == "Resource not found"
    assert j["status"] == 404
    assert err.exit_code == 1


def test_auth_error_exit_code() -> None:
    err = AuthError(message="No credentials")
    assert err.exit_code == 2
    assert err.to_json()["error"] == "auth_error"


def test_not_found_error_exit_code() -> None:
    err = NotFoundError(message="Not found")
    assert err.exit_code == 3
    assert err.to_json()["error"] == "not_found"


def test_permission_denied_error_exit_code() -> None:
    err = PermissionDeniedError(message="Forbidden")
    assert err.exit_code == 4
    assert err.to_json()["error"] == "permission_denied"


def test_throttled_error_json() -> None:
    err = ThrottledError(message="Too many requests", retry_after=30)
    assert err.exit_code == 5
    j = err.to_json()
    assert j["error"] == "throttled"
    assert j["retry_after"] == 30


def test_error_print_and_exit(cli_runner: CliRunner, capsys: object) -> None:
    import io
    import sys

    err = ApiError(message="Bad request", status=400)
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        err.print_and_exit()
    except SystemExit as e:
        assert e.code == 1
        output = sys.stderr.getvalue()
        parsed = json.loads(output)
        assert parsed["error"] == "api_error"
        assert parsed["status"] == 400
    finally:
        sys.stderr = old_stderr
