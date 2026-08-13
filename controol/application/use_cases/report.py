"""ReportUseCase: geração dos relatórios de trabalho/estudo (gate por modo)."""
from __future__ import annotations

from ..session import Session


class ReportUseCase:
    """Regras dos relatórios: só geram quando o modo correspondente está ativo."""

    def write_work(self, session: Session, harness_desc: str) -> str | None:
        """Regenera `controol-report.html` no modo Trabalho; senão `None`."""
        if not session.modes.get("trabalho"):
            return None
        from ...report.work_report import write_work_report

        return write_work_report(session.cwd, session.interactions, harness_desc)

    async def write_study(self, session: Session, harness) -> str | None:
        """Gera `controol-estudo.html` no modo Estudo (usa o harness); senão `None`."""
        if not session.modes.get("estudo"):
            return None
        from ...report.study_report import write_study_report

        return await write_study_report(session.cwd, session.interactions, harness)
