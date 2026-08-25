"""Tests for the chat service. Mocks ``graph.run_graph`` directly so no real
LLM call is ever made.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.features.ai import service


@pytest.fixture(autouse=True)
def _reset_memory_singleton(monkeypatch):
    # The module-level memory singleton is lazily built from settings; force
    # a fresh one per test so no history leaks between tests.
    monkeypatch.setattr(service, "_memory", None)


async def test_chat_returns_the_mocked_reply(monkeypatch):
    session_id = str(uuid.uuid4())
    mock_run_graph = AsyncMock(return_value="mocked reply")
    monkeypatch.setattr(service.graph, "run_graph", mock_run_graph)

    reply = await service.chat(session_id, "hello")

    assert reply == "mocked reply"


async def test_chat_appends_user_and_assistant_turns_to_memory(monkeypatch):
    session_id = str(uuid.uuid4())
    mock_run_graph = AsyncMock(return_value="mocked reply")
    monkeypatch.setattr(service.graph, "run_graph", mock_run_graph)

    await service.chat(session_id, "hello")

    assert service._get_memory().get_history(session_id) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "mocked reply"},
    ]


async def test_chat_passes_prior_turns_as_history_on_the_next_call(monkeypatch):
    session_id = str(uuid.uuid4())
    mock_run_graph = AsyncMock(side_effect=["first reply", "second reply"])
    monkeypatch.setattr(service.graph, "run_graph", mock_run_graph)

    await service.chat(session_id, "one")
    await service.chat(session_id, "two")

    second_call_messages = mock_run_graph.await_args_list[1].args[0]
    assert [m["content"] for m in second_call_messages] == ["one", "first reply", "two"]
