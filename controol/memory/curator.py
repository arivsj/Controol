"""Curador de memória: usa o harness (headless) para ler o commit e gerar notas.

Categorias:
- documentacao → atualiza AGENTS.md + nota `<slug>.md` resumida + parágrafo
  em doc-conhecimento.md (leitura humana).
- bugs → nota em bugsRaras.md (consulta de IA) + parágrafo na doc.
- customizada → nova nota `<slug>.md` na categoria indicada + parágrafo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..git_tools import commit_message, commit_patch, commit_stat
from ..jsontools import extract_json
from .store import MemoryStore

_DOC_PROMPT = """Você é o curador de memória do projeto. Analise o commit abaixo e responda EXCLUSIVAMENTE com um objeto JSON válido (sem markdown, sem texto extra) seguindo exatamente este schema:
{{
  "title": "título curto e específico do que o commit faz",
  "slug": "kebab-case curto para nome de arquivo",
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "resumo técnico de 3 a 6 frases explicando O QUE mudou, POR QUE e COMO, escrito para uma IA recuperar por busca depois",
  "agentsmd": "1 a 3 frases prontas para adicionar como seção no AGENTS.md do projeto",
  "doc_paragraph": "parágrafo de 2 a 4 frases para leitura humana na documentação"
}}

Regras:
- Conteúdo em português (Brasil).
- Objetivo, técnico, sem enrolação.

--- COMMIT: MENSAGEM ---
{message}
--- COMMIT: STAT ---
{stat}
--- COMMIT: PATCH ---
{patch}
"""

_BUG_PROMPT = """Você é o curador de memória do projeto, especializado em BUGS RAROS. Analise o commit abaixo e responda EXCLUSIVAMENTE com um objeto JSON válido seguindo exatamente este schema:
{{
  "title": "título curto do bug",
  "slug": "kebab-case curto",
  "tags": ["bug", "raro", "outras-tags"],
  "sintoma": "sintoma exato: o que acontece, quando e onde",
  "contexto": "situações específicas que disparam o bug (usuário específico, servidor, ambiente, dado específico etc.)",
  "causa": "causa raiz do problema",
  "fix": "correção aplicada, passo a passo curto",
  "doc_paragraph": "parágrafo curto para leitura humana, sem jargão excessivo"
}}

A nota vai para bugsRaras.md e deve ser consultável por uma IA quando ela falhar
repetidamente num bug parecido. Regras: português, objetivo, técnico.

--- COMMIT: MENSAGEM ---
{message}
--- COMMIT: STAT ---
{stat}
--- COMMIT: PATCH ---
{patch}
"""

_CUSTOM_PROMPT = """Você é o curador de memória do projeto. Analise o commit abaixo para a categoria "{category}" e responda EXCLUSIVAMENTE com um objeto JSON válido seguindo exatamente este schema:
{{
  "title": "título curto e específico",
  "slug": "kebab-case curto",
  "tags": ["tag1", "tag2"],
  "summary": "resumo técnico de 3 a 6 frases para recuperação futura por IA",
  "doc_paragraph": "parágrafo curto para leitura humana"
}}
Regras: português, objetivo, técnico. Foco da categoria "{category}".

--- COMMIT: MENSAGEM ---
{message}
--- COMMIT: STAT ---
{stat}
--- COMMIT: PATCH ---
{patch}
"""


async def _ask(harness: Any, prompt: str) -> dict:
    buf: list[str] = []
    async for ev in harness.run(prompt):
        if ev.type == "agent_text":
            buf.append(ev.text)
        elif ev.type == "error":
            raise RuntimeError(ev.text)
    return extract_json("\n".join(buf))


def _append_agentsmd(store: MemoryStore, heading: str, section: str) -> None:
    if not section.strip():
        return
    path = store.agents_md_path()
    text = path.read_text(encoding="utf-8") if path.exists() else "# AGENTS.md\n"
    if not text.endswith("\n"):
        text += "\n"
    text += f"\n## {heading}\n\n{section.strip()}\n"
    path.write_text(text, encoding="utf-8")


async def curate_commit(
    store: MemoryStore,
    harness: Any,
    commit: str,
    category: str,
    name: str | None = None,
) -> str:
    """Gera a memória de `commit` na categoria e grava no vault. Retorna resumo."""
    message = commit_message(store.root, commit)
    stat = commit_stat(store.root, commit)
    patch = commit_patch(store.root, commit)
    if not patch.strip():
        patch = "(sem patch — commit de merge/estrutural)"

    mem_id = store.next_mem_id()

    if category == "documentacao":
        data = await _ask(harness, _DOC_PROMPT.format(message=message, stat=stat, patch=patch))
        body = f"# {data['title']}\n\n{data['summary']}\n"
        path = store.write_note(
            data["slug"], mem_id, data["title"], data.get("tags", []),
            "documentacao", commit, body,
        )
        _append_agentsmd(store, f"{mem_id} — {data['title']}", data.get("agentsmd", ""))
        store.append_paragraph(
            "doc-conhecimento.md", f"{mem_id} — {data['title']}",
            data.get("doc_paragraph", data["summary"]),
        )
        store.update_index()
        return f"{mem_id} → {path.name} + AGENTS.md + doc-conhecimento.md"

    if category == "bugs":
        data = await _ask(harness, _BUG_PROMPT.format(message=message, stat=stat, patch=patch))
        entry = (
            f"### {mem_id} — {data['title']}\n\n"
            f"- **Sintoma:** {data.get('sintoma', '')}\n"
            f"- **Contexto:** {data.get('contexto', '')}\n"
            f"- **Causa:** {data.get('causa', '')}\n"
            f"- **Fix:** {data.get('fix', '')}\n"
            f"- **Commit:** `{commit}`\n"
            f"- **Tags:** {', '.join(data.get('tags', []))}\n"
        )
        store.write_note(
            data["slug"], mem_id, data["title"], data.get("tags", ["bug"]),
            "bugs", commit, entry,
        )
        store.append_paragraph("bugsRaras.md", f"{mem_id} — {data['title']}", entry)
        store.append_paragraph(
            "doc-conhecimento.md", f"{mem_id} — {data['title']} (bug raro)",
            data.get("doc_paragraph", ""),
        )
        store.update_index()
        return f"{mem_id} → bugsRaras.md + doc-conhecimento.md"

    # categoria customizada
    cat_name = name or category
    data = await _ask(
        harness, _CUSTOM_PROMPT.format(category=cat_name, message=message, stat=stat, patch=patch)
    )
    body = f"# {data['title']}\n\n{data['summary']}\n\n*Categoria:* {cat_name}\n"
    path = store.write_note(
        data["slug"], mem_id, data["title"], data.get("tags", []),
        cat_name, commit, body,
    )
    store.append_paragraph(
        "doc-conhecimento.md", f"{mem_id} — {data['title']}",
        data.get("doc_paragraph", data["summary"]),
    )
    store.update_index()
    return f"{mem_id} → {path.name}"
