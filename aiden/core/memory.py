"""
Conversation memory — manages session history with SQLite persistence.

Each session stores:
  - A list of messages (role, content, timestamp, metadata)
  - Editable system prompt
  - Configurable context window
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from aiden.core.config import settings


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user" | "assistant" | "system" | "tool_result"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tool_calls: Optional[list[dict]] = None
    tool_use_id: Optional[str] = None
    name: Optional[str] = None  # tool name for tool_result

    def to_dict(self) -> dict:
        d = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_use_id:
            d["tool_use_id"] = self.tool_use_id
        if self.name:
            d["name"] = self.name
        return d


class ConversationMemory:
    """Thread-safe conversation memory backed by SQLite."""

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self._lock = Lock()
        self._db_path = settings.data_dir / "conversations.db"
        self._init_db()
        # In-memory cache for fast reads
        self._messages: list[Message] = []
        self._load_messages()

    # ── schema ──────────────────────────────────────────────

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    system_prompt TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool_calls TEXT,
                    tool_use_id TEXT,
                    name TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at, updated_at) "
                "VALUES (?, ?, ?)",
                (self.session_id, datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )

    # ── persistence ─────────────────────────────────────────

    def _load_messages(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp, tool_calls, tool_use_id, name "
                "FROM messages WHERE session_id = ? ORDER BY id",
                (self.session_id,),
            ).fetchall()
        self._messages = [
            Message(
                role=r[0],
                content=r[1],
                timestamp=r[2],
                tool_calls=json.loads(r[3]) if r[3] else None,
                tool_use_id=r[4],
                name=r[5],
            )
            for r in rows
        ]

    def add_message(self, message: Message) -> None:
        with self._lock:
            self._messages.append(message)
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, timestamp, "
                    "tool_calls, tool_use_id, name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        self.session_id,
                        message.role,
                        message.content,
                        message.timestamp,
                        json.dumps(message.tool_calls) if message.tool_calls else None,
                        message.tool_use_id,
                        message.name,
                    ),
                )
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (datetime.now(timezone.utc).isoformat(), self.session_id),
                )

    def get_history(self, limit: Optional[int] = None) -> list[Message]:
        with self._lock:
            msgs = self._messages
            if limit and limit > 0:
                msgs = msgs[-limit:]
            return list(msgs)

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "DELETE FROM messages WHERE session_id = ?", (self.session_id,)
                )

    def delete(self) -> None:
        self.clear()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (self.session_id,)
            )

    @property
    def system_prompt(self) -> str:
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT system_prompt FROM sessions WHERE session_id = ?",
                (self.session_id,),
            ).fetchone()
        return row[0] if row else ""

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "UPDATE sessions SET system_prompt = ? WHERE session_id = ?",
                (value, self.session_id),
            )

    # ── session management ──────────────────────────────────

    @staticmethod
    def list_sessions() -> list[dict]:
        db_path = settings.data_dir / "conversations.db"
        if not db_path.exists():
            return []
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                "SELECT session_id, created_at, updated_at FROM sessions "
                "ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {"id": r[0], "created_at": r[1], "updated_at": r[2]} for r in rows
        ]

    def __len__(self) -> int:
        return len(self._messages)
