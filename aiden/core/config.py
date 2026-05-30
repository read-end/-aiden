"""
Global configuration for Aiden.

Reads from environment variables / .env file with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).resolve().parent.parent.parent
_dotenv = _project_root / ".env"
if _dotenv.exists():
    load_dotenv(_dotenv)


@dataclass
class Settings:
    # ── Anthropic / LLM ──────────────────────────────────────
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    model: str = os.getenv("MODEL", "claude-sonnet-4-20250514")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))

    # ── Storage ──────────────────────────────────────────────
    data_dir: Path = Path(
        os.getenv("AIDEN_DATA_DIR", str(_project_root / "data"))
    )

    # ── Server ───────────────────────────────────────────────
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(",")
    )

    # ── Web Search ───────────────────────────────────────────
    search_provider: str = os.getenv("SEARCH_PROVIDER", "duckduckgo")
    search_api_key: Optional[str] = os.getenv("SEARCH_API_KEY", None)

    # ── WeCom (企业微信) ───────────────────────────────────────
    wecom_corp_id: str = field(
        default_factory=lambda: os.getenv("WECOM_CORP_ID", "")
    )
    wecom_agent_id: int = int(os.getenv("WECOM_AGENT_ID", "0"))
    wecom_secret: str = field(
        default_factory=lambda: os.getenv("WECOM_SECRET", "")
    )
    wecom_token: str = field(
        default_factory=lambda: os.getenv("WECOM_TOKEN", "")
    )
    wecom_encoding_aes_key: str = field(
        default_factory=lambda: os.getenv("WECOM_ENCODING_AES_KEY", "")
    )

    # ── Logging ──────────────────────────────────────────────
    verbose: bool = os.getenv("VERBOSE", "0") == "1"

    def __post_init__(self) -> None:
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
