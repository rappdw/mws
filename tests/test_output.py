"""Phase F tests: output formatting — JSON, NDJSON, table, YAML."""

from __future__ import annotations

import json

from mws.output.format import OutputFormat, format_response


class TestJsonFormat:
    def test_single_object(self) -> None:
        data = {"displayName": "Alice", "id": "123"}
        out = format_response(data, OutputFormat.json)
        parsed = json.loads(out)
        assert parsed["displayName"] == "Alice"

    def test_list_ndjson(self) -> None:
        data = {"value": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}
        out = format_response(data, OutputFormat.json)
        lines = out.strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["id"] == "1"
        assert json.loads(lines[2])["id"] == "3"

    def test_paginated_ndjson(self) -> None:
        data = [
            {"value": [{"id": "1"}]},
            {"value": [{"id": "2"}]},
        ]
        out = format_response(data, OutputFormat.json)
        lines = out.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == "1"

    def test_empty_value_list(self) -> None:
        data = {"value": []}
        out = format_response(data, OutputFormat.json)
        assert out == ""


class TestTableFormat:
    def test_basic_table(self) -> None:
        data = {"value": [{"name": "Alice", "id": "1"}]}
        out = format_response(data, OutputFormat.table)
        assert "Alice" in out
        assert "name" in out

    def test_truncates_long_values(self) -> None:
        long_value = "A" * 100
        data = {"value": [{"subject": long_value}]}
        out = format_response(data, OutputFormat.table)
        assert long_value not in out  # Should be truncated
        assert "A" * 39 in out

    def test_single_object_table(self) -> None:
        data = {"displayName": "Bob", "id": "42"}
        out = format_response(data, OutputFormat.table)
        assert "Bob" in out

    def test_empty_results(self) -> None:
        data = {"value": []}
        out = format_response(data, OutputFormat.table)
        assert "no results" in out


class TestYamlFormat:
    def test_single_object(self) -> None:
        data = {"displayName": "Alice"}
        out = format_response(data, OutputFormat.yaml)
        assert "displayName: Alice" in out

    def test_list_yaml(self) -> None:
        data = {"value": [{"id": "1"}, {"id": "2"}]}
        out = format_response(data, OutputFormat.yaml)
        assert "id: '1'" in out or "id: 1" in out

    def test_paginated_yaml(self) -> None:
        data = [
            {"value": [{"id": "1"}]},
            {"value": [{"id": "2"}]},
        ]
        out = format_response(data, OutputFormat.yaml)
        assert "id" in out


class TestStringFormat:
    def test_accepts_string_format(self) -> None:
        data = {"key": "val"}
        out = format_response(data, "json")
        assert json.loads(out)["key"] == "val"
