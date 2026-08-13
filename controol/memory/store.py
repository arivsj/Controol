"""Armazenamento do vault de memória em Markdown (.controol/memory/).

Notas individuais ficam em `nodes/<slug>.md` com frontmatter (id, title,
tags, category, date, commit) e wikilinks `[[...]]`; `bugsRaras.md` e
`doc-conhecimento.md` acumulam entradas para consulta; `index.md` lista tudo.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


class MemoryStore:
    def __init__(self, cwd: Path | str):
        self.root = Path(cwd)
        self.memory_dir = self.root / ".controol" / "memory"
        self.nodes_dir = self.memory_dir / "nodes"
        self.state_path = self.root / ".controol" / "state.json"
        self.pending_path = self.root / ".controol" / "pending_commits"

    # ---------- inicialização ----------
    def ensure(self) -> None:
        self.nodes_dir.mkdir(parents=True, exist_ok=True)

    # ---------- estado / pendências ----------
    def _state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_state(self, data: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def pending_commits(self) -> list[str]:
        """Hashes de commits (registrados pelo hook) ainda não processados."""
        if not self.pending_path.exists():
            return []
        handled = set(self._state().get("handled_commits", []))
        commits: list[str] = []
        for line in self.pending_path.read_text(encoding="utf-8").splitlines():
            h = line.strip()
            if h and h not in handled and h not in commits:
                commits.append(h)
        return commits

    def add_pending(self, commit: str) -> None:
        if commit in self.pending_commits():
            return
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        with self.pending_path.open("a", encoding="utf-8") as fh:
            fh.write(commit + "\n")

    def mark_handled(self, commit: str) -> None:
        state = self._state()
        state.setdefault("handled_commits", [])
        if commit not in state["handled_commits"]:
            state["handled_commits"].append(commit)
        self._save_state(state)

    def next_mem_id(self) -> str:
        state = self._state()
        n = int(state.get("mem_counter", 0)) + 1
        state["mem_counter"] = n
        self._save_state(state)
        return f"MEM-{date.today().year}-{n:03d}"

    # ---------- escrita de notas ----------
    def write_note(
        self,
        slug: str,
        mem_id: str,
        title: str,
        tags: list[str],
        category: str,
        commit: str,
        body: str,
    ) -> Path:
        self.ensure()
        path = self.nodes_dir / f"{slug}.md"
        frontmatter = (
            f"---\n"
            f"id: {mem_id}\n"
            f"title: {title}\n"
            f"tags: [{', '.join(tags)}]\n"
            f"category: {category}\n"
            f"date: {date.today().isoformat()}\n"
            f"commit: {commit}\n"
            f"---\n\n"
        )
        path.write_text(frontmatter + body, encoding="utf-8")
        return path

    def append_paragraph(self, filename: str, heading: str, body: str) -> Path:
        """Adiciona uma seção ao final de bugsRaras.md / doc-conhecimento.md."""
        self.ensure()
        path = self.memory_dir / filename
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {heading}\n\n{body.strip()}\n")
        return path

    def agents_md_path(self) -> Path:
        return self.root / "AGENTS.md"

    def update_index(self) -> None:
        self.ensure()
        notes = sorted(self.nodes_dir.glob("*.md"))
        lines = [
            "# Índice de memória — Controol CLI",
            "",
            "Conecte notas com wikilinks: [[slug]].",
            "",
        ]
        for note in notes:
            lines.append(f"- {note.stem}")
        (self.memory_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
