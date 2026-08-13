"""Conversão de `git diff --unified=N` em linhas tipadas para renderização."""
from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@.*$")


@dataclass
class DiffLine:
    kind: str  # ' ' contexto | '+' adição | '-' remoção | 'hunk' cabeçalho
    old_no: int | None
    new_no: int | None
    text: str


def parse_unified_diff(text: str) -> list[DiffLine]:
    """Transforma a saída de `git diff --unified=N` em linhas tipadas.

    Usado tanto pelo painel de diff do TUI (verde/vermelho) quanto pelos
    relatórios HTML.
    """
    lines: list[DiffLine] = []
    old_no = new_no = None
    for raw in text.splitlines():
        if raw.startswith("@@"):
            m = _HUNK_RE.match(raw)
            if m:
                old_no, new_no = int(m.group(1)), int(m.group(2))
            lines.append(DiffLine("hunk", None, None, raw))
        elif raw.startswith(("diff ", "index ", "--- ", "+++ ")):
            continue
        elif old_no is None:
            continue
        elif raw.startswith("+"):
            lines.append(DiffLine("+", None, new_no, raw[1:]))
            new_no += 1
        elif raw.startswith("-"):
            lines.append(DiffLine("-", old_no, None, raw[1:]))
            old_no += 1
        else:
            body = raw[1:] if raw.startswith(" ") else raw
            lines.append(DiffLine(" ", old_no, new_no, body))
            old_no += 1
            new_no += 1
    return lines
