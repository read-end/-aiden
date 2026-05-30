"""
Aiden Engine — the core agent loop.

Orchestrates: receive message → build context → call LLM →
handle tool calls → stream response → save to memory.

Uses Anthropic Claude Messages API with Tool Use.
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional

from anthropic import AsyncAnthropic
from anthropic.types import (
    MessageParam,
    ContentBlockParam,
    ToolUseBlock,
    TextBlock,
)

from aiden.core.config import settings
from aiden.core.memory import ConversationMemory, Message
from aiden.plugins.registry import PluginRegistry


# ── System prompt ─────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = """You are **Aiden**, an intelligent AI personal assistant.

You have access to tools that let you:
1. **Search the web** — fetch real-time information when asked.
2. **Analyze code** — read, summarize, and inspect code files.

**Guidelines:**
- Be helpful, concise, and accurate.
- When using a tool, explain what you're doing and why.
- If a tool returns an error, inform the user clearly.
- If you're unsure about something, say so — don't make things up.
- Use markdown formatting for readability.
"""


# ── Tool definitions (Claude Tool Use format) ─────────────────

def _build_tools(registry: PluginRegistry) -> list[dict]:
    """Build the tools array for the Anthropic API from registered plugins."""
    return [
        {
            "name": plugin.spec.name,
            "description": plugin.spec.description,
            "input_schema": plugin.spec.parameters,
        }
        for plugin in registry.list_plugins()
    ]


# ── Engine ────────────────────────────────────────────────────

class Engine:
    """Main agent engine that orchestrates conversations."""

    def __init__(
        self,
        session_id: str = "default",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.session_id = session_id
        self.memory = ConversationMemory(session_id)
        self.registry = PluginRegistry()
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.model
        self._client: Optional[AsyncAnthropic] = None

    # ── lazy client ──────────────────────────────────────────

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Set it in .env or pass api_key to Engine()."
                )
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    # ── public API ───────────────────────────────────────────

    async def chat(
        self, user_message: str
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message through the agent loop.
        Yields response text chunks as they arrive.
        """
        # 1. Save user message
        self.memory.add_message(Message(role="user", content=user_message))

        # 2. Build message history for Claude
        messages = self._build_messages()

        # 3. Gather available tools
        tools = _build_tools(self.registry)

        # 4. Main agent loop — may make multiple API calls for tool use
        full_response: list[ContentBlockParam] = []
        while True:
            response = await self._get_client().messages.create(
                model=self._model,
                max_tokens=settings.max_tokens,
                temperature=settings.temperature,
                system=self.memory.system_prompt or DEFAULT_SYSTEM_PROMPT,
                messages=messages,
                tools=tools if tools else None,
            )

            # Process response content blocks
            tool_results: list[MessageParam] = []
            response_text = ""

            for block in response.content:
                if isinstance(block, TextBlock):
                    response_text += block.text
                    yield block.text
                    full_response.append(block)

                elif isinstance(block, ToolUseBlock):
                    full_response.append(block)
                    # Execute the tool
                    tool_result = await self._execute_tool(block)
                    tool_results.append(tool_result)

            # If no tool calls, we're done
            if not tool_results:
                break

            # Append assistant response to messages and continue
            messages.append({"role": "assistant", "content": full_response})
            messages.extend(tool_results)
            full_response = []

        # 5. Save assistant response
        final_text = "".join(
            b.text for b in full_response if isinstance(b, TextBlock)
        ) if full_response else response_text

        if final_text:
            self.memory.add_message(Message(role="assistant", content=final_text))

    async def simple_chat(self, user_message: str) -> str:
        """Non-streaming chat — returns the full response."""
        chunks: list[str] = []
        async for chunk in self.chat(user_message):
            chunks.append(chunk)
        return "".join(chunks)

    # ── internals ────────────────────────────────────────────

    def _build_messages(self) -> list[MessageParam]:
        """Convert stored messages to Anthropic API format."""
        history = self.memory.get_history(limit=50)
        messages: list[MessageParam] = []
        for msg in history:
            if msg.role == "system":
                continue  # system prompt is passed separately
            if msg.role == "tool_result":
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_use_id or "",
                            "content": msg.content,
                        }
                    ],
                })
            else:
                entry: MessageParam = {"role": msg.role, "content": msg.content}
                if msg.tool_calls:
                    entry["content"] = [
                        {"type": "text", "text": msg.content}
                    ] + msg.tool_calls
                messages.append(entry)
        return messages

    async def _execute_tool(self, block: ToolUseBlock) -> MessageParam:
        """Execute a tool call and return a tool_result message."""
        try:
            plugin_name = block.name
            plugin = self.registry.get(plugin_name)
            if plugin is None:
                result_text = f"Error: unknown tool '{plugin_name}'"
            else:
                result_text = await plugin.execute(**block.input)
        except Exception as exc:
            result_text = f"Error executing {block.name}: {exc}"

        # Save to memory
        self.memory.add_message(Message(
            role="tool_result",
            content=result_text,
            tool_use_id=block.id,
            name=block.name,
        ))

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                }
            ],
        }
