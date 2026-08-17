"""Operações git usadas pelo Controol (diff, revisão, hooks, commits)."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

# Hook post-commit: grava o hash do commit em `.controol/pending_commits`
# (linha por linha). Simples, sem dependência de python no hook.
_HOOK = """#!/bin/sh
# Controol CLI — registra commit pendente para captura de memória.
# Gerenciado pelo Controol CLI (`controol init`).
HASH=$(git rev-parse HEAD)
FILE=".controol/pending_commits"
[ -d .controol ] && echo "$HASH" >> "$FILE"
exit 0
"""


def _git(cwd: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    return out.stdout if out.returncode == 0 else None


def repo_root(cwd: Path) -> Path | None:
    out = _git(cwd, "rev-parse", "--show-toplevel")
    return Path(out.strip()) if out and out.strip() else None


def is_repo(cwd: Path) -> bool:
    return repo_root(cwd) is not None


def head_commit(cwd: Path) -> str | None:
    out = _git(cwd, "rev-parse", "HEAD")
    return out.strip() if out else None


def last_commits(cwd: Path, n: int = 5) -> list[tuple[str, str]]:
    """Lista `(hash_curto, subject)` dos últimos n commits."""
    out = _git(cwd, "log", f"-{n}", "--format=%h%x01%s") or ""
    result = []
    for line in out.splitlines():
        if "\x01" in line:
            h, s = line.split("\x01", 1)
            result.append((h, s))
    return result


def commit_subject(cwd: Path, commit: str) -> str:
    """`hash_curto subject` de um commit específico."""
    out = _git(cwd, "log", "-1", "--format=%h %s", commit)
    return (out or "").strip()


def commits_since(cwd: Path, since: str) -> list[str]:
    """Hashes completos dos commits novos em `since..HEAD` (vazio se não há)."""
    out = _git(cwd, "log", "--format=%H", f"{since}..HEAD") or ""
    return [line.strip() for line in out.splitlines() if line.strip()]


def changed_files(cwd: Path) -> list[tuple[str, str]]:
    """Arquivos alterados vs HEAD: lista de `(status, path_rel)`.

    Usa `git status --porcelain` para incluir arquivos **untracked** (criados
    pelo harness e ainda não commitados), que `git diff HEAD` não mostra.
    Untracked vira status "A" (adição); renomeações são normalizadas.
    """
    out = _git(cwd, "status", "--porcelain") or ""
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        xy, path = line[:2], line[3:]
        if "->" in path:  # renomeação/cópia: "old -> new"
            path = path.split("->")[-1].strip()
        code = xy[0] if xy[0] != " " else xy[1]
        if code == "?":  # untracked
            code = "A"
        result.append((code, path))
    return result


_EXCLUDED_PREFIXES = (".controol/",)
_EXCLUDED_NAMES = ("controol-report.html", "controol-estudo.html")


def reviewable_changes(cwd: Path) -> list[tuple[str, str]]:
    """Alterações que o usuário deve revisar (sem os artefatos do próprio Controol).

    `git status --porcelain` também lista o que o Controol gera por conta
    própria (.controol/, relatórios HTML) — isso poluiria o painel de diff
    como "alterações" mesmo quando o opencode não mudou nada.
    """
    result = []
    for status, path in changed_files(cwd):
        if path == ".controol" or path.startswith(_EXCLUDED_PREFIXES):
            continue
        if path in _EXCLUDED_NAMES:
            continue
        result.append((status, path))
    return result


def file_at_head(cwd: Path, rel_path: str) -> str | None:
    """Conteúdo de um arquivo no HEAD (None se não existia)."""
    return _git(cwd, "show", f"HEAD:{rel_path}")


def file_diff_text(cwd: Path, rel_path: str, context: int = 3) -> str:
    """`git diff --unified=N HEAD -- <path>` (vazio se inalterado).

    Para arquivo **untracked** (não existe no HEAD), monta um diff com o
    conteúdo inteiro como adição, já que `git diff` não cobre untracked.
    """
    diff = (
        _git(cwd, "diff", f"--unified={context}", "--no-color", "HEAD", "--", rel_path) or ""
    )
    if diff:
        return diff
    fp = cwd / rel_path
    if fp.exists() and file_at_head(cwd, rel_path) is None:
        try:
            lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        head = f"diff --git a/{rel_path} b/{rel_path}\n"
        head += f"new file mode 100644\n--- /dev/null\n+++ b/{rel_path}\n"
        body = "\n".join(f"+{ln}" for ln in lines)
        return head + f"@@ -0,0 +1,{len(lines)} @@\n{body}"
    return diff


def reject_file(cwd: Path, rel_path: str) -> bool:
    """Descarta alterações do arquivo (restaura do HEAD).

    Arquivo untracked (novo) não tem versão no HEAD: "rejeitar" = remover.
    """
    if (cwd / rel_path).exists() and file_at_head(cwd, rel_path) is None:
        try:
            (cwd / rel_path).unlink()
            return True
        except OSError:
            return False
    res = subprocess.run(
        ["git", "checkout", "--", rel_path],
        cwd=str(cwd),
        capture_output=True,
    )
    return res.returncode == 0


def commit_patch(cwd: Path, commit: str = "HEAD") -> str:
    """Patch completo de um commit (sem mensagem)."""
    return _git(cwd, "show", "--format=", "--no-color", commit) or ""


def commit_stat(cwd: Path, commit: str = "HEAD") -> str:
    """--stat de um commit (arquivos + contagem de alterações)."""
    return _git(cwd, "show", "--stat", "--format=", commit) or ""


def commit_message(cwd: Path, commit: str = "HEAD") -> str:
    out = _git(cwd, "log", "-1", "--format=%h %s%n%n%b", commit)
    return (out or "").strip()


def install_hooks(cwd: Path) -> bool:
    """Instala o git hook post-commit do Controol. Retorna True se ok."""
    root = repo_root(cwd)
    if root is None:
        return False
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "post-commit"
    hook.write_text(_HOOK, encoding="utf-8")
    hook.chmod(0o755)
    return True


# ---------- operações assíncronas (add / commit / push / fetch / pull) ----------

async def _git_async(cwd: Path, *args: str) -> tuple[bool, str]:
    """Roda `git <args>` sem bloquear a TUI; retorna `(ok, stdout+stderr)`."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return False, "git não encontrado no PATH"
    out, err = await proc.communicate()
    text = (out or b"").decode(errors="replace").strip()
    text += (err or b"").decode(errors="replace").strip()
    return proc.returncode == 0, text


async def git_status(cwd: Path) -> tuple[bool, str]:
    """`git status --short --branch` — estado compacto da working tree."""
    return await _git_async(cwd, "status", "--short", "--branch")


async def git_add(cwd: Path) -> tuple[bool, str]:
    """`git add -A` — prepara todas as alterações (inclui untracked)."""
    return await _git_async(cwd, "add", "-A")


async def git_commit(cwd: Path, message: str) -> tuple[bool, str]:
    """`git commit -m <msg>` — commita o que está no stage."""
    return await _git_async(cwd, "commit", "-m", message)


async def git_push(cwd: Path) -> tuple[bool, str]:
    """`git push` para o upstream configurado."""
    return await _git_async(cwd, "push")


async def git_fetch(cwd: Path) -> tuple[bool, str]:
    """`git fetch` — baixa refs do remoto."""
    return await _git_async(cwd, "fetch")


async def git_pull(cwd: Path) -> tuple[bool, str]:
    """`git pull` — busca e integra o remoto no branch atual."""
    return await _git_async(cwd, "pull")


def staged_files(cwd: Path) -> list[str]:
    """Arquivos já no stage (`git diff --cached --name-only`)."""
    out = _git(cwd, "diff", "--cached", "--name-only") or ""
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def no_commits_yet(cwd: Path) -> bool:
    """True se o repo ainda não tem nenhum commit (HEAD inexistente)."""
    return head_commit(cwd) is None


def upstream_ref(cwd: Path) -> str | None:
    """Ref de upstream do branch atual (ex.: `origin/main`) ou None."""
    out = _git(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    return out.strip() if out else None


def outgoing_files(cwd: Path) -> list[str]:
    """Arquivos que o próximo `git push` vai enviar (rel_paths, sem duplicatas).

    Cobre dois casos: (a) há upstream → arquivos dos commits ainda não
    pusheados (`<upstream>..HEAD`) + arquivos no stage (vão para o próximo
    commit); (b) primeiro push (sem upstream) → todos os arquivos rastreados,
    pois tudo será enviado.
    """
    files: set[str] = set()
    files.update(staged_files(cwd))
    upstream = upstream_ref(cwd)
    if upstream is not None:
        out = _git(cwd, "log", "--name-only", "--format=", f"{upstream}..HEAD") or ""
    else:
        out = _git(cwd, "ls-files") or ""
    for line in out.splitlines():
        if line.strip():
            files.add(line.strip())
    return sorted(files)


def read_index_file(cwd: Path, rel_path: str) -> str | None:
    """Conteúdo de um arquivo no stage (`git show :<path>`)."""
    return _git(cwd, "show", f":{rel_path}")
