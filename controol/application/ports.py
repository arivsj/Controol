"""Ports de saída da camada de aplicação (Protocols, sem Textual).

Os use cases conversam com a apresentação através destes contratos; o
`ControolApp` os implementa renderizando nos widgets.
"""
from __future__ import annotations

from typing import Protocol


class LogSink(Protocol):
    """Canal de log do card de execução (o app escreve via `_write`)."""

    def write(self, text: str, style: str = "") -> None: ...


class PromptPresenter(Protocol):
    """Onde os eventos normalizados do harness viram renderização na TUI."""

    def on_agent_text(self, text: str) -> None: ...
    def on_tool(self, text: str) -> None: ...
    def on_file_touched(self, path: str, label: str) -> None: ...
    def on_step_done(self, data: dict) -> None: ...
    def on_error(self, text: str) -> None: ...
    def on_files_changed(self) -> None: ...
