"""Integration tests: verify dynamic commands, aliases, and auth wiring through the CLI."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from mws.cli import app
from mws.schema.build import build_command_tree
from tests.test_schema import MINIMAL_OPENAPI

runner = CliRunner()


def _patch_schema():  # type: ignore[no-untyped-def]
    """Patch schema loading to return our minimal test tree."""
    mock = AsyncMock(return_value=_mock_tree())
    return patch("mws.schema.cache.load_command_tree", mock)


def _mock_tree():  # type: ignore[no-untyped-def]
    return build_command_tree(MINIMAL_OPENAPI)


class TestDynamicCommandsIntegration:
    """F-01: Verify dynamic commands are actually wired into the CLI."""

    def test_dry_run_me_messages_list(self) -> None:
        with _patch_schema():
            result = runner.invoke(app, ["--dry-run", "me", "messages", "list"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["method"] == "GET"
        assert "/me/messages" in data["url"]
        assert data["headers"]["Authorization"] == "Bearer [REDACTED]"

    def test_dry_run_me_messages_get_with_params(self) -> None:
        with _patch_schema():
            result = runner.invoke(
                app,
                [
                    "--dry-run",
                    "--params",
                    '{"message-id": "abc123"}',
                    "me",
                    "messages",
                    "get",
                ],
            )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "/me/messages/abc123" in data["url"]

    def test_dry_run_with_odata_shorthands(self) -> None:
        with _patch_schema():
            result = runner.invoke(
                app,
                [
                    "--dry-run",
                    "--select",
                    "subject,from",
                    "--filter",
                    "isRead eq false",
                    "--top",
                    "5",
                    "--orderby",
                    "receivedDateTime desc",
                    "me",
                    "messages",
                    "list",
                ],
            )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["params"]["$select"] == "subject,from"
        assert data["params"]["$filter"] == "isRead eq false"
        assert data["params"]["$top"] == 5
        assert data["params"]["$orderby"] == "receivedDateTime desc"

    def test_nested_calendar_events(self) -> None:
        with _patch_schema():
            result = runner.invoke(app, ["--dry-run", "me", "calendar", "events", "list"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "/me/calendar/events" in data["url"]


class TestAliasIntegration:
    """F-02: Verify alias resolution works."""

    def test_alias_mail_list_expands(self) -> None:
        from mws.engine.aliases import resolve_alias

        expanded = resolve_alias(["mail", "list", "--top", "5"])
        assert expanded == ["me", "messages", "list", "--top", "5"]

    def test_alias_cal_list_expands(self) -> None:
        from mws.engine.aliases import resolve_alias

        expanded = resolve_alias(["cal", "list"])
        assert expanded == ["me", "calendar", "events", "list"]


class TestAuthWiring:
    """F-03: Verify auth is resolved for non-dry-run, skipped for dry-run."""

    def test_dry_run_skips_auth(self) -> None:
        with _patch_schema():
            result = runner.invoke(app, ["--dry-run", "me", "messages", "list"])
        assert result.exit_code == 0, result.output

    def test_no_auth_shows_error(self) -> None:
        """Without --dry-run and no auth config, should show auth error."""
        from mws.auth.config import AuthConfig, ProfileConfig

        with (
            _patch_schema(),
            patch("mws.auth.client_creds.ClientCredentialAuth.from_env", return_value=None),
            patch("mws.auth.config.load_config", return_value=AuthConfig()),
            patch(
                "mws.auth.config.resolve_effective_profile",
                return_value=("default", ProfileConfig()),
            ),
        ):
            result = runner.invoke(app, ["me", "messages", "list"])
        assert result.exit_code == 2


class TestSchemaPathShortcut:
    """F-23: Verify mws schema /me/messages works without 'show' subcommand."""

    def test_schema_path_without_show(self) -> None:
        with patch("mws.schema.introspect._get_tree", return_value=_mock_tree()):
            result = runner.invoke(app, ["schema", "/me/messages"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "methods" in data

    def test_schema_show_still_works(self) -> None:
        with patch("mws.schema.introspect._get_tree", return_value=_mock_tree()):
            result = runner.invoke(app, ["schema", "show", "/me/messages"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "methods" in data
