"""FastAPI TestClient tests for POST /chat.

Uses the shared ``client`` fixture from ``tests/conftest.py`` (the real app,
all infra mocked) and mocks the chat service directly
(``app.features.ai.service.chat``, imported into the endpoint module as
``run_chat``) so no real LLM call is ever made.

If the auth service is included, the API-key dependency is overridden too —
via a plain ``try``/``except ImportError`` rather than a Jinja conditional,
so this one file works unmodified whether or not ``include_auth`` was
selected at generation time.
"""

from unittest.mock import AsyncMock, patch

import pytest

try:
    from app.core.auth import _verify as _auth_dependency
except ImportError:  # include_auth was declined for this project
    _auth_dependency = None


@pytest.fixture(autouse=True)
def _bypass_auth(client):
    if _auth_dependency is None:
        yield
        return
    client.app.dependency_overrides[_auth_dependency] = lambda: {"client_name": "test"}
    yield
    client.app.dependency_overrides.pop(_auth_dependency, None)


def test_send_message_returns_the_reply(client):
    with patch(
        "app.api.v1.endpoints.chat.run_chat", new=AsyncMock(return_value="mocked reply")
    ):
        response = client.post("/api/v1/chat", json={"session_id": "s1", "message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"session_id": "s1", "reply": "mocked reply"}


def test_send_message_calls_the_chat_service_with_the_request_body(client):
    mock_chat = AsyncMock(return_value="mocked reply")

    with patch("app.api.v1.endpoints.chat.run_chat", new=mock_chat):
        client.post("/api/v1/chat", json={"session_id": "s2", "message": "hi there"})

    mock_chat.assert_awaited_once_with("s2", "hi there")


def test_send_message_rejects_a_missing_field(client):
    response = client.post("/api/v1/chat", json={"session_id": "s3"})
    assert response.status_code == 422
