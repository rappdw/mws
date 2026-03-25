"""Translate CLI invocation into a Graph HTTP request."""

from __future__ import annotations

import json
import sys
from typing import Any

from mws.client.graph import GraphClient
from mws.errors import MwsError
from mws.schema.build import MethodNode


def merge_odata_params(
    params: dict[str, Any] | None,
    select: str | None,
    filter_expr: str | None,
    top: int | None,
) -> dict[str, Any]:
    """Merge --select, --filter, --top shorthands into the params dict."""
    result = dict(params) if params else {}
    if select:
        result["$select"] = select
    if filter_expr:
        result["$filter"] = filter_expr
    if top is not None:
        result["$top"] = top
    return result


def substitute_path_params(
    path_template: str,
    params: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Substitute path parameters into the URL template.

    Returns (resolved_url, remaining_query_params).
    """
    import re

    remaining = dict(params)
    path = path_template

    # Find all {param-name} placeholders
    for match in re.finditer(r"\{([^}]+)\}", path_template):
        param_name = match.group(1)
        if param_name in remaining:
            path = path.replace(f"{{{param_name}}}", str(remaining.pop(param_name)))

    return path, remaining


def validate_required_params(method: MethodNode, params: dict[str, Any]) -> None:
    """Check that all required parameters are provided."""
    for p in method.parameters:
        if p.required and p.name not in params:
            raise MwsError(
                message=f"Missing required parameter: {p.name}",
                exit_code=1,
                error_code="validation_error",
            )


def parse_json_arg(value: str | None) -> dict[str, Any] | None:
    """Parse a JSON string argument, supporting '-' for stdin."""
    if value is None:
        return None
    if value == "-":
        return json.load(sys.stdin)
    return json.loads(value)


def build_dry_run_output(
    method: str,
    url: str,
    query_params: dict[str, Any],
    body: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the --dry-run output dict."""
    result: dict[str, Any] = {
        "method": method,
        "url": url,
        "params": query_params if query_params else {},
        "headers": {"Authorization": "Bearer [REDACTED]"},
    }
    if body:
        result["body"] = body
    return result


async def execute(
    method_node: MethodNode,
    params_json: str | None,
    body_json: str | None,
    select: str | None,
    filter_expr: str | None,
    top: int | None,
    dry_run: bool,
    page_all: bool,
    page_limit: int,
    client: GraphClient,
) -> Any:
    """Execute a Graph API operation.

    Returns the response data (dict or list of pages for paginated).
    """
    # Parse JSON arguments
    params = parse_json_arg(params_json) or {}
    body = parse_json_arg(body_json)

    # Merge OData shorthands
    params = merge_odata_params(params, select, filter_expr, top)

    # Validate required params
    validate_required_params(method_node, params)

    # Substitute path params
    url, query_params = substitute_path_params(method_node.path_template, params)

    # Build full URL
    full_url = f"https://graph.microsoft.com/{client.api_version}{url}"

    if dry_run:
        return build_dry_run_output(method_node.http_method, full_url, query_params, body)

    # Execute
    if page_all and method_node.http_method == "GET":
        pages = []
        async for page in client.paginate(
            method_node.http_method, url, params=query_params, page_limit=page_limit
        ):
            pages.append(page)
        return pages
    else:
        return await client.request(
            method_node.http_method,
            url,
            params=query_params,
            json_body=body,
        )
