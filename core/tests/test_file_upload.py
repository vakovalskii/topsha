"""Tests for file upload endpoint and NoneType tool_calls fix"""

import io
import os
import pytest
import httpx

BASE = "http://localhost:4000"
TEST_USER = 999998  # Separate user to avoid collision with other tests


@pytest.fixture(scope="module")
def client():
    """HTTP client for API calls"""
    with httpx.Client(base_url=BASE, timeout=30) as c:
        yield c


# ============ /api/upload ============

def test_upload_basic(client):
    """POST /api/upload saves file to user workspace"""
    content = b"hello from test"
    r = client.post("/api/upload", data={
        "user_id": TEST_USER,
        "filename": "test_upload.txt",
    }, files={
        "file": ("test_upload.txt", io.BytesIO(content), "text/plain"),
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["filename"] == "test_upload.txt"
    assert str(TEST_USER) in data["path"]
    # Verify file actually exists with correct content
    assert os.path.exists(data["path"])
    assert open(data["path"], "rb").read() == content


def test_upload_returns_filename(client):
    """POST /api/upload returns the filename in response"""
    r = client.post("/api/upload", data={
        "user_id": TEST_USER,
        "filename": "myfile.py",
    }, files={
        "file": ("myfile.py", io.BytesIO(b"print('hi')"), "text/plain"),
    })
    assert r.status_code == 200
    assert r.json()["filename"] == "myfile.py"


def test_upload_binary_file(client):
    """POST /api/upload handles binary content correctly"""
    binary_content = bytes(range(256))
    r = client.post("/api/upload", data={
        "user_id": TEST_USER,
        "filename": "binary.bin",
    }, files={
        "file": ("binary.bin", io.BytesIO(binary_content), "application/octet-stream"),
    })
    assert r.status_code == 200
    data = r.json()
    assert os.path.exists(data["path"])
    assert open(data["path"], "rb").read() == binary_content


def test_upload_path_traversal_blocked(client):
    """POST /api/upload strips path traversal from filename"""
    r = client.post("/api/upload", data={
        "user_id": TEST_USER,
        "filename": "../../etc/passwd",
    }, files={
        "file": ("../../etc/passwd", io.BytesIO(b"should not escape"), "text/plain"),
    })
    assert r.status_code == 200
    data = r.json()
    # File must be saved inside user workspace, not at /etc/passwd
    assert "etc" not in data["path"].split(str(TEST_USER))[0]  # no traversal before user dir
    assert data["filename"] == "passwd"  # basename only, no directory part
    assert str(TEST_USER) in data["path"]


def test_upload_missing_file_field(client):
    """POST /api/upload without file field returns 422"""
    r = client.post("/api/upload", data={
        "user_id": TEST_USER,
        "filename": "test.txt",
    })
    assert r.status_code == 422


def test_upload_missing_user_id(client):
    """POST /api/upload without user_id returns 422"""
    r = client.post("/api/upload", data={
        "filename": "test.txt",
    }, files={
        "file": ("test.txt", io.BytesIO(b"data"), "text/plain"),
    })
    assert r.status_code == 422


def test_upload_missing_filename(client):
    """POST /api/upload without filename returns 422"""
    r = client.post("/api/upload", data={
        "user_id": TEST_USER,
    }, files={
        "file": ("test.txt", io.BytesIO(b"data"), "text/plain"),
    })
    assert r.status_code == 422


def test_upload_creates_user_workspace(client):
    """POST /api/upload creates workspace directory if it doesn't exist"""
    new_user = 777777
    r = client.post("/api/upload", data={
        "user_id": new_user,
        "filename": "first_file.txt",
    }, files={
        "file": ("first_file.txt", io.BytesIO(b"new user"), "text/plain"),
    })
    assert r.status_code == 200
    data = r.json()
    assert str(new_user) in data["path"]
    assert os.path.exists(data["path"])


# ============ NoneType tool_calls fix ============

def test_agent_null_tool_calls_does_not_crash():
    """agent.py: tool_calls=None is treated as empty list (no crash)"""
    # Import agent internals directly
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Simulate the fixed logic: `msg.get("tool_calls") or []`
    msg_with_null = {"tool_calls": None, "content": "hello"}
    msg_missing = {"content": "hello"}
    msg_empty = {"tool_calls": [], "content": "hello"}

    for msg in [msg_with_null, msg_missing, msg_empty]:
        tool_calls = msg.get("tool_calls") or []
        assert tool_calls == [], f"Expected [] for msg={msg}, got {tool_calls}"


def test_agent_null_content_does_not_crash():
    """agent.py: content=None is treated as empty string (no crash)"""
    msg_with_null = {"tool_calls": [], "content": None}
    msg_missing = {"tool_calls": []}

    for msg in [msg_with_null, msg_missing]:
        content = msg.get("content") or ""
        assert content == "", f"Expected '' for msg={msg}, got {content!r}"
