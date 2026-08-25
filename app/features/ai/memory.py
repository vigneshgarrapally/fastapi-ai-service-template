"""In-process conversation history, keyed by session id.

This is in-process only: history is lost on restart and not shared across
replicas. A real deployment should back this with Postgres or Redis instead
(see ``app.infrastructure.cache`` if ``include_cache`` is enabled for a
starting point) — building that is out of scope for this template's default.
"""

from __future__ import annotations


class ConversationMemory:
    """Fixed-size, in-process message history per session.

    Args:
        max_messages: Maximum number of messages retained per session. The
            oldest messages are dropped once a session exceeds this cap.
    """

    def __init__(self, max_messages: int) -> None:
        self._max_messages = max_messages
        self._sessions: dict[str, list[dict[str, str]]] = {}

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Return a copy of the stored history for a session (empty if unseen)."""
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append one message to a session's history, trimming to the cap."""
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": role, "content": content})
        overflow = len(history) - self._max_messages
        if overflow > 0:
            del history[:overflow]
