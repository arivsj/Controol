"""Funções puras de contagem/formatação de tokens (movidas do app)."""
from __future__ import annotations


def fmt_tokens(n: int) -> str:
    """`1.7k` para valores >= 1000; número puro caso contrário."""
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def tokens_from_data(data: dict) -> tuple[int, int]:
    """Extrai (entrada, total) de tokens reportados pelo harness (step_done).

    `total` inclui saída e cache (importante: cache.read costuma dominar).
    """
    tok = data.get("tokens")
    if isinstance(tok, dict):
        inp = tok.get("input") or tok.get("prompt_tokens") or 0
        out = tok.get("output") or tok.get("completion_tokens") or 0
        total = tok.get("total") or (inp + out)
        return int(inp or 0), int(total or 0)
    if isinstance(tok, (int, float)):
        return int(tok), int(tok)
    return 0, 0


def count_text_tokens(text: str) -> int:
    """Estimativa aproximada (chars/4) usada quando o harness não reporta uso."""
    return max(1, len(text) // 4)
