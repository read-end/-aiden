"""
WeCom (企业微信/WeChat Work) integration module.

Provides bidirectional communication between Aiden and WeCom:
  - Receive messages via callback API (AES-256-CBC encrypted)
  - Send messages via WeCom API (text, markdown, etc.)
  - Automatic token management with caching

Documentation: https://developer.work.weixin.qq.com/document/
"""

from aiden.wecom.client import WeComClient
from aiden.wecom.handler import WeComHandler
