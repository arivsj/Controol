"""MemoryManager: ponte entre detecção de commits, vault e curator."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..git_tools import commits_since
from .curator import curate_commit
from .store import MemoryStore


class MemoryManager:
    def __init__(self, cwd: Path | str):
        self.store = MemoryStore(cwd)
        self.store.ensure()

    # ---------- detecção ----------
    def pending_commits(self) -> list[str]:
        return self.store.pending_commits()

    def scan_commits_since(self, since: str | None) -> list[str]:
        """Registra commits novos desde `since` (comparação com HEAD na sessão)."""
        if not since:
            return self.pending_commits()
        for h in commits_since(self.store.root, since):
            self.store.add_pending(h)
        return self.pending_commits()

    # ---------- curadoria ----------
    async def curate(
        self,
        commit: str,
        category: str,
        harness: Any,
        name: str | None = None,
    ) -> str:
        result = await curate_commit(self.store, harness, commit, category, name)
        self.store.mark_handled(commit)
        return result
