"""Modais de memória: escolha de categoria e nome de categoria customizada."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class MemoryModal(ModalScreen[str | None]):
    """Pergunta se quer salvar memória dos commits pendentes e em qual categoria."""

    def __init__(self, pending: list[tuple[str, str]]) -> None:
        super().__init__()
        self.pending = pending

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-modal"):
            yield Static("▸ MEMÓRIA", classes="panel-title")
            yield Static("Há commit(s) sem memória salva:")
            for h, s in self.pending:
                yield Static(f"  {h} — {s}")
            yield Static("Salvar memória como:")
            yield Button("1 · Documentação de software", id="cat-documentacao")
            yield Button("2 · Bugs raros", id="cat-bugs")
            yield Button("3 · Nova categoria…", id="cat-custom")
            yield Button("Agora não", id="cat-later")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        cat = str(event.button.id).removeprefix("cat-")
        self.dismiss(None if cat == "later" else cat)


class NameModal(ModalScreen[str | None]):
    """Coleta o nome de uma categoria customizada."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self._label = label

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-modal"):
            yield Static(self._label, classes="panel-title")
            yield Input(placeholder="ex.: arquitetura, build, android…", id="name-input")
            yield Button("OK", id="btn-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-ok":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        if name:
            self.dismiss(name)
