"""
Code Analyzer Plugin — reads, inspects, and analyzes code files.

Supports:
  - Reading file contents with line numbers
  - Getting file metadata (size, lines, language)
  - Simple structure analysis (functions, classes)
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Optional

from aiden.plugins.base import Plugin, PluginSpec

# Common file extensions → language name
LANG_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".jsx": "JavaScript React",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".cs": "C#",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".sql": "SQL",
    ".sh": "Shell Script",
    ".bat": "Batch",
    ".ps1": "PowerShell",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Configuration",
}


class CodeAnalyzerPlugin(Plugin):
    """Read and analyze code files in the workspace."""

    spec = PluginSpec(
        name="code_analyzer",
        description="Read and analyze code files. Get file contents, structure "
        "overview (functions, classes), and metadata. "
        "Useful for understanding a codebase or reviewing code.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory (absolute or relative "
                    "to the workspace root)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["read", "analyze", "list"],
                    "description": "'read' = show file contents, "
                    "'analyze' = extract structure (functions, classes), "
                    "'list' = list directory contents",
                    "default": "read",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to return when reading a file (0 = all)",
                    "default": 100,
                },
            },
            "required": ["path"],
        },
    )

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self._workspace_root = Path(
            workspace_root or os.getcwd()
        ).resolve()

    async def execute(
        self, path: str, mode: str = "read", max_lines: int = 100
    ) -> str:
        """Execute code analysis."""
        target = self._resolve_path(path)
        if target is None:
            return f"❌ Path not found or outside workspace: `{path}`"

        if target.is_dir():
            if mode == "list":
                return self._list_directory(target)
            return f"`{path}` is a directory. Use `list` mode to see contents."

        if not target.is_file():
            return f"❌ File not found: `{path}`"

        try:
            if mode == "read":
                return self._read_file(target, max_lines)
            elif mode == "analyze":
                return self._analyze_file(target)
            else:
                return f"❌ Unknown mode: '{mode}'. Use 'read', 'analyze', or 'list'."
        except PermissionError:
            return f"❌ Permission denied: `{path}`"
        except Exception as e:
            return f"❌ Error reading `{path}`: {type(e).__name__}: {e}"

    # ── path resolution ──────────────────────────────────────

    def _resolve_path(self, path: str) -> Optional[Path]:
        """Resolve a user-provided path safely within the workspace."""
        p = Path(path)
        if not p.is_absolute():
            p = self._workspace_root / p
        p = p.resolve()
        # Security: prevent directory traversal outside workspace
        try:
            p.relative_to(self._workspace_root)
        except ValueError:
            # Allow common system paths if explicitly requested
            if not str(p).startswith("/tmp/") and not str(p).startswith("/home/"):
                return None
        return p

    # ── read mode ────────────────────────────────────────────

    def _read_file(self, path: Path, max_lines: int) -> str:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        line_count = len(lines)

        if max_lines > 0 and line_count > max_lines:
            lines = lines[:max_lines]
            truncated = True
        else:
            truncated = False

        lang = LANG_MAP.get(path.suffix, "Unknown")
        result = [
            f"📄 **{path.name}** ({lang})",
            f"   Path: `{path}`",
            f"   Size: {path.stat().st_size:,} bytes",
            f"   Lines: {line_count}",
            "",
            "```" + path.suffix[1:] if path.suffix else "```",
        ]
        for i, line in enumerate(lines, 1):
            result.append(f"{i:4d}│ {line}")
        result.append("```")

        if truncated:
            result.append(f"\n_... truncated at {max_lines} of {line_count} lines._")

        return "\n".join(result)

    # ── analyze mode ─────────────────────────────────────────

    def _analyze_file(self, path: Path) -> str:
        lang = LANG_MAP.get(path.suffix, "Unknown")
        size = path.stat().st_size
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        line_count = len(lines)

        result = [
            f"🔬 **Analysis:** `{path.name}`",
            f"   Language: {lang}",
            f"   Size: {size:,} bytes",
            f"   Lines: {line_count}",
            "",
        ]

        if path.suffix == ".py":
            analysis = self._analyze_python(content)
            result.append(analysis)
        else:
            # Generic analysis
            imports = [l for l in lines if l.startswith("import ")]
            if imports:
                result.append(f"📦 Imports ({len(imports)}):")
                for imp in imports[:10]:
                    result.append(f"   - `{imp}`")
                if len(imports) > 10:
                    result.append(f"   _... and {len(imports)-10} more_")
            result.append(f"📏 Avg line length: {sum(len(l) for l in lines)/max(line_count,1):.1f} chars")

        return "\n".join(result)

    def _analyze_python(self, content: str) -> str:
        """Analyze Python source code structure using AST."""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return f"⚠️ Could not parse Python file: {e}"

        classes = [
            node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        functions = [
            node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        lines: list[str] = []

        if classes:
            lines.append(f"🏛️  Classes ({len(classes)}):")
            for cls in classes[:10]:
                bases = ", ".join(
                    _ast_name(b) for b in cls.bases if hasattr(b, "id")
                )
                base_str = f"({bases})" if bases else ""
                lines.append(
                    f"   - `{cls.name}{base_str}` — line {cls.lineno}"
                )
            if len(classes) > 10:
                lines.append(f"   _... and {len(classes)-10} more_")

        if functions:
            # Separate module-level from methods
            top_level = [f for f in functions if isinstance(f.parent, ast.Module)] if hasattr(ast, 'parent') else functions[:5]
            lines.append(f"⚙️  Functions ({len(functions)}):")
            for fn in functions[:15]:
                kind = "async " if isinstance(fn, ast.AsyncFunctionDef) else ""
                args = _format_args(fn)
                lines.append(f"   - {kind}`{fn.name}({args})` — line {fn.lineno}")
            if len(functions) > 15:
                lines.append(f"   _... and {len(functions)-15} more_")

        if not classes and not functions:
            lines.append("📝 Script — no class or function definitions found.")

        return "\n".join(lines)

    # ── list mode ────────────────────────────────────────────

    def _list_directory(self, path: Path) -> str:
        entries: list[Path] = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        dirs = [e for e in entries if e.is_dir()]
        files = [e for e in entries if not e.is_dir()]

        result = [f"📁 **Directory:** `{path}`\n"]
        for d in dirs:
            result.append(f"   📂 {d.name}/")
        for f in files:
            size = f.stat().st_size
            lang = LANG_MAP.get(f.suffix, "")
            tag = f" ({lang})" if lang else ""
            result.append(f"   📄 {f.name}  _{size:,}B_{tag}")

        result.append(f"\n_{len(dirs)} directories, {len(files)} files_")
        return "\n".join(result)


# ── helpers ───────────────────────────────────────────────────

def _ast_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_ast_name(node.value)}.{node.attr}"
    return "?"


def _format_args(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    for a in fn.args.args:
        args.append(a.arg)
    if fn.args.vararg:
        args.append(f"*{fn.args.vararg.arg}")
    if fn.args.kwarg:
        args.append(f"**{fn.args.kwarg.arg}")
    return ", ".join(args) if args else ""
