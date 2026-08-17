"""Configuração do Controol: `.controol/config.json` dentro do repositório."""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CONFIG: dict = {
    "harness": "opencode",   # opencode | claude
    "model": None,           # ex.: anthropic/claude-sonnet-4-5 (opencode) ou nome do modelo
    "agent": None,           # ex.: plan (opencode)
    "auto_approve": False,   # --auto no opencode (cuidado: auto-aprova permissões)
    "language": "pt",        # idioma da UI e do conteúdo gerado
    "git_security": True,    # varre segredos nos arquivos do push antes de enviar
    "memory_dir": ".controol",
}


class Config:
    """Carrega/grava a configuração em `.controol/config.json` no cwd."""

    def __init__(self, root: Path):
        self.root = root
        self.path = root / ".controol" / "config.json"
        self._data: dict = dict(DEFAULT_CONFIG)

    @classmethod
    def load(cls, cwd: Path | None = None) -> "Config":
        cfg = cls(cwd or Path.cwd())
        if cfg.path.exists():
            try:
                cfg._data.update(json.loads(cfg.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        return cfg

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()
