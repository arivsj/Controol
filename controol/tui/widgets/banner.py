"""Cabeçalho estilo bashtop: caixa neon com título, harness, modos e cwd."""
from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from rich import box
from textual.widgets import Static


class Banner(Static):
    """Barra de topo emoldurada, como as caixas do bashtop."""

    def set_status(self, harness: str, modos: str, cwd: str) -> None:
        t = Text()
        t.append("▌ CONTROOL CLI", style="bold #00f5d4")
        t.append("  ▸  ", style="#535768")
        t.append(harness, style="bold #f72585")
        t.append("  ▸  ", style="#535768")
        t.append(modos, style="bold #ffb703")
        t.append("\n", style="")
        t.append("▚ ", style="#9d4edd")
        t.append(cwd, style="#8a8f9e")
        self.update(
            Panel(
                t,
                box=box.ROUNDED,
                border_style="bold #00f5d4",
                padding=(0, 1),
                expand=True,
            )
        )
