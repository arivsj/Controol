"""Factory de harness a partir da configuração."""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from .base import Harness
from .claude_code import ClaudeCodeHarness
from .opencode import OpenCodeHarness


def create_harness(config: Config, cwd: Path | None = None) -> Harness:
    name = (config.get("harness") or "opencode").lower()
    cwd = cwd or config.root
    if name == "claude":
        return ClaudeCodeHarness(
            cwd,
            model=config.get("model"),
            agent=config.get("agent"),
            auto_approve=bool(config.get("auto_approve")),
        )
    return OpenCodeHarness(
        cwd,
        model=config.get("model"),
        agent=config.get("agent"),
        auto_approve=bool(config.get("auto_approve")),
    )
