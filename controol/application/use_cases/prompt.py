"""RunPromptUseCase: orquestração de um prompt do harness (regras do run)."""
from __future__ import annotations

from ...git_tools import file_diff_text
from ..ports import PromptPresenter
from ..session import Session


class RunPromptUseCase:
    """Itera o harness despachando eventos ao presenter e fecha a interação.

    A fila, a animação e o foco ficam no coordenador (app); aqui moram as
    regras: zerar `accepted` a cada run, montar a interação (prompt, files,
    explanation) e preencher os diffs reais no fim.
    """

    def __init__(self, session: Session, harness, presenter: PromptPresenter, review):
        self.session = session
        self.harness = harness
        self.presenter = presenter
        self.review = review

    async def run(self, prompt: str, interaction: dict) -> None:
        """Executa o prompt e despacha cada evento normalizado ao presenter."""
        session = self.session
        session.accepted.clear()  # nova iteração = novo lote de revisão
        async for ev in self.harness.run(prompt):
            self._dispatch(ev, interaction)

    def _dispatch(self, ev, interaction: dict) -> None:
        if ev.type == "agent_text":
            if ev.text.strip():
                interaction["explanation"] = ev.text
                self.presenter.on_agent_text(ev.text)
        elif ev.type == "tool":
            self.presenter.on_tool(ev.text)
        elif ev.type == "file_touched":
            if ev.file:
                self.presenter.on_file_touched(ev.file, ev.text or ev.file)
                interaction["files"].setdefault(ev.file, "")
                # arquivo alterado entra na lista de revisão ao vivo
                if not any(p == ev.file for _, p in self.session.changed_files):
                    self.session.changed_files.append(("M", ev.file))
                    self.presenter.on_files_changed()
        elif ev.type == "error":
            self.presenter.on_error(ev.text)
        elif ev.type == "step_done":
            self.presenter.on_step_done(ev.data)

    def finish(self, session: Session, interaction: dict) -> str:
        """Fecha a interação: refresh da revisão + diffs reais; devolve o rótulo.

        O rótulo é o resumo que o card de execução mostra no fim do run
        (`N arquivo(s) alterado(s): …` ou `nenhum arquivo alterado`).
        """
        self.review.refresh(session)
        for _status, path in session.changed_files:
            interaction["files"][path] = file_diff_text(session.cwd, path)
        n = len(session.changed_files)
        if n:
            files = ", ".join(p for _, p in session.changed_files)
            return f"{n} arquivo(s) alterado(s): {files}"
        return "nenhum arquivo alterado"
