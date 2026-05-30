"""
WeCom message encryption/decryption (AES-256-CBC).

Implements the enterprise微信 callback message encryption protocol:
  - AES-256-CBC with PKCS7 padding
  - Custom padding scheme (random + length + content + corpid)
  - SHA1 signature verification

Ref: https://developer.work.weixin.qq.com/document/path/90968
"""

from __future__ import annotations

import base64
import hashlib
import random
import socket
import struct
import string
from typing import Optional

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class WeComCrypto:
    """Enterprise微信 message encryption/decryption handler."""

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str) -> None:
        """
        Args:
            token: 企业微信回调配置的 Token
            encoding_aes_key: 企业微信回调配置的 EncodingAESKey (43 chars)
            corp_id: 企业微信 CorpID（或企业微信应用的 AgentID）
        """
        self._token = token.encode("utf-8")
        self._corp_id = corp_id
        self._aes_key = base64.b64decode(encoding_aes_key + "=")
        if len(self._aes_key) != 32:
            raise ValueError(
                f"Invalid EncodingAESKey: decoded length must be 32, got {len(self._aes_key)}"
            )

    # ── Public API ──────────────────────────────────────────────

    def decrypt(self, encrypted_msg: str) -> str:
        """Decrypt an encrypted message from 企业微信 callback.

        Returns the raw XML message string, or raises on failure.
        """
        raw = base64.b64decode(encrypted_msg)
        iv = self._aes_key[:16]
        cipher = Cipher(algorithms.AES(self._aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(raw) + decryptor.finalize()

        # Remove PKCS7 padding
        unpadder = padding.PKCS7(256).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        # Parse: [16 random bytes][4-byte network order length][content][corp_id]
        msg_len = struct.unpack(">I", plaintext[16:20])[0]
        msg = plaintext[20:20 + msg_len].decode("utf-8")
        corp_id = plaintext[20 + msg_len:].decode("utf-8")

        if corp_id != self._corp_id:
            raise ValueError(
                f"CorpID mismatch: expected '{self._corp_id}', got '{corp_id}'"
            )

        return msg

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a response message for 企业微信 callback.

        Returns base64-encoded ciphertext.
        """
        # Build: [16 random bytes][4-byte length][content][corp_id]
        random_bytes = "".join(
            random.choices(string.ascii_letters + string.digits, k=16)
        ).encode("utf-8")
        content = plaintext.encode("utf-8")
        corp_id_bytes = self._corp_id.encode("utf-8")

        raw = random_bytes + struct.pack(">I", len(content)) + content + corp_id_bytes

        # PKCS7 padding
        padder = padding.PKCS7(256).padder()
        padded = padder.update(raw) + padder.finalize()

        # AES-256-CBC encrypt
        iv = self._aes_key[:16]
        cipher = Cipher(algorithms.AES(self._aes_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()

        return base64.b64encode(encrypted).decode("utf-8")

    def verify_signature(
        self, signature: str, timestamp: str, nonce: str, echo_str: Optional[str] = None
    ) -> bool:
        """Verify SHA1 signature.

        Used for URL verification (GET) and message callback (POST).
        """
        items = [self._token, timestamp.encode("utf-8"), nonce.encode("utf-8")]
        if echo_str:
            items.append(echo_str.encode("utf-8") if isinstance(echo_str, str) else echo_str)

        items.sort(key=lambda x: x if isinstance(x, bytes) else x.encode("utf-8"))
        sha1 = hashlib.sha1()
        for item in items:
            if isinstance(item, str):
                sha1.update(item.encode("utf-8"))
            else:
                sha1.update(item)
        return sha1.hexdigest() == signature

    def generate_signature(
        self, timestamp: str, nonce: str, echo_str: str
    ) -> str:
        """Generate SHA1 signature (used for testing)."""
        items = sorted(
            [self._token, timestamp.encode("utf-8"), nonce.encode("utf-8"), echo_str.encode("utf-8")],
            key=lambda x: x if isinstance(x, bytes) else x.encode("utf-8"),
        )
        sha1 = hashlib.sha1()
        for item in items:
            if isinstance(item, str):
                sha1.update(item.encode("utf-8"))
            else:
                sha1.update(item)
        return sha1.hexdigest()

    def verify_url(
        self, msg_signature: str, timestamp: str, nonce: str, echostr: str
    ) -> str:
        """Verify callback URL (GET request from 企业微信).

        Returns the decrypted echostr on success.
        Raises ValueError on signature mismatch.
        """
        if not self.verify_signature(msg_signature, timestamp, nonce, echostr):
            raise ValueError("Signature verification failed")
        return self.decrypt(echostr)
