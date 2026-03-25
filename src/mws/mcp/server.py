"""MCP server mode: expose Graph API operations as MCP tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from mws.schema.build import CommandTree, MethodNode, ResourceNode

# Default services exposed when --services is not specified
DEFAULT_SERVICES = {"me", "users", "groups", "teams", "drive"}
MAX_TOOLS = 128


def _tool_name(resource_path: list[str], method: MethodNode) -> str:
    """Generate a tool name like mws_me_messages_list."""
    parts = ["mws"] + resource_path + [method.operation_name]
    return "_".join(parts)


def _tool_description(method: MethodNode) -> str:
    """Generate a tool description from the method summary."""
    desc = method.summary or f"{method.http_method} {method.path_template}"
    return desc[:200]


def _method_input_schema(method: MethodNode) -> dict[str, Any]:
    """Build a JSON Schema for the tool's input parameters."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for p in method.parameters:
        prop: dict[str, Any] = {"type": p.param_type, "description": p.description}
        if p.enum:
            prop["enum"] = p.enum
        properties[p.name] = prop
        if p.required:
            required.append(p.name)

    if method.has_request_body:
        properties["body"] = method.request_body_schema or {"type": "object"}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _collect_methods(
    node: ResourceNode,
    path: list[str],
    result: list[tuple[list[str], MethodNode]],
) -> None:
    """Recursively collect all methods from a resource tree."""
    current_path = path + [node.name]
    for method in node.methods.values():
        result.append((current_path, method))
    for child in node.children.values():
        _collect_methods(child, current_path, result)


def create_mcp_server(
    tree: CommandTree,
    services: list[str] | None = None,
) -> FastMCP:
    """Create an MCP server from the command tree.

    Args:
        tree: The parsed command tree.
        services: Optional list of top-level resource groups to include.
                  Defaults to DEFAULT_SERVICES.
    """
    mcp = FastMCP("mws", instructions="Microsoft 365 CLI for Graph API")

    allowed_services = set(services) if services else DEFAULT_SERVICES

    # Collect all methods from allowed services
    all_methods: list[tuple[list[str], MethodNode]] = []
    for name, resource in tree.children.items():
        if name in allowed_services:
            _collect_methods(resource, [], all_methods)

    # Limit tool count
    if len(all_methods) > MAX_TOOLS:
        all_methods = all_methods[:MAX_TOOLS]

    # Register each method as a tool
    for resource_path, method in all_methods:
        tool_name = _tool_name(resource_path, method)
        description = _tool_description(method)
        input_schema = _method_input_schema(method)

        # Capture method in closure
        _register_tool(mcp, tool_name, description, input_schema, method)

    return mcp


def _register_tool(
    mcp: FastMCP,
    name: str,
    description: str,
    input_schema: dict[str, Any],
    method: MethodNode,
) -> None:
    """Register a single tool on the MCP server."""

    @mcp.tool(name=name, description=description)
    async def tool_handler(**kwargs: Any) -> str:
        from mws.client.graph import GraphClient
        from mws.engine.executor import execute

        client = GraphClient(api_version="v1.0")
        body = kwargs.pop("body", None)

        try:
            result = await execute(
                method_node=method,
                params_json=json.dumps(kwargs) if kwargs else None,
                body_json=json.dumps(body) if body else None,
                select=None,
                filter_expr=None,
                top=None,
                dry_run=False,
                page_all=False,
                page_limit=10,
                client=client,
            )
            return json.dumps(result, ensure_ascii=False)
        finally:
            await client.close()
