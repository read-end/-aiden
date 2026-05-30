"""FastAPI route definitions for the Aiden API."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from aiden import __version__
from aiden.api.schemas import (
    ChatRequest,
    ChatResponse,
    ConfigUpdate,
    SessionInfo,
    StatusResponse,
)
from aiden.core.engine import Engine
from aiden.core.memory import ConversationMemory

router = APIRouter()

# Active engines (session_id → Engine) — simple in-memory cache
_engines: dict[str, Engine] = {}


def _get_engine(session_id: str) -> Engine:
    """Get or create an engine for the given session."""
    if session_id not in _engines:
        _engines[session_id] = Engine(session_id=session_id)
    return _engines[session_id]


# ── Status ────────────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get server status and configuration."""
    engine = _get_engine("default")
    sessions = ConversationMemory.list_sessions()
    return StatusResponse(
        version=__version__,
        model=engine._model,
        session_count=len(sessions),
        plugin_count=engine.registry.count,
    )


# ── Chat ──────────────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest):
    """Send a message and get a response (supports streaming)."""
    if request.stream:
        return StreamingResponse(
            _stream_chat(request.message, request.session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Request-Session": request.session_id,
            },
        )
    else:
        engine = _get_engine(request.session_id)
        response = await engine.simple_chat(request.message)
        return ChatResponse(session_id=request.session_id, response=response)


async def _stream_chat(message: str, session_id: str) -> AsyncGenerator[str, None]:
    """Stream chat response as SSE events."""
    engine = _get_engine(session_id)
    try:
        async for chunk in engine.chat(message):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


# ── Sessions ──────────────────────────────────────────────────

@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions():
    """List all conversation sessions."""
    sessions = ConversationMemory.list_sessions()
    result = []
    for s in sessions:
        mem = ConversationMemory(s["id"])
        result.append(SessionInfo(
            id=s["id"],
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            message_count=len(mem),
        ))
    return result


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    mem = ConversationMemory(session_id)
    mem.delete()
    _engines.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}


# ── Messages ──────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, limit: int = 50):
    """Get message history for a session."""
    mem = ConversationMemory(session_id)
    messages = mem.get_history(limit=limit)
    return [
        {
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp,
            "tool_calls": m.tool_calls,
        }
        for m in messages
    ]


# ── System Prompt ─────────────────────────────────────────────

@router.get("/sessions/{session_id}/system-prompt")
async def get_system_prompt(session_id: str):
    """Get the custom system prompt for a session."""
    mem = ConversationMemory(session_id)
    return {"session_id": session_id, "system_prompt": mem.system_prompt}


@router.put("/sessions/{session_id}/system-prompt")
async def update_system_prompt(session_id: str, data: dict):
    """Update the system prompt for a session."""
    prompt = data.get("system_prompt", "")
    mem = ConversationMemory(session_id)
    mem.system_prompt = prompt
    return {"session_id": session_id, "system_prompt": prompt}


# ── Plugins ───────────────────────────────────────────────────

@router.get("/plugins")
async def list_plugins():
    """List registered plugins/tools."""
    engine = _get_engine("default")
    return [
        {
            "name": p.spec.name,
            "description": p.spec.description,
            "parameters": p.spec.parameters,
        }
        for p in engine.registry.list_plugins()
    ]
