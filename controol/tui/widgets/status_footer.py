"""Footer rosa: stats (modelo/contexto/tokens) + botão Clear à direita."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Static


class ClearContext(Message):
    """Usuário quer limpar o contexto da conversa (economizar tokens)."""


class StatusFooter(Horizontal):
    """Linha inferior com modelo / contexto / tokens usados + botão Clear.

    O Clear reinicia os contadores e as interações da sessão.
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="footer-content")
        yield Button("Clear", id="btn-clear")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-clear":
            self.post_message(ClearContext())

    def update_stats(self, modelo: str, contexto: str, tokens: str) -> None:
        t = Text()
        t.append("▌ MODELO", style="bold #f72585")
        t.append(f" {modelo}   ", style="#e4e4e4")
        t.append("▌ CONTEXTO", style="bold #f72585")
        t.append(f" {contexto}   ", style="#e4e4e4")
        t.append("▌ TOKENS", style="bold #f72585")
        t.append(f" {tokens}", style="#e4e4e4")
        self.query_one("#footer-content", Static).update(t)
