"""
Plugin base classes.

Defines the abstract interface all plugins must implement.
Plugins map to Claude Tool Use — each plugin is one tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field


class PluginSpec(BaseModel):
    """Specification for Claude Tool Use — maps directly to tool schema."""

    name: str = Field(description="Tool name (snake_case, 1-64 chars)")
    description: str = Field(description="What this tool does")
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        },
        description="JSON Schema for tool parameters",
    )


class Plugin(ABC):
    """Base class for all Aiden plugins.

    Subclasses must define:
      - `spec`: a PluginSpec describing the tool
      - `execute(**kwargs)`: the actual tool logic
    """

    spec: PluginSpec

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the plugin with the given arguments.

        Args:
            **kwargs: Arguments matching the plugin's parameter schema.

        Returns:
            A string result to be sent back to the LLM.
        """
        ...

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description
