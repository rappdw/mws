"""Output formatters: JSON, table, YAML."""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from typing import Any


class OutputFormat(StrEnum):
    json = "json"
    table = "table"
    yaml = "yaml"


MAX_TABLE_WIDTH = 40
MAX_TABLE_COLUMNS = 5


def _truncate(value: str, max_len: int = MAX_TABLE_WIDTH) -> str:
    if len(value) > max_len:
        return value[: max_len - 1] + "…"
    return value


def _format_json(data: Any) -> str:
    """Format as JSON. NDJSON for lists, pretty for single objects."""
    if isinstance(data, list):
        # List of pages — emit each item as NDJSON
        lines = []
        for page in data:
            if isinstance(page, dict) and "value" in page:
                for item in page["value"]:
                    lines.append(json.dumps(item, ensure_ascii=False))
            else:
                lines.append(json.dumps(page, ensure_ascii=False))
        return "\n".join(lines)
    elif isinstance(data, dict) and "value" in data and isinstance(data["value"], list):
        # Single page with value array — NDJSON
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in data["value"])
    else:
        return json.dumps(data, indent=2, ensure_ascii=False)


def _format_table(data: Any, select_fields: list[str] | None = None) -> str:
    """Format as a Rich table."""
    from rich.console import Console
    from rich.table import Table

    # Extract items
    items: list[dict[str, Any]] = []
    if isinstance(data, list):
        for page in data:
            if isinstance(page, dict) and "value" in page:
                items.extend(page["value"])
            elif isinstance(page, dict):
                items.append(page)
    elif isinstance(data, dict) and "value" in data and isinstance(data["value"], list):
        items = data["value"]
    elif isinstance(data, dict):
        items = [data]

    if not items:
        return "(no results)"

    # Determine columns
    columns = select_fields or list(items[0].keys())[:MAX_TABLE_COLUMNS]

    table = Table()
    for col in columns:
        table.add_column(col)

    for item in items:
        row = []
        for col in columns:
            val = item.get(col, "")
            row.append(_truncate(str(val)))
        table.add_row(*row)

    console = Console(file=sys.stdout, no_color=False)
    with console.capture() as capture:
        console.print(table)
    return capture.get()


def _format_yaml(data: Any) -> str:
    """Format as YAML."""
    import yaml

    # For paginated data, extract value items
    if isinstance(data, list):
        items = []
        for page in data:
            if isinstance(page, dict) and "value" in page:
                items.extend(page["value"])
            else:
                items.append(page)
        return yaml.dump(items, default_flow_style=False, allow_unicode=True)
    elif isinstance(data, dict) and "value" in data and isinstance(data["value"], list):
        return yaml.dump(data["value"], default_flow_style=False, allow_unicode=True)
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


def format_response(data: Any, fmt: OutputFormat | str) -> str:
    """Format response data according to the chosen output format."""
    fmt_str = fmt.value if isinstance(fmt, OutputFormat) else fmt
    if fmt_str == "table":
        return _format_table(data)
    elif fmt_str == "yaml":
        return _format_yaml(data)
    return _format_json(data)


def format_and_print(data: Any, fmt: Any, quiet: bool = False) -> None:
    """Format and print response data to stdout."""
    if quiet:
        return
    fmt_value = fmt.value if hasattr(fmt, "value") else str(fmt)
    output = format_response(data, fmt_value)
    if output:
        print(output)
