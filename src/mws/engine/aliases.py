"""Alias layer: well-known shortcuts for common Graph API operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import typer


@dataclass
class AliasTarget:
    """Target command segments that an alias expands to."""

    path: list[str]
    description: str = ""


# Flat alias table: (group, action) → expanded path
ALIASES: dict[tuple[str, ...], AliasTarget] = {
    ("mail", "list"): AliasTarget(
        path=["me", "messages", "list"],
        description="List messages in inbox",
    ),
    ("mail", "get"): AliasTarget(
        path=["me", "messages", "get"],
        description="Get a specific message",
    ),
    ("mail", "send"): AliasTarget(
        path=["me", "send-mail"],
        description="Send an email",
    ),
    ("cal", "list"): AliasTarget(
        path=["me", "calendar", "events", "list"],
        description="List calendar events",
    ),
    ("cal", "create"): AliasTarget(
        path=["me", "calendar", "events", "create"],
        description="Create a calendar event",
    ),
    ("teams", "list"): AliasTarget(
        path=["me", "joined-teams", "list"],
        description="List joined teams",
    ),
    ("drive", "ls"): AliasTarget(
        path=["me", "drive", "root", "children", "list"],
        description="List files in OneDrive root",
    ),
    ("drive", "get"): AliasTarget(
        path=["me", "drive", "root", "get"],
        description="Get a file from OneDrive",
    ),
}


def resolve_alias(argv: list[str]) -> list[str]:
    """Resolve alias in argv, returning expanded argv or original if no match.

    Checks first 2 tokens, then first 1 token against the alias table.
    """
    if len(argv) >= 2:
        key = (argv[0], argv[1])
        if key in ALIASES:
            return ALIASES[key].path + argv[2:]

    if len(argv) >= 1:
        key_single = (argv[0],)
        if key_single in ALIASES:
            return ALIASES[key_single].path + argv[1:]

    return argv


def list_aliases() -> list[dict[str, Any]]:
    """Return all aliases as a list of dicts for JSON output."""
    result = []
    for key, target in sorted(ALIASES.items()):
        result.append(
            {
                "alias": " ".join(key),
                "expands_to": " ".join(target.path),
                "description": target.description,
            }
        )
    return result


aliases_app = typer.Typer(help="Manage command aliases.")


@aliases_app.command("list")
def aliases_list_cmd() -> None:
    """List all available aliases."""
    print(json.dumps(list_aliases(), indent=2))
