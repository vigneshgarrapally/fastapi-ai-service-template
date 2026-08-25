"""Tests for ConversationMemory's history-cap behavior."""

from app.features.ai.memory import ConversationMemory


def test_get_history_empty_for_unseen_session():
    memory = ConversationMemory(max_messages=5)
    assert memory.get_history("unknown") == []


def test_append_accumulates_history_in_order():
    memory = ConversationMemory(max_messages=5)
    memory.append("s1", "user", "hi")
    memory.append("s1", "assistant", "hello")
    assert memory.get_history("s1") == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_history_is_capped_and_drops_oldest_first():
    memory = ConversationMemory(max_messages=3)
    for i in range(5):
        memory.append("s1", "user", f"msg-{i}")

    history = memory.get_history("s1")

    assert len(history) == 3
    assert [m["content"] for m in history] == ["msg-2", "msg-3", "msg-4"]


def test_sessions_are_isolated_from_each_other():
    memory = ConversationMemory(max_messages=5)
    memory.append("s1", "user", "a")
    memory.append("s2", "user", "b")

    assert memory.get_history("s1") == [{"role": "user", "content": "a"}]
    assert memory.get_history("s2") == [{"role": "user", "content": "b"}]


def test_get_history_returns_a_copy_not_a_live_reference():
    memory = ConversationMemory(max_messages=5)
    memory.append("s1", "user", "a")

    history = memory.get_history("s1")
    history.append({"role": "user", "content": "mutated"})

    assert memory.get_history("s1") == [{"role": "user", "content": "a"}]
