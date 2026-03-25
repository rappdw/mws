"""Auth configuration: profiles, config file, env var precedence."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_config_dir


def _default_config_dir() -> Path:
    return Path(user_config_dir("mws"))


@dataclass
class ProfileConfig:
    """Configuration for a single auth profile."""

    tenant_id: str = ""
    client_id: str = ""
    auth_type: str = "device_code"
    token_cache_path: str = ""

    def effective_token_cache_path(self, config_dir: Path, profile_name: str) -> Path:
        if self.token_cache_path:
            return Path(self.token_cache_path).expanduser()
        return config_dir / "tokens" / f"{profile_name}.json"


@dataclass
class AuthConfig:
    """Top-level auth configuration with multiple profiles."""

    default_profile: str = "default"
    profiles: dict[str, ProfileConfig] = field(default_factory=dict)


def load_config(config_dir: Path | None = None) -> AuthConfig:
    """Load config from ~/.config/mws/config.json."""
    config_dir = config_dir or _default_config_dir()
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return AuthConfig()
    data = json.loads(config_file.read_text())
    profiles = {name: ProfileConfig(**pdata) for name, pdata in data.get("profiles", {}).items()}
    return AuthConfig(
        default_profile=data.get("default_profile", "default"),
        profiles=profiles,
    )


def save_config(config: AuthConfig, config_dir: Path | None = None) -> None:
    """Save config to ~/.config/mws/config.json with restricted permissions."""
    config_dir = config_dir or _default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    data = {
        "default_profile": config.default_profile,
        "profiles": {name: asdict(p) for name, p in config.profiles.items()},
    }
    config_file.write_text(json.dumps(data, indent=2) + "\n")
    config_file.chmod(stat.S_IRUSR | stat.S_IWUSR)


def resolve_effective_profile(config: AuthConfig) -> tuple[str, ProfileConfig]:
    """Resolve the active profile, respecting env var override.

    Precedence: MWS_PROFILE env var > config default_profile.
    Individual fields can be overridden by MWS_TENANT_ID, MWS_CLIENT_ID.
    """
    profile_name = os.environ.get("MWS_PROFILE", config.default_profile)
    profile = config.profiles.get(profile_name, ProfileConfig())

    # Env var overrides for individual fields
    if tenant_id := os.environ.get("MWS_TENANT_ID"):
        profile.tenant_id = tenant_id
    if client_id := os.environ.get("MWS_CLIENT_ID"):
        profile.client_id = client_id

    return profile_name, profile
