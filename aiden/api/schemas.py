"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)
    session_id: str = Field(default="default", max_length=128)
    stream: bool = Field(default=True)


class ChatResponse(BaseModel):
    session_id: str
    response: str


class SessionInfo(BaseModel):
    id: str
    created_at: str
    updated_at: str
    message_count: int


class ConfigUpdate(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=8192)


class StatusResponse(BaseModel):
    status: str = "ok"
    version: str
    model: str
    session_count: int
    plugin_count: int
