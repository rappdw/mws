"""Phase G tests: MCP server — tool generation, filtering, schemas."""

from __future__ import annotations

from mws.mcp.server import (
    _collect_methods,
    _method_input_schema,
    _tool_description,
    _tool_name,
    create_mcp_server,
)
from mws.schema.build import (
    CommandTree,
    MethodNode,
    Parameter,
    ResourceNode,
    build_command_tree,
)
from tests.test_schema import MINIMAL_OPENAPI


def _make_tree() -> CommandTree:
    return build_command_tree(MINIMAL_OPENAPI)


class TestToolNaming:
    def test_basic_name(self) -> None:
        method = MethodNode(
            operation_name="list",
            http_method="GET",
            path_template="/me/messages",
        )
        name = _tool_name(["me", "messages"], method)
        assert name == "mws_me_messages_list"

    def test_nested_name(self) -> None:
        method = MethodNode(
            operation_name="list",
            http_method="GET",
            path_template="/me/calendar/events",
        )
        name = _tool_name(["me", "calendar", "events"], method)
        assert name == "mws_me_calendar_events_list"


class TestToolDescription:
    def test_from_summary(self) -> None:
        method = MethodNode(
            operation_name="list",
            http_method="GET",
            path_template="/me/messages",
            summary="List messages in the signed-in user's mailbox",
        )
        assert "List messages" in _tool_description(method)

    def test_fallback_to_method(self) -> None:
        method = MethodNode(
            operation_name="list",
            http_method="GET",
            path_template="/me/messages",
        )
        desc = _tool_description(method)
        assert "GET" in desc
        assert "/me/messages" in desc


class TestInputSchema:
    def test_includes_parameters(self) -> None:
        method = MethodNode(
            operation_name="list",
            http_method="GET",
            path_template="/me/messages",
            parameters=[
                Parameter(name="$top", location="query", param_type="integer"),
                Parameter(name="$filter", location="query", param_type="string"),
            ],
        )
        schema = _method_input_schema(method)
        assert "properties" in schema
        assert "$top" in schema["properties"]
        assert schema["properties"]["$top"]["type"] == "integer"

    def test_required_params(self) -> None:
        method = MethodNode(
            operation_name="get",
            http_method="GET",
            path_template="/me/messages/{id}",
            parameters=[
                Parameter(name="message-id", location="path", required=True),
            ],
        )
        schema = _method_input_schema(method)
        assert "message-id" in schema["required"]

    def test_includes_body_for_post(self) -> None:
        method = MethodNode(
            operation_name="create",
            http_method="POST",
            path_template="/me/messages",
            has_request_body=True,
            request_body_schema={
                "type": "object",
                "properties": {"subject": {"type": "string"}},
            },
        )
        schema = _method_input_schema(method)
        assert "body" in schema["properties"]


class TestCollectMethods:
    def test_collects_all_methods(self) -> None:
        tree = _make_tree()
        me = tree.children["me"]
        result: list = []
        _collect_methods(me, [], result)
        assert len(result) > 0
        # Should have list, get, create, update, delete for messages + events
        op_names = [m.operation_name for _, m in result]
        assert "list" in op_names
        assert "get" in op_names
        assert "create" in op_names


class TestCreateMcpServer:
    def test_creates_server(self) -> None:
        tree = _make_tree()
        server = create_mcp_server(tree, services=["me"])
        assert server is not None

    def test_services_filter(self) -> None:
        # Create a tree with multiple top-level resources
        tree = _make_tree()
        # Add a fake "users" resource
        tree.children["users"] = ResourceNode(
            name="users",
            methods={
                "list": MethodNode(
                    operation_name="list",
                    http_method="GET",
                    path_template="/users",
                ),
            },
        )

        server_me_only = create_mcp_server(tree, services=["me"])
        server_both = create_mcp_server(tree, services=["me", "users"])

        # We can't easily inspect tool count without running the server,
        # but verify it doesn't error
        assert server_me_only is not None
        assert server_both is not None

    def test_default_services(self) -> None:
        tree = _make_tree()
        server = create_mcp_server(tree)  # Uses DEFAULT_SERVICES
        assert server is not None
