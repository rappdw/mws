"""Fetch the Microsoft Graph OpenAPI spec."""

from __future__ import annotations

import httpx

OPENAPI_URLS = {
    "v1.0": "https://aka.ms/graph/v1.0/openapi.yaml",
    "beta": "https://aka.ms/graph/beta/openapi.yaml",
}


async def fetch_openapi_spec(api_version: str = "v1.0") -> bytes:
    """Download the Graph OpenAPI spec for the given API version.

    Returns raw YAML bytes (not parsed, to allow caching the raw file).
    """
    url = OPENAPI_URLS.get(api_version)
    if not url:
        raise ValueError(
            f"Unknown API version: {api_version}. Must be one of: {list(OPENAPI_URLS.keys())}"
        )

    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(120.0)) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content
