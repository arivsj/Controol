"""SecurityUseCase (gitSecurity): varre o que vai no push procurando segredos.

O scan roda **sem IA**: heurística de padrões de tokens de plataformas
(GitHub/OpenAI/AWS/…) + chaves nomeadas genéricas (`api_key=…`, `SENHA: …`).
Regras de negócio puras — sem nenhum import de Textual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ...git_tools import file_at_head, outgoing_files, read_index_file, staged_files

# Padrões de tokens de plataforma (formato conhecido → alta confiança)
_TOKEN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("token do GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("token do GitHub (fine-grained)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("chave da OpenAI", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("chave da Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_]{20,}\b")),
    ("chave de acesso AWS", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("chave da API do Google", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b")),
    ("token do Slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("chave privada", re.compile(r"-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
]

# Chave nomeada genérica (ex.: `api_key=`, `SENHA: …`) — exige um valor com
# pelo menos 8 chars para evitar falso positivo em palavras soltas.
_ASSIGN_PATTERN = re.compile(
    r"""(?i)(?:api[_-]?key|apikey|access[_-]?key|client[_-]?secret|private[_-]?key|secret|password|passwd|senha|auth[_-]?token|bearer[_-]?token)\s*[:=]\s*["']?([A-Za-z0-9_\-./+=]{8,})["']?"""
)

_FALSE_POSITIVE_VALUES = {
    "none", "null", "true", "false", "undefined", "placeholder",
    "example", "xxxxx", "changeme", "todo",
}


@dataclass
class SecretFinding:
    """Um possível segredo num arquivo que vai para o push."""

    path: str
    line: int
    kind: str
    match: str

    def snippet(self, max_len: int = 60) -> str:
        """Trecho encontrado, colapsado e truncado para exibição."""
        m = self.match.replace("\n", " ").strip()
        return m if len(m) <= max_len else m[: max_len - 1] + "…"


class SecurityUseCase:
    """gitSecurity: encontra possíveis segredos nos arquivos do próximo push."""

    def __init__(self, cwd: Path | str):
        self.cwd = Path(cwd)

    def scan(self) -> list[SecretFinding]:
        """Varre os arquivos que o push enviará e devolve os achados."""
        findings: list[SecretFinding] = []
        for rel in outgoing_files(self.cwd):
            content = self._read_outgoing(rel)
            if not content:
                continue
            findings.extend(self._scan_content(rel, content))
        return findings

    # ---------- helpers ----------
    def _read_outgoing(self, rel: str) -> str | None:
        """Conteúdo que vai no commit: do index (staged) ou, se já commitado,
        do HEAD."""
        if rel in staged_files(self.cwd):
            return read_index_file(self.cwd, rel)
        return file_at_head(self.cwd, rel)

    @classmethod
    def _scan_content(cls, rel: str, content: str) -> list[SecretFinding]:
        findings: list[SecretFinding] = []
        for kind, rx in _TOKEN_PATTERNS:
            for m in rx.finditer(content):
                line = content[: m.start()].count("\n") + 1
                findings.append(SecretFinding(rel, line, kind, m.group(0)))
        for m in _ASSIGN_PATTERN.finditer(content):
            if m.group(1).strip().lower() in _FALSE_POSITIVE_VALUES:
                continue
            line = content[: m.start()].count("\n") + 1
            findings.append(
                SecretFinding(rel, line, "chave nomeada genérica", m.group(0).strip())
            )
        return findings
