"""Utilitários para extrair JSON de respostas de LLM (tolerante a markdown)."""
from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict:
    """Extrai o primeiro objeto JSON do texto do agente."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("resposta sem JSON: " + text[:200])
    return json.loads(t[start : end + 1])
