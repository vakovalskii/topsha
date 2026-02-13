"""MCP tests: API routes (api_key, list masking) and fetch_mcp_tools (Streamable HTTP, legacy, SSE)."""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.mcp import MCPServer, fetch_mcp_tools


# ----- Helpers for fetch_mcp_tools tests -----

def _make_response(status_code: int, headers: dict = None, text: str = "", json_body: dict = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = MagicMock()
    resp.headers.get.side_effect = lambda k, d=None: (headers or {}).get(k, d)
    resp.text = text
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
    else:
        resp.json = MagicMock(side_effect=ValueError("not JSON"))
    return resp


# ----- Fixtures for route tests -----

@pytest.fixture(scope="module")
def temp_data_dir():
    """Temporary directory for MCP config and cache in tests."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture(scope="module")
def app_with_temp_config(temp_data_dir):
    """App with MCP config and cache pointing to temp dir; fetch_mcp_tools mocked."""
    config_file = os.path.join(temp_data_dir, "mcp_servers.json")
    cache_file = os.path.join(temp_data_dir, "mcp_tools_cache.json")

    with patch("src.mcp.MCP_CONFIG_FILE", config_file), patch(
        "src.mcp.MCP_TOOLS_CACHE", cache_file
    ), patch("src.routes.mcp.fetch_mcp_tools", new_callable=AsyncMock, return_value=[]):
        from app import app
        yield app


@pytest.fixture
def client(app_with_temp_config):
    """Test client for MCP routes."""
    return TestClient(app_with_temp_config)


# ----- Route tests (API: add/list, api_key, masking) -----

def test_add_mcp_server_accepts_optional_api_key(client):
    """POST /mcp/servers accepts optional api_key (Bearer token)."""
    r = client.post(
        "/mcp/servers",
        json={
            "name": "test-server",
            "url": "http://localhost:9999",
            "api_key": "secret-bearer-token-123",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert data.get("name") == "test-server"


def test_list_servers_does_not_expose_api_key(client):
    """GET /mcp/servers must not return raw api_key (security)."""
    client.post(
        "/mcp/servers",
        json={
            "name": "secure-server",
            "url": "http://localhost:8888",
            "api_key": "do-not-expose-this",
        },
    )
    r = client.get("/mcp/servers")
    assert r.status_code == 200
    servers = r.json().get("servers", [])
    assert len(servers) >= 1
    secure = next((s for s in servers if s.get("name") == "secure-server"), None)
    assert secure is not None
    assert secure.get("api_key") != "do-not-expose-this"
    assert "api_key_set" in secure
    assert secure["api_key_set"] is True


def test_add_mcp_server_without_api_key(client):
    """POST /mcp/servers works without api_key (optional field)."""
    r = client.post(
        "/mcp/servers",
        json={
            "name": "no-auth-server",
            "url": "http://localhost:7777",
        },
    )
    assert r.status_code == 200
    r2 = client.get("/mcp/servers")
    servers = r2.json().get("servers", [])
    no_auth = next((s for s in servers if s.get("name") == "no-auth-server"), None)
    assert no_auth is not None
    assert no_auth.get("api_key_set") is False


# ----- fetch_mcp_tools tests (Streamable HTTP, legacy, SSE) -----

def test_streamable_http_sse_tools_list():
    """Streamable HTTP: session id in header, tools/list returns SSE lines."""
    init_resp = _make_response(200, {"mcp-session-id": "sess-123"}, "")
    tools_body = 'data: {"result":{"tools":[{"name":"tool_a"},{"name":"tool_b"}]}}\n'
    tools_resp = _make_response(200, {}, tools_body)

    mock_post = AsyncMock(side_effect=[init_resp, tools_resp])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(name="stream", url="http://localhost:8000", transport="http")
        result = asyncio.run(fetch_mcp_tools(server))

    assert result == [{"name": "tool_a"}, {"name": "tool_b"}]
    assert mock_post.call_count == 2


def test_streamable_http_session_id_from_body():
    """Streamable HTTP: session id in initialize response body when not in header."""
    init_resp = _make_response(200, {}, "", json_body={"result": {"sessionId": "from-body"}})
    tools_resp = _make_response(200, {}, 'data: {"result":{"tools":[{"name":"only"}]}}\n')

    mock_post = AsyncMock(side_effect=[init_resp, tools_resp])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(name="stream", url="http://localhost:8000", transport="http")
        result = asyncio.run(fetch_mcp_tools(server))

    assert result == [{"name": "only"}]
    assert mock_post.call_count == 2


def test_streamable_http_tools_list_single_json():
    """Streamable HTTP: tools/list returns single JSON object (fallback)."""
    init_resp = _make_response(200, {"mcp-session-id": "sess-1"}, "")
    tools_resp = _make_response(
        200,
        {},
        json.dumps({"result": {"tools": [{"name": "json_tool"}]}}),
    )

    mock_post = AsyncMock(side_effect=[init_resp, tools_resp])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(name="stream", url="http://localhost:8000", transport="http")
        result = asyncio.run(fetch_mcp_tools(server))

    assert result == [{"name": "json_tool"}]


def test_streamable_http_empty_data_line_skipped():
    """Streamable HTTP: empty 'data:' line is skipped without crash."""
    init_resp = _make_response(200, {"mcp-session-id": "sess-1"}, "")
    tools_body = 'data: \ndata: {"result":{"tools":[{"name":"one"}]}}\n'
    tools_resp = _make_response(200, {}, tools_body)

    mock_post = AsyncMock(side_effect=[init_resp, tools_resp])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(name="stream", url="http://localhost:8000", transport="http")
        result = asyncio.run(fetch_mcp_tools(server))

    assert result == [{"name": "one"}]


def test_legacy_json_rpc_tools_list():
    """Legacy path: no session id, tools/list returns plain JSON-RPC."""
    init_resp = _make_response(200, {}, "", json_body={})
    tools_resp = _make_response(
        200,
        {},
        json.dumps({"result": {"tools": [{"name": "legacy_a"}]}}),
    )

    mock_post = AsyncMock(side_effect=[init_resp, tools_resp])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(name="legacy", url="http://localhost:8000", transport="http")
        result = asyncio.run(fetch_mcp_tools(server))

    assert result == [{"name": "legacy_a"}]


def test_legacy_sse_fallback():
    """Legacy path: tools/list returns SSE when body is not single JSON."""
    init_resp = _make_response(200, {}, "", json_body={})
    tools_body = 'data: {"result":{"tools":[{"name":"sse_legacy"}]}}\n'
    tools_resp = _make_response(200, {}, tools_body)

    mock_post = AsyncMock(side_effect=[init_resp, tools_resp])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(name="legacy", url="http://localhost:8000", transport="http")
        result = asyncio.run(fetch_mcp_tools(server))

    assert result == [{"name": "sse_legacy"}]


def test_bearer_auth_sent_when_api_key_set():
    """Authorization Bearer header is sent when server has api_key."""
    init_resp = _make_response(200, {"mcp-session-id": "s"}, "")
    tools_resp = _make_response(200, {}, 'data: {"result":{"tools":[]}}\n')

    mock_post = AsyncMock(side_effect=[init_resp, tools_resp])
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(
            name="auth",
            url="http://localhost:8000",
            transport="http",
            api_key="secret-token",
        )
        asyncio.run(fetch_mcp_tools(server))

    calls = mock_post.call_args_list
    assert len(calls) >= 1
    first_kw = calls[0].kwargs
    assert first_kw["headers"].get("Authorization") == "Bearer secret-token"


def test_initialize_non_200_returns_empty():
    """When initialize returns non-200, no session path; legacy tools/list also fails, result empty."""
    init_resp = _make_response(403, {}, "Forbidden")

    mock_post = AsyncMock(return_value=init_resp)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.mcp.httpx.AsyncClient", return_value=mock_client):
        server = MCPServer(name="bad", url="http://localhost:8000", transport="http")
        result = asyncio.run(fetch_mcp_tools(server))

    assert result == []
    assert mock_post.call_count == 2
