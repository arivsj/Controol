"""Testes das operações git (incluindo arquivos untracked do harness)."""
from __future__ import annotations

from pathlib import Path

import pytest

from controol.git_tools import (
    changed_files,
    file_diff_text,
    git_add,
    git_commit,
    git_status,
    reject_file,
    reviewable_changes,
    staged_files,
)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("linha\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_untracked_aparece_como_adicao(repo: Path):
    (repo / "banco.py").write_text("class Conta:\n    pass\n")
    files = changed_files(repo)
    assert ("A", "banco.py") in files
    diff = file_diff_text(repo, "banco.py")
    assert "+class Conta:" in diff and "+    pass" in diff
    assert "new file mode" in diff


def test_modificado_rastreado(repo: Path):
    (repo / "a.txt").write_text("linha\nmudanca\n")
    files = changed_files(repo)
    assert ("M", "a.txt") in files
    assert "+mudanca" in file_diff_text(repo, "a.txt")


def test_reject_remove_untracked(repo: Path):
    (repo / "banco.py").write_text("class Conta:\n    pass\n")
    assert reject_file(repo, "banco.py") is True
    assert not (repo / "banco.py").exists()


def test_reject_restaura_rastreado(repo: Path):
    (repo / "a.txt").write_text("linha\nmudanca\n")
    assert reject_file(repo, "a.txt") is True
    assert (repo / "a.txt").read_text() == "linha\n"


def test_reviewable_filtra_artefatos_internos(repo: Path):
    """`.controol/` e relatórios gerados não contam como alteração a revisar."""
    (repo / ".controol").mkdir(exist_ok=True)
    (repo / ".controol" / "session.json").write_text("{}")
    (repo / "controol-report.html").write_text("<html></html>")
    (repo / "codigo.py").write_text("x = 1\n")
    assert changed_files(repo)  # os 3 aparecem no status git
    paths = {p for _, p in reviewable_changes(repo)}
    assert paths == {"codigo.py"}


# ---------- operações assíncronas (barra git da TUI) ----------

async def test_git_status_mostra_estado_curto(repo: Path):
    (repo / "a.txt").write_text("linha\nmudou\n")
    ok, out = await git_status(repo)
    assert ok is True
    assert "a.txt" in out
    assert "##" in out  # linha do branch


async def test_git_add_prepara_untracked(repo: Path):
    (repo / "novo.txt").write_text("conteudo\n")
    ok, _ = await git_add(repo)
    assert ok is True
    assert "novo.txt" in staged_files(repo)


async def test_git_commit_limpa_working_tree(repo: Path):
    (repo / "a.txt").write_text("linha\nalterada\n")
    await git_add(repo)
    ok, out = await git_commit(repo, "fix: altera a.txt")
    assert ok is True
    assert "a.txt" in out
    assert changed_files(repo) == []  # commit feito → sem alterações pendentes


async def test_git_commit_sem_stage_falha_amigavel(repo: Path):
    ok, out = await git_commit(repo, "sem stage")
    assert ok is False
    assert "nothing to commit" in out.lower() or "no changes added" in out.lower()
