"""
WeCom API Client — handles authentication and message sending.

Supports:
  - Automatic access token management with caching
  - Send text and markdown messages
  - Send interactive card messages
  - Automatic token refresh on expiry

API Docs: https://developer.work.weixin.qq.com/document/path/90236
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from aiden.core.config import settings


# ── Exceptions ────────────────────────────────────────────────

class WeComError(Exception):
    """Base exception for WeCom API errors."""

class WeComAuthError(WeComError):
    """Authentication/authorization error."""

class WeComAPIError(WeComError):
    """General API error."""


# ── Message types ─────────────────────────────────────────────

@dataclass
class TextMessage:
    content: str
    safe: int = 0  # 0=plain text, 1=secret message


@dataclass
class MarkdownMessage:
    content: str  # Markdown formatted text


@dataclass
class NewsArticle:
    title: str
    url: str
    description: str = ""
    picurl: str = ""


@dataclass
class InteractiveTaskCard:
    title: str
    description: str
    url: str
    task_id: str
    btn_text: str = "查看详情"


# ── API Client ────────────────────────────────────────────────

class WeComClient:
    """Enterprise微信 API client with automatic token management."""

    API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(
        self,
        corp_id: Optional[str] = None,
        agent_id: Optional[int] = None,
        secret: Optional[str] = None,
    ) -> None:
        self._corp_id = corp_id or settings.wecom_corp_id
        self._agent_id = agent_id or settings.wecom_agent_id
        self._secret = secret or settings.wecom_secret
        self._token: str = ""
        self._token_expires_at: float = 0
        self._client = httpx.AsyncClient(timeout=15.0)

    # ── Token Management ────────────────────────────────────

    async def _ensure_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        if self._token and time.time() < self._token_expires_at:
            return self._token

        if not self._corp_id or not self._secret:
            raise WeComAuthError(
                "企业微信未配置。请在 .env 中设置:\n"
                "  WECOM_CORP_ID=xxx\n"
                "  WECOM_AGENT_ID=xxx\n"
                "  WECOM_SECRET=xxx"
            )

        resp = await self._client.get(
            f"{self.API_BASE}/gettoken",
            params={
                "corpid": self._corp_id,
                "corpsecret": self._secret,
            },
        )
        data = resp.json()
        if data.get("errcode") != 0:
            raise WeComAuthError(
                f"获取 access_token 失败: {data.get('errmsg', 'unknown error')}"
                f" (code={data.get('errcode')})"
            )

        self._token = data["access_token"]
        # Refresh 5 minutes before actual expiry (token valid for 7200s)
        self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
        return self._token

    async def _request(
        self, method: str, path: str, **kwargs
    ) -> dict:
        """Make an authenticated API request with automatic retry on 401."""
        token = await self._ensure_token()
        url = f"{self.API_BASE}/{path}"
        params = {"access_token": token}
        params.update(kwargs.get("params", {}))
        kwargs["params"] = params

        resp = await self._client.request(method, url, **kwargs)
        data = resp.json()

        # Token expired — refresh and retry once
        if data.get("errcode") == 40014 or data.get("errcode") == 42001:
            self._token = ""
            token = await self._ensure_token()
            params["access_token"] = token
            resp = await self._client.request(method, url, **kwargs)
            data = resp.json()

        if data.get("errcode") != 0:
            raise WeComAPIError(
                f"API 错误: {data.get('errmsg', 'unknown')}"
                f" (code={data.get('errcode')})"
            )

        return data

    # ── Send Message ───────────────────────────────────────

    async def send_text(self, message: TextMessage, to_user: str = "@all") -> dict:
        """Send a text message to a user or group."""
        return await self._request(
            "POST",
            "message/send",
            json={
                "touser": to_user,
                "msgtype": "text",
                "agentid": self._agent_id,
                "text": {"content": message.content},
                "safe": message.safe,
            },
        )

    async def send_markdown(self, message: MarkdownMessage, to_user: str = "@all") -> dict:
        """Send a markdown message."""
        return await self._request(
            "POST",
            "message/send",
            json={
                "touser": to_user,
                "msgtype": "markdown",
                "agentid": self._agent_id,
                "markdown": {"content": message.content},
            },
        )

    async def send_news(self, articles: list[NewsArticle], to_user: str = "@all") -> dict:
        """Send a news/article card message."""
        return await self._request(
            "POST",
            "message/send",
            json={
                "touser": to_user,
                "msgtype": "news",
                "agentid": self._agent_id,
                "news": {
                    "articles": [
                        {
                            "title": a.title,
                            "url": a.url,
                            "description": a.description,
                            "picurl": a.picurl,
                        }
                        for a in articles
                    ]
                },
            },
        )

    async def send_task_card(
        self, task: InteractiveTaskCard, to_user: str = "@all"
    ) -> dict:
        """Send an interactive task card message."""
        return await self._request(
            "POST",
            "message/send",
            json={
                "touser": to_user,
                "msgtype": "interactive_taskcard",
                "agentid": self._agent_id,
                "interactive_taskcard": {
                    "title": task.title,
                    "description": task.description,
                    "url": task.url,
                    "task_id": task.task_id,
                    "btn": [
                        {"key": "view", "name": task.btn_text},
                    ],
                },
            },
        )

    async def reply_text(
        self, content: str, conversation_id: str
    ) -> dict:
        """Reply in a conversation (passive, via callback)."""
        # For passive replies, we send to the specific user
        return await self.send_text(TextMessage(content), to_user=conversation_id)

    # ── Get User Info ──────────────────────────────────────

    async def get_user_info(self, user_id: str) -> dict:
        """Get detailed user information by UserID."""
        return await self._request("GET", "user/get", params={"userid": user_id})

    # ── Cleanup ────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()
