"""GitUseCase: regras das operações git da barra + feedback formatado."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...git_tools import (
    changed_files,
    git_add,
    git_commit,
    git_fetch,
    git_pull,
    git_push,
    git_status,
    staged_files,
)

_STYLE_OK = "bold #00f5d4"
_STYLE_WARN = "bold #ffb703"
_STYLE_ERR = "bold #ff2e63"
_STYLE_DIM = "dim #e0e6ed"
_STYLE_FAINT = "dim #8a8f9e"


@dataclass
class GitResult:
    """Resultado de uma operação git: sucesso + linhas formatadas p/ o card."""

    ok: bool
    lines: list[tuple[str, str]] = field(default_factory=list)


class GitUseCase:
    """Dispatch das ações da barra git + formatação de feedback.

    As operações assíncronas ficam em `git_tools.py`; aqui moram as regras
    (commit exige stage, parse do status, feedback "já atualizado", …).
    """

    def __init__(self, cwd: Path | str):
        self.cwd = Path(cwd)

    async def execute(self, action: str, message: str | None = None) -> GitResult:
        if action == "status":
            ok, out = await git_status(self.cwd)
            return GitResult(ok, self._status_lines(ok, out))
        if action == "add":
            ok, out = await git_add(self.cwd)
            if ok:
                n = len(staged_files(self.cwd))
                return GitResult(ok, [(f"✓ add: {n} arquivo(s) no stage", _STYLE_OK)])
            return GitResult(ok, [(f"⚠ add: {out}", _STYLE_WARN)])
        if action == "commit":
            ok, out = await git_commit(self.cwd, message or "")
            return GitResult(ok, self._commit_lines(ok, out))
        if action == "push":
            ok, out = await git_push(self.cwd)
            return GitResult(ok, self._push_lines(ok, out))
        if action == "fetch":
            ok, out = await git_fetch(self.cwd)
            return GitResult(ok, self._fetch_lines(ok, out))
        if action == "pull":
            ok, out = await git_pull(self.cwd)
            return GitResult(ok, self._pull_lines(ok, out))
        return GitResult(False, [])

    def has_stage(self) -> bool:
        """Existe algo no stage (regra do commit exigir stage)."""
        return bool(staged_files(self.cwd))

    def has_changes(self) -> bool:
        """A working tree tem alguma alteração (para a mensagem do commit)."""
        return bool(changed_files(self.cwd))

    # ---------- formatação de feedback ----------
    def _status_lines(self, ok: bool, out: str) -> list[tuple[str, str]]:
        if not ok:
            return [(f"⚠ status: {out}", _STYLE_ERR)]
        lines = [ln for ln in out.splitlines() if ln.strip()]
        if len(lines) <= 1:
            return [("✓ status: working tree limpa", _STYLE_OK)]
        result = [(f"✓ status: {len(lines) - 1} item(ns) — {lines[0]}", _STYLE_OK)]
        result += [(f"  {ln}", _STYLE_DIM) for ln in lines[1:13]]
        if len(lines) > 13:
            result.append((f"  … +{len(lines) - 13} linha(s)", _STYLE_FAINT))
        return result

    def _commit_lines(self, ok: bool, out: str) -> list[tuple[str, str]]:
        if ok:
            first = out.splitlines()[0] if out else "commit ok"
            return [(f"✓ {first}", _STYLE_OK)]
        low = out.lower()
        if "nothing to commit" in low or "no changes added" in low:
            return [("⚠ commit: nada no stage — rode + add antes", _STYLE_WARN)]
        return [(f"⚠ commit: {out}", _STYLE_ERR)]

    def _push_lines(self, ok: bool, out: str) -> list[tuple[str, str]]:
        low = out.lower()
        if ok:
            msg = (
                "✓ push: já atualizado"
                if "up to date" in low or "up-to-date" in low
                else "✓ push concluído"
            )
            return [(msg, _STYLE_OK)]
        if "no upstream" in low:
            return [
                ("⚠ push: sem upstream — rode: git push -u origin <branch>", _STYLE_WARN)
            ]
        return [(f"⚠ push: {out}", _STYLE_ERR)]

    def _fetch_lines(self, ok: bool, out: str) -> list[tuple[str, str]]:
        if ok:
            low = out.lower()
            msg = "✓ fetch: já atualizado" if "up to date" in low else "✓ fetch concluído"
            return [(msg, _STYLE_OK)]
        return [(f"⚠ fetch: {out}", _STYLE_ERR)]

    def _pull_lines(self, ok: bool, out: str) -> list[tuple[str, str]]:
        if ok:
            low = out.lower()
            msg = "✓ pull: já atualizado" if "up to date" in low else "✓ pull concluído"
            return [(msg, _STYLE_OK)]
        return [(f"⚠ pull: {out}", _STYLE_ERR)]
