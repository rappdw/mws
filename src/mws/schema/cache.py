"""Cache management for the Graph OpenAPI spec."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from platformdirs import user_cache_dir

from mws.schema.build import CommandTree, build_command_tree, command_tree_to_index
from mws.schema.fetch import fetch_openapi_spec

DEFAULT_TTL_HOURS = 24


def _default_cache_dir() -> Path:
    return Path(user_cache_dir("mws"))


def _ttl_seconds() -> float:
    hours = float(os.environ.get("MWS_SCHEMA_TTL_HOURS", str(DEFAULT_TTL_HOURS)))
    return hours * 3600


def _spec_path(cache_dir: Path, api_version: str) -> Path:
    return cache_dir / f"graph-openapi-{api_version}.yaml"


def _index_path(cache_dir: Path, api_version: str) -> Path:
    return cache_dir / f"graph-index-{api_version}.json"


def _is_fresh(path: Path, ttl_seconds: float) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < ttl_seconds


async def load_command_tree(
    api_version: str = "v1.0",
    cache_dir: Path | None = None,
    force_refresh: bool = False,
    quiet: bool = False,
) -> CommandTree:
    """Load the command tree, using cached index if fresh.

    Priority:
    1. Cached index (JSON) — fast warm start
    2. Cached raw spec (YAML) — rebuild index
    3. Fetch from network — download, cache, build index
    """
    cache_dir = cache_dir or _default_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    spec_file = _spec_path(cache_dir, api_version)
    index_file = _index_path(cache_dir, api_version)
    ttl = _ttl_seconds()

    # 1. Try cached index
    if not force_refresh and _is_fresh(index_file, ttl):
        index_data = json.loads(index_file.read_text())
        return CommandTree.from_index(index_data)

    # 2. Try cached raw spec
    if not force_refresh and _is_fresh(spec_file, ttl):
        import yaml

        spec = yaml.safe_load(spec_file.read_bytes())
        tree = build_command_tree(spec)
        # Rebuild index
        index_file.write_text(json.dumps(command_tree_to_index(tree)))
        return tree

    # 3. Fetch from network
    if not quiet:
        print("Fetching Graph API schema...", end=" ", file=sys.stderr, flush=True)

    raw = await fetch_openapi_spec(api_version)
    spec_file.write_bytes(raw)

    import yaml

    spec = yaml.safe_load(raw)
    tree = build_command_tree(spec)
    index_file.write_text(json.dumps(command_tree_to_index(tree)))

    if not quiet:
        print(f"done (cached at {spec_file})", file=sys.stderr)

    return tree
