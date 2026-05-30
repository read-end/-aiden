"""
Plugin registry — discovers, registers, and provides access to plugins.

Two registration modes:
  1. Manual: Registry.register(plugin_instance)
  2. Auto-discovery (future): scan a directory for Plugin subclasses
"""

from __future__ import annotations

from typing import Optional

from aiden.plugins.base import Plugin
from aiden.plugins.web_search import WebSearchPlugin
from aiden.plugins.code_analyzer import CodeAnalyzerPlugin


class PluginRegistry:
    """Central registry for all available plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in plugins."""
        self.register(WebSearchPlugin())
        self.register(CodeAnalyzerPlugin())

    def register(self, plugin: Plugin) -> None:
        """Register a plugin by its spec name."""
        name = plugin.spec.name
        if name in self._plugins:
            raise ValueError(f"Plugin '{name}' is already registered")
        self._plugins[name] = plugin

    def get(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name, or None if not found."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[Plugin]:
        """Return all registered plugins."""
        return list(self._plugins.values())

    def remove(self, name: str) -> None:
        """Unregister a plugin by name."""
        self._plugins.pop(name, None)

    @property
    def count(self) -> int:
        return len(self._plugins)
