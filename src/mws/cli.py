"""Root Typer app with global flags and static commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

import typer

from mws import __version__
from mws.auth.commands import auth_app
from mws.engine.aliases import aliases_app
from mws.engine.commander import LazySchemaGroup
from mws.schema.introspect import schema_app


class OutputFormat(StrEnum):
    json = "json"
    table = "table"
    yaml = "yaml"


class ApiVersion(StrEnum):
    v1_0 = "v1.0"
    beta = "beta"


@dataclass
class GlobalOptions:
    """Resolved global options, available to all commands."""

    format: OutputFormat = OutputFormat.json
    api_version: ApiVersion = ApiVersion.v1_0
    profile: str = "default"
    dry_run: bool = False
    params: str | None = None
    body: str | None = None
    select: str | None = None
    filter: str | None = None
    top: int | None = None
    orderby: str | None = None
    page_all: bool = False
    page_limit: int = 10
    no_color: bool = False
    quiet: bool = False
    verbose: bool = False


# Stored per-invocation so subcommands can access it.
_current_options: GlobalOptions = GlobalOptions()


def get_global_options() -> GlobalOptions:
    return _current_options


def _version_callback(value: bool) -> None:
    if value:
        print(f"mws {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="mws",
    cls=LazySchemaGroup,
    help="Agent-first CLI for Microsoft 365 (Graph API).",
    no_args_is_help=True,
    add_completion=False,
)


app.add_typer(auth_app, name="auth")
app.add_typer(schema_app, name="schema")
app.add_typer(aliases_app, name="aliases")


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format.", envvar="MWS_FORMAT"),
    ] = OutputFormat.json,
    api_version: Annotated[
        ApiVersion,
        typer.Option("--api-version", help="Graph API version.", envvar="MWS_API_VERSION"),
    ] = ApiVersion.v1_0,
    profile: Annotated[
        str,
        typer.Option("--profile", help="Auth profile to use.", envvar="MWS_PROFILE"),
    ] = "default",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the request without executing."),
    ] = False,
    params: Annotated[
        str | None,
        typer.Option("--params", help="OData query parameters as JSON."),
    ] = None,
    body: Annotated[
        str | None,
        typer.Option("--body", help="Request body as JSON (or '-' for stdin)."),
    ] = None,
    select: Annotated[
        str | None,
        typer.Option("--select", help="Shorthand for $select."),
    ] = None,
    filter: Annotated[
        str | None,
        typer.Option("--filter", help="Shorthand for $filter."),
    ] = None,
    top: Annotated[
        int | None,
        typer.Option("--top", help="Shorthand for $top."),
    ] = None,
    orderby: Annotated[
        str | None,
        typer.Option("--orderby", help="Shorthand for $orderby."),
    ] = None,
    page_all: Annotated[
        bool,
        typer.Option("--page-all", help="Follow all @odata.nextLink pages."),
    ] = False,
    page_limit: Annotated[
        int,
        typer.Option("--page-limit", help="Max pages when --page-all is set."),
    ] = 10,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable Rich color output."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress all output except data."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Emit HTTP debug info to stderr."),
    ] = False,
) -> None:
    """Agent-first CLI for Microsoft 365 (Graph API)."""
    global _current_options
    _current_options = GlobalOptions(
        format=format,
        api_version=api_version,
        profile=profile,
        dry_run=dry_run,
        params=params,
        body=body,
        select=select,
        filter=filter,
        top=top,
        orderby=orderby,
        page_all=page_all,
        page_limit=page_limit,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
    )


@app.command()
def mcp(
    services: Annotated[
        str | None,
        typer.Option(
            "--services",
            help="Comma-separated list of services to expose (e.g., me,users,teams).",
        ),
    ] = None,
    transport: Annotated[
        str,
        typer.Option("--transport", help="Transport: stdio or sse."),
    ] = "stdio",
    port: Annotated[
        int,
        typer.Option("--port", help="Port for SSE transport."),
    ] = 8080,
) -> None:
    """Start MCP server mode."""
    import asyncio

    from mws.mcp.server import create_mcp_server
    from mws.schema.cache import load_command_tree

    tree = asyncio.run(load_command_tree(get_global_options().api_version.value))
    svc_list = [s.strip() for s in services.split(",")] if services else None
    server = create_mcp_server(tree, services=svc_list)

    if transport == "sse":
        server.settings.port = port
        server.run(transport="sse")
    else:
        server.run(transport="stdio")


def cli_main() -> None:
    """Entry point that resolves aliases before Typer dispatch."""
    import sys

    from mws.engine.aliases import resolve_alias

    sys.argv[1:] = resolve_alias(sys.argv[1:])
    app()
