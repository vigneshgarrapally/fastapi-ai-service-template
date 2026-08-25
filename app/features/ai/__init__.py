"""Conversational AI agent: system prompt, tools, memory, and the LangGraph loop.

``service.chat()`` is the single entry point — both the synchronous ``/chat``
endpoint and the async job worker call into it, so there is exactly one code
path that talks to the agent.
"""
