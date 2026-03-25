"""Dynamically register Typer/Click commands from the schema command tree."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click
from typer.core import TyperGroup

from mws.schema.build import MethodNode, ResourceNode


def _resolve_auth(dry_run: bool = False) -> Any:
    """Resolve auth provider from config/env, or None for dry-run."""
    if dry_run:
        return None

    from mws.auth.client_creds import ClientCredentialAuth
    from mws.auth.config import load_config, resolve_effective_profile
    from mws.client.graph import MsalAuth

    # Try client credentials first (env vars)
    cred_auth = ClientCredentialAuth.from_env()
    if cred_auth:
        return MsalAuth(cred_auth)

    # Fall back to device code flow
    config = load_config()
    _profile_name, profile = resolve_effective_profile(config)

    if not profile.tenant_id:
        from mws.errors import AuthError

        raise AuthError(message="No profile configured. Run 'mws auth login' to get started.")

    from mws.auth.device_flow import DeviceCodeAuth

    device_auth = DeviceCodeAuth(
        tenant_id=profile.tenant_id,
        client_id=profile.client_id,
        profile_name=_profile_name,
    )
    return MsalAuth(device_auth)


def _make_method_callback(method_node: MethodNode) -> Any:
    """Create a Click command callback for a specific API method."""

    @click.pass_context
    def callback(ctx: click.Context, /, **kwargs: Any) -> None:
        from mws.cli import get_global_options
        from mws.engine.executor import execute

        opts = get_global_options()

        from mws.client.graph import GraphClient

        client: GraphClient | None = None
        try:
            auth = _resolve_auth(dry_run=opts.dry_run)
            client = GraphClient(
                auth=auth, api_version=opts.api_version.value, verbose=opts.verbose
            )
            result = asyncio.run(
                execute(
                    method_node=method_node,
                    params_json=opts.params,
                    body_json=opts.body,
                    select=opts.select,
                    filter_expr=opts.filter,
                    top=opts.top,
                    dry_run=opts.dry_run,
                    page_all=opts.page_all,
                    page_limit=opts.page_limit,
                    client=client,
                    orderby=opts.orderby,
                )
            )

            from mws.output.format import format_and_print

            format_and_print(result, opts.format, opts.quiet, opts.no_color)

        except Exception as e:
            from mws.errors import MwsError

            if isinstance(e, MwsError):
                e.print_and_exit()
            print(json.dumps({"error": "error", "message": str(e)}), file=sys.stderr)
            raise SystemExit(1) from e
        finally:
            if client is not None:
                asyncio.run(client.close())

    return callback


def _build_method_command(method_node: MethodNode) -> click.Command:
    """Build a Click Command for a single API method."""
    help_text = method_node.summary or f"{method_node.http_method} {method_node.path_template}"

    cmd = click.Command(
        name=method_node.operation_name,
        callback=_make_method_callback(method_node),
        help=help_text,
    )
    return cmd


def _build_resource_group(resource: ResourceNode) -> click.Group:
    """Recursively build a Click Group for a resource and its children."""
    group = click.Group(name=resource.name, help=f"Operations on {resource.name}.")

    # Add method commands
    for method_name, method_node in resource.methods.items():
        group.add_command(_build_method_command(method_node), method_name)

    # Recursively add child resources
    for child_name, child_node in resource.children.items():
        group.add_command(_build_resource_group(child_node), child_name)

    return group


class LazySchemaGroup(TyperGroup):
    """A Click Group that lazily loads the schema and registers dynamic commands.

    This enables two-phase parsing: global flags are parsed first by Typer,
    then dynamic commands are loaded from the schema on first access.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._schema_loaded = False

    def _ensure_schema(self) -> None:
        """Load schema and register dynamic commands if not already done."""
        if self._schema_loaded:
            return
        self._schema_loaded = True

        try:
            from mws.cli import get_global_options

            opts = get_global_options()
            api_version = opts.api_version.value
        except Exception:
            api_version = "v1.0"

        try:
            from mws.schema.cache import load_command_tree

            tree = asyncio.run(load_command_tree(api_version, quiet=False))
        except Exception as e:
            # Schema loading failed — commands won't be available
            print(
                json.dumps({"error": "schema_error", "message": f"Failed to load schema: {e}"}),
                file=sys.stderr,
            )
            return

        # Register top-level resource groups
        for name, resource in tree.children.items():
            if name not in self.commands:
                self.add_command(_build_resource_group(resource), name)

    def list_commands(self, ctx: click.Context) -> list[str]:
        self._ensure_schema()
        return super().list_commands(ctx)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        self._ensure_schema()
        return super().get_command(ctx, cmd_name)
