"""Painel superior direito: código do arquivo selecionado, verde/vermelho.

As linhas adicionadas ganham fundo verde ("canetinha") e as removidas fundo
vermelho. Botões Aceitar / Rejeitar (restaura via git) e Aceitar tudo.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Static
from rich.text import Text

from ...report.diffing import parse_unified_diff


class AcceptFile(Message):
    def __init__(self, path: str | None) -> None:
        super().__init__()
        self.path = path


class RejectFile(Message):
    def __init__(self, path: str | None) -> None:
        super().__init__()
        self.path = path


class AcceptAll(Message):
    """Aceita todos os arquivos alterados de uma vez."""


class NavigateFile(Message):
    """Botões < > pediram para trocar o arquivo exibido no diff."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


class DiffPanel(Vertical):
    """Mostra o diff (git diff HEAD) do arquivo selecionado."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_path: str | None = None
        self._files: list[str] = []
        self._index = 0

    def compose(self) -> ComposeResult:
        yield Static("▸ DIFF", id="diff-title", classes="panel-title")
        with Horizontal(id="diff-nav"):
            yield Button("<", id="btn-prev-file")
            yield Button(">", id="btn-next-file")
        with VerticalScroll(id="diff-scroll"):
            yield Static(id="diff-content")
        yield Static(id="diff-status", classes="diff-status")
        with Horizontal(id="diff-actions"):
            yield Button("✓ Aceitar", id="btn-accept", variant="success")
            yield Button("✗ Rejeitar", id="btn-reject", variant="error")
            yield Button("✓ Aceitar tudo", id="btn-accept-all", variant="success")

    def set_has_changes(self, has: bool) -> None:
        """Aceitar/Rejeitar/Aceitar tudo só aparecem quando há alterações."""
        self.query_one("#diff-actions").display = has

    def set_files(self, files: list[str]) -> None:
        """Lista de arquivos revisáveis — alimenta os botões < > de navegação."""
        self._files = files
        if self._index >= len(files):
            self._index = max(0, len(files) - 1)
        self._sync_nav()

    def _sync_nav(self) -> None:
        few = len(self._files) <= 1
        self.query_one("#btn-prev-file", Button).disabled = few
        self.query_one("#btn-next-file", Button).disabled = few

    def show_diff(self, path: str | None, diff_text: str, accepted: bool = False) -> None:
        self._current_path = path
        if path and path in self._files:
            self._index = self._files.index(path)
        title = self.query_one("#diff-title", Static)
        title.update(f"▸ DIFF — {path or 'nenhum'}")
        status = self.query_one("#diff-status", Static)
        if accepted:
            status.update("✓ aceito — mantido")
        else:
            status.update("")
        content = self.query_one("#diff-content", Static)
        if not path:
            content.update("  Selecione um arquivo alterado para revisar o diff.")
            return
        if not diff_text:
            content.update("  (sem alterações em relação ao HEAD)")
            return

        t = Text()
        for ln in parse_unified_diff(diff_text):
            if ln.kind == "+":
                t.append("+ ", "bold #baffc9 on #0b2b1a")
                t.append(ln.text + "\n", "#baffc9 on #0b2b1a")
            elif ln.kind == "-":
                t.append("- ", "bold #ffb4b4 on #2b0b0f")
                t.append(ln.text + "\n", "#ffb4b4 on #2b0b0f")
            elif ln.kind == "hunk":
                t.append(ln.text + "\n", "bold #00bbf9")
            else:
                t.append("  " + ln.text + "\n", "#8a8f9e")
        content.update(t)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("btn-prev-file", "btn-next-file"):
            if not self._files:
                return
            step = -1 if event.button.id == "btn-prev-file" else 1
            self._index = (self._index + step) % len(self._files)
            self.post_message(NavigateFile(self._files[self._index]))
        elif event.button.id == "btn-accept":
            self.post_message(AcceptFile(self._current_path))
        elif event.button.id == "btn-reject":
            self.post_message(RejectFile(self._current_path))
        elif event.button.id == "btn-accept-all":
            self.post_message(AcceptAll())
