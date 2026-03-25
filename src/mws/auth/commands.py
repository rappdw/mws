"""CLI commands for mws auth subgroup."""

from __future__ import annotations

import json
import sys
from typing import Annotated

import typer

from mws.auth.config import (
    ProfileConfig,
    load_config,
    resolve_effective_profile,
    save_config,
)
from mws.auth.device_flow import DeviceCodeAuth
from mws.errors import AuthError

auth_app = typer.Typer(help="Manage authentication profiles and tokens.")


@auth_app.command()
def login(
    tenant_id: Annotated[
        str | None,
        typer.Option("--tenant-id", help="Azure AD tenant ID.", envvar="MWS_TENANT_ID"),
    ] = None,
    client_id: Annotated[
        str | None,
        typer.Option("--client-id", help="Azure AD client (app) ID.", envvar="MWS_CLIENT_ID"),
    ] = None,
    profile: Annotated[
        str,
        typer.Option("--profile", help="Profile name to store credentials under."),
    ] = "default",
) -> None:
    """Authenticate with Microsoft 365 via device code flow."""
    config = load_config()

    # Merge with existing profile if present
    existing = config.profiles.get(profile, ProfileConfig())
    effective_tenant = tenant_id or existing.tenant_id
    effective_client = client_id or existing.client_id

    if not effective_tenant:
        print(
            json.dumps(
                {
                    "error": "auth_error",
                    "message": "Missing --tenant-id. Run: mws auth login --tenant-id <tid>"
                    " --client-id <cid>",
                }
            ),
            file=sys.stderr,
        )
        raise typer.Exit(2)

    if not effective_client:
        print(
            json.dumps(
                {
                    "error": "auth_error",
                    "message": "Missing --client-id. Register an Azure AD app and provide"
                    " --client-id <cid>. See docs/auth-setup.md.",
                }
            ),
            file=sys.stderr,
        )
        raise typer.Exit(2)

    auth = DeviceCodeAuth(
        tenant_id=effective_tenant,
        client_id=effective_client,
        profile_name=profile,
    )

    try:
        auth.acquire_token()
    except AuthError as e:
        e.print_and_exit()

    # Save profile to config
    config.profiles[profile] = ProfileConfig(
        tenant_id=effective_tenant,
        client_id=effective_client or auth.client_id,
        auth_type="device_code",
    )
    if not config.profiles.get(config.default_profile):
        config.default_profile = profile
    save_config(config)

    # Output success as JSON
    accounts = auth.get_accounts()
    identity = accounts[0]["username"] if accounts else "unknown"
    print(json.dumps({"status": "authenticated", "profile": profile, "identity": identity}))


@auth_app.command()
def logout(
    profile: Annotated[
        str,
        typer.Option("--profile", help="Profile to log out."),
    ] = "default",
) -> None:
    """Remove cached tokens for a profile."""
    config = load_config()
    profile_config = config.profiles.get(profile, ProfileConfig())

    auth = DeviceCodeAuth(
        tenant_id=profile_config.tenant_id or "placeholder",
        client_id=profile_config.client_id,
        profile_name=profile,
    )
    auth.clear_cache()

    # Remove profile from config
    config.profiles.pop(profile, None)
    save_config(config)

    print(json.dumps({"status": "logged_out", "profile": profile}))


@auth_app.command()
def status() -> None:
    """Show current authentication status."""
    config = load_config()
    profile_name, profile = resolve_effective_profile(config)

    if not profile.tenant_id:
        print(
            json.dumps(
                {
                    "error": "auth_error",
                    "message": "No profile configured. Run 'mws auth login' to get started.",
                }
            ),
            file=sys.stderr,
        )
        raise typer.Exit(2)

    auth = DeviceCodeAuth(
        tenant_id=profile.tenant_id,
        client_id=profile.client_id,
        profile_name=profile_name,
    )

    accounts = auth.get_accounts()
    token = auth.get_cached_token()

    result = {
        "profile": profile_name,
        "tenant_id": profile.tenant_id,
        "auth_type": profile.auth_type,
        "authenticated": token is not None,
    }
    if accounts:
        result["identity"] = accounts[0].get("username", "unknown")
    if token:
        result["scopes"] = token.get("scope", "").split()

    print(json.dumps(result))


@auth_app.command()
def switch(
    profile: Annotated[str, typer.Argument(help="Profile name to switch to.")],
) -> None:
    """Set the default auth profile."""
    config = load_config()
    if profile not in config.profiles:
        print(
            json.dumps(
                {
                    "error": "not_found",
                    "message": f"Profile '{profile}' not found. "
                    f"Available: {list(config.profiles.keys())}",
                }
            ),
            file=sys.stderr,
        )
        raise typer.Exit(3)

    config.default_profile = profile
    save_config(config)
    print(json.dumps({"status": "switched", "default_profile": profile}))
