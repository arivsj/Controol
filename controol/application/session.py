"""Estado da sessão do Controol (dados, sem lógica de UI)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Session:
    """Estado de uma sessão do Controol — a fonte única de verdade.

    Os widgets/TUI apenas leem/refletem isto; as regras que mutam o estado
    vivem nos use cases (`controol/application/use_cases`).
    """

    cwd: Path
    modes: dict[str, bool] = field(
        default_factory=lambda: {"trabalho": True, "estudo": False}
    )
    accepted: set[str] = field(default_factory=set)
    selected_file: str | None = None
    changed_files: list[tuple[str, str]] = field(default_factory=list)
    interactions: list[dict] = field(default_factory=list)
    session_start_head: str | None = None
    git_security: bool = True  # gitSecurity: verifica segredos antes do push


def persist_session(cwd: Path | str, harness_desc: str, interactions: list[dict]) -> None:
    """Salva as interações para regenerar relatórios via `controol report`."""
    try:
        path = Path(cwd) / ".controol" / "session.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"harness": harness_desc, "interactions": interactions},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:  # pragma: no cover
        pass
