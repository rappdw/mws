"""Schema introspection CLI commands: mws schema list/refresh/<path>."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import click
import typer
from typer.core import TyperGroup

from mws.schema.build import CommandTree, MethodNode, ResourceNode

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


def _show_path(path: str, method: str | None, api_version: str) -> None:
    """Show schema details for a resource path."""
    tree = _get_tree(api_version)

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


class SchemaGroup(TyperGroup):
    """Custom group that handles path arguments like /me/messages as schema show."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        # If it looks like a path (starts with /), treat as schema show
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        if cmd_name.startswith("/"):
            return self._make_show_command(cmd_name)
        return None

    def _make_show_command(self, path: str) -> click.Command:
        """Create an ad-hoc command that shows schema for the given path."""

        @click.command(name=path, hidden=True)
        @click.option("--method", default=None, help="Filter by HTTP method.")
        @click.option(
            "--api-version", default="v1.0", envvar="MWS_API_VERSION", help="Graph API version."
        )
        def show_cmd(method: str | None, api_version: str) -> None:
            _show_path(path, method, api_version)

        return show_cmd


schema_app = typer.Typer(cls=SchemaGroup, help="Introspect the Graph API schema.")


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
    _show_path(path, method, api_version)
