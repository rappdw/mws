"""Client credentials (service principal) authentication."""

from __future__ import annotations

import os
from typing import Any

import msal

from mws.errors import AuthError

DEFAULT_SCOPES = ["https://graph.microsoft.com/.default"]


class ClientCredentialAuth:
    """Service principal authentication via client secret.

    Activated by --auth-type sp or env vars MWS_TENANT_ID + MWS_CLIENT_ID + MWS_CLIENT_SECRET.
    Tokens are not persisted to disk.
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    def from_env(cls) -> ClientCredentialAuth | None:
        """Create from environment variables, or return None if not set."""
        tenant_id = os.environ.get("MWS_TENANT_ID", "")
        client_id = os.environ.get("MWS_CLIENT_ID", "")
        client_secret = os.environ.get("MWS_CLIENT_SECRET", "")
        if tenant_id and client_id and client_secret:
            return cls(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
        return None

    def _get_app(self) -> msal.ConfidentialClientApplication:
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        return msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=authority,
        )

    def acquire_token(self, scopes: list[str] | None = None) -> dict[str, Any]:
        """Acquire token using client credentials flow."""
        scopes = scopes or DEFAULT_SCOPES
        app = self._get_app()
        result = app.acquire_token_for_client(scopes=scopes)
        if not result or "access_token" not in result:
            error_msg = "unknown error"
            if result:
                error_msg = result.get("error_description", error_msg)
            raise AuthError(message=f"Client credentials auth failed: {error_msg}")
        return result
