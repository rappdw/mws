"""Schema introspection CLI commands: mws schema list/refresh/<path>."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer

from mws.schema.build import CommandTree, MethodNode, ResourceNode

schema_app = typer.Typer(help="Introspect the Graph API schema.")

# Lazy-loaded tree cache (per api_version)
_tree_cache: dict[str, CommandTree] = {}


def _get_tree(api_version: str, force_refresh: bool = False, quiet: bool = False) -> CommandTree:
    """Get or load the command tree (with caching)."""
    if not force_refresh and api_version in _tree_cache:
        return _tree_cache[api_version]

    from mws.schema.cache import load_command_tree

    tree = asyncio.run(load_command_tree(api_version, force_refresh=force_refresh, quiet=quiet))
    _tree_cache[api_version] = tree
    return tree


def _clear_tree_cache() -> None:
    _tree_cache.clear()


@schema_app.command("list")
def schema_list(
    api_version: Annotated[
        str,
        typer.Option("--api-version", help="Graph API version.", envvar="MWS_API_VERSION"),
    ] = "v1.0",
) -> None:
    """List all top-level resource groups."""
    tree = _get_tree(api_version)
    groups = tree.list_top_level()
    print(json.dumps(groups, indent=2))


@schema_app.command("refresh")
def schema_refresh(
    api_version: Annotated[
        str,
        typer.Option("--api-version", help="Graph API version.", envvar="MWS_API_VERSION"),
    ] = "v1.0",
) -> None:
    """Force re-download of the Graph API schema."""
    _clear_tree_cache()
    _get_tree(api_version, force_refresh=True)
    print(json.dumps({"status": "refreshed", "api_version": api_version}))


@schema_app.command("show")
def schema_show(
    path: Annotated[str, typer.Argument(help="Resource path (e.g., /me/messages).")],
    method: Annotated[
        str | None,
        typer.Option("--method", help="Filter by HTTP method (GET, POST, etc.)."),
    ] = None,
    api_version: Annotated[
        str,
        typer.Option("--api-version", help="Graph API version.", envvar="MWS_API_VERSION"),
    ] = "v1.0",
) -> None:
    """Show schema details for a resource path."""
    tree = _get_tree(api_version)

    # Normalize path: strip leading slash, split
    segments = [s for s in path.strip("/").split("/") if s]
    if not segments:
        print(json.dumps({"error": "invalid_path", "message": "Path cannot be empty."}))
        raise typer.Exit(1)

    result = tree.resolve_path(segments)
    if result is None:
        print(json.dumps({"error": "not_found", "message": f"Path not found: {path}"}))
        raise typer.Exit(3)

    if isinstance(result, MethodNode):
        print(json.dumps(result.to_dict(), indent=2))
    elif isinstance(result, ResourceNode):
        output: dict[str, object] = {"resource": result.name}
        if result.methods:
            methods_list = list(result.methods.values())
            if method:
                methods_list = [m for m in methods_list if m.http_method.upper() == method.upper()]
            output["methods"] = [m.to_dict() for m in methods_list]
        if result.children:
            output["children"] = sorted(result.children.keys())
        print(json.dumps(output, indent=2))
