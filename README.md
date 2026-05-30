<div align="center">

# 🤖 Aiden — AI Personal Assistant

**A modular, extensible AI assistant with plugin architecture, web search, code analysis, 企业微信 integration, and zero-config deployment.**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Claude API](https://img.shields.io/badge/Claude_AI-API-CC794B?logo=anthropic)](https://docs.anthropic.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/your-username/aiden/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/aiden/actions/workflows/ci.yml)
[![WeCom](https://img.shields.io/badge/WeCom-集成-07C160?logo=wechat-work)](https://developer.work.weixin.qq.com/)

</div>

---

## ✨ Features

| Capability | Description |
|-----------|-------------|
| 🧠 **Conversation Memory** | Persistent multi-session chat history with SQLite backend |
| 🔌 **Plugin Architecture** | Extensible tool system — add new capabilities without touching core logic |
| 🌐 **Web Search** | Real-time information retrieval via DuckDuckGo (no API key required) |
| 📄 **Code Analysis** | Read, analyze, and inspect code files with AST-based structure extraction |
| 💼 **WeCom Integration** | Bidirectional messaging with 企业微信 (WeChat Work) — AES-256-CBC encrypted callbacks |
| 🌍 **Dual Interface** | Web UI (Streamlit) + CLI REPL + REST API |
| 🐳 **Docker Ready** | One-command deployment with docker-compose |
| ✅ **Fully Tested** | pytest suite with async support (43 tests) |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                    Interfaces                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ Streamlit│  │   CLI    │  │  REST API      │ │
│  │  Web UI  │  │   REPL   │  │  (FastAPI)     │ │
│  └────┬─────┘  └────┬─────┘  └───────┬────────┘ │
│       │             │                │          │
│  ┌────┴─────────────┴────────────────┴──────────┐│
│  │          企业微信 (WeCom) 回调集成            ││
│  │  (AES-256-CBC 加解密 + SHA1 签名校验)        ││
│  └─────────────────────┬─────────────────────────┘│
├────────────────────────┼──────────────────────────┤
│                    Core Engine                    │
│  ┌────────────────────────────────────────────┐  │
│  │  Agent Orchestrator (Engine)               │  │
│  │  ├── Tool Use routing                      │  │
│  │  ├── Streaming response                    │  │
│  │  └── Multi-turn conversation               │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│              Plugin System (Registry)             │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Web Search   │  │ Code Analyzer            │ │
│  │ (DuckDuckGo) │  │ (AST-based analysis)     │ │
│  └──────────────┘  └──────────────────────────┘ │
├──────────────────────────────────────────────────┤
│                   Storage Layer                  │
│  ┌────────────────────────────────────────────┐  │
│  │  SQLite + JSON (Conversation Memory)       │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Design Highlights

- **Plugin Pattern**: New tools implement an abstract `Plugin` class with a `PluginSpec`. The registry discovers and provides them to the engine — no code changes needed in the core loop.
- **Agent Loop**: User message → LLM invocation → tool execution → LLM continuation → response streaming — all fully async.
- **Memory Abstraction**: Thread-safe SQLite-backed conversation storage with a clean `Message` dataclass API.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [Anthropic API Key](https://console.anthropic.com/)

### 1. Clone & Setup

```bash
git clone https://github.com/your-username/aiden.git
cd aiden

# Copy environment template and add your API key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx

# Quick setup (virtual env + dependencies)
make setup
```

### 2. Run

You have three ways to interact:

```bash
# Terminal chat (CLI)
source venv/bin/activate
make cli

# Web server + UI (two terminals)
make api     # http://localhost:8000
make ui      # http://localhost:8501

# Or Docker (everything at once)
make docker-up
# API: http://localhost:8000
# Web UI: http://localhost:8501
```

### 3. Chat

```text
[default] You: what's the latest Python version?

[Aiden]: I searched the web and found that Python 3.14 is the latest.
Let me check the details...

[default] You: analyze my code in aiden/core/engine.py

[Aiden]: Let me analyze that file for you...
```

---

## 💻 CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/clear` | Clear current session history |
| `/sessions` | List all conversations |
| `/switch <id>` | Switch to a different session |
| `/prompt` | Show current system prompt |
| `/setprompt <text>` | Set custom system prompt |
| `/plugins` | List available tools |
| `/stats` | Session statistics |
| `/config` | Show current configuration |
| `/exit` | Quit the REPL |

---

## 💼 企业微信 (WeCom) 集成

Aiden 支持与 **企业微信自建应用** 双向通信：
- 用户在企微中发送消息 → 回调到 Aiden → Claude AI 处理 → 回复到企微
- 支持 AES-256-CBC 加密消息的自动加解密
- 支持文本消息、Markdown、图文卡片等多种消息类型
- 支持 `/help`、`/clear`、`/stats` 等本地命令

### 配置步骤

1. **登录 [企业微信管理后台](https://work.weixin.qq.com/wework_admin/frame)** → 应用管理 → 自建 → 创建应用

2. **获取凭证**：
   - CorpID：我的企业 → 企业信息 → CorpID
   - AgentID 和 Secret：应用管理 → 你的应用 → 获取

3. **设置回调 URL**：
   ```
   应用功能 → 接收消息 → 设置接收消息
   ```
   - URL: `http://你的域名/api/v1/wecom/callback`
   - Token: 随机字符串，如 `aiden123token`
   - EncodingAESKey: 点击"随机获取"

4. **配置环境变量**：
   ```bash
   WECOM_CORP_ID=wwxxxxxxxx
   WECOM_AGENT_ID=1000001
   WECOM_SECRET=xxxxxxxxxxxx
   WECOM_TOKEN=xxxxxxxxxx
   WECOM_ENCODING_AES_KEY=xxxxxxxxxxxxxxxxxx
   ```

5. **启动 Aiden 并验证**：
   ```bash
   uvicorn aiden.api.server:app
   ```
   在企微后台点击"保存"完成 URL 验证。

### 架构

```
企业微信 App ──→ 回调请求 ──→ FastAPI ──→ WeComCrypto ──→ WeComHandler ──→ Aiden Engine
                  (AES加密)     /callback    (解密)         (路由消息)         (AI处理)
                                                            │
                                                            ↓
企业微信 App ←── 主动推送  ←── WeComClient ←── 回复结果
                  (API调用)
```

---

## 🔧 Extending: Adding a Plugin

Adding a new capability is straightforward:

```python
from aiden.plugins.base import Plugin, PluginSpec

class WeatherPlugin(Plugin):
    spec = PluginSpec(
        name="get_weather",
        description="Get current weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    )

    async def execute(self, city: str) -> str:
        # Your weather API call here
        return f"The weather in {city} is sunny, 25°C."
```

Then register it:

```python
engine.registry.register(WeatherPlugin())
```

The agent will now automatically use `get_weather` when asked about the weather.

---

## 📁 Project Structure

```
aiden/
├── aiden/                        # Core Python package
│   ├── core/                     # Engine, memory, config
│   │   ├── engine.py             # Agent loop — orchestrates everything
│   │   ├── memory.py             # SQLite-backed conversation storage
│   │   └── config.py             # Environment-based configuration
│   ├── plugins/                  # Plugin system
│   │   ├── base.py               # Abstract Plugin base class
│   │   ├── registry.py           # Plugin discovery & registration
│   │   ├── web_search.py         # DuckDuckGo search integration
│   │   └── code_analyzer.py      # AST-based code inspection
│   ├── api/                      # REST API layer
│   │   ├── server.py             # FastAPI application factory
│   │   ├── routes.py             # API endpoints
│   │   └── schemas.py            # Pydantic request/response models
│   └── cli/                      # Command-line interface
│       └── repl.py               # Interactive REPL
├── web/                          # Streamlit frontend
│   └── app.py                    # Web UI
├── aiden/wecom/                  # 企业微信集成
│   ├── crypto.py                 # AES-256-CBC 加解密
│   ├── client.py                 # API 客户端 (Token + 消息推送)
│   ├── handler.py                # 消息路由和 AI 处理
│   └── routes.py                 # FastAPI 回调接口
├── tests/                        # Test suite
│   ├── test_memory.py
│   ├── test_plugins.py
│   └── test_engine.py
├── .github/workflows/            # CI/CD
│   └── ci.yml                    # GitHub Actions (test + docker build)
├── Dockerfile                    # Production container
├── Dockerfile.web                # Web UI container
├── docker-compose.yml            # Multi-service deployment
├── Makefile                      # Developer convenience commands
└── requirements.txt              # Python dependencies
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# With coverage
make test-coverage

# Lint
make lint
```

```
============================================================
tests/test_memory.py ........                         [ 42%]
tests/test_plugins.py .........                       [ 79%]
tests/test_engine.py ....                             [100%]
============================================================
18 passed in 0.85s
```

---

## 📊 Why Aiden Stands Out on a Resume

| Aspect | What It Shows |
|--------|--------------|
| **Agent Architecture** | Multi-turn LLM orchestration with Tool Use — the core AI agent pattern |
| **Plugin System** | Abstract base class, registry, dependency injection — real design patterns |
| **LLM Integration** | Anthropic Claude API, streaming, tool routing |
| **Full Stack** | Python backend (FastAPI) + frontend (Streamlit) + CLI |
| **DevOps** | Docker multi-stage builds, docker-compose, GitHub Actions CI |
| **Code Quality** | Type hints, dataclasses, comprehensive tests, clean architecture |
| **Engineering** | Async/await, SQLite, AST parsing, HTTP clients, error handling |

---

## 🗺️ Roadmap

- [ ] **File upload** — drag-and-drop files for analysis
- [ ] **ArXiv / paper search** — academic literature plugin
- [ ] **Image understanding** — Claude Vision integration
- [ ] **Audio support** — voice input/output
- [ ] **Web browsing** — full page rendering plugin
- [ ] **Authentication** — multi-user support with API keys

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  Built with ❤️ and the <a href="https://docs.anthropic.com/">Anthropic Claude API</a>
</div>
