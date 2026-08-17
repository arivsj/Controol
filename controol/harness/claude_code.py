"""Integração com o Claude Code via `claude -p --output-format stream-json`."""
from __future__ import annotations

import asyncio
import json
import shutil
from typing import AsyncIterator

from .base import Event, Harness


class ClaudeCodeHarness(Harness):
    name = "claude"

    def _cmd(self, prompt: str) -> list[str]:
        cmd = ["claude", "-p", "--output-format", "stream-json"]
        if self.model:
            cmd += ["--model", self.model]
        if self.auto_approve:
            cmd += ["--dangerously-skip-permissions"]
        cmd.append(prompt)
        return cmd

    async def run(self, prompt: str) -> AsyncIterator[Event]:
        if not shutil.which("claude"):
            yield Event(
                "error",
                text="claude não encontrado no PATH. Veja: https://docs.anthropic.com/en/docs/claude-code",
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
                ev = self._parse(obj)
                if ev is not None:
                    yield ev
            await proc.wait()
        except asyncio.CancelledError:
            proc.terminate()
            raise

    @staticmethod
    def _parse(obj: dict) -> Event | None:
        t = obj.get("type")
        if t == "assistant":
            for block in (obj.get("message", {}) or {}).get("content", []):
                btype = block.get("type")
                if btype == "text":
                    return Event("agent_text", text=block.get("text", ""), data={"raw": obj})
                if btype == "tool_use":
                    name = str(block.get("name", ""))
                    inp = block.get("input", {}) or {}
                    file = inp.get("file_path") or inp.get("path")
                    ev = Event("tool", text=f"[{name}]", tool=name, data={"raw": obj})
                    if file:
                        ev.file = str(file)
                        ev.type = "file_touched"
                    return ev
            return None
        if t == "result":
            return Event(
                "step_done",
                text=obj.get("result") or "",
                data={"is_error": bool(obj.get("is_error")), "raw": obj},
            )
        return None
