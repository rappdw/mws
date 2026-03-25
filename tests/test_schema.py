"""Phase D tests: schema engine — build, cache, introspect."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from mws.cli import app
from mws.schema.build import CommandTree, build_command_tree

# Minimal OpenAPI 3.0 fixture for testing
MINIMAL_OPENAPI: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Graph API", "version": "v1.0"},
    "paths": {
        "/me/messages": {
            "get": {
                "summary": "List messages",
                "parameters": [
                    {"name": "$top", "in": "query", "schema": {"type": "integer"}},
                    {"name": "$filter", "in": "query", "schema": {"type": "string"}},
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "summary": "Create message",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"subject": {"type": "string"}},
                            },
                        }
                    }
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/me/messages/{message-id}": {
            "parameters": [
                {
                    "name": "message-id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            ],
            "get": {
                "summary": "Get message",
                "responses": {"200": {"description": "OK"}},
            },
            "patch": {
                "summary": "Update message",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"},
                        }
                    }
                },
                "responses": {"200": {"description": "OK"}},
            },
            "delete": {
                "summary": "Delete message",
                "responses": {"204": {"description": "No Content"}},
            },
        },
        "/me/calendar/events": {
            "get": {
                "summary": "List events",
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/me/calendar/events/{event-id}": {
            "parameters": [
                {
                    "name": "event-id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            ],
            "get": {
                "summary": "Get event",
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}

MINIMAL_OPENAPI_YAML = yaml.dump(MINIMAL_OPENAPI)


class TestBuildCommandTree:
    def test_top_level_resources(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        assert "me" in tree.children

    def test_nested_resources(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        me = tree.children["me"]
        assert "messages" in me.children
        assert "calendar" in me.children

    def test_deeply_nested_resources(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        calendar = tree.children["me"].children["calendar"]
        assert "events" in calendar.children

    def test_list_method_on_collection(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        messages = tree.children["me"].children["messages"]
        assert "list" in messages.methods
        assert messages.methods["list"].http_method == "GET"
        assert messages.methods["list"].path_template == "/me/messages"

    def test_get_method_on_item(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        messages = tree.children["me"].children["messages"]
        assert "get" in messages.methods
        assert messages.methods["get"].http_method == "GET"
        assert "{message-id}" in messages.methods["get"].path_template

    def test_create_method(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        messages = tree.children["me"].children["messages"]
        assert "create" in messages.methods
        assert messages.methods["create"].http_method == "POST"
        assert messages.methods["create"].has_request_body

    def test_update_method(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        messages = tree.children["me"].children["messages"]
        assert "update" in messages.methods
        assert messages.methods["update"].http_method == "PATCH"

    def test_delete_method(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        messages = tree.children["me"].children["messages"]
        assert "delete" in messages.methods
        assert messages.methods["delete"].http_method == "DELETE"

    def test_parameters_extracted(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        messages = tree.children["me"].children["messages"]
        list_method = messages.methods["list"]
        param_names = {p.name for p in list_method.parameters}
        assert "$top" in param_names
        assert "$filter" in param_names

    def test_path_parameters_from_path_item(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        messages = tree.children["me"].children["messages"]
        get_method = messages.methods["get"]
        path_params = [p for p in get_method.parameters if p.location == "path"]
        assert any(p.name == "message-id" for p in path_params)

    def test_request_body_schema(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        create_method = tree.children["me"].children["messages"].methods["create"]
        assert create_method.request_body_schema is not None
        assert "properties" in create_method.request_body_schema

    def test_resolve_path(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        result = tree.resolve_path(["me", "messages"])
        assert result is not None
        assert result.name == "messages"  # type: ignore

    def test_resolve_path_method(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        result = tree.resolve_path(["me", "messages", "list"])
        assert result is not None
        assert result.operation_name == "list"  # type: ignore

    def test_resolve_path_not_found(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        result = tree.resolve_path(["nonexistent"])
        assert result is None

    def test_list_top_level(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        top = tree.list_top_level()
        assert "me" in top

    def test_empty_spec(self) -> None:
        tree = build_command_tree({"paths": {}})
        assert tree.children == {}


class TestCommandTreeSerialization:
    def test_round_trip(self) -> None:
        tree = build_command_tree(MINIMAL_OPENAPI)
        data = tree.to_dict()
        restored = CommandTree.from_index(data)
        assert restored.list_top_level() == tree.list_top_level()
        messages = restored.children["me"].children["messages"]
        assert "list" in messages.methods
        assert "get" in messages.methods
        assert "create" in messages.methods


class TestSchemaCache:
    @pytest.mark.asyncio
    async def test_cache_miss_fetches(self, tmp_path: Path) -> None:
        with patch("mws.schema.cache.fetch_openapi_spec", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MINIMAL_OPENAPI_YAML.encode()
            from mws.schema.cache import load_command_tree

            tree = await load_command_tree("v1.0", cache_dir=tmp_path, quiet=True)

        assert "me" in tree.children
        assert (tmp_path / "graph-openapi-v1.0.yaml").exists()
        assert (tmp_path / "graph-index-v1.0.json").exists()
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_no_fetch(self, tmp_path: Path) -> None:
        # Pre-populate cache
        spec_file = tmp_path / "graph-openapi-v1.0.yaml"
        spec_file.write_text(MINIMAL_OPENAPI_YAML)
        index_file = tmp_path / "graph-index-v1.0.json"
        tree = build_command_tree(MINIMAL_OPENAPI)
        index_file.write_text(json.dumps(tree.to_dict()))

        with patch("mws.schema.cache.fetch_openapi_spec", new_callable=AsyncMock) as mock_fetch:
            from mws.schema.cache import load_command_tree

            result = await load_command_tree("v1.0", cache_dir=tmp_path, quiet=True)

        mock_fetch.assert_not_called()
        assert "me" in result.children

    @pytest.mark.asyncio
    async def test_force_refresh(self, tmp_path: Path) -> None:
        # Pre-populate cache
        spec_file = tmp_path / "graph-openapi-v1.0.yaml"
        spec_file.write_text(MINIMAL_OPENAPI_YAML)
        index_file = tmp_path / "graph-index-v1.0.json"
        tree = build_command_tree(MINIMAL_OPENAPI)
        index_file.write_text(json.dumps(tree.to_dict()))

        with patch("mws.schema.cache.fetch_openapi_spec", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MINIMAL_OPENAPI_YAML.encode()
            from mws.schema.cache import load_command_tree

            await load_command_tree("v1.0", cache_dir=tmp_path, force_refresh=True, quiet=True)

        mock_fetch.assert_called_once()


class TestSchemaCommands:
    def _mock_tree(self) -> CommandTree:
        return build_command_tree(MINIMAL_OPENAPI)

    def test_schema_list(self, cli_runner: CliRunner) -> None:
        with patch("mws.schema.introspect._get_tree", return_value=self._mock_tree()):
            result = cli_runner.invoke(app, ["schema", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert "me" in data

    def test_schema_show_resource(self, cli_runner: CliRunner) -> None:
        with patch("mws.schema.introspect._get_tree", return_value=self._mock_tree()):
            result = cli_runner.invoke(app, ["schema", "show", "/me/messages"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "methods" in data
        assert "resource" in data

    def test_schema_show_with_method_filter(self, cli_runner: CliRunner) -> None:
        with patch("mws.schema.introspect._get_tree", return_value=self._mock_tree()):
            result = cli_runner.invoke(app, ["schema", "show", "/me/messages", "--method", "GET"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        methods = data["methods"]
        assert all(m["httpMethod"] == "GET" for m in methods)

    def test_schema_show_not_found(self, cli_runner: CliRunner) -> None:
        with patch("mws.schema.introspect._get_tree", return_value=self._mock_tree()):
            result = cli_runner.invoke(app, ["schema", "show", "/nonexistent"])
        assert result.exit_code == 3
