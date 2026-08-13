"""ReviewUseCase: regras de revisão de diff (listar/aceitar/rejeitar)."""
from __future__ import annotations

from pathlib import Path

from ...git_tools import file_diff_text, reject_file, reviewable_changes
from ..session import Session


class ReviewUseCase:
    """Regras da revisão de código alterado (painel direito da TUI).

    Só muta o estado da `Session` e lê o git — nenhum widget aqui.
    """

    def __init__(self, cwd: Path | str):
        self.cwd = Path(cwd)

    def refresh(self, session: Session) -> None:
        """Re-lê os arquivos revisáveis (sem os artefatos do Controol).

        Ignora `.controol/` e os relatórios gerados — senão o próprio Controol
        apareceria como "alteração" e os botões aceitar/rejeitar não sumiriam.
        """
        session.changed_files = reviewable_changes(self.cwd)
        valid = {p for _, p in session.changed_files}
        if session.selected_file is None or session.selected_file not in valid:
            session.selected_file = (
                session.changed_files[0][1] if session.changed_files else None
            )

    def diff_for(self, path: str) -> str:
        """Diff unificado do arquivo selecionado."""
        return file_diff_text(self.cwd, path)

    def has_pending(self, session: Session) -> bool:
        """Há alteração ainda não aceita (mostra aceitar/rejeitar)."""
        return any(p not in session.accepted for _, p in session.changed_files)

    def accept(self, session: Session, path: str) -> None:
        """Marca o arquivo como mantido na sessão (revisão local, sem IA)."""
        session.accepted.add(path)

    def accept_all(self, session: Session) -> None:
        for _status, path in session.changed_files:
            session.accepted.add(path)

    def reject(self, session: Session, path: str) -> bool:
        """Descarta a alteração (restaura do HEAD no disco); True se restaurou."""
        session.accepted.discard(path)
        return reject_file(self.cwd, path)
