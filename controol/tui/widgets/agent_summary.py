"""Execução + resposta do agente — card único acima do input (substituiu o `#log`)."""
from __future__ import annotations

import textwrap

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

# engrenagem girando (spinner braille) + esteira por onde a caixa desliza
_SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
_BELT = 14
# o card agora tem a largura da coluna esquerda (54): conteúdo ~50 colunas
_MAX_COLS = 46  # quebra de linha prévia (o Static também embrulha na largura)


def _wrap(text: str, width: int = _MAX_COLS) -> list[str]:
    """Quebra preservando quebras explícitas (textwrap.wrap as achata)."""
    out: list[str] = []
    for para in text.split("\n"):
        out.extend(textwrap.wrap(para, width=width) or [""])
    return out


class AgentSummary(Vertical):
    """Card único de execução (assumiu o papel do antigo `#log`).

    Acumula o que o agente executou (tool calls, arquivos alterados, passos,
    feedback do app) e, no fim, a resposta do agente. Enquanto o agente
    trabalha, a primeira linha é a animação de fábrica e a resposta vai
    entrando por baixo dela.

    API:
    - log de execução: `add_line(text, style)` / `clear()`
    - animação: `start_working` / `set_working_label` / `append_reply` /
      `stop_working` (devolve a resposta acumulada, movida pro log)
    - fim do run: `set_summary(reply, files)`
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._working = False
        self._timer = None
        self._frame = 0
        self._label = ""
        self._reply = ""
        self._lines: list[tuple[str, str]] = []  # (texto, estilo rich)

    def compose(self) -> ComposeResult:
        yield Static("▸ EXECUÇÃO · RESPOSTA DO AGENTE", classes="panel-title")
        yield Static("", id="summary-content", markup=False)

    # ---------- log de execução ----------
    def add_line(self, text: str, style: str = "#e0e6ed") -> None:
        """Linha do log (tool call, arquivo, passo, feedback do app)."""
        self._lines.append((text, style))
        if len(self._lines) > 100:  # guarda as recentes; o card mostra as últimas
            self._lines = self._lines[-100:]
        self._draw()

    def clear(self) -> None:
        self.stop_working()
        self._lines = []
        self._reply = ""
        self._draw()

    # ---------- animação de fábrica (agente trabalhando) ----------
    def start_working(self, label: str = "") -> None:
        self._working = True
        self._label = label
        self._reply = ""
        self._frame = 0
        if self._timer is None:
            self._timer = self.set_interval(0.15, self._tick)
        self._draw()

    def set_working_label(self, label: str) -> None:
        """Ação corrente (tool call) exibida na animação."""
        self._label = label

    def append_reply(self, text: str) -> None:
        """Resposta do agente entrando por baixo da animação."""
        if self._reply:
            self._reply += "\n" + text
        else:
            self._reply = text
        self._draw()

    def stop_working(self) -> str:
        """Para a animação; preserva a resposta acumulada no log.

        Devolve a resposta que foi movida para as linhas (para o chamador não
        duplicá-la no `set_summary`).
        """
        moved = self._reply
        self._working = False
        if moved:
            self._lines.append((moved, "#e4e4e4"))
            self._reply = ""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._draw()
        return moved

    def _tick(self) -> None:
        self._frame += 1
        self._draw()

    def _draw(self) -> None:
        """Desenha o frame — ATENÇÃO: NÃO chamar de `_render`
        (colide com `Widget._render()` do Textual e quebra o render)."""
        content = self.query_one("#summary-content", Static)
        t = Text()
        added = False

        def _sep() -> None:
            nonlocal added
            if added:
                t.append("\n")
            added = True

        if self._working:
            # linha da fábrica: engrenagem + esteira com caixa deslizando
            t.append("🏭 ", style="bold #ffb703")
            t.append(_SPIN[self._frame % len(_SPIN)], style="bold #00f5d4")
            t.append(" ═", style="#9d4edd")
            belt = ["─"] * _BELT
            pos = (self._frame % (_BELT + 3)) - 3  # caixa entra pela esquerda
            for k in range(3):
                if 0 <= pos + k < _BELT:
                    belt[pos + k] = "█"
            t.append("".join(belt), style="#9d4edd")
            t.append("═", style="#9d4edd")
            t.append(" construindo…", style="bold #f72585")
            if self._label:
                t.append(f"\n  {self._label}", style="dim #8a8f9e")
            if self._reply:
                t.append(f"\n{self._reply}", style="#e4e4e4")
            added = True

        for text, style in self._lines:
            for piece in _wrap(text):
                _sep()
                t.append(piece, style=style)

        if not added:
            t.append("—")
        content.update(t)

    # ---------- resultado final ----------
    def set_summary(self, reply: str, files: str = "") -> None:
        moved = self.stop_working()
        # se a resposta já foi movida pro log pelo stop_working, não duplica
        if reply and reply != moved:
            self._lines.append((reply, "#e4e4e4"))
        if files:
            self._lines.append((files, "dim #8a8f9e"))
        self._draw()
