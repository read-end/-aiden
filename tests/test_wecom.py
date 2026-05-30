"""Tests for the 企业微信 (WeCom) integration module."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiden.wecom.client import (
    WeComClient,
    TextMessage,
    MarkdownMessage,
    NewsArticle,
    WeComAuthError,
    WeComAPIError,
)
from aiden.wecom.crypto import WeComCrypto
from aiden.wecom.handler import WeComHandler


# ── Test Data ──────────────────────────────────────────────────

TOKEN = "test_token_12345"
CORP_ID = "wx_test_corp_id"

# Generate a valid 43-char EncodingAESKey (32 bytes base64-encoded with padding stripped)
# 企业微信规范: EncodingAESKey = base64(32_bytes).rstrip("=")
import os
_VALID_AES_BYTES = os.urandom(32)
VALID_AES_KEY = base64.b64encode(_VALID_AES_BYTES).decode("utf-8").rstrip("=")
assert len(VALID_AES_KEY) == 43, f"AES key must be 43 chars, got {len(VALID_AES_KEY)}"


@pytest.fixture
def crypto() -> WeComCrypto:
    return WeComCrypto(token=TOKEN, encoding_aes_key=VALID_AES_KEY, corp_id=CORP_ID)


# ── Crypto Tests ───────────────────────────────────────────────

class TestWeComCrypto:
    def test_init_invalid_key(self):
        """Invalid AES key length should raise."""
        with pytest.raises(ValueError, match="Invalid EncodingAESKey"):
            WeComCrypto(token=TOKEN, encoding_aes_key="too_short", corp_id=CORP_ID)

    def test_encrypt_decrypt_roundtrip(self, crypto: WeComCrypto):
        """Encrypt then decrypt should return the original text."""
        original = "<xml><ToUserName><![CDATA[user1]]></ToUserName></xml>"
        encrypted = crypto.encrypt(original)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_signature_generation_and_verification(self, crypto: WeComCrypto):
        """Generated signature should verify correctly."""
        timestamp = str(int(time.time()))
        nonce = "1234567890"
        echo_str = "test_echo_string"

        signature = crypto.generate_signature(timestamp, nonce, echo_str)
        assert crypto.verify_signature(signature, timestamp, nonce, echo_str)

    def test_signature_mismatch(self, crypto: WeComCrypto):
        """Wrong signature should fail verification."""
        assert not crypto.verify_signature(
            "wrong_signature", "12345", "nonce", "echo"
        )

    def test_verify_url_success(self, crypto: WeComCrypto):
        """URL verification should decrypt echostr correctly."""
        # Encrypt a known string
        original = "test_echostr_content"
        encrypted = crypto.encrypt(original)
        timestamp = str(int(time.time()))
        nonce = "test_nonce"
        signature = crypto.generate_signature(timestamp, nonce, encrypted)

        result = crypto.verify_url(signature, timestamp, nonce, encrypted)
        assert result == original

    def test_verify_url_fail(self, crypto: WeComCrypto):
        """Wrong signature on URL verification should raise."""
        with pytest.raises(ValueError, match="Signature verification failed"):
            crypto.verify_url("bad_sig", "123", "456", "encrypted")

    def test_decrypt_wrong_corp_id(self):
        """Decrypting with wrong CorpID should raise."""
        crypto_a = WeComCrypto(token=TOKEN, encoding_aes_key=VALID_AES_KEY, corp_id="corp_a")
        crypto_b = WeComCrypto(token=TOKEN, encoding_aes_key=VALID_AES_KEY, corp_id="corp_b")

        encrypted = crypto_a.encrypt("hello")
        with pytest.raises(ValueError, match="CorpID mismatch"):
            crypto_b.decrypt(encrypted)


# ── Client Tests ───────────────────────────────────────────────

class TestWeComClient:
    @pytest.fixture
    def client(self) -> WeComClient:
        return WeComClient(
            corp_id="test_corp",
            agent_id=1000001,
            secret="test_secret",
        )

    @pytest.mark.asyncio
    async def test_send_text(self, client: WeComClient):
        """Test text message sending with mocked API."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "errcode": 0,
            "errmsg": "ok",
            "invaliduser": "",
        }
        client._client.request = AsyncMock(return_value=mock_resp)
        client._token = "fake_token"
        client._token_expires_at = time.time() + 3600

        result = await client.send_text(
            TextMessage(content="Hello from Aiden!"),
            to_user="user123",
        )
        assert result["errcode"] == 0
        assert result["errmsg"] == "ok"

    @pytest.mark.asyncio
    async def test_send_markdown(self, client: WeComClient):
        """Test markdown message sending."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
        client._client.request = AsyncMock(return_value=mock_resp)
        client._token = "fake_token"
        client._token_expires_at = time.time() + 3600

        result = await client.send_markdown(
            MarkdownMessage(content="# Hello\nThis is **bold** text."),
            to_user="user123",
        )
        assert result["errcode"] == 0

    @pytest.mark.asyncio
    async def test_send_news(self, client: WeComClient):
        """Test news article message sending."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
        client._client.request = AsyncMock(return_value=mock_resp)
        client._token = "fake_token"
        client._token_expires_at = time.time() + 3600

        articles = [
            NewsArticle(
                title="Aiden AI Assistant",
                url="https://github.com/read-end/-aiden",
                description="A modular AI personal assistant",
            )
        ]
        result = await client.send_news(articles, to_user="user123")
        assert result["errcode"] == 0

    @pytest.mark.asyncio
    async def test_missing_config_raises(self):
        """Client without config should raise."""
        client = WeComClient(corp_id="", agent_id=0, secret="")
        with pytest.raises(WeComAuthError, match="企业微信未配置"):
            await client._ensure_token()

    @pytest.mark.asyncio
    async def test_token_refresh_on_401(self, client: WeComClient):
        """Should automatically refresh token on 40014 error."""
        # First call returns token error
        mock_resp_1 = MagicMock()
        mock_resp_1.json.return_value = {"errcode": 40014, "errmsg": "invalid access_token"}

        # Second call succeeds after refresh
        mock_resp_2 = MagicMock()
        mock_resp_2.json.return_value = {"errcode": 0, "errmsg": "ok"}

        # Mock gettoken (token refresh) to succeed
        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {
            "errcode": 0,
            "access_token": "new_token",
            "expires_in": 7200,
        }

        client._client.request = AsyncMock()
        # First call for gettoken, then for send_text (fails), then gettoken again, then send_text (succeeds)
        client._client.request.side_effect = [
            mock_token_resp,  # _ensure_token
            mock_resp_1,      # send_text (401)
            mock_token_resp,  # _ensure_token retry
            mock_resp_2,      # send_text retry (succeeds)
        ]

        result = await client.send_text(TextMessage(content="test"))
        assert result["errcode"] == 0


# ── Handler Tests ──────────────────────────────────────────────

class TestWeComHandler:
    @pytest.fixture
    def handler(self) -> WeComHandler:
        mock_client = MagicMock(spec=WeComClient)
        mock_client.send_text = AsyncMock()
        mock_client.send_markdown = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.simple_chat = AsyncMock(return_value="你好！我是 Aiden。")
        mock_engine.memory = MagicMock()
        mock_engine.memory.__len__ = MagicMock(return_value=5)
        mock_engine.registry.list_plugins = MagicMock(return_value=[])

        def get_engine(session_id: str):
            return mock_engine

        return WeComHandler(client=mock_client, engine_getter=get_engine)

    def test_build_reply_xml(self, handler: WeComHandler):
        """Reply XML should have correct structure."""
        xml = handler._build_reply_xml("user1", "bot1", "Hello!")
        assert "<ToUserName><![CDATA[user1]]></ToUserName>" in xml
        assert "<FromUserName><![CDATA[bot1]]></FromUserName>" in xml
        assert "<Content><![CDATA[Hello!]]></Content>" in xml
        assert "<MsgType><![CDATA[text]]></MsgType>" in xml

    @pytest.mark.asyncio
    async def test_handle_text_message(self, handler: WeComHandler):
        """Text message should be routed to AI engine."""
        xml = (
            "<xml>"
            "<ToUserName><![CDATA[bot1]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1234567890</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[你好，请问Python怎么学？]]></Content>"
            "<MsgId>123456</MsgId>"
            "</xml>"
        )
        response = await handler.handle(xml)
        assert "<Content><![CDATA[你好！我是 Aiden。" in response

    @pytest.mark.asyncio
    async def test_handle_subscribe_event(self, handler: WeComHandler):
        """Subscribe event should return welcome message."""
        xml = (
            "<xml>"
            "<ToUserName><![CDATA[bot1]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1234567890</CreateTime>"
            "<MsgType><![CDATA[event]]></MsgType>"
            "<Event><![CDATA[subscribe]]></Event>"
            "</xml>"
        )
        response = await handler.handle(xml)
        assert "Aiden" in response
        assert "联网搜索" in response

    @pytest.mark.asyncio
    async def test_handle_help_command(self, handler: WeComHandler):
        """/help should return local help without AI call."""
        xml = (
            "<xml>"
            "<ToUserName><![CDATA[bot1]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1234567890</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[/help]]></Content>"
            "<MsgId>123456</MsgId>"
            "</xml>"
        )
        response = await handler.handle(xml)
        assert "Aiden 帮助" in response
        # AI should NOT have been called
        handler._get_engine("wecom_user1").simple_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_clear_command(self, handler: WeComHandler):
        """/clear should clear memory without AI call."""
        xml = (
            "<xml>"
            "<ToUserName><![CDATA[bot1]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1234567890</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[/clear]]></Content>"
            "<MsgId>123456</MsgId>"
            "</xml>"
        )
        response = await handler.handle(xml)
        assert "已清除" in response
        handler._get_engine("wecom_user1").memory.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_empty_text(self, handler: WeComHandler):
        """Empty text should return a prompt."""
        xml = (
            "<xml>"
            "<ToUserName><![CDATA[bot1]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1234567890</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[]]></Content>"
            "<MsgId>123456</MsgId>"
            "</xml>"
        )
        response = await handler.handle(xml)
        assert "你好" in response

    @pytest.mark.asyncio
    async def test_handle_unknown_message_type(self, handler: WeComHandler):
        """Unknown message type should return a friendly message."""
        xml = (
            "<xml>"
            "<ToUserName><![CDATA[bot1]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1234567890</CreateTime>"
            "<MsgType><![CDATA[location]]></MsgType>"
            "<Content><![CDATA[some location]]></Content>"
            "</xml>"
        )
        response = await handler.handle(xml)
        assert "暂不支持" in response

    @pytest.mark.asyncio
    async def test_long_response_truncated(self, handler: WeComHandler):
        """Long responses should be truncated in sync reply and sent via API."""
        long_reply = "A" * 3000
        handler._get_engine("wecom_user1").simple_chat = AsyncMock(return_value=long_reply)

        xml = (
            "<xml>"
            "<ToUserName><![CDATA[bot1]]></ToUserName>"
            "<FromUserName><![CDATA[user1]]></FromUserName>"
            "<CreateTime>1234567890</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[帮我写篇文章]]></Content>"
            "<MsgId>123456</MsgId>"
            "</xml>"
        )
        response = await handler.handle(xml)
        assert "正在处理中" in response
        # Verify async push was attempted
        handler._client.send_markdown.assert_called_once()
