"""Tests for the conversation memory module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aiden.core.memory import ConversationMemory, Message


@pytest.fixture(autouse=True)
def _temp_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Use a temporary directory for each test."""
    from aiden.core.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path)


def test_add_and_retrieve_messages() -> None:
    mem = ConversationMemory("test_session")
    assert len(mem) == 0

    mem.add_message(Message(role="user", content="Hello"))
    mem.add_message(Message(role="assistant", content="Hi there!"))

    assert len(mem) == 2
    history = mem.get_history()
    assert history[0].role == "user"
    assert history[0].content == "Hello"
    assert history[1].role == "assistant"
    assert history[1].content == "Hi there!"


def test_history_limit() -> None:
    mem = ConversationMemory("test_limit")
    for i in range(10):
        mem.add_message(Message(role="user", content=str(i)))

    full = mem.get_history()
    assert len(full) == 10

    limited = mem.get_history(limit=3)
    assert len(limited) == 3
    assert limited[0].content == "7"


def test_clear_messages() -> None:
    mem = ConversationMemory("test_clear")
    mem.add_message(Message(role="user", content="Hello"))
    assert len(mem) == 1
    mem.clear()
    assert len(mem) == 0


def test_system_prompt() -> None:
    mem = ConversationMemory("test_prompt")
    assert mem.system_prompt == ""

    mem.system_prompt = "You are a helpful assistant."
    assert mem.system_prompt == "You are a helpful assistant."


def test_list_sessions() -> None:
    mem1 = ConversationMemory("session_a")
    mem1.add_message(Message(role="user", content="Hello"))

    mem2 = ConversationMemory("session_b")
    mem2.add_message(Message(role="user", content="Hi"))

    sessions = ConversationMemory.list_sessions()
    ids = {s["id"] for s in sessions}
    assert "session_a" in ids
    assert "session_b" in ids


def test_message_with_tool_calls() -> None:
    mem = ConversationMemory("test_tools")
    msg = Message(
        role="assistant",
        content="Let me search that.",
        tool_calls=[
            {
                "type": "tool_use",
                "id": "toolu_abc123",
                "name": "web_search",
                "input": {"query": "test"},
            }
        ],
        tool_use_id="toolu_abc123",
        name="web_search",
    )
    mem.add_message(msg)
    history = mem.get_history()
    assert len(history) == 1
    assert history[0].tool_calls is not None
    assert history[0].tool_use_id == "toolu_abc123"


def test_empty_session() -> None:
    mem = ConversationMemory("fresh_session")
    assert len(mem) == 0
    assert mem.get_history() == []
