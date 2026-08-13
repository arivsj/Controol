"""Painel superior esquerdo: modos ativos + lista de arquivos alterados."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Checkbox, OptionList, Static
from textual.widgets.option_list import Option

_STATUS_GLYPH = {"A": "+", "M": "~", "D": "-", "R": "→", "C": "="}
_STATUS_STYLE = {"A": "#a6e22e", "M": "#e6db74", "D": "#f92672", "R": "#66d9ef", "C": "#66d9ef"}


class ModeChanged(Message):
    def __init__(self, mode: str, checked: bool) -> None:
        super().__init__()
        self.mode = mode
        self.checked = checked


class FileSelected(Message):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


class ModesPanel(Vertical):
    """Toggles de modo + lista de arquivos alterados na sessão."""

    def compose(self) -> ComposeResult:
        yield Static("▸ MODOS", classes="panel-title")
        with Horizontal(id="mode-row"):
            yield Checkbox("Trabalho", id="mode-trabalho", value=True)
            yield Checkbox("Estudo", id="mode-estudo", value=False)
        yield Static("▸ ARQUIVOS ALTERADOS", classes="panel-title")
        yield OptionList(id="file-list")

    def on_mount(self) -> None:
        self._sync_selected()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._sync_selected()
        mode = {
            "mode-trabalho": "trabalho",
            "mode-estudo": "estudo",
        }.get(event.checkbox.id or "", "")
        if mode:
            self.post_message(ModeChanged(mode, event.value))

    def _sync_selected(self) -> None:
        """Contorno verde no modo ativo (classe `.selected`)."""
        for cb in self.query(Checkbox):
            if cb.value:
                cb.add_class("selected")
            else:
                cb.remove_class("selected")

    def set_files(self, files: list[tuple[str, str]]) -> None:
        ol = self.query_one("#file-list", OptionList)
        ol.clear_options()
        for status, path in files:
            glyph = _STATUS_GLYPH.get(status, " ")
            color = _STATUS_STYLE.get(status, "#8a8f9e")
            t = Text()
            t.append(f"{glyph} ", style=f"bold {color}")
            t.append(path, style="#e4e4e4")
            ol.add_option(Option(t, id=path))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.post_message(FileSelected(str(event.option.id)))
