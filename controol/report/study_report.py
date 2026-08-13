"""Gera `controol-estudo.html`: guia didático sobre o código alterado.

Usa o harness para explicar o código "como se fosse para um estudante",
com perguntas e respostas clicáveis. A estrutura do JSON é fixa; o HTML
é autocontido (CSS/JS inline).
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from ..jsontools import extract_json

_PROMPT = """Você é um professor de programação. Analise o código alterado abaixo e produza um material de estudo para um estudante.
Responda EXCLUSIVAMENTE com um objeto JSON válido seguindo exatamente este schema:
{{
  "sections": [
    {{
      "file": "caminho/do/arquivo",
      "explicacao": "explicação didática de como o código funciona, passo a passo, para um estudante entender os conceitos e o fluxo",
      "perguntas": [
        {{"p": "pergunta 1", "r": "resposta didática 1"}},
        {{"p": "pergunta 2", "r": "resposta didática 2"}}
      ]
    }}
  ]
}}

Regras:
- Português (Brasil).
- Explique conceitos, fluxo e porquês; não só descreva o que cada linha faz.
- De 2 a 4 perguntas por seção, com respostas explicativas.

--- CÓDIGO ALTERADO ---
{code}
"""

_PAGE_HEAD = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Controol CLI — Estudo</title>
<style>
:root{
  --bg:#0f101d; --surface:#181928; --elev:#232538; --border:#2e2f45;
  --text:#e0e6ed; --muted:#8a8f9e;
  --cyan:#00f5d4; --pink:#f72585; --violet:#9d4edd; --yellow:#ffb703; --red:#ff2e63;
}
*{box-sizing:border-box}
body{background:var(--bg); color:var(--text); font-family:'Inter','Segoe UI',sans-serif;
     margin:0; padding:24px; max-width:900px; margin:0 auto; line-height:1.6;}
h1{color:var(--cyan); font-size:20px; text-transform:uppercase; letter-spacing:2px; font-family:ui-monospace,monospace;}
h2{color:var(--violet); font-size:17px; border-bottom:1px solid var(--border); padding-bottom:6px;}
h3{color:var(--yellow); font-size:14px;}
.card{border:1px solid var(--border); background:var(--surface); padding:14px 18px;
      margin:16px 0; border-radius:8px;}
.file{font-family:ui-monospace,monospace; color:var(--cyan); font-size:12px; background:var(--bg);
      display:inline-block; padding:2px 8px; border:1px solid var(--border); border-radius:4px;}
.explicacao{color:var(--text); margin:10px 0;}
.q{border:1px solid var(--border); border-left:3px solid var(--cyan); background:var(--bg);
   margin:8px 0; border-radius:6px;}
.q summary{cursor:pointer; padding:10px 12px; color:var(--text); font-weight:600;}
.q summary:hover{color:var(--cyan);}
.a{padding:0 12px 12px; color:var(--muted);}
.a strong{color:var(--cyan);}
.foot{color:var(--muted); font-size:11px; margin-top:32px; text-align:center;}
</style>
</head>
<body>
"""

_FOOT = """
<div class="foot">Gerado pelo Controol CLI · modo Estudo</div>
</body>
</html>
"""


async def write_study_report(
    cwd: Path | str,
    interactions: list[dict],
    harness: Any,
    out_name: str = "controol-estudo.html",
) -> str:
    """Gera o guia de estudo usando o harness e retorna o caminho relativo."""
    cwd = Path(cwd)
    seen: set[str] = set()
    chunks: list[str] = []
    for inter in interactions:
        for p in inter.get("files") or {}:
            if p in seen:
                continue
            seen.add(p)
            fp = cwd / p
            if fp.exists():
                src = fp.read_text(encoding="utf-8", errors="replace")
                chunks.append(f"### {p}\n```\n{src}\n```")
    if not chunks:
        raise ValueError("não há código alterado para estudar")
    prompt = _PROMPT.format(code="\n\n".join(chunks))

    buf: list[str] = []
    async for ev in harness.run(prompt):
        if ev.type == "agent_text":
            buf.append(ev.text)
        elif ev.type == "error":
            raise RuntimeError(ev.text)
    data = extract_json("\n".join(buf))

    parts = [_PAGE_HEAD]
    parts.append("<h1>▸ Controol CLI — Estudo</h1>")
    parts.append(f'<div style="color:var(--muted)">Guia didático sobre as alterações da sessão.</div>')
    for sec in data.get("sections", []):
        parts.append('<div class="card">')
        parts.append(f'<span class="file">📁 {html.escape(str(sec.get("file", "")))}</span>')
        parts.append(f'<div class="explicacao">{html.escape(sec.get("explicacao", ""))}</div>')
        for i, q in enumerate(sec.get("perguntas", []), 1):
            parts.append('<details class="q"><summary>')
            parts.append(f"Pergunta {i}: {html.escape(str(q.get('p', '')))}")
            parts.append("</summary><div class=\"a\">")
            parts.append(html.escape(str(q.get("r", ""))))
            parts.append("</div></details>")
        parts.append("</div>")

    parts.append(_FOOT)
    out = cwd / out_name
    out.write_text("\n".join(parts), encoding="utf-8")
    return str(out.relative_to(cwd))
