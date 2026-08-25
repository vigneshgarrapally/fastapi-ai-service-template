"""Chat service — the single entry point both the sync endpoint and the async
worker call into (see ``app/api/v1/endpoints/chat.py`` and
``app/worker/ai_job_worker.py``), so there is exactly one code path that
talks to the agent.

``graph`` is imported as a module (not ``from app.features.ai.graph import
run_graph``) specifically so tests can monkeypatch ``graph.run_graph`` and
have it take effect here without patching this module directly.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.features.ai import graph
from app.features.ai.memory import ConversationMemory

_memory: ConversationMemory | None = None


def _get_memory() -> ConversationMemory:
    global _memory
    if _memory is None:
        _memory = ConversationMemory(get_settings().ai.max_history_messages)
    return _memory


async def chat(session_id: str, message: str) -> str:
    """Run one conversational turn and persist it to the session's history.

    Args:
        session_id: Client-supplied conversation identifier.
        message: The user's message for this turn.

    Returns:
        The assistant's reply text.
    """
    memory = _get_memory()
    memory.append(session_id, "user", message)
    reply = await graph.run_graph(memory.get_history(session_id))
    memory.append(session_id, "assistant", reply)
    return reply
