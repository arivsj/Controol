"""Barra de conversa: onde você fala com o agente (input + botão Enviar).

O input **continua digitável enquanto o agente trabalha**: um novo prompt
digitado nessa hora entra na **fila** (mostrada aqui dentro do card, em
`#queue-list`) e é processado quando o agente terminar.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Static

# quantos pedidos da fila aparecem antes do "+N na fila"
_QUEUE_MAX = 3


class PromptSubmitted(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class PromptInput(Vertical):
    """Painel de conversa com o agente: título + input + botão Enviar + fila.

    O container em si NÃO é focável — o foco vai para o `#prompt-field`
    (Input). Tudo aqui é para deixar claro que é neste campo que se fala
    com o agente.
    """

    def compose(self) -> ComposeResult:
        yield Static("▸ FALE COM O AGENTE", classes="panel-title")
        with Horizontal(id="prompt-row"):
            yield Input(
                placeholder="❯ seu pedido para o agente… (Enter envia)",
                id="prompt-field",
            )
            yield Button("Enviar", id="btn-send", variant="primary")
        yield Static("", id="queue-list", markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-send":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        inp = self.query_one("#prompt-field", Input)
        text = inp.value.strip()
        if text:
            inp.clear()
            self.post_message(PromptSubmitted(text))

    def set_loading(self, loading: bool) -> None:
        """Aviso de agente ocupado — sem desabilitar o input (novos pedidos
        vão para a fila enquanto ele trabalha)."""
        inp = self.query_one("#prompt-field", Input)
        btn = self.query_one("#btn-send", Button)
        inp.placeholder = (
            "agente trabalhando… novos pedidos entram na fila" if loading
            else "❯ seu pedido para o agente… (Enter envia)"
        )
        btn.label = "…" if loading else "Enviar"

    def set_queue(self, items: list[str]) -> None:
        """Mostra/esconde os pedidos aguardando na fila (amarelo, dentro do card)."""
        q = self.query_one("#queue-list", Static)
        if not items:
            q.display = False
            q.update("")
            return
        q.display = True
        t = Text()
        for i, p in enumerate(items[:_QUEUE_MAX], 1):
            if i > 1:
                t.append("\n")
            short = p if len(p) <= 60 else p[:57] + "…"
            t.append(f"  ⏳ {i}. ", style="bold #ffb703")
            t.append(short, style="#e4e4e4")
        if len(items) > _QUEUE_MAX:
            t.append(
                f"\n  ⏳ … e mais {len(items) - _QUEUE_MAX} na fila",
                style="dim #8a8f9e",
            )
        q.update(t)
