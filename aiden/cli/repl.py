"""
Command-line REPL for Aiden — interactive chat right in the terminal.

Usage:
    python -m aiden
    # or
    python -m aiden.cli.repl
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from aiden.core.engine import Engine
from aiden.core.memory import ConversationMemory


def _clear_screen() -> None:
    print("\033[2J\033[H", end="")


def _print_banner() -> None:
    print("╔══════════════════════════════════════════╗")
    print("║          Aiden — AI Assistant            ║")
    print("║     Type /help for commands              ║")
    print("╚══════════════════════════════════════════╝")
    print()


def _print_help() -> None:
    print("""
Commands:
  /help           Show this help message
  /clear          Clear current session history
  /sessions       List all sessions
  /switch <id>    Switch to a different session
  /prompt         Show current system prompt
  /setprompt <p>  Set a custom system prompt
  /plugins        List available plugins/tools
  /stats          Show session statistics
  /config         Show current configuration
  /exit, /quit    Exit the REPL

Press Ctrl+C at any time to stop response generation.
""")


async def _async_main() -> None:
    _clear_screen()
    _print_banner()

    session_id = "default"
    engine = Engine(session_id=session_id)

    while True:
        try:
            user_input = input(f"\n[{session_id}] You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ── commands ──────────────────────────────────────
        if user_input.startswith("/"):
            cmd = user_input.lower().split()
            match cmd[0]:
                case "/help":
                    _print_help()
                    continue
                case "/clear":
                    engine.memory.clear()
                    print("✅ Session cleared.")
                    continue
                case "/sessions":
                    sessions = ConversationMemory.list_sessions()
                    if sessions:
                        print(f"Sessions ({len(sessions)}):")
                        for s in sessions:
                            mem = ConversationMemory(s["id"])
                            print(f"  [{s['id']}] {len(mem)} msgs — {s['updated_at'][:19]}")
                    else:
                        print("No sessions yet.")
                    continue
                case "/switch":
                    if len(cmd) > 1:
                        session_id = cmd[1]
                        engine = Engine(session_id=session_id)
                        print(f"✅ Switched to session '{session_id}'")
                    else:
                        print("Usage: /switch <session_id>")
                    continue
                case "/prompt":
                    prompt = engine.memory.system_prompt
                    if prompt:
                        print(f"Current system prompt:\n---\n{prompt}\n---")
                    else:
                        print("Using default system prompt.")
                    continue
                case "/setprompt":
                    new_prompt = user_input[len("/setprompt "):].strip()
                    if new_prompt:
                        engine.memory.system_prompt = new_prompt
                        print("✅ System prompt updated.")
                    else:
                        print("Usage: /setprompt <your custom prompt here>")
                    continue
                case "/plugins":
                    print(f"Plugins ({engine.registry.count}):")
                    for p in engine.registry.list_plugins():
                        print(f"  🛠️  {p.spec.name}: {p.spec.description}")
                    continue
                case "/stats":
                    mem = engine.memory
                    print(f"Session: {session_id}")
                    print(f"Messages: {len(mem)}")
                    print(f"Plugins: {engine.registry.count}")
                    print(f"Model: {engine._model}")
                    continue
                case "/config":
                    from aiden.core.config import settings
                    print(f"Model: {settings.model}")
                    print(f"Max tokens: {settings.max_tokens}")
                    print(f"Temperature: {settings.temperature}")
                    print(f"Data dir: {settings.data_dir}")
                    continue
                case "/exit" | "/quit":
                    print("Goodbye!")
                    break
                case _:
                    print(f"Unknown command: {cmd[0]}. Type /help for available commands.")
                    continue

        # ── normal chat ───────────────────────────────────
        print(f"\n[Aiden]: ", end="", flush=True)
        try:
            async for chunk in engine.chat(user_input):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"\n⚠️  Error: {e}")


def main() -> None:
    """Entry point for the CLI REPL."""
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
