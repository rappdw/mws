"""Async Graph API client with retry, pagination, and auth injection."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from typing import Any

import httpx

from mws.errors import (
    ApiError,
    AuthError,
    NotFoundError,
    PermissionDeniedError,
    ThrottledError,
)

GRAPH_BASE_URL = "https://graph.microsoft.com"
MAX_RETRIES = 3
MAX_RETRY_DELAY = 60
# OData metadata fields stripped from responses unless verbose
ODATA_METADATA_KEYS = {"@odata.context", "@odata.type", "@odata.id", "@odata.etag"}


def compute_retry_delay(retry_after: str | None, attempt: int) -> float:
    """Compute delay in seconds, respecting Retry-After header."""
    if retry_after:
        try:
            delay = float(retry_after)
            return min(delay, MAX_RETRY_DELAY)
        except ValueError:
            pass
    # Exponential backoff: 1, 2, 4 seconds
    return min(2**attempt, MAX_RETRY_DELAY)


def _classify_error(status: int, body: dict[str, Any]) -> type:
    """Map HTTP status to error class."""
    if status == 401 or status == 403:
        return PermissionDeniedError if status == 403 else AuthError
    if status == 404:
        return NotFoundError
    if status == 429:
        return ThrottledError
    return ApiError


def strip_odata_metadata(data: dict[str, Any]) -> dict[str, Any]:
    """Remove OData metadata fields from a response dict."""
    return {k: v for k, v in data.items() if k not in ODATA_METADATA_KEYS}


def strip_metadata_recursive(data: Any) -> Any:
    """Strip OData metadata from response, including nested value arrays."""
    if isinstance(data, dict):
        result = strip_odata_metadata(data)
        if "value" in result and isinstance(result["value"], list):
            result["value"] = [
                strip_odata_metadata(item) if isinstance(item, dict) else item
                for item in result["value"]
            ]
        return result
    return data


class MsalAuth(httpx.Auth):
    """httpx auth class that injects Bearer token from a token provider."""

    def __init__(self, token_provider: Any) -> None:
        """token_provider must have acquire_token() -> dict with 'access_token'."""
        self._provider = token_provider

    def auth_flow(self, request: httpx.Request) -> Any:
        token_result = self._provider.acquire_token()
        request.headers["Authorization"] = f"Bearer {token_result['access_token']}"
        yield request


class GraphClient:
    """Async HTTP client for Microsoft Graph API."""

    def __init__(
        self,
        auth: httpx.Auth | None = None,
        api_version: str = "v1.0",
        verbose: bool = False,
    ) -> None:
        self.api_version = api_version
        self.verbose = verbose
        self.base_url = f"{GRAPH_BASE_URL}/{api_version}"
        self._auth = auth
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=self._auth,
                http2=True,
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _raw_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send a request with retry on 429/503. Returns raw (unstripped) JSON."""
        client = await self._get_client()

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
            except httpx.HTTPError as e:
                if attempt == MAX_RETRIES - 1:
                    raise ApiError(message=f"HTTP request failed: {e}") from e
                await asyncio.sleep(compute_retry_delay(None, attempt))
                continue

            if self.verbose:
                print(
                    f"[HTTP] {method} {response.url} → {response.status_code}",
                    file=sys.stderr,
                )

            if response.status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                retry_after = response.headers.get("Retry-After")
                delay = compute_retry_delay(retry_after, attempt)
                if self.verbose:
                    print(
                        f"[HTTP] Retrying after {delay}s (attempt {attempt + 1})",
                        file=sys.stderr,
                    )
                await asyncio.sleep(delay)
                continue

            if response.status_code >= 400:
                try:
                    body = response.json()
                except Exception:
                    body = {}
                error_msg = (
                    body.get("error", {}).get("message", response.text[:200])
                    if isinstance(body.get("error"), dict)
                    else response.text[:200]
                )
                error_cls = _classify_error(response.status_code, body)
                if error_cls == ThrottledError:
                    raise ThrottledError(
                        message=error_msg,
                        retry_after=int(response.headers.get("Retry-After", "0")),
                    )
                raise error_cls(message=error_msg)

            return response.json()

        raise ApiError(message="Max retries exceeded")

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send a request, stripping OData metadata unless verbose."""
        data = await self._raw_request(method, path, params, json_body, headers)
        if not self.verbose:
            data = strip_metadata_recursive(data)
        return data

    async def paginate(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        page_limit: int = 10,
    ) -> AsyncIterator[dict[str, Any]]:
        """Follow @odata.nextLink pagination, yielding each page (stripped)."""
        current_url: str | None = path
        current_params = params
        use_full_url = False
        pages = 0

        while current_url and pages < page_limit:
            if use_full_url:
                # nextLink is a full URL — bypass base_url by using a separate client call
                raw_data = await self._raw_request_full_url(method, current_url)
            else:
                raw_data = await self._raw_request(method, current_url, params=current_params)

            next_link = raw_data.get("@odata.nextLink")

            # Strip metadata for the yielded data
            if not self.verbose:
                yield strip_metadata_recursive(raw_data)
            else:
                yield raw_data

            current_url = next_link
            current_params = None
            use_full_url = True  # nextLink is always a full URL
            pages += 1

    async def _raw_request_full_url(
        self,
        method: str,
        url: str,
    ) -> dict[str, Any]:
        """Send a request to a full URL (for pagination nextLink)."""
        client = await self._get_client()

        for attempt in range(MAX_RETRIES):
            try:
                # Use httpx.Request with the absolute URL to avoid base_url resolution
                req = httpx.Request(method=method, url=url, headers=dict(client.headers))
                response = await client.send(req)
            except httpx.HTTPError as e:
                if attempt == MAX_RETRIES - 1:
                    raise ApiError(message=f"HTTP request failed: {e}") from e
                await asyncio.sleep(compute_retry_delay(None, attempt))
                continue

            if response.status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                retry_after = response.headers.get("Retry-After")
                delay = compute_retry_delay(retry_after, attempt)
                await asyncio.sleep(delay)
                continue

            if response.status_code >= 400:
                try:
                    body = response.json()
                except Exception:
                    body = {}
                error_msg = (
                    body.get("error", {}).get("message", response.text[:200])
                    if isinstance(body.get("error"), dict)
                    else response.text[:200]
                )
                error_cls = _classify_error(response.status_code, body)
                raise error_cls(message=error_msg)

            return response.json()

        raise ApiError(message="Max retries exceeded")
