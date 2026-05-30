"""
Aiden Web UI — Streamlit chat interface.

Provides:
  - Chat interface with message history
  - Session management (create, switch, delete sessions)
  - Plugin/tool overview
  - Settings panel (API key, model, system prompt)
  - Real-time streaming responses
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
import streamlit as st

# ── Page config ───────────────────────────────────────────────

st.set_page_config(
    page_title="Aiden — AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────

API_BASE = os.getenv("AIDEN_API_URL", "http://localhost:8000/api/v1")

st.markdown(
    """
    <style>
    .stApp {
        max-width: 100%;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .user-message {
        background-color: #e8f0fe;
    }
    .assistant-message {
        background-color: #f0f0f0;
    }
    .tool-message {
        background-color: #fff3e0;
        font-size: 0.85rem;
        border-left: 3px solid #ff9800;
        padding-left: 0.75rem;
    }
    .status-ok { color: #2e7d32; }
    .status-err { color: #c62828; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Session state ─────────────────────────────────────────────

def init_state() -> None:
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = "default"
    if "api_key" not in st.session_state:
        st.session_state.api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if "server_ok" not in st.session_state:
        st.session_state.server_ok = False


init_state()


# ── API helpers ───────────────────────────────────────────────

def api_get(path: str) -> Optional[dict | list]:
    """Make a GET request to the API."""
    try:
        resp = httpx.get(f"{API_BASE}{path}", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def api_post(path: str, data: dict) -> Optional[dict]:
    """Make a POST request to the API."""
    try:
        resp = httpx.post(f"{API_BASE}{path}", json=data, timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def api_delete(path: str) -> bool:
    try:
        resp = httpx.delete(f"{API_BASE}{path}", timeout=5.0)
        return resp.is_success
    except Exception:
        return False


# ── Check server status ───────────────────────────────────────

status_data = api_get("/status")
if status_data and isinstance(status_data, dict):
    st.session_state.server_ok = True
else:
    st.session_state.server_ok = False


# ── Sidebar ────────────────────────────────────────────────────

with st.sidebar:
    st.title("🤖 Aiden")
    st.caption("AI Personal Assistant")

    # Server status
    if st.session_state.server_ok:
        st.markdown(
            f'<p class="status-ok">● Server connected</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p class="status-err">● Server offline</p>'
            f'<p style="font-size:0.8rem">Start with: <code>uvicorn aiden.api.server:app</code></p>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Settings expander ──────────────────────────────────
    with st.expander("⚙️ Settings", expanded=False):
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            value=st.session_state.api_key,
            help="Set ANTHROPIC_API_KEY in .env or paste here",
        )
        if api_key != st.session_state.api_key:
            st.session_state.api_key = api_key
            os.environ["ANTHROPIC_API_KEY"] = api_key

        model = st.selectbox(
            "Model",
            ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-haiku-3-5-20241022"],
            index=0,
        )
        st.caption(f"Active: {status_data.get('model', 'N/A') if status_data else 'N/A'}")

    # ── Sessions ───────────────────────────────────────────
    st.subheader("💬 Sessions")
    sessions_data = api_get("/sessions")

    if isinstance(sessions_data, list):
        for s in sessions_data:
            sid = s["id"]
            msg_count = s.get("message_count", 0)
            is_active = sid == st.session_state.session_id
            btn_label = f"📌 {sid}" if is_active else f"  {sid} ({msg_count})"
            if st.button(btn_label, key=f"session_{sid}", use_container_width=True):
                st.session_state.session_id = sid
                st.session_state.messages = []
                st.rerun()

    # New session button
    col1, col2 = st.columns(2)
    with col1:
        new_sid = st.text_input("New session", value="", label_visibility="collapsed",
                                placeholder="session-id")
    with col2:
        if st.button("➕", help="Create new session"):
            if new_sid:
                st.session_state.session_id = new_sid
                st.session_state.messages = []
                st.rerun()

    # Delete current session
    if st.button("🗑️ Delete current session", use_container_width=True,
                 type="secondary"):
        if st.session_state.session_id != "default":
            api_delete(f"/sessions/{st.session_state.session_id}")
            st.session_state.session_id = "default"
            st.session_state.messages = []
            st.rerun()

    st.divider()

    # ── Plugins info ───────────────────────────────────────
    with st.expander("🔌 Plugins", expanded=False):
        plugins_data = api_get("/plugins")
        if isinstance(plugins_data, list):
            for p in plugins_data:
                st.markdown(f"**{p['name']}**")
                st.caption(p["description"])
                st.markdown("---")
        else:
            st.caption("No plugins available (server offline)")


# ── Main chat area ────────────────────────────────────────────

st.title("💬 Aiden")

# Display chat messages
for msg in st.session_state.messages:
    role = msg.get("role", "user")
    content = msg.get("content", "")

    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)
    elif role == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)
    elif role == "tool_result":
        with st.chat_message("tool", avatar="🛠️"):
            st.caption(content[:200] + ("..." if len(content) > 200 else ""))

# Chat input
if prompt := st.chat_input("Type your message here..."):
    if not st.session_state.api_key and not st.session_state.server_ok:
        st.error("⚠️ API key required. Set ANTHROPIC_API_KEY in .env or in Settings.")
        st.stop()

    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Show streaming response
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{API_BASE}/chat",
                    json={
                        "message": prompt,
                        "session_id": st.session_state.session_id,
                        "stream": True,
                    },
                )

                if response.is_success:
                    # Parse SSE stream
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if data["type"] == "chunk":
                                full_response += data["content"]
                                message_placeholder.markdown(full_response + "▌")
                            elif data["type"] == "done":
                                message_placeholder.markdown(full_response)
                                break
                            elif data["type"] == "error":
                                message_placeholder.error(f"⚠️ {data['content']}")
                                st.session_state.messages.pop()
                                st.rerun()
                else:
                    message_placeholder.error(f"⚠️ API error: {response.status_code}")
                    st.session_state.messages.pop()
                    st.rerun()

        except httpx.ConnectError:
            message_placeholder.error(
                "⚠️ Cannot connect to Aiden server. "
                "Run `uvicorn aiden.api.server:app` first."
            )
            st.session_state.messages.pop()
            st.rerun()
        except Exception as e:
            message_placeholder.error(f"⚠️ Error: {type(e).__name__}: {e}")
            st.session_state.messages.pop()
            st.rerun()

    # Save to session state
    if full_response:
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )

    st.rerun()
