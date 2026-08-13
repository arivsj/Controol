"""App Textual do Controol: coordenador/presenter fino (Clean pragmático).

A camada de apresentação (widgets) delega as regras de negócio aos use cases
de `controol/application/use_cases`; este módulo só orquestra mensagens →
use case → renderização. As propriedades (`changed_files`, `interactions`, …)
são proxies da `Session` para compatibilidade com a suíte de testes.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Checkbox, Input

from .. import __version__
from ..application import Session, count_text_tokens, fmt_tokens, tokens_from_data
from ..application.use_cases import (
    GitUseCase,
    MemoryUseCase,
    ModelProbeUseCase,
    ReportUseCase,
    ReviewUseCase,
    RunPromptUseCase,
)
from ..config import Config
from ..git_tools import head_commit
from ..harness import create_harness
from .widgets import (
    AcceptAll,
    AcceptFile,
    AgentSummary,
    Banner,
    ClearContext,
    CommitModal,
    DiffPanel,
    FileSelected,
    GitAction,
    GitBar,
    ModeChanged,
    ModesPanel,
    NavigateFile,
    PromptInput,
    PromptSubmitted,
    RejectFile,
    StatusFooter,
)
from .widgets.memory_modal import MemoryModal, NameModal

MODE_IDS = {"trabalho": "mode-trabalho", "estudo": "mode-estudo"}


class ControolApp(App):
    """Interface principal estilo bashtop, orquestrando o harness por trás.

    A captura de memória não é um modo: ela vigia os commits sempre
    (dentro da sessão e na abertura), independente de toggle.
    """

    TITLE = "CONTROOL CLI"
    CSS_PATH = "theme.css"

    BINDINGS = [
        Binding("ctrl+r", "toggle('trabalho')", "Trabalho", priority=True),
        Binding("ctrl+e", "toggle('estudo')", "Estudo", priority=True),
        Binding("ctrl+a", "accept_selected", "Aceitar", priority=True),
        Binding("ctrl+x", "reject_selected", "Rejeitar", priority=True),
    ]

    def __init__(self, config: Config, cwd: Path | None = None) -> None:
        super().__init__()
        self.config = config
        self.cwd = cwd or config.root
        self.harness = create_harness(config, self.cwd)
        # estado da sessão (fonte única de verdade) + use cases (aplicação)
        self.session = Session(
            cwd=self.cwd,
            session_start_head=head_commit(self.cwd),
        )
        self.review = ReviewUseCase(self.cwd)
        self.git = GitUseCase(self.cwd)
        self.memory = MemoryUseCase(self.cwd)
        self.report = ReportUseCase()
        self.model_probe = ModelProbeUseCase()
        self.run_uc = RunPromptUseCase(self.session, self.harness, self, self.review)
        # estado de apresentação (footer / resposta / fila)
        self.tokens_input = 0   # entrada (contexto)
        self.tokens_total = 0   # uso total (inclui saída/cache)
        self._tokens_measured = False  # True quando o harness reporta uso real
        # modelo conhecido sem rodar prompt (probe do harness no startup);
        # o `harness.model` (config/detectado no run) tem prioridade no footer
        self._probe_model: str | None = None
        # resposta do agente na última interação (painel acima do input)
        self.last_reply = ""
        self.agent_response = ""   # resposta acumulada do run em andamento
        self._busy = False         # um run de harness está rodando
        self._queue: list[str] = []  # pedidos digitados durante o trabalho

    # ---------- proxy de compatibilidade (fonte única: Session) ----------
    @property
    def modes(self) -> dict[str, bool]:
        return self.session.modes

    @modes.setter
    def modes(self, value: dict[str, bool]) -> None:
        self.session.modes = value

    @property
    def accepted(self) -> set[str]:
        return self.session.accepted

    @accepted.setter
    def accepted(self, value: set[str]) -> None:
        self.session.accepted = value

    @property
    def changed_files(self) -> list[tuple[str, str]]:
        return self.session.changed_files

    @changed_files.setter
    def changed_files(self, value: list[tuple[str, str]]) -> None:
        self.session.changed_files = value

    @property
    def selected_file(self) -> str | None:
        return self.session.selected_file

    @selected_file.setter
    def selected_file(self, value: str | None) -> None:
        self.session.selected_file = value

    @property
    def interactions(self) -> list[dict]:
        return self.session.interactions

    @interactions.setter
    def interactions(self, value: list[dict]) -> None:
        self.session.interactions = value

    @property
    def session_start_head(self) -> str | None:
        return self.session.session_start_head

    # ---------- compose ----------
    def compose(self) -> ComposeResult:
        yield Banner(id="banner")
        with Horizontal(id="columns"):
            # coluna esquerda (54): modos c/ lista de arquivos + git + execução
            with Vertical(id="left"):
                yield ModesPanel(id="modes")
                yield GitBar(id="gitbar")
                yield AgentSummary(id="agent-summary")  # 54 de largura, mais alto
            yield DiffPanel(id="diff")  # card de revisão alto (coluna direita)
        yield PromptInput(id="prompt")
        yield StatusFooter(id="status-footer")

    def on_mount(self) -> None:
        self.refresh_files()
        self._update_header()
        self._update_footer()
        self._focus_prompt()
        if self.harness.model is None:
            # detecta o modelo em background (sem gastar prompt) e atualiza o
            # footer assim que souber
            self.run_worker(self._probe_model_worker, group="probe")

    async def _probe_model_worker(self) -> None:
        detected = await asyncio.to_thread(self.model_probe.detect, self.harness)
        if detected and self.harness.model is None:
            self._probe_model = detected
            self._update_footer()
        self._write(
            f"CONTROOL CLI v{__version__} · harness: {self.harness.describe()}",
            "bold #00f5d4",
        )
        self._check_memory()

    # ---------- helpers ----------
    def _write(self, text: str, style: str = "#e0e6ed") -> None:
        # o log agora mora no card de execução (o antigo RichLog #log saiu)
        self.query_one(AgentSummary).add_line(text, style)

    def write(self, text: str, style: str = "") -> None:
        """LogSink: canal de log usado pelos use cases (ex.: memória)."""
        self._write(text, style or "#e0e6ed")

    def _update_header(self) -> None:
        # memória vigia commits sempre (não é um modo alternável)
        on = [k.upper() for k, v in self.modes.items() if v]
        label = "MEMÓRIA ✓" if not on else f"MEMÓRIA ✓ · {', '.join(on)}"
        self.query_one(Banner).set_status(self.harness.describe(), label, str(self.cwd))

    def set_loading(self, loading: bool) -> None:
        self.query_one(PromptInput).set_loading(loading)

    def _focus_prompt(self) -> None:
        """Devolve o foco ao campo do prompt (container não é focável)."""
        try:
            self.query_one("#prompt-field", Input).focus()
        except Exception:  # pragma: no cover
            pass

    # ---------- stats do footer ----------
    @staticmethod
    def _tokens_from_data(data: dict) -> tuple[int, int]:
        """Extrai (entrada, total) de tokens (delega a `application/tokens.py`)."""
        return tokens_from_data(data)

    def _update_footer(self) -> None:
        try:
            fw = self.query_one(StatusFooter)
        except Exception:  # pragma: no cover
            return
        # o footer mostra o MODELO (config/detectado/probe), nunca o harness
        modelo = self.model_probe.label(self.harness.model, self._probe_model)
        fw.update_stats(
            str(modelo),
            f"{fmt_tokens(self.tokens_input)} (entrada)",
            fmt_tokens(self.tokens_total),
        )

    # ---------- clear: resetar o contexto da conversa ----------
    def on_clear_context(self, event: ClearContext) -> None:
        self._clear_context()

    def _clear_context(self) -> None:
        """Zera o contexto da sessão para economizar tokens.

        Cada rodada do opencode já é uma sessão nova; este botão reinicia o
        que o Controol acumula: contadores do footer, interações do relatório
        e a resposta do agente.
        """
        self.session.interactions = []
        self.session.accepted.clear()
        self.tokens_input = 0
        self.tokens_total = 0
        self._tokens_measured = False
        self.last_reply = ""
        self.agent_response = ""
        self._queue = []
        self._update_footer()
        self.query_one(AgentSummary).clear()
        self._refresh_queue()
        self._write(
            "✓ contexto da conversa limpo — contadores zerados",
            "bold #00f5d4",
        )

    # ---------- arquivos / diff ----------
    def refresh_files(self) -> None:
        # regra (arquivos revisáveis, fixup do selecionado) no use case;
        # aqui só a renderização dos widgets
        self.review.refresh(self.session)
        self._render_files()

    def _render_files(self) -> None:
        self.query_one(ModesPanel).set_files(self.changed_files)
        self.query_one(DiffPanel).set_files([p for _, p in self.changed_files])
        self._show_selected()

    def _show_selected(self) -> None:
        panel = self.query_one(DiffPanel)
        # aceitar/rejeitar só aparecem com aceite pendente (alteração não aceita)
        panel.set_has_changes(self.review.has_pending(self.session))
        if not self.selected_file:
            panel.show_diff(None, "", accepted=False)
            return
        panel.show_diff(
            self.selected_file,
            self.review.diff_for(self.selected_file),
            accepted=self.selected_file in self.accepted,
        )

    # ---------- prompt -> harness ----------
    def on_prompt_submitted(self, event: PromptSubmitted) -> None:
        self._enqueue_or_run(event.text)

    def _enqueue_or_run(self, prompt: str) -> None:
        """Roda na hora se livre; senão, entra na fila (mostrada no card)."""
        if self._busy:
            self._queue.append(prompt)
            self._refresh_queue()
            self._write(
                f"⏳ na fila ({len(self._queue)}): {prompt}", "bold #ffb703"
            )
            return
        self._busy = True  # reserva imediata: Enter duplo vira fila, não cancela
        self.run_worker(self._handle_prompt(prompt), group="harness", exclusive=True)

    def _refresh_queue(self) -> None:
        self.query_one(PromptInput).set_queue(self._queue)

    async def _handle_prompt(self, prompt: str) -> None:
        self._write(f"❯ {prompt}", "bold #00bbf9")
        self._busy = True
        self.set_loading(True)
        self.last_reply = ""
        self.agent_response = ""
        self.query_one(AgentSummary).start_working()  # animação de fábrica
        self._refresh_queue()
        interaction: dict = {"prompt": prompt, "files": {}, "explanation": ""}
        self.interactions.append(interaction)
        try:
            await self.run_uc.run(prompt, interaction)  # loop + eventos → presenter
            self._on_run_done(interaction)
        except asyncio.CancelledError:
            self._write("⏹ interrompido", "bold #ffb703")
        except Exception as exc:  # falha do agente não pode matar a TUI
            self._write(f"⚠ falha ao rodar o agente: {exc}", "bold #ff2e63")
        finally:
            self._busy = False
            self.query_one(AgentSummary).stop_working()
            self.set_loading(False)
            self._refresh_queue()
            self._focus_prompt()  # pronto pra próxima fala com o agente
            if self._queue:
                nxt = self._queue.pop(0)
                self._busy = True  # sem gap: um submit não furaria a fila
                self._refresh_queue()
                self._write("▶ fila: processando próximo pedido", "bold #00f5d4")
                self.run_worker(
                    self._handle_prompt(nxt), group="harness", exclusive=True
                )

    # ---------- PromptPresenter (eventos normalizados → renderização) ----------
    def on_agent_text(self, text: str) -> None:
        self.last_reply = text  # resposta do agente → painel acima
        self.agent_response = (self.agent_response + "\n" + text).strip()
        self.query_one(AgentSummary).append_reply(text)
        if not self._tokens_measured:
            est = count_text_tokens(text)
            self.tokens_input += est
            self.tokens_total += est
            self._update_footer()
        # a resposta já entra por baixo da animação (append_reply) —
        # não logar de novo para não duplicar no card

    def on_tool(self, text: str) -> None:
        self._write(text, "dim #8a8f9e")
        self.query_one(AgentSummary).set_working_label(text)

    def on_file_touched(self, path: str, label: str) -> None:
        self.query_one(AgentSummary).set_working_label(label)
        self._write(label, "dim #a6e22e")  # verde: alterado

    def on_files_changed(self) -> None:
        self.query_one(ModesPanel).set_files(self.changed_files)
        self._show_selected()  # botões aceitar/rejeitar ao vivo

    def on_step_done(self, data: dict) -> None:
        i, t = self._tokens_from_data(data)
        if i or t:
            self._tokens_measured = True
            self.tokens_input += i
            self.tokens_total += t
            self._update_footer()
        self._write("▸ passo concluído", "dim #535768")

    def on_error(self, text: str) -> None:
        self._write(f"⚠ {text}", "bold #ff2e63")

    def _on_run_done(self, interaction: dict) -> None:
        label = self.run_uc.finish(self.session, interaction)
        self._render_files()
        self._update_footer()
        resposta = self.agent_response or self.last_reply
        self.query_one(AgentSummary).set_summary(resposta, label)
        self._write("✓ execução concluída", "bold #00f5d4")
        self._persist_session()
        if self.session.modes["trabalho"]:
            self._feed_work_report()
        if self.session.modes["estudo"]:
            self._feed_study_report()
        self._check_memory()

    # ---------- relatórios (Fase D) ----------
    def _feed_work_report(self) -> None:
        try:
            out = self.report.write_work(self.session, self.harness.describe())
            if out:
                self._write(f"→ relatório de trabalho: {out}", "bold #00f5d4")
        except Exception as exc:  # pragma: no cover
            self._write(f"⚠ relatório de trabalho: {exc}", "bold #ffb703")

    def _feed_study_report(self) -> None:
        self.run_worker(self._do_study_report(), group="study", exclusive=True)

    async def _do_study_report(self) -> None:
        try:
            out = await self.report.write_study(self.session, self.harness)
            if out:
                self._write(f"→ relatório de estudo: {out}", "bold #9d4edd")
        except Exception as exc:  # pragma: no cover
            self._write(f"⚠ relatório de estudo: {exc}", "bold #ffb703")

    def _persist_session(self) -> None:
        """Salva as interações para regenerar relatórios via `controol report`."""
        from ..application import persist_session

        persist_session(self.cwd, self.harness.describe(), self.interactions)

    # ---------- memória ----------
    def _check_memory(self) -> None:
        """Vigia commits sempre: pendências do hook + commits feitos na sessão."""
        try:
            items = self.memory.pending(self.session)
            if items:
                self._open_memory_modal(items)
        except Exception as exc:  # pragma: no cover
            self._write(f"⚠ memória: {exc}", "bold #ffb703")

    def _open_memory_modal(self, items: list[tuple[str, str]]) -> None:
        def on_result(category: str | None) -> None:
            if category == "custom":
                self.push_screen(NameModal("Nome da nova categoria:"), self._on_custom_name)
            elif category:
                self.run_worker(self._save_memory(category))

        self.push_screen(MemoryModal(items), on_result)

    def _on_custom_name(self, name: str | None) -> None:
        if not name:
            return
        self.run_worker(self._save_memory("custom", name))

    async def _save_memory(self, category: str, name: str | None = None) -> None:
        commits = self.memory.pending_commits()
        await self.memory.save(commits, category, self.harness, name, sink=self)

    # ---------- modos / ações ----------
    def action_toggle(self, mode: str) -> None:
        self.modes[mode] = not self.modes[mode]
        cb = self.query_one(f"#{MODE_IDS[mode]}", Checkbox)
        cb.value = self.modes[mode]

    def on_mode_changed(self, event: ModeChanged) -> None:
        self.modes[event.mode] = event.checked
        self._update_header()

    def on_file_selected(self, event: FileSelected) -> None:
        self.selected_file = event.path
        self._show_selected()

    def on_navigate_file(self, event: NavigateFile) -> None:
        self.selected_file = event.path
        self._show_selected()

    def on_accept_file(self, event: AcceptFile) -> None:
        if event.path:
            self.review.accept(self.session, event.path)
            self._write(f"✓ aceito: {event.path}", "bold #00f5d4")
            self._show_selected()

    def on_accept_all(self, event: AcceptAll) -> None:
        self.review.accept_all(self.session)
        self._write(
            f"✓✓ {len(self.changed_files)} arquivo(s) aceito(s) de uma vez",
            "bold #00f5d4",
        )
        self._show_selected()

    def on_reject_file(self, event: RejectFile) -> None:
        if event.path and self.review.reject(self.session, event.path):
            self._write(
                f"✗ rejeitado (restaurado do HEAD): {event.path}", "bold #ff2e63"
            )
            self.refresh_files()

    def action_accept_selected(self) -> None:
        self.on_accept_file(AcceptFile(self.selected_file))

    def action_reject_selected(self) -> None:
        self.on_reject_file(RejectFile(self.selected_file))

    # ---------- git (barra acima do card de execução) ----------
    def on_git_action(self, event: GitAction) -> None:
        if event.action == "commit":
            self._start_commit()
        else:
            self.run_worker(self._run_git(event.action), group="git")

    def _start_commit(self) -> None:
        if not self.git.has_stage():
            if self.git.has_changes():
                self._write("⚠ commit: nada no stage — rode + add antes", "bold #ffb703")
            else:
                self._write("⚠ commit: não há alterações para commitar", "bold #ffb703")
            return
        self.push_screen(CommitModal(), self._on_commit_msg)

    def _on_commit_msg(self, message: str | None) -> None:
        if message:
            self.run_worker(self._run_git("commit", message), group="git")
        else:
            # foco volta ao prompt depois que o modal termina de sair da tela
            # (senão o dismiss restaura o foco do botão por cima do nosso)
            self.call_after_refresh(self._focus_prompt)

    async def _run_git(self, action: str, message: str | None = None) -> None:
        self.query_one(GitBar).set_busy(True)
        self._write(f"▶ git {action} …", "dim #8a8f9e")
        try:
            result = await self.git.execute(action, message)
        finally:
            self.query_one(GitBar).set_busy(False)
        for text, style in result.lines:
            self._write(text, style)
        self.refresh_files()
        self._focus_prompt()  # foco de volta no prompt após qualquer git op
        # memória vigia commits sempre: comitar (ou pull que integra commits)
        # pela TUI dispara a pergunta de salvar memória na hora — sem esperar
        # o próximo run do harness
        if result.ok and action in ("commit", "pull"):
            self._check_memory()
