"""Abstração de harness: eventos normalizados emitidos por `run(prompt)`."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator


@dataclass
class Event:
    """Evento normalizado do harness, independente do schema de cada um.

    type: agent_text | tool | file_touched | step_done | error
    """
    type: str
    text: str = ""
    tool: str = ""    # nome da ferramenta (bash, edit, write, ...)
    file: str = ""    # caminho de arquivo quando relevante
    data: dict = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Event {self.type} {self.tool or self.file or (self.text[:40])}>"


class Harness(ABC):
    """Interface para um harness de IA de linha de comando."""

    name = "base"

    # As linhas JSON dos harnesses embutem diffs/texto grandes. O StreamReader
    # do asyncio tem limite padrão de 64 KiB: uma linha maior estoura em
    # `asyncio.LimitOverrunError` ("separator is found, but chunk is longer than
    # limit"), que não é JSONDecodeError e derruba o run. O `limit` do
    # create_subprocess_exec é propagado para o reader do stdout.
    STREAM_LIMIT = 64 * 1024 * 1024  # 64 MiB

    def __init__(
        self,
        cwd: Path,
        model: str | None = None,
        agent: str | None = None,
        auto_approve: bool = False,
    ):
        self.cwd = cwd
        self.model = model
        self.agent = agent
        self.auto_approve = auto_approve

    @abstractmethod
    async def run(self, prompt: str) -> AsyncIterator[Event]:
        """Executa um prompt (não-interativo) e emite eventos até terminar."""

    def probe_model(self) -> str | None:
        """Modelo já conhecido sem rodar um prompt (default: o configurado).

        Subclasses podem inferir o modelo que será usado (ex.: config do
        harness ou última sessão) para o footer mostrar o modelo de verdade.
        """
        return self.model

    def describe(self) -> str:
        parts = [self.name]
        if self.model:
            parts.append(str(self.model))
        if self.agent:
            parts.append(f"agent={self.agent}")
        return "/".join(parts)
