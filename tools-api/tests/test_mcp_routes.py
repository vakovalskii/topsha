"""Tests for MCP server routes: api_key (Bearer token) support."""

import tempfile
import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Patch config paths and fetch_mcp_tools before importing app and routes
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
    # Add server with api_key
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
    # Must not expose raw token
    assert secure.get("api_key") != "do-not-expose-this"
    # Should expose only that a token is set (for UI hint)
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
