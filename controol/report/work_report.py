"""Gera `controol-report.html`: relatório de trabalho da sessão.

Lista colapsável por arquivo alterado, com classes/funções completas
(extraídas SEM IA) e botão de copiar com feedback. O arquivo é realimentado
a cada interação (a função regenera o HTML inteiro a partir das interações).
"""
from __future__ import annotations

import html
from pathlib import Path

from .class_extractor import extract_units, language_of
from .diffing import parse_unified_diff

_PAGE_HEAD = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Controol CLI — Relatório de Trabalho</title>
<style>
:root{
  --bg:#0f101d; --surface:#181928; --elev:#232538; --border:#2e2f45;
  --text:#e0e6ed; --muted:#8a8f9e;
  --cyan:#00f5d4; --pink:#f72585; --violet:#9d4edd; --yellow:#ffb703; --red:#ff2e63;
  --green-bg:#0b2b1a; --green:#baffc9; --red-bg:#2b0b0f; --red-del:#ffb4b4;
}
*{box-sizing:border-box}
body{background:var(--bg); color:var(--text); font-family:'JetBrains Mono',ui-monospace,monospace;
     margin:0; padding:24px; max-width:1100px; margin:0 auto;}
h1{color:var(--cyan); font-size:20px; text-transform:uppercase; letter-spacing:2px;}
h2{color:var(--pink); font-size:15px;}
h3{color:var(--violet); font-size:13px; text-transform:uppercase; letter-spacing:1px;}
.sub{color:var(--muted); font-size:12px;}
.interaction{border:1px solid var(--border); background:var(--surface);
             padding:12px 16px; margin:16px 0; border-left:4px solid var(--pink);}
.explanation{color:var(--text); background:var(--bg); padding:8px 12px; border:1px solid var(--border);}
details{border:1px solid var(--border); margin:8px 0; background:var(--bg);}
summary{cursor:pointer; padding:8px 12px; color:var(--cyan); background:var(--surface);
        font-size:13px;}
summary:hover{color:var(--pink);}
.unit{background:#0b0c16; padding:10px 12px; overflow-x:auto; border-left:3px solid var(--cyan);
      white-space:pre; font-size:12px; line-height:1.5;}
.copy{background:var(--elev); color:var(--cyan); border:1px solid var(--cyan);
      padding:6px 12px; cursor:pointer; margin:8px 0 4px; font-family:inherit; font-size:12px;}
.copy:hover{background:var(--cyan); color:var(--bg);}
.copy.copied{background:var(--cyan); color:var(--bg);}
.diff{overflow-x:auto; font-size:12px; line-height:1.5;}
.add{background:var(--green-bg); color:var(--green); display:block; white-space:pre;}
.del{background:var(--red-bg); color:var(--red-del); display:block; white-space:pre;}
.ctx{color:var(--muted); display:block; white-space:pre;}
.foot{color:var(--muted); font-size:11px; margin-top:32px; text-align:center;}
</style>
</head>
<body>
"""

_FOOT = """
<div class="foot">Gerado pelo Controol CLI · atualizado a cada interação</div>
<script>
function copiar(id, btn){
  var el = document.getElementById(id);
  var text = el ? el.innerText : "";
  function ok(){
    btn.textContent = "Copiado ✓";
    btn.classList.add("copied");
    setTimeout(function(){ btn.textContent = "📋 Copiar"; btn.classList.remove("copied"); }, 1500);
  }
  function fallback(){
    var ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch(e) {}
    document.body.removeChild(ta); ok();
  }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(ok).catch(fallback);
  } else { fallback(); }
}
</script>
</body>
</html>
"""


def _slug(text: str) -> str:
    keep = [c for c in text if c.isalnum()]
    return "".join(keep) or "x"


def _diff_html(diff_text: str) -> str:
    out = ['<div class="diff">']
    for ln in parse_unified_diff(diff_text):
        if ln.kind == "+":
            out.append(f'<span class="add">+ {html.escape(ln.text)}</span>')
        elif ln.kind == "-":
            out.append(f'<span class="del">- {html.escape(ln.text)}</span>')
        elif ln.kind == "hunk":
            out.append(f'<div class="sub">{html.escape(ln.text)}</div>')
        else:
            out.append(f'<span class="ctx">  {html.escape(ln.text)}</span>')
    out.append("</div>")
    return "\n".join(out)


def _units_html(cwd: Path, file_path: str) -> str:
    p = cwd / file_path
    if not p.exists():
        return ""
    src = p.read_text(encoding="utf-8", errors="replace")
    units = extract_units(src, language_of(file_path), file_path)
    if not units:
        return ""
    parts = ["<h3>Classes / funções (código completo)</h3>"]
    for u in units:
        block_id = f"u-{_slug(file_path)}-{_slug(u.name)}-{u.start_line}"
        parts.append(
            f'<button class="copy" onclick="copiar(\'{block_id}\', this)">📋 Copiar</button>'
        )
        parts.append(
            f'<pre class="unit" id="{block_id}"><code>{html.escape(u.code)}</code></pre>'
        )
        parts.append(
            f'<div class="sub">{html.escape(u.kind)} {html.escape(u.name)} · '
            f'linhas {u.start_line}–{u.end_line} · {html.escape(file_path)}</div>'
        )
    return "\n".join(parts)


def write_work_report(
    cwd: Path | str,
    interactions: list[dict],
    harness_desc: str = "",
    out_name: str = "controol-report.html",
) -> str:
    """(Re)gera o relatório de trabalho completo e retorna o caminho relativo."""
    cwd = Path(cwd)
    parts = [_PAGE_HEAD]
    parts.append("<h1>▸ Controol CLI — Relatório de Trabalho</h1>")
    parts.append(
        f'<div class="sub">harness: {html.escape(harness_desc)} · '
        f'{len(interactions)} interação(ões)</div>'
    )
    for idx, inter in enumerate(interactions, 1):
        parts.append('<section class="interaction">')
        parts.append(f"<h2>Interação {idx} — {html.escape(inter.get('prompt', ''))}</h2>")
        expl = (inter.get("explanation") or "").strip()
        if expl:
            parts.append(f'<div class="explanation">{html.escape(expl)}</div>')
        files = inter.get("files") or {}
        if not files:
            parts.append('<div class="sub">(nenhum arquivo alterado)</div>')
        for file_path in sorted(files):
            diff_text = files[file_path] or ""
            parts.append("<details open>")
            parts.append(f"<summary>📁 {html.escape(file_path)}</summary>")
            parts.append(_units_html(cwd, file_path))
            if diff_text.strip():
                parts.append("<h3>Diff</h3>")
                parts.append(_diff_html(diff_text))
            parts.append("</details>")
        parts.append("</section>")

    parts.append(_FOOT)
    out = cwd / out_name
    out.write_text("\n".join(parts), encoding="utf-8")
    return str(out.relative_to(cwd))
