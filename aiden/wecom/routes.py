"""
FastAPI routes for 企业微信 callback integration.

GET  /api/v1/wecom/callback  — URL verification (decrypt echostr)
POST /api/v1/wecom/callback  — Message receiving (encrypted XML)

Both endpoints handle the enterprise微信 encryption protocol:
  1. Verify msg_signature via SHA1(token + timestamp + nonce + encrypted)
  2. Decrypt request body with AES-256-CBC
  3. Process message
  4. Encrypt response
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException, Query, Request

from aiden.core.config import settings
from aiden.core.engine import Engine
from aiden.wecom.crypto import WeComCrypto
from aiden.wecom.handler import WeComHandler
from aiden.wecom.client import WeComClient

# ── Router ────────────────────────────────────────────────────

router = APIRouter()

# Lazy initialization
_crypto: WeComCrypto | None = None
_handler: WeComHandler | None = None
_client: WeComClient | None = None


def _ensure_crypto() -> WeComCrypto:
    global _crypto
    if _crypto is None:
        if not settings.wecom_token or not settings.wecom_encoding_aes_key:
            raise RuntimeError(
                "企业微信回调未配置。请在 .env 中设置:\n"
                "  WECOM_TOKEN=xxx\n"
                "  WECOM_ENCODING_AES_KEY=xxx"
            )
        _crypto = WeComCrypto(
            token=settings.wecom_token,
            encoding_aes_key=settings.wecom_encoding_aes_key,
            corp_id=settings.wecom_corp_id,
        )
    return _crypto


def _ensure_handler() -> WeComHandler:
    global _client, _handler
    if _handler is None:
        _client = WeComClient()
        _handler = WeComHandler(
            client=_client,
            engine_getter=lambda sid: Engine(session_id=sid),
        )
    return _handler


# ── URL Verification (GET) ────────────────────────────────────

@router.get("/callback")
async def verify_url(
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """Verify callback URL — called by 企业微信 when setting up the callback.

    Decrypts echostr and returns it as plaintext.
    """
    try:
        crypto = _ensure_crypto()
        decrypted = crypto.verify_url(msg_signature, timestamp, nonce, echostr)
        return decrypted
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Message Callback (POST) ───────────────────────────────────

@router.post("/callback")
async def receive_message(
    request: Request,
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """Receive an encrypted message from 企业微信.

    1. Verifies msg_signature
    2. Decrypts the message XML
    3. Processes via WeComHandler → Aiden Engine
    4. Encrypts and returns the response
    """
    try:
        # Read raw XML body
        body = await request.body()
        xml_str = body.decode("utf-8")

        # 1. Verify signature
        crypto = _ensure_crypto()

        # 2. Extract Encrypt node from XML
        root = ET.fromstring(xml_str)
        encrypt_node = root.findtext("Encrypt")
        if not encrypt_node:
            raise HTTPException(status_code=400, detail="Missing Encrypt node in XML")

        # Verify signature against the encrypted message
        if not crypto.verify_signature(msg_signature, timestamp, nonce, encrypt_node):
            raise HTTPException(status_code=400, detail="Signature verification failed")

        # 3. Decrypt the message
        decrypted_xml = crypto.decrypt(encrypt_node)

        # 4. Process with handler
        handler = _ensure_handler()
        reply_xml = await handler.handle(decrypted_xml)

        # 5. If there's a reply, encrypt it
        if reply_xml.strip():
            encrypted_reply = crypto.encrypt(reply_xml)
            new_nonce = str(hash(nonce + "reply"))[:16] if nonce else "aiden"
            new_timestamp = str(int(__import__("time").time()))
            new_signature = crypto.generate_signature(
                new_timestamp, new_nonce, encrypted_reply
            )

            # Build response XML
            response_xml = (
                f"<xml>"
                f"<Encrypt><![CDATA[{encrypted_reply}]]></Encrypt>"
                f"<MsgSignature><![CDATA[{new_signature}]]></MsgSignature>"
                f"<TimeStamp>{new_timestamp}</TimeStamp>"
                f"<Nonce><![CDATA[{new_nonce}]]></Nonce>"
                f"</xml>"
            )
            return response_xml

        # Empty reply (e.g., unsubscribe event)
        return ""

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {type(e).__name__}")
