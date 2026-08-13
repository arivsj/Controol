"""MemoryUseCase: regras de captura de memória (vigia commits sempre)."""
from __future__ import annotations

from pathlib import Path

from ...git_tools import commit_subject
from ...memory import MemoryManager
from ..ports import LogSink
from ..session import Session


class MemoryUseCase:
    """Ponte para o vault de memória: pendências + curadoria dos commits.

    A memória **não é um modo**: vigia os commits sempre (na abertura da TUI
    e após cada commit/pull pela barra git). Uma única instância de
    `MemoryManager` serve a sessão toda (scan + curate).
    """

    def __init__(self, cwd: Path | str):
        self.cwd = Path(cwd)
        self._mgr = MemoryManager(self.cwd)

    def pending(self, session: Session) -> list[tuple[str, str]]:
        """Registra commits novos desde o início da sessão e devolve p/ o modal.

        Retorna `(hash8, subject)` — exatamente o que o `MemoryModal` exibe.
        """
        if session.session_start_head:
            self._mgr.scan_commits_since(session.session_start_head)
        return [
            (h[:8], commit_subject(self.cwd, h)) for h in self._mgr.pending_commits()
        ]

    def pending_commits(self) -> list[str]:
        """Hashes completos ainda pendentes (para salvar de fato)."""
        return self._mgr.pending_commits()

    async def save(
        self,
        commits: list[str],
        category: str,
        harness,
        name: str | None = None,
        sink: LogSink | None = None,
    ) -> None:
        """Cura cada commit pendente, reportando progresso pelo sink."""
        for commit in commits:
            if sink:
                sink.write(
                    f"→ salvando memória do commit {commit[:8]} ({category}) …",
                    "bold #9d4edd",
                )
            try:
                result = await self._mgr.curate(commit, category, harness, name)
                if sink:
                    sink.write(f"✓ {result}", "bold #00f5d4")
            except Exception as exc:
                if sink:
                    sink.write(f"⚠ falha ao salvar memória: {exc}", "bold #ff2e63")
