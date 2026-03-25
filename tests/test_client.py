"""Phase C tests: Graph client retry, pagination, metadata stripping."""

from __future__ import annotations

import httpx
import pytest
import respx

from mws.client.graph import GraphClient, compute_retry_delay
from mws.errors import AuthError, NotFoundError


@pytest.fixture
def graph_client() -> GraphClient:
    return GraphClient(auth=None, api_version="v1.0", verbose=False)


@pytest.mark.asyncio
@respx.mock
async def test_simple_get(graph_client: GraphClient) -> None:
    respx.get("https://graph.microsoft.com/v1.0/me").respond(
        200, json={"displayName": "Test User", "id": "123"}
    )
    data = await graph_client.request("GET", "/me")
    assert data["displayName"] == "Test User"
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_429(graph_client: GraphClient) -> None:
    route = respx.get("https://graph.microsoft.com/v1.0/me")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"displayName": "Test User"}),
    ]
    data = await graph_client.request("GET", "/me")
    assert data["displayName"] == "Test User"
    assert route.call_count == 2
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_503(graph_client: GraphClient) -> None:
    route = respx.get("https://graph.microsoft.com/v1.0/me")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"displayName": "Test"}),
    ]
    data = await graph_client.request("GET", "/me")
    assert data["displayName"] == "Test"
    assert route.call_count == 2
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_not_found(graph_client: GraphClient) -> None:
    respx.get("https://graph.microsoft.com/v1.0/me/messages/bad").respond(
        404, json={"error": {"code": "ErrorItemNotFound", "message": "Not found"}}
    )
    with pytest.raises(NotFoundError, match="Not found"):
        await graph_client.request("GET", "/me/messages/bad")
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_auth_error(graph_client: GraphClient) -> None:
    respx.get("https://graph.microsoft.com/v1.0/me").respond(
        401, json={"error": {"message": "Invalid token"}}
    )
    with pytest.raises(AuthError):
        await graph_client.request("GET", "/me")
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_odata_metadata_stripped(graph_client: GraphClient) -> None:
    respx.get("https://graph.microsoft.com/v1.0/me").respond(
        200,
        json={
            "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users/$entity",
            "@odata.type": "#microsoft.graph.user",
            "displayName": "Test",
            "id": "123",
        },
    )
    data = await graph_client.request("GET", "/me")
    assert "@odata.context" not in data
    assert "@odata.type" not in data
    assert data["displayName"] == "Test"
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_odata_metadata_preserved_when_verbose() -> None:
    client = GraphClient(auth=None, api_version="v1.0", verbose=True)
    respx.get("https://graph.microsoft.com/v1.0/me").respond(
        200,
        json={"@odata.context": "https://...", "displayName": "Test"},
    )
    data = await client.request("GET", "/me")
    assert "@odata.context" in data
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_pagination_follows_nextlink(graph_client: GraphClient) -> None:
    call_count = 0

    def _side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if "$skip=1" in str(request.url):
            return httpx.Response(200, json={"value": [{"id": "2", "subject": "Second"}]})
        return httpx.Response(
            200,
            json={
                "value": [{"id": "1", "subject": "First"}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=1",
            },
        )

    respx.get(url__startswith="https://graph.microsoft.com/v1.0/me/messages").mock(
        side_effect=_side_effect
    )
    pages = [p async for p in graph_client.paginate("GET", "/me/messages", page_limit=10)]
    assert len(pages) == 2
    assert pages[0]["value"][0]["id"] == "1"
    assert pages[1]["value"][0]["id"] == "2"
    assert call_count == 2
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_pagination_respects_page_limit(graph_client: GraphClient) -> None:
    # Set up 3 pages but limit to 1
    respx.get("https://graph.microsoft.com/v1.0/me/messages").respond(
        200,
        json={
            "value": [{"id": "1"}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=1",
        },
    )
    respx.get("https://graph.microsoft.com/v1.0/me/messages?$skip=1").respond(
        200,
        json={"value": [{"id": "2"}]},
    )
    pages = [p async for p in graph_client.paginate("GET", "/me/messages", page_limit=1)]
    assert len(pages) == 1
    await graph_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_pagination_strips_metadata(graph_client: GraphClient) -> None:
    respx.get("https://graph.microsoft.com/v1.0/me/messages").respond(
        200,
        json={
            "@odata.context": "https://...",
            "value": [{"@odata.type": "#msg", "id": "1"}],
        },
    )
    pages = [p async for p in graph_client.paginate("GET", "/me/messages", page_limit=10)]
    assert "@odata.context" not in pages[0]
    assert "@odata.type" not in pages[0]["value"][0]
    await graph_client.close()


def test_compute_retry_delay_with_header() -> None:
    assert compute_retry_delay("5", attempt=0) == 5.0


def test_compute_retry_delay_capped() -> None:
    assert compute_retry_delay("300", attempt=0) == 60.0


def test_compute_retry_delay_exponential_backoff() -> None:
    assert compute_retry_delay(None, attempt=0) == 1.0
    assert compute_retry_delay(None, attempt=1) == 2.0
    assert compute_retry_delay(None, attempt=2) == 4.0
