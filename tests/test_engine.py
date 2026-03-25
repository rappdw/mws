"""Phase E tests: dynamic command builder from schema tree."""

from __future__ import annotations

import click
from click.testing import CliRunner as ClickRunner

from mws.engine.commander import _build_method_command, _build_resource_group
from mws.schema.build import (
    CommandTree,
    MethodNode,
    ResourceNode,
    build_command_tree,
)
from tests.test_schema import MINIMAL_OPENAPI


def _make_test_tree() -> CommandTree:
    return build_command_tree(MINIMAL_OPENAPI)


class TestBuildMethodCommand:
    def test_creates_click_command(self) -> None:
        method = MethodNode(
            operation_name="list",
            http_method="GET",
            path_template="/me/messages",
            summary="List messages",
        )
        cmd = _build_method_command(method)
        assert isinstance(cmd, click.Command)
        assert cmd.name == "list"

    def test_help_text_from_summary(self) -> None:
        method = MethodNode(
            operation_name="get",
            http_method="GET",
            path_template="/me/messages/{id}",
            summary="Get a specific message",
        )
        cmd = _build_method_command(method)
        assert "Get a specific message" in (cmd.help or "")


class TestBuildResourceGroup:
    def test_creates_group_with_methods(self) -> None:
        resource = ResourceNode(
            name="messages",
            methods={
                "list": MethodNode(
                    operation_name="list",
                    http_method="GET",
                    path_template="/me/messages",
                ),
                "create": MethodNode(
                    operation_name="create",
                    http_method="POST",
                    path_template="/me/messages",
                    has_request_body=True,
                ),
            },
        )
        group = _build_resource_group(resource)
        assert isinstance(group, click.Group)
        assert "list" in group.commands
        assert "create" in group.commands

    def test_nested_children(self) -> None:
        tree = _make_test_tree()
        me = tree.children["me"]
        group = _build_resource_group(me)

        # me should have messages and calendar as subgroups
        assert "messages" in group.commands
        assert "calendar" in group.commands

        # messages should have list, get, create, etc.
        messages_group = group.commands["messages"]
        assert isinstance(messages_group, click.Group)

    def test_help_output(self) -> None:
        tree = _make_test_tree()
        me = tree.children["me"]
        group = _build_resource_group(me)

        runner = ClickRunner()
        result = runner.invoke(group, ["messages", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output

    def test_deeply_nested_help(self) -> None:
        tree = _make_test_tree()
        me = tree.children["me"]
        group = _build_resource_group(me)

        runner = ClickRunner()
        result = runner.invoke(group, ["calendar", "events", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
