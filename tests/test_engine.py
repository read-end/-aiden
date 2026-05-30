"""Tests for the core engine and tool execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from aiden.core.engine import Engine
from aiden.core.memory import ConversationMemory, Message
from aiden.plugins.base import Plugin, PluginSpec


# ── Mock plugin for testing ───────────────────────────────────

class WeatherPlugin(Plugin):
    spec = PluginSpec(
        name="get_weather",
        description="Get the current weather",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name",
                },
            },
            "required": ["city"],
        },
    )

    async def execute(self, city: str) -> str:
        return f"The weather in {city} is sunny, 25°C."


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _temp_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aiden.core.config import settings
    monkeypatch.setattr(settings, "data_dir", tmp_path)


@pytest.fixture
def engine() -> Engine:
    eng = Engine(session_id="test_engine")
    eng.registry.register(WeatherPlugin())
    return eng


# ── Tests ─────────────────────────────────────────────────────

def test_engine_init(engine: Engine) -> None:
    assert engine.session_id == "test_engine"
    assert engine.memory is not None
    assert engine.registry.count >= 3  # 2 built-in + 1 weather


def test_build_messages_empty(engine: Engine) -> None:
    messages = engine._build_messages()
    assert messages == []


def test_build_messages_with_history(engine: Engine) -> None:
    engine.memory.add_message(Message(role="user", content="Hello"))
    engine.memory.add_message(Message(role="assistant", content="Hi!"))

    messages = engine._build_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi!"


def test_tool_definitions_include_plugins(engine: Engine) -> None:
    tools = [
        {
            "name": p.spec.name,
            "description": p.spec.description,
            "input_schema": p.spec.parameters,
        }
        for p in engine.registry.list_plugins()
    ]
    names = {t["name"] for t in tools}
    assert "get_weather" in names
    assert "web_search" in names
    assert "code_analyzer" in names


@pytest.mark.asyncio
async def test_engine_api_key_missing() -> None:
    eng = Engine(session_id="no_key", api_key="")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        await eng.simple_chat("Hello")
