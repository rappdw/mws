"""Phase B auth tests: config, device flow, auth commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mws.auth.config import (
    AuthConfig,
    ProfileConfig,
    load_config,
    resolve_effective_profile,
    save_config,
)
from mws.cli import app


def test_config_save_and_load(tmp_path: Path) -> None:
    config = AuthConfig(
        default_profile="work",
        profiles={
            "work": ProfileConfig(tenant_id="t1", client_id="c1", auth_type="device_code"),
        },
    )
    save_config(config, config_dir=tmp_path)
    loaded = load_config(config_dir=tmp_path)
    assert loaded.default_profile == "work"
    assert loaded.profiles["work"].tenant_id == "t1"
    assert loaded.profiles["work"].client_id == "c1"


def test_config_file_permissions(tmp_path: Path) -> None:
    config = AuthConfig(profiles={"default": ProfileConfig(tenant_id="t")})
    save_config(config, config_dir=tmp_path)
    config_file = tmp_path / "config.json"
    mode = config_file.stat().st_mode & 0o777
    assert mode == 0o600


def test_config_load_missing_file(tmp_path: Path) -> None:
    config = load_config(config_dir=tmp_path)
    assert config.default_profile == "default"
    assert config.profiles == {}


def test_resolve_effective_profile_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MWS_PROFILE", "personal")
    config = AuthConfig(
        default_profile="work",
        profiles={
            "work": ProfileConfig(tenant_id="t-work"),
            "personal": ProfileConfig(tenant_id="t-personal"),
        },
    )
    name, profile = resolve_effective_profile(config)
    assert name == "personal"
    assert profile.tenant_id == "t-personal"


def test_resolve_effective_profile_tenant_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MWS_TENANT_ID", "env-tenant")
    config = AuthConfig(profiles={"default": ProfileConfig(tenant_id="config-tenant")})
    name, profile = resolve_effective_profile(config)
    assert profile.tenant_id == "env-tenant"


def test_auth_status_no_profile(cli_runner: CliRunner) -> None:
    with patch("mws.auth.commands.load_config", return_value=AuthConfig()):
        result = cli_runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 2
    assert "No profile configured" in result.output


def test_auth_login_missing_tenant(cli_runner: CliRunner) -> None:
    with patch("mws.auth.commands.load_config", return_value=AuthConfig()):
        result = cli_runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 2
    assert "tenant-id" in result.output


def test_auth_login_invokes_device_flow(cli_runner: CliRunner, tmp_path: Path) -> None:
    mock_config = AuthConfig()
    with (
        patch("mws.auth.commands.load_config", return_value=mock_config),
        patch("mws.auth.commands.save_config") as mock_save,
        patch("mws.auth.commands.DeviceCodeAuth") as mock_auth_cls,
    ):
        mock_auth = mock_auth_cls.return_value
        mock_auth.acquire_token.return_value = {"access_token": "tok123"}
        mock_auth.get_accounts.return_value = [{"username": "user@example.com"}]
        mock_auth.client_id = "test-client"

        result = cli_runner.invoke(
            app, ["auth", "login", "--tenant-id", "test-tenant", "--client-id", "test-client"]
        )

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "authenticated"
    assert output["identity"] == "user@example.com"
    mock_save.assert_called_once()


def test_auth_logout(cli_runner: CliRunner) -> None:
    mock_config = AuthConfig(profiles={"default": ProfileConfig(tenant_id="t")})
    with (
        patch("mws.auth.commands.load_config", return_value=mock_config),
        patch("mws.auth.commands.save_config"),
        patch("mws.auth.commands.DeviceCodeAuth") as mock_auth_cls,
    ):
        mock_auth = mock_auth_cls.return_value
        result = cli_runner.invoke(app, ["auth", "logout"])

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["status"] == "logged_out"
    mock_auth.clear_cache.assert_called_once()


def test_auth_switch(cli_runner: CliRunner) -> None:
    mock_config = AuthConfig(
        default_profile="default",
        profiles={
            "default": ProfileConfig(tenant_id="t1"),
            "work": ProfileConfig(tenant_id="t2"),
        },
    )
    with (
        patch("mws.auth.commands.load_config", return_value=mock_config),
        patch("mws.auth.commands.save_config"),
    ):
        result = cli_runner.invoke(app, ["auth", "switch", "work"])

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output["default_profile"] == "work"


def test_auth_switch_nonexistent_profile(cli_runner: CliRunner) -> None:
    mock_config = AuthConfig(profiles={"default": ProfileConfig()})
    with patch("mws.auth.commands.load_config", return_value=mock_config):
        result = cli_runner.invoke(app, ["auth", "switch", "nonexistent"])
    assert result.exit_code == 3


def test_token_cache_path(tmp_path: Path) -> None:
    profile = ProfileConfig(tenant_id="t")
    path = profile.effective_token_cache_path(tmp_path, "work")
    assert path == tmp_path / "tokens" / "work.json"
