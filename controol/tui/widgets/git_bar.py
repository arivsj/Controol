"""Barra de ações git acima do card de execução + modal da mensagem de commit.

Cada botão posta um `GitAction`; o app roda a operação assíncrona e dá o
feedback no card de execução. O `CommitModal` coleta a mensagem antes de
`git commit`.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

GIT_BUTTON_IDS = (
    "git-status", "git-add", "git-commit", "git-push", "git-fetch", "git-pull",
)


class GitAction(Message):
    """Pedido de operação git vinda da barra de botões."""

    def __init__(self, action: str) -> None:
        super().__init__()
        self.action = action


class GitBar(Horizontal):
    """Botões add / commit / push / fetch / pull, acima do card de iteração."""

    def compose(self) -> ComposeResult:
        # sem prefixos (+, ↑, ↓): os 6 botões cabem nos 54 da coluna esquerda
        yield Button("status", id="git-status")
        yield Button("add", id="git-add")
        yield Button("commit", id="git-commit")
        yield Button("push", id="git-push")
        yield Button("fetch", id="git-fetch")
        yield Button("pull", id="git-pull")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not event.button.id or not event.button.id.startswith("git-"):
            return
        self.post_message(GitAction(event.button.id.removeprefix("git-")))

    def set_busy(self, busy: bool) -> None:
        """Trava/libera os botões enquanto uma operação git roda."""
        for btn_id in GIT_BUTTON_IDS:
            self.query_one(f"#{btn_id}", Button).disabled = busy


class CommitModal(ModalScreen[str | None]):
    """Pede a mensagem do commit antes de rodar `git commit`."""

    def compose(self) -> ComposeResult:
        with Vertical(id="commit-modal"):
            yield Static("▸ COMMIT", classes="panel-title")
            yield Static("Mensagem do commit (Enter para commitar):")
            yield Input(placeholder="ex.: fix: corrige parsing de eventos", id="commit-input")
            yield Button("Commiter", id="btn-commit-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-commit-ok":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        msg = self.query_one("#commit-input", Input).value.strip()
        if msg:
            self.dismiss(msg)
