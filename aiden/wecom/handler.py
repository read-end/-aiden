"""
WeCom message handler — routes incoming messages to Aiden engine.

Handles:
  - Text messages → AI processing via Claude
  - Event messages (subscribe, enter app)
  - Error handling with user-friendly fallback messages
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from aiden.wecom.client import WeComClient, TextMessage, MarkdownMessage


class WeComHandler:
    """Process incoming 企业微信 messages and route them to Aiden."""

    def __init__(self, client: WeComClient, engine_getter) -> None:
        """
        Args:
            client: WeComClient instance for sending responses
            engine_getter: callable(session_id) -> Engine
                           (avoids circular import by accepting the engine factory)
        """
        self._client = client
        self._get_engine = engine_getter

    # ── Main entry point ───────────────────────────────────

    async def handle(self, xml_body: str) -> str:
        """Process an incoming message XML and return a response XML.

        Returns an empty string for async responses (reply via API),
        or a response XML for sync replies.
        """
        root = ET.fromstring(xml_body)
        msg_type = root.findtext("MsgType", "")

        handlers = {
            "text": self._handle_text,
            "event": self._handle_event,
            "image": self._handle_image,
            "voice": self._handle_voice,
        }

        handler = handlers.get(msg_type)
        if handler:
            return await handler(root)

        # Unknown message type
        return self._build_reply_xml(
            root.findtext("FromUserName", ""),
            root.findtext("ToUserName", ""),
            f"暂不支持 {msg_type} 类型的消息。请发送文字消息与我交流。",
        )

    # ── Message type handlers ──────────────────────────────

    async def _handle_text(self, root: ET.Element) -> str:
        """Handle incoming text message."""
        content = root.findtext("Content", "").strip()
        from_user = root.findtext("FromUserName", "")
        to_user = root.findtext("ToUserName", "")
        msg_id = root.findtext("MsgId", "0")

        if not content:
            return self._build_reply_xml(
                from_user, to_user, "你好！请输入你想了解的内容。"
            )

        # If it's a command, handle locally
        if content.startswith("/"):
            local_reply = self._handle_local_command(content, from_user)
            if local_reply:
                return self._build_reply_xml(from_user, to_user, local_reply)

        # Route to Aiden engine for AI processing
        try:
            engine = self._get_engine(f"wecom_{from_user}")
            reply = await engine.simple_chat(content)

            # 企业微信要求被动回复必须在 5 秒内响应
            # 对于需要联网搜索等耗时操作，先返回一个"正在思考"消息，
            # 然后通过主动推送发送完整结果
            if len(reply) > 2000:
                # Truncate for sync reply, send full via push
                await self._send_long_reply(from_user, reply)
                return self._build_reply_xml(
                    from_user, to_user,
                    "🤔 正在处理中，请稍候...\n"
                    "结果较长，将通过消息推送发送给您。"
                )

            return self._build_reply_xml(from_user, to_user, reply[:2000])
        except Exception as e:
            error_msg = (
                "😅 抱歉，处理消息时出现了点问题。\n"
                f"错误: {type(e).__name__}\n"
                "请稍后再试，或联系管理员。"
            )
            return self._build_reply_xml(from_user, to_user, error_msg)

    async def _handle_event(self, root: ET.Element) -> str:
        """Handle event messages."""
        event = root.findtext("Event", "")
        from_user = root.findtext("FromUserName", "")
        to_user = root.findtext("ToUserName", "")

        welcome_msg = (
            "🤖 你好！我是 **Aiden**，你的 AI 个人助手。\n\n"
            "我可以帮你：\n"
            "🔍 **联网搜索** — 实时获取最新信息\n"
            "📄 **代码分析** — 阅读和理解代码文件\n"
            "💬 **智能对话** — 基于 Claude AI 的深度思考\n\n"
            "直接发送消息即可开始对话！"
        )

        replies = {
            "subscribe": welcome_msg,
            "enter_agent": "🤖 我准备好啦！有什么可以帮你的？",
            "unsubscribe": "",
        }

        reply = replies.get(event, f"收到事件: {event}")
        if not reply:
            return ""

        return self._build_reply_xml(from_user, to_user, reply)

    async def _handle_image(self, root: ET.Element) -> str:
        """Handle image message (placeholder for future Vision support)."""
        from_user = root.findtext("FromUserName", "")
        to_user = root.findtext("ToUserName", "")
        return self._build_reply_xml(
            from_user, to_user,
            "📷 已收到图片。图片识别功能正在开发中，敬请期待！"
        )

    async def _handle_voice(self, root: ET.Element) -> str:
        """Handle voice message (placeholder for future support)."""
        from_user = root.findtext("FromUserName", "")
        to_user = root.findtext("ToUserName", "")
        return self._build_reply_xml(
            from_user, to_user,
            "🎤 已收到语音。语音识别功能正在开发中，请发送文字消息。"
        )

    # ── Local commands ─────────────────────────────────────

    def _handle_local_command(self, content: str, from_user: str) -> Optional[str]:
        """Handle commands that don't need AI processing."""
        cmd = content.lower().strip()

        if cmd == "/help":
            return (
                "📋 **Aiden 帮助**\n\n"
                "直接发送消息即可与我对话。\n\n"
                "我支持：\n"
                "• 通用问答 — 任何你有疑问的话题\n"
                "• 联网搜索 — 最新信息查询\n"
                "• 代码分析 — 代码理解和审查\n\n"
                "可用命令：\n"
                "  /help  — 显示此帮助\n"
                "  /clear — 清除对话历史\n"
                "  /stats — 查看会话统计"
            )
        if cmd == "/clear":
            engine = self._get_engine(f"wecom_{from_user}")
            engine.memory.clear()
            return "✅ 对话历史已清除，让我们重新开始吧！"
        if cmd == "/stats":
            engine = self._get_engine(f"wecom_{from_user}")
            mem = engine.memory
            plugins = engine.registry.list_plugins()
            return (
                f"📊 **会话统计**\n\n"
                f"消息数: {len(mem)}\n"
                f"插件数: {len(plugins)}\n"
                f"模型: {engine._model}\n"
                f"会话: wecom_{from_user}\n"
            )

        return None

    # ── Long message handling ──────────────────────────────

    async def _send_long_reply(self, user_id: str, content: str) -> None:
        """Send a long response asynchronously via the API."""
        try:
            # Try markdown first for rich formatting
            await self._client.send_markdown(
                MarkdownMessage(content=content[:4096]),
                to_user=user_id,
            )
        except Exception:
            # Fallback to plain text
            try:
                await self._client.send_text(
                    TextMessage(content=content[:2048]),
                    to_user=user_id,
                )
            except Exception as e:
                # Log and give up — no way to notify user at this point
                print(f"[WeCom] Failed to send long reply to {user_id}: {e}")

    # ── XML helpers ────────────────────────────────────────

    @staticmethod
    def _build_reply_xml(
        from_user: str, to_user: str, content: str
    ) -> str:
        """Build a passive response XML for sync replies."""
        import time
        timestamp = str(int(time.time()))
        # CDATA escaping for XML
        safe_content = content.replace("]]>", "]]]]><![CDATA[>")
        return (
            f"<xml>"
            f"<ToUserName><![CDATA[{from_user}]]></ToUserName>"
            f"<FromUserName><![CDATA[{to_user}]]></FromUserName>"
            f"<CreateTime>{timestamp}</CreateTime>"
            f"<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{safe_content}]]></Content>"
            f"</xml>"
        )
