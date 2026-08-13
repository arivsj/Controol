"""Extração de unidades de código (classes, funções) SEM usar IA.

Python usa `ast` (preciso). Outras linguagens usam um scanner genérico de
declarações com casamento de chaves — suficiente para copiar blocos inteiros
no relatório de trabalho sem gastar tokens.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".cs": "csharp",
    ".rb": "ruby",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".swift": "swift",
    ".sh": "bash",
}

_DECL_RE = re.compile(
    r"^(?:(?:public|private|protected|internal|export|default|static|abstract|final|async|sealed|non-sealed|native)\s+)*"
    r"\b(class|struct|interface|enum|record|trait|impl|def|fn|func|function)\b"
    r"(?:\s+([A-Za-z_$][A-Za-z0-9_$]*))?"
)

# Padrão Go: `type Nome struct { ... }` / `type Nome interface { ... }`
_GO_TYPE_RE = re.compile(r"^\btype\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+(struct|interface)\b")

_FUNC_KEYWORDS = {"def", "fn", "func", "function"}


@dataclass
class Unit:
    name: str
    kind: str  # class | function | struct | interface | ...
    code: str
    start_line: int
    end_line: int
    path: str = ""


def language_of(path: str | Path) -> str:
    return _EXT_TO_LANG.get(Path(path).suffix.lower(), "")


def extract_units(source: str, language: str = "", path: str = "") -> list[Unit]:
    """Extrai classes/funções top-level de `source`."""
    if language == "python" or (not language and str(path).endswith(".py")):
        units = _python_units(source)
    else:
        units = _generic_units(source)
    for u in units:
        u.path = str(path)
    return units


def _python_units(source: str) -> list[Unit]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _generic_units(source)
    units: list[Unit] = []
    lines = source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            # inclui decorators acima da declaração (ex.: @dataclass)
            start = node.lineno
            decorators = getattr(node, "decorator_list", None)
            if decorators:
                start = min(d.lineno for d in decorators)
            end = node.end_lineno or node.lineno
            code = "".join(lines[start - 1 : end])
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            units.append(Unit(node.name, kind, code, start, end))
    return units


def _generic_units(source: str) -> list[Unit]:
    lines = source.splitlines(keepends=True)
    units: list[Unit] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _GO_TYPE_RE.match(lines[i].strip())
        if m:
            name, kind = m.group(1), m.group(2)
            end = _find_block_end(lines, i)
            code = "".join(lines[i : end + 1])
            units.append(Unit(name, kind, code, i + 1, end + 1))
            i = end + 1
            continue
        m = _DECL_RE.match(lines[i].strip())
        if m:
            kw, name = m.group(1), m.group(2)
            end = _find_block_end(lines, i)
            code = "".join(lines[i : end + 1])
            kind = "function" if kw in _FUNC_KEYWORDS else kw
            units.append(Unit(name or f"{kw}-anônimo@{i+1}", kind, code, i + 1, end + 1))
            i = end + 1
        else:
            i += 1
    return units


def _find_block_end(lines: list[str], start: int) -> int:
    """Fim do bloco iniciado em `start`: casamento de chaves ou indentação."""
    if "{" in lines[start]:
        depth = 0
        for j in range(start, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            if depth == 0 and j > start:
                return j
        return len(lines) - 1
    # sem chaves (estilo Python): linhas seguintes indentadas
    base_indent = len(lines[start]) - len(lines[start].lstrip())
    j = start + 1
    while j < len(lines):
        line = lines[j]
        if not line.strip():
            j += 1
            continue
        if len(line) - len(line.lstrip()) > base_indent:
            j += 1
        else:
            break
    return j - 1
