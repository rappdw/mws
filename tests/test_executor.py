"""Phase E tests: executor — dry-run, path substitution, param validation."""

from __future__ import annotations

import io

import pytest

from mws.client.graph import GraphClient
from mws.engine.executor import (
    execute,
    merge_odata_params,
    parse_json_arg,
    substitute_path_params,
    validate_required_params,
)
from mws.errors import MwsError
from mws.schema.build import MethodNode, Parameter


@pytest.fixture
def list_messages_method() -> MethodNode:
    return MethodNode(
        operation_name="list",
        http_method="GET",
        path_template="/me/messages",
        parameters=[
            Parameter(name="$top", location="query", param_type="integer"),
            Parameter(name="$filter", location="query", param_type="string"),
        ],
        summary="List messages",
    )


@pytest.fixture
def get_message_method() -> MethodNode:
    return MethodNode(
        operation_name="get",
        http_method="GET",
        path_template="/me/messages/{message-id}",
        parameters=[
            Parameter(name="message-id", location="path", required=True, param_type="string"),
        ],
        summary="Get message",
    )


@pytest.fixture
def create_message_method() -> MethodNode:
    return MethodNode(
        operation_name="create",
        http_method="POST",
        path_template="/me/messages",
        has_request_body=True,
        request_body_schema={"type": "object"},
        summary="Create message",
    )


class TestMergeOdataParams:
    def test_merge_select(self) -> None:
        result = merge_odata_params(None, select="subject,from", filter_expr=None, top=None)
        assert result["$select"] == "subject,from"

    def test_merge_filter(self) -> None:
        result = merge_odata_params(None, select=None, filter_expr="isRead eq false", top=None)
        assert result["$filter"] == "isRead eq false"

    def test_merge_top(self) -> None:
        result = merge_odata_params(None, select=None, filter_expr=None, top=5)
        assert result["$top"] == 5

    def test_merge_preserves_existing(self) -> None:
        result = merge_odata_params(
            {"$orderby": "receivedDateTime desc"},
            select="subject",
            filter_expr=None,
            top=None,
        )
        assert result["$orderby"] == "receivedDateTime desc"
        assert result["$select"] == "subject"

    def test_merge_all(self) -> None:
        result = merge_odata_params(
            {"$orderby": "date"},
            select="subject,from",
            filter_expr="isRead eq false",
            top=10,
        )
        assert len(result) == 4


class TestSubstitutePathParams:
    def test_single_param(self) -> None:
        url, remaining = substitute_path_params(
            "/me/messages/{message-id}",
            {"message-id": "abc123", "$top": 5},
        )
        assert url == "/me/messages/abc123"
        assert "message-id" not in remaining
        assert remaining["$top"] == 5

    def test_multiple_params(self) -> None:
        url, remaining = substitute_path_params(
            "/users/{user-id}/messages/{message-id}",
            {"user-id": "u1", "message-id": "m1"},
        )
        assert url == "/users/u1/messages/m1"
        assert remaining == {}

    def test_no_params(self) -> None:
        url, remaining = substitute_path_params("/me/messages", {"$top": 10})
        assert url == "/me/messages"
        assert remaining == {"$top": 10}


class TestValidateRequiredParams:
    def test_passes_when_present(self, get_message_method: MethodNode) -> None:
        validate_required_params(get_message_method, {"message-id": "abc"})

    def test_raises_when_missing(self, get_message_method: MethodNode) -> None:
        with pytest.raises(MwsError, match="message-id"):
            validate_required_params(get_message_method, {})


class TestParseJsonArg:
    def test_none(self) -> None:
        assert parse_json_arg(None) is None

    def test_json_string(self) -> None:
        result = parse_json_arg('{"key": "value"}')
        assert result == {"key": "value"}

    def test_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO('{"subject": "Test"}'))
        result = parse_json_arg("-")
        assert result == {"subject": "Test"}


class TestDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_output(self, list_messages_method: MethodNode) -> None:
        client = GraphClient(api_version="v1.0")
        result = await execute(
            method_node=list_messages_method,
            params_json='{"$top": 10}',
            body_json=None,
            select=None,
            filter_expr="isRead eq false",
            top=None,
            dry_run=True,
            page_all=False,
            page_limit=10,
            client=client,
        )
        assert result["method"] == "GET"
        assert "me/messages" in result["url"]
        assert result["params"]["$top"] == 10
        assert result["params"]["$filter"] == "isRead eq false"
        assert result["headers"]["Authorization"] == "Bearer [REDACTED]"
        await client.close()

    @pytest.mark.asyncio
    async def test_dry_run_with_path_params(self, get_message_method: MethodNode) -> None:
        client = GraphClient(api_version="v1.0")
        result = await execute(
            method_node=get_message_method,
            params_json='{"message-id": "abc123"}',
            body_json=None,
            select=None,
            filter_expr=None,
            top=None,
            dry_run=True,
            page_all=False,
            page_limit=10,
            client=client,
        )
        assert "/me/messages/abc123" in result["url"]
        assert "message-id" not in result["params"]
        await client.close()

    @pytest.mark.asyncio
    async def test_dry_run_with_body(self, create_message_method: MethodNode) -> None:
        client = GraphClient(api_version="v1.0")
        result = await execute(
            method_node=create_message_method,
            params_json=None,
            body_json='{"subject": "Hello"}',
            select=None,
            filter_expr=None,
            top=None,
            dry_run=True,
            page_all=False,
            page_limit=10,
            client=client,
        )
        assert result["method"] == "POST"
        assert result["body"] == {"subject": "Hello"}
        await client.close()

    @pytest.mark.asyncio
    async def test_dry_run_odata_shorthands(self, list_messages_method: MethodNode) -> None:
        client = GraphClient(api_version="v1.0")
        result = await execute(
            method_node=list_messages_method,
            params_json=None,
            body_json=None,
            select="subject,from",
            filter_expr="isRead eq false",
            top=5,
            dry_run=True,
            page_all=False,
            page_limit=10,
            client=client,
        )
        assert result["params"]["$select"] == "subject,from"
        assert result["params"]["$filter"] == "isRead eq false"
        assert result["params"]["$top"] == 5
        await client.close()
