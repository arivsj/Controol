"""Testes do SecurityUseCase (gitSecurity): scan de segredos no push."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from controol.application.use_cases import SecurityUseCase


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "banco.py").write_text("class Conta:\n    pass\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path


def _scan(repo: Path):
    return SecurityUseCase(repo).scan()


def test_sem_segredo_nao_acha_nada(repo: Path):
    (repo / "mod.py").write_text("X = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert _scan(repo) == []


def test_token_do_github_staged_e_detectado(repo: Path):
    (repo / "seg.py").write_text("TOKEN = 'ghp_1234567890abcdefghij'\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    findings = _scan(repo)
    assert findings, "esperava ao menos um achado"
    assert any(f.kind == "token do GitHub" for f in findings)
    assert any(f.path == "seg.py" and f.line == 1 for f in findings)


def test_chave_privada_commitada_e_detectada(repo: Path):
    (repo / "id_rsa").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nabcdef\n-----END OPENSSH PRIVATE KEY-----\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "chave"], cwd=repo, check=True)
    assert any(f.kind == "chave privada" for f in _scan(repo))


def test_chave_nomeada_generica_detectada(repo: Path):
    (repo / "app.py").write_text("API_KEY = 'abcd1234-efgh-5678'\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert any(f.kind == "chave nomeada genérica" for f in _scan(repo))


def test_placeholder_nao_e_falso_positivo(repo: Path):
    (repo / "cfg.py").write_text("secret = 'placeholder'\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert _scan(repo) == []


def test_valor_nulo_nao_e_falso_positivo(repo: Path):
    (repo / "cfg.py").write_text("api_key = None\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert _scan(repo) == []


def test_sem_repo_retorna_vazio(tmp_path: Path):
    assert SecurityUseCase(tmp_path).scan() == []


def test_snippet_trunca_match_longo():
    long = "ghp_" + "a" * 70
    findings = SecurityUseCase._scan_content("x.py", f"TOKEN='{long}'\n")
    assert findings
    snip = findings[0].snippet()
    assert snip.endswith("…") and len(snip) == 60


def test_snippet_colapsa_novas_linhas():
    from controol.application.use_cases import SecretFinding

    f = SecretFinding("x.py", 1, "teste", "aaaa\nbbbb")
    assert f.snippet() == "aaaa bbbb"
