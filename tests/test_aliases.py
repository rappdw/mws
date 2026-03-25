"""Phase F tests: alias resolution and aliases list command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from mws.cli import app
from mws.engine.aliases import list_aliases, resolve_alias


class TestResolveAlias:
    def test_mail_list(self) -> None:
        assert resolve_alias(["mail", "list", "--top", "5"]) == [
            "me",
            "messages",
            "list",
            "--top",
            "5",
        ]

    def test_cal_list(self) -> None:
        assert resolve_alias(["cal", "list"]) == [
            "me",
            "calendar",
            "events",
            "list",
        ]

    def test_drive_ls(self) -> None:
        assert resolve_alias(["drive", "ls"]) == [
            "me",
            "drive",
            "root",
            "children",
            "list",
        ]

    def test_unknown_passthrough(self) -> None:
        assert resolve_alias(["users", "list"]) == ["users", "list"]

    def test_empty_passthrough(self) -> None:
        assert resolve_alias([]) == []

    def test_preserves_trailing_args(self) -> None:
        result = resolve_alias(["mail", "get", "--format", "table"])
        assert result == ["me", "messages", "get", "--format", "table"]


class TestListAliases:
    def test_returns_list(self) -> None:
        aliases = list_aliases()
        assert isinstance(aliases, list)
        assert len(aliases) > 0

    def test_alias_structure(self) -> None:
        aliases = list_aliases()
        for a in aliases:
            assert "alias" in a
            assert "expands_to" in a
            assert "description" in a

    def test_mail_list_in_aliases(self) -> None:
        aliases = list_aliases()
        alias_names = [a["alias"] for a in aliases]
        assert "mail list" in alias_names


class TestAliasesCommand:
    def test_aliases_list(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["aliases", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert any(a["alias"] == "mail list" for a in data)
