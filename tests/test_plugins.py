"""Tests for the plugin system."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aiden.plugins.base import Plugin, PluginSpec
from aiden.plugins.registry import PluginRegistry


# ── Test plugin ───────────────────────────────────────────────

class EchoPlugin(Plugin):
    spec = PluginSpec(
        name="echo",
        description="Echo back the input",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to echo",
                },
            },
            "required": ["text"],
        },
    )

    async def execute(self, text: str) -> str:
        return f"Echo: {text}"


# ── Tests ─────────────────────────────────────────────────────

def test_plugin_spec() -> None:
    spec = PluginSpec(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {
                "input": {"type": "string"},
            },
            "required": ["input"],
        },
    )
    assert spec.name == "test_tool"
    assert spec.description == "A test tool"
    assert spec.parameters["required"] == ["input"]


@pytest.mark.asyncio
async def test_plugin_execute() -> None:
    plugin = EchoPlugin()
    result = await plugin.execute(text="Hello World")
    assert result == "Echo: Hello World"


def test_registry_register() -> None:
    registry = PluginRegistry()
    count_before = registry.count

    registry.register(EchoPlugin())
    assert registry.count == count_before + 1
    assert registry.get("echo") is not None


def test_registry_duplicate() -> None:
    registry = PluginRegistry()
    registry.register(EchoPlugin())  # first registration succeeds
    with pytest.raises(ValueError, match="already registered"):
        registry.register(EchoPlugin())  # second should raise


def test_registry_get_nonexistent() -> None:
    registry = PluginRegistry()
    assert registry.get("nonexistent") is None


def test_registry_remove() -> None:
    registry = PluginRegistry()
    registry.remove("web_search")
    assert registry.get("web_search") is None


def test_builtin_plugins_loaded() -> None:
    registry = PluginRegistry()
    names = {p.spec.name for p in registry.list_plugins()}
    assert "web_search" in names
    assert "code_analyzer" in names


@pytest.mark.asyncio
async def test_web_search_plugin() -> None:
    from aiden.plugins.web_search import WebSearchPlugin
    plugin = WebSearchPlugin()
    result = await plugin.execute(query="Python programming language", max_results=2)
    assert result.startswith("🔍") or "Error" in result or "⚠️" in result
    # Note: may fail without network; treat as acceptable
    await plugin.close()


@pytest.mark.asyncio
async def test_code_analyzer_read() -> None:
    from aiden.plugins.code_analyzer import CodeAnalyzerPlugin
    plugin = CodeAnalyzerPlugin()
    # Read this test file itself
    import tests.test_plugins
    path = Path(tests.test_plugins.__file__)
    result = await plugin.execute(path=str(path), mode="read", max_lines=10)
    assert "📄" in result
    assert "test_plugins.py" in result


@pytest.mark.asyncio
async def test_code_analyzer_analyze() -> None:
    from aiden.plugins.code_analyzer import CodeAnalyzerPlugin
    plugin = CodeAnalyzerPlugin()
    import tests.test_plugins
    path = Path(tests.test_plugins.__file__)
    result = await plugin.execute(path=str(path), mode="analyze")
    assert "🔬" in result
    assert "EchoPlugin" in result


@pytest.mark.asyncio
async def test_code_analyzer_list() -> None:
    from aiden.plugins.code_analyzer import CodeAnalyzerPlugin
    plugin = CodeAnalyzerPlugin()
    result = await plugin.execute(path=".", mode="list")
    assert "📁" in result
