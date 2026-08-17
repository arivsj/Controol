"""Integração com o opencode via `opencode run --format json`.

Schema real (fixado por teste em 2026-08): cada linha é um objeto JSON com
`type` em {step_start, text, tool_use, step_finish, error} e o payload em
`part`:
  - text:       part.text
  - tool_use:   part.tool, part.state.{status,input,metadata,output}
                * edit/write trazem part.state.input.filePath (absoluto) e
                  part.state.metadata.diff (unified diff) + additions/deletions
  - step_finish: part.reason ∈ {stop, tool-calls, ...}; "stop" = fim de turno
Para outras versões use `controol debug --raw "..."`.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import AsyncIterator

from .base import Event, Harness

# Ferramentas que mutam arquivos (alimentam a lista de alterados)
_MUTATING = ("edit", "write", "patch", "create", "replace")
_TOOLS_COM_ARQUIVO = _MUTATING + ("read", "webfetch")


def _session_id(ev: Event) -> str | None:
    """Extrai o sessionID de um evento step_done (para exportar a sessão)."""
    raw = ev.data.get("raw")
    if isinstance(raw, dict):
        part = raw.get("part") or {}
        if isinstance(part, dict):
            return part.get("sessionID")
    return None


def _rel_path(cwd: Path, path: str) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.relative_to(cwd))
        except ValueError:
            return str(p)
    return str(p)


class OpenCodeHarness(Harness):
    name = "opencode"

    def __init__(self, cwd: Path, **kwargs) -> None:
        super().__init__(cwd, **kwargs)
        self._model_detected = False

    def _detect_model(self, session_id: str) -> str | None:
        """Lê o modelo real usado pela sessão via `opencode export <id>`."""
        try:
            out = subprocess.run(
                ["opencode", "export", session_id],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(self.cwd),
            )
            data = json.loads(out.stdout or "{}")
            # o schema varia: `model` no topo ou em `info.model`
            model = data.get("model") or (data.get("info") or {}).get("model") or {}
            mid = model.get("id")
            if not mid:
                return None
            pid = model.get("providerID")
            return f"{pid}/{mid}" if pid and "/" not in mid else mid
        except Exception:  # pragma: no cover
            return None

    def probe_model(self) -> str | None:
        """Modelo sem rodar um prompt: config do opencode, depois última sessão."""
        return self._config_model() or self._last_session_model() or self.model

    def _config_model(self) -> str | None:
        """Modelo configurado no opencode (config global ou do projeto)."""
        for path in (
            Path.home() / ".config" / "opencode" / "opencode.json",
            Path.home() / ".config" / "opencode" / "opencode.jsonc",
            self.cwd / ".opencode.json",
        ):
            try:
                if not path.exists():
                    continue
                data = json.loads(path.read_text(errors="replace"))
                m = data.get("model")
                if isinstance(m, str) and m:
                    return m
            except Exception:  # pragma: no cover
                continue
        return None

    @staticmethod
    def _db_candidates() -> list[Path]:
        """Caminhos prováveis do banco de sessões do opencode (por SO)."""
        home = Path.home()
        appdata = os.environ.get("APPDATA", "")
        return [
            home / ".local" / "share" / "opencode" / "opencode.db",  # Linux
            home / "Library" / "Application Support" / "opencode" / "opencode.db",  # macOS
            Path(appdata) / "opencode" / "opencode.db",  # Windows
        ]

    def _last_session_model(self) -> str | None:
        """Modelo da sessão mais recente, lido direto do banco do opencode.

        Custo zero (sem rodar prompt): a tabela `session.model` guarda o JSON
        `{"id","providerID"}` do modelo usado. Serve de palpite para o footer
        até a detecção real via `opencode export` no primeiro run.
        """
        for path in self._db_candidates():
            try:
                if not path.exists():
                    continue
                con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                try:
                    row = con.execute(
                        "SELECT model FROM session "
                        "WHERE model IS NOT NULL AND model != '' "
                        "ORDER BY time_created DESC LIMIT 1"
                    ).fetchone()
                finally:
                    con.close()
                if not row or not row[0]:
                    continue
                m = json.loads(row[0])
                mid = m.get("id")
                if not mid:
                    continue
                pid = m.get("providerID")
                return f"{pid}/{mid}" if pid and "/" not in mid else mid
            except Exception:  # pragma: no cover
                continue
        return None

    def _cmd(self, prompt: str) -> list[str]:
        cmd = ["opencode", "run", "--format", "json"]
        if self.model:
            cmd += ["--model", self.model]
        if self.agent:
            cmd += ["--agent", self.agent]
        if self.auto_approve:
            cmd += ["--auto"]
        cmd.append(prompt)
        return cmd

    async def run(self, prompt: str) -> AsyncIterator[Event]:
        if not shutil.which("opencode"):
            yield Event(
                "error",
                text="opencode não encontrado no PATH. Instale com: curl -fsSL https://opencode.ai/install | bash",
            )
            return

        proc = await asyncio.create_subprocess_exec(
            *self._cmd(prompt),
            cwd=str(self.cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # linha JSON com diff grande não estoura o buffer (64 KiB padrão)
            limit=self.STREAM_LIMIT,
        )
        assert proc.stdout is not None
        try:
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    yield Event("agent_text", text=line, data={"raw": line})
                    continue
                ev = self._parse(obj, self.cwd)
                if ev is not None:
                    if ev.type == "step_done" and self.model is None and not self._model_detected:
                        # o modelo real não vem nos eventos; o export da sessão
                        # revela `model.id`/`providerID` — detecta 1x por app
                        self._model_detected = True
                        sid = _session_id(ev)
                        if sid:
                            detected = await asyncio.to_thread(self._detect_model, sid)
                            if detected:
                                self.model = detected
                    yield ev
            await proc.wait()
        except asyncio.CancelledError:
            proc.terminate()
            raise

    @staticmethod
    def _parse(obj: dict, cwd: Path) -> Event | None:
        t = obj.get("type") or ""
        part = obj.get("part") or {}
        ptype = part.get("type") if isinstance(part, dict) else None

        # Erros
        if t == "error" or "error" in obj:
            err = obj.get("error", obj)
            if isinstance(err, dict):
                msg = (
                    err.get("message")
                    or (err.get("data", {}) or {}).get("message")
                    or str(err)
                )
            else:
                msg = str(err)
            return Event("error", text=str(msg), data={"raw": obj})

        # Fim de turno real: step_finish com reason "stop"
        if t == "step_finish" and isinstance(part, dict):
            if part.get("reason") == "stop":
                return Event(
                    "step_done",
                    data={"tokens": part.get("tokens"), "raw": obj},
                )
            return None

        # Texto do agente
        if ptype == "text":
            return Event("agent_text", text=part.get("text", ""), data={"raw": obj})

        # Chamada de ferramenta
        if ptype == "tool":
            tool = str(part.get("tool", ""))
            state = part.get("state") or {}
            status = state.get("status") if isinstance(state, dict) else None
            input_ = (state.get("input") or {}) if isinstance(state, dict) else {}
            metadata = (
                (state.get("metadata") or {}) if isinstance(state, dict) else {}
            )
            if not isinstance(metadata, dict):
                metadata = {}

            # rótulo legível
            title = metadata.get("title") or (
                input_.get("command") if isinstance(input_, dict) else None
            )
            text = f"[{tool}] {title or ''}".rstrip()

            ev = Event(
                "tool",
                text=text,
                tool=tool,
                data={
                    "status": status,
                    "input": input_,
                    "metadata": metadata,
                    "raw": obj,
                },
            )

            # Arquivo (quando houver)
            if tool in _TOOLS_COM_ARQUIVO:
                f = input_.get("filePath") if isinstance(input_, dict) else None
                if f:
                    ev.file = _rel_path(cwd, str(f))
                    if tool in _MUTATING:
                        ev.type = "file_touched"
                        diff = metadata.get("diff") or (
                            (metadata.get("filediff") or {}).get("patch")
                        )
                        if diff:
                            ev.data["diff"] = diff
                        if metadata.get("additions") is not None:
                            ev.data["additions"] = metadata["additions"]
                        if metadata.get("deletions") is not None:
                            ev.data["deletions"] = metadata["deletions"]
            return ev

        # step_start e outros: ignorados para não poluir o log
        return None
