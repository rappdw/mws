"""MSAL device code flow authentication."""

from __future__ import annotations

import stat
import sys
from pathlib import Path
from typing import Any

import msal

from mws.errors import AuthError

# Default Azure AD app client ID for mws CLI
DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
DEFAULT_AUTHORITY = "https://login.microsoftonline.com"
DEFAULT_SCOPES = ["https://graph.microsoft.com/.default"]


class DeviceCodeAuth:
    """Handles MSAL device code flow with file-based token cache."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str = "",
        config_dir: Path | None = None,
        profile_name: str = "default",
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id or DEFAULT_CLIENT_ID
        self.profile_name = profile_name
        self._config_dir = config_dir
        self._cache = msal.SerializableTokenCache()
        self._cache_path = self._resolve_cache_path()
        self._load_cache()

    def _resolve_cache_path(self) -> Path:
        if self._config_dir:
            tokens_dir = self._config_dir / "tokens"
        else:
            from platformdirs import user_config_dir

            tokens_dir = Path(user_config_dir("mws")) / "tokens"
        tokens_dir.mkdir(parents=True, exist_ok=True)
        return tokens_dir / f"{self.profile_name}.json"

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            self._cache.deserialize(self._cache_path.read_text())

    def _save_cache(self) -> None:
        if self._cache.has_state_changed:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(self._cache.serialize())
            self._cache_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def _get_app(self) -> msal.PublicClientApplication:
        authority = f"{DEFAULT_AUTHORITY}/{self.tenant_id}"
        return msal.PublicClientApplication(
            client_id=self.client_id,
            authority=authority,
            token_cache=self._cache,
        )

    def acquire_token(self, scopes: list[str] | None = None) -> dict[str, Any]:
        """Acquire a token, trying silent first, then device code flow."""
        scopes = scopes or DEFAULT_SCOPES
        app = self._get_app()

        # Try silent acquisition first
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])
            if result and "access_token" in result:
                self._save_cache()
                return result

        # Fall back to device code flow
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise AuthError(
                message="Failed to initiate device code flow: "
                f"{flow.get('error_description', 'unknown error')}"
            )

        # Print device code instructions to stderr (not stdout, which is for data)
        print(flow["message"], file=sys.stderr)

        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise AuthError(
                message=f"Authentication failed: {result.get('error_description', 'unknown error')}"
            )

        self._save_cache()
        return result

    def get_cached_token(self, scopes: list[str] | None = None) -> dict[str, Any] | None:
        """Try to get a cached token without interactive flow."""
        scopes = scopes or DEFAULT_SCOPES
        app = self._get_app()
        accounts = app.get_accounts()
        if not accounts:
            return None
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            self._save_cache()
            return result
        return None

    def clear_cache(self) -> None:
        """Remove the token cache file."""
        if self._cache_path.exists():
            self._cache_path.unlink()

    def get_accounts(self) -> list[dict[str, Any]]:
        """List cached accounts."""
        app = self._get_app()
        return app.get_accounts()
