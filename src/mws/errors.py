"""Error types and exit codes for mws CLI.

Exit codes:
    0 — success
    1 — general / API error
    2 — authentication error
    3 — not found
    4 — permission denied
    5 — throttled (429)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MwsError(Exception):
    """Base error for mws CLI."""

    message: str
    exit_code: int = 1
    error_code: str = "error"
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def to_json(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result.update(self.details)
        return result

    def print_and_exit(self) -> None:
        print(json.dumps(self.to_json()), file=sys.stderr)
        raise SystemExit(self.exit_code)


@dataclass
class ApiError(MwsError):
    """Graph API returned an error response."""

    status: int = 0
    exit_code: int = 1
    error_code: str = "api_error"

    def to_json(self) -> dict[str, Any]:
        result = super().to_json()
        result["status"] = self.status
        return result


@dataclass
class AuthError(MwsError):
    """Authentication failed or no credentials configured."""

    exit_code: int = 2
    error_code: str = "auth_error"


@dataclass
class NotFoundError(MwsError):
    """Requested resource was not found."""

    exit_code: int = 3
    error_code: str = "not_found"


@dataclass
class PermissionDeniedError(MwsError):
    """Insufficient permissions for this operation."""

    exit_code: int = 4
    error_code: str = "permission_denied"


@dataclass
class ThrottledError(MwsError):
    """Request was throttled (429). Retry after delay."""

    retry_after: int = 0
    exit_code: int = 5
    error_code: str = "throttled"

    def to_json(self) -> dict[str, Any]:
        result = super().to_json()
        if self.retry_after:
            result["retry_after"] = self.retry_after
        return result
