"""Testes de fumaça da TUI (headless, via Textual pilot)."""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, Input

from controol.config import Config
from controol.tui.app import ControolApp
from controol.tui.widgets import (
    AgentSummary,
    Banner,
    CommitModal,
    DiffPanel,
    GitBar,
    MenuModal,
    ModesPanel,
    PromptInput,
    SecurityAlertModal,
    StatusFooter,
)
from controol.tui.widgets.memory_modal import MemoryModal


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "banco.py").write_text("class Conta:\n    pass\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    # altera um arquivo para aparecer na lista de mudanças
    (tmp_path / "banco.py").write_text("class Conta:\n    saldo = 0\n")
    return tmp_path


def _make_app(repo: Path) -> ControolApp:
    cfg = Config.load(repo)
    return ControolApp(cfg, repo)


async def test_app_monta_e_lista_arquivo_alterado(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.changed_files == [("M", "banco.py")]
        panel = app.query_one(ModesPanel)
        ol = panel.query_one("#file-list")
        assert ol.option_count == 1
        assert app.query_one(PromptInput) is not None
        assert app.query_one(Banner) is not None  # cabeçalho em caixa (bashtop)
        # com um único arquivo, os botões < > ficam desabilitados
        dp = app.query_one(DiffPanel)
        assert dp.query_one("#btn-prev-file", Button).disabled
        assert dp.query_one("#btn-next-file", Button).disabled
        await pilot.pause()


async def test_toggle_modes(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        # padrão: trabalho e memória ligados
        assert app.modes["trabalho"] is True
        assert app.modes["estudo"] is False
        await pilot.press("ctrl+e")
        await pilot.pause()
        assert app.modes["estudo"] is True
        cb = app.query_one("#mode-estudo", Checkbox)
        assert cb.value is True
        # alternativa: clicar no checkbox
        await pilot.click("#mode-estudo")
        await pilot.pause()
        assert app.modes["estudo"] is False


async def test_accept_selected(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.selected_file == "banco.py"
        await pilot.press("ctrl+a")
        await pilot.pause()
        assert "banco.py" in app.accepted


async def test_reject_restaura_arquivo(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+x")
        await pilot.pause()
        content = (repo / "banco.py").read_text()
        assert "saldo = 0" not in content  # restaurado do HEAD


async def test_nav_diff_alterna_entre_arquivos(repo: Path):
    """Os botões < > do card de diff alternam entre os arquivos alterados."""
    (repo / "cliente.py").write_text("class Cliente:\n    saldo = 0\n")
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        order = [p for _, p in app.changed_files]
        assert len(order) == 2  # banco.py + cliente.py
        dp = app.query_one(DiffPanel)
        prev = dp.query_one("#btn-prev-file", Button)
        nxt = dp.query_one("#btn-next-file", Button)
        assert not prev.disabled
        assert not nxt.disabled
        # ">" avança na lista (com volta no fim)
        nxt.press()
        await pilot.pause()
        assert app.selected_file == order[1]
        nxt.press()
        await pilot.pause()
        assert app.selected_file == order[0]  # wrap-around
        # "<" volta na lista
        prev.press()
        await pilot.pause()
        assert app.selected_file == order[1]
        # o título do diff mostra o arquivo navegado
        title = str(dp.query_one("#diff-title").render())
        assert order[1] in title


async def test_accept_all(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        # um arquivo rastreado modificado + um untracked
        (repo / "outro.py").write_text("y = 1\n")
        app.refresh_files()
        await pilot.pause()
        assert len(app.changed_files) == 2
        assert app.accepted == set()
        actions = app.query_one(DiffPanel).query_one("#diff-actions")
        assert actions.display is True  # há aceite pendente
        from controol.tui.widgets import AcceptAll

        app.on_accept_all(AcceptAll())
        await pilot.pause()
        assert app.accepted == {p for _, p in app.changed_files}
        assert actions.display is False  # nada pendente → botões somem


async def test_memoria_sempre_vigia_sem_toggle(repo: Path):
    """Memória não é modo: com commit pendente o modal abre já na montagem."""
    from controol.memory.store import MemoryStore

    # simula o hook: registra um commit pendente
    import subprocess

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    store = MemoryStore(repo)
    store.ensure()
    store.add_pending(head)

    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)  # deixa o push_screen assíncrono completar
        assert any(isinstance(s, MemoryModal) for s in app.screen_stack)
        modal = app.screen_stack[-1]
        assert isinstance(modal, MemoryModal)
        # "Agora não" fecha o modal (dismiss direto: evita flakiness de clique)
        await modal.dismiss(None)
        await pilot.pause(0.5)
        assert not any(isinstance(s, MemoryModal) for s in app.screen_stack)


async def test_gitbar_renderiza(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        bar = app.query_one(GitBar)
        for btn_id in (
            "git-status", "git-add", "git-commit", "git-push", "git-fetch", "git-pull",
        ):
            assert bar.query_one(f"#{btn_id}") is not None
        await pilot.pause()


async def test_aceitar_rejeitar_visiveis_com_alteracoes(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.changed_files  # fixture deixa banco.py alterado
        actions = app.query_one(DiffPanel).query_one("#diff-actions")
        assert actions.display is True


async def test_aceitar_rejeitar_escondidos_sem_alteracoes(repo: Path):
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "limpo"], cwd=repo, check=True)
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.changed_files == []
        actions = app.query_one(DiffPanel).query_one("#diff-actions")
        assert actions.display is False  # display:none → sem espaço nem render


async def test_falha_do_agente_mostra_aceite_pendente(repo: Path):
    """Run que falha no meio não pode esconder o aceite: o painel reflete o git
    real na hora (sem esperar a próxima interação)."""
    import subprocess

    from controol.harness.base import Event, Harness

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "limpo"], cwd=repo, check=True)

    class _CrashHarness(Harness):
        name = "fake"

        async def run(self, prompt):
            (self.cwd / "banco.py").write_text("class Conta:\n    saldo = 1\n")
            yield Event("agent_text", text="vou alterar")
            raise RuntimeError("falha simulada no meio do run")

    app = _make_app(repo)
    app.harness = _CrashHarness(repo)
    app.run_uc.harness = app.harness
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.changed_files == []  # partiu de árvore limpa
        app._enqueue_or_run("mude algo")
        await pilot.pause(1.0)  # run falha → except → refresh_files
        assert app.changed_files == [("M", "banco.py")]
        actions = app.query_one(DiffPanel).query_one("#diff-actions")
        assert actions.display is True  # aceite pendente visível já na falha


async def test_artefatos_internos_nao_poluem_revisao(repo: Path):
    """`.controol/`/relatórios gerados pelo Controol não viram botões de revisão."""
    (repo / ".controol").mkdir(exist_ok=True)
    (repo / ".controol" / "session.json").write_text("{}")
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert ("M", "banco.py") in app.changed_files
        assert all(not p.startswith(".controol") for _, p in app.changed_files)


async def test_modos_mesmo_tamanho_e_contorno_verde(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        trab = app.query_one("#mode-trabalho", Checkbox)
        estu = app.query_one("#mode-estudo", Checkbox)
        assert trab.size.width == estu.size.width  # mesmo tamanho horizontal
        assert "selected" in trab.classes  # verde = selecionado
        assert "selected" not in estu.classes
        await pilot.press("ctrl+e")
        await pilot.pause()
        # modos são toggles independentes: ambos podem estar ativos
        assert "selected" in estu.classes
        assert "selected" in trab.classes
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert "selected" not in trab.classes
        assert "selected" in estu.classes


async def test_commit_abre_modal_e_commita(repo: Path):
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)  # precisa de stage
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#git-commit")
        await pilot.pause(0.2)  # deixa o push_screen completar
        assert any(isinstance(s, CommitModal) for s in app.screen_stack)
        modal = app.screen_stack[-1]
        assert isinstance(modal, CommitModal)
        modal.query_one("#commit-input", Input).value = "fix: mensagem do modal"
        modal.query_one("#btn-commit-ok").press()
        await pilot.pause(0.5)  # worker do git commit termina
        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        assert subject == "fix: mensagem do modal"
        assert app.changed_files == []  # working tree limpo após commit


async def test_commit_pela_tui_dispara_memoria(repo: Path):
    """Comitar pela barra git dispara a pergunta de memória na hora."""
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)  # precisa de stage
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#git-commit")
        await pilot.pause(0.2)
        modal = app.screen_stack[-1]
        assert isinstance(modal, CommitModal)
        modal.query_one("#commit-input", Input).value = "feat: muda banco"
        modal.query_one("#btn-commit-ok").press()
        await pilot.pause(0.6)  # worker do commit termina + _check_memory
        # memória sempre vigia commits: modal de salvar memória deve abrir
        assert any(isinstance(s, MemoryModal) for s in app.screen_stack)


async def test_footer_mostra_modelo_contexto_tokens(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        fw = app.query_one(StatusFooter)
        assert fw.id == "status-footer"
        content = str(fw.query_one("#footer-content").render())
        for label in ("MODELO", "CONTEXTO", "TOKENS"):
            assert label in content
        # dados atualizam conforme o harness reporta tokens (total inclui cache)
        app.tokens_input = 1234
        app.tokens_total = 1666
        app._update_footer()
        content = str(fw.query_one("#footer-content").render())
        assert "1.2k" in content  # entrada formatada
        assert "1.7k" in content  # total = 1666
        # botão Clear fica no final do footer
        assert fw.query_one("#btn-clear") is not None


async def test_detect_model_usa_info_do_export(monkeypatch, repo: Path):
    """O modelo real vem de `opencode export` → `info.model`."""
    import subprocess
    from pathlib import Path

    from controol.config import Config
    from controol.harness.opencode import OpenCodeHarness

    class _Out:
        returncode = 0
        stdout = '{"info": {"model": {"id": "deepseek-v4-flash", "providerID": "deepseek"}}, "messages": []}'
        stderr = ""

    def _fake_run(cmd, **kw):
        assert cmd[0] == "opencode" and cmd[1] == "export"
        return _Out()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    h = OpenCodeHarness(repo)
    assert h._detect_model("ses_x") == "deepseek/deepseek-v4-flash"


async def test_probe_model_le_ultima_sessao_do_banco(monkeypatch, repo: Path):
    """O probe do footer lê a última sessão do banco (sem rodar prompt)."""
    import json
    import sqlite3

    from controol.harness.opencode import OpenCodeHarness

    db = repo / "fake.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE session (model TEXT, time_created INTEGER)")
    con.execute(
        "INSERT INTO session VALUES (?, ?)",
        (json.dumps({"id": "deepseek-v4-flash", "providerID": "deepseek"}), 100),
    )
    con.commit()
    con.close()

    h = OpenCodeHarness(repo)
    monkeypatch.setattr(h, "_db_candidates", lambda: [db])
    monkeypatch.setattr(h, "_config_model", lambda: None)  # isola o caminho do banco
    assert h.probe_model() == "deepseek/deepseek-v4-flash"


async def test_harness_linha_grande_nao_estoura_buffer(repo: Path, monkeypatch):
    """Linha JSON do opencode > 64 KiB (diff grande) não estoura o buffer padrão
    do StreamReader — senão vira asyncio.LimitOverrunError e derruba o run."""
    import asyncio
    import json
    import shutil

    from controol.harness.opencode import OpenCodeHarness

    calls: dict = {}

    class _Proc:
        returncode = 0

        def __init__(self, reader: asyncio.StreamReader) -> None:
            self.stdout = reader

        async def wait(self) -> int:
            return self.returncode

    async def _fake_subprocess(*args, **kw):
        calls["limit"] = kw.get("limit")
        reader = asyncio.StreamReader(limit=OpenCodeHarness.STREAM_LIMIT)
        payload = json.dumps(
            {"type": "text", "part": {"type": "text", "text": "x" * 70_000}}
        )
        reader.feed_data((payload + "\n").encode())
        reader.feed_eof()
        return _Proc(reader)

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/opencode")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_subprocess)

    h = OpenCodeHarness(repo)
    events = [e async for e in h.run("altere algo")]
    assert calls["limit"] and calls["limit"] > 65536  # default do asyncio
    assert events and events[0].type == "agent_text"
    assert len(events[0].text) == 70_000


async def test_tokens_from_data_usa_total(repo: Path):
    from controol.tui.app import ControolApp

    i, t = ControolApp._tokens_from_data(
        {"tokens": {"input": 65, "output": 2, "total": 10179,
                    "cache": {"read": 10112}}}
    )
    assert i == 65
    assert t == 10179  # total (não só input+output = 67)


async def test_clear_btn_zera_contexto(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.tokens_input = 5000
        app.tokens_total = 9000
        app.interactions = [{"prompt": "oi"}]
        app.last_reply = "resposta"
        app.agent_response = "resposta completa"
        app._queue = ["pedido 1"]
        app._update_footer()
        await pilot.click("#btn-clear")
        await pilot.pause()
        assert app.tokens_input == 0
        assert app.tokens_total == 0
        assert app.interactions == []
        assert app.last_reply == ""
        assert app.agent_response == ""
        assert app._queue == []
        # footer reflete a limpeza
        content = str(app.query_one(StatusFooter).query_one("#footer-content").render())
        assert "0" in content


async def test_agent_summary_mostra_resposta_do_agente(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        panel = app.query_one(AgentSummary)
        assert "RESPOSTA DO AGENTE" in str(
            panel.query_one(".panel-title").render()
        )
        # sem resposta ainda → placeholder (o log de boas-vindas do on_mount
        # agora vive no card de execução; limpamos para ver o estado vazio)
        panel.clear()
        await pilot.pause()
        assert "—" in str(panel.query_one("#summary-content").render())
        # após um run, o app preenche com a explicação + arquivos
        app.last_reply = "Criei a função saldo() no banco.py."
        app.changed_files = [("M", "banco.py")]
        app._on_run_done({"prompt": "x", "files": {}, "explanation": ""})
        await pilot.pause()
        content = str(panel.query_one("#summary-content").render())
        assert "saldo()" in content
        assert "1 arquivo(s)" in content


async def test_prompt_entra_na_fila_quando_agente_ocupado(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app._busy = True  # agente trabalhando
        app.set_loading(True)  # placeholder avisa que novos pedidos vão pra fila
        app._enqueue_or_run("pedido dois")
        await pilot.pause()
        assert app._queue == ["pedido dois"]
        q = app.query_one(PromptInput).query_one("#queue-list")
        assert q.display is True
        assert "pedido dois" in str(q.render())
        # o input continua digitável durante o trabalho (novo pedido → fila)
        inp = app.query_one("#prompt-field", Input)
        assert inp.disabled is False
        assert "fila" in inp.placeholder


async def test_agent_summary_anima_quando_trabalhando(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        panel = app.query_one(AgentSummary)
        panel.start_working("edit banco.py")
        await pilot.pause()
        content = str(panel.query_one("#summary-content").render())
        assert "construindo" in content  # animação de fábrica ligada
        assert "banco.py" in content     # ação corrente na animação
        # resposta chegando entra por baixo da animação
        panel.append_reply("fiz o saldo()")
        await pilot.pause()
        assert "saldo()" in str(panel.query_one("#summary-content").render())
        # fim do run: animação para e mostra o resultado final
        panel.set_summary("fim", "1 arquivo(s) alterado(s): banco.py")
        await pilot.pause()
        content = str(panel.query_one("#summary-content").render())
        assert "fim" in content
        assert "construindo" not in content


async def test_prompt_painel_visivel_e_digitavel(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        inp = app.query_one("#prompt-field", Input)
        # regressão: height:1 + border deixava a área de conteúdo em 0
        # e o texto digitado ficava invisível (input parecia "morto")
        assert inp.size.height >= 1
        pi = app.query_one(PromptInput)
        assert "FALE COM O AGENTE" in str(pi.query_one(".panel-title").render())
        # digitação funciona e aparece no campo
        await pilot.press("o", "l", "a")
        await pilot.pause()
        assert inp.value == "ola"


async def test_foco_inicial_ja_no_campo_do_prompt(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.focused is app.query_one("#prompt-field", Input)


async def test_foco_volta_ao_prompt_apos_commit(repo: Path):
    """Após commit pela TUI, a memória abre (vigia commits sempre) e toma o foco;
    dispensá-la devolve o foco ao prompt."""
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#git-commit")
        await pilot.pause(0.2)
        modal = app.screen_stack[-1]
        assert isinstance(modal, CommitModal)
        modal.query_one("#commit-input", Input).value = "fix: foco"
        modal.query_one("#btn-commit-ok").press()
        await pilot.pause(0.6)  # worker do commit termina + _check_memory
        # memória vigia commits sempre → modal aberto e com o foco
        memory = next(s for s in app.screen_stack if isinstance(s, MemoryModal))
        assert app.focused is not app.query_one("#prompt-field", Input)
        memory.query_one("#cat-later").press()  # "Agora não"
        await pilot.pause(0.3)  # modal fecha; foco restaura para o prompt
        assert app.focused is app.query_one("#prompt-field", Input)


async def test_foco_volta_ao_prompt_ao_cancelar_commit(repo: Path):
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#git-commit")
        await pilot.pause(0.2)
        modal = app.screen_stack[-1]
        assert isinstance(modal, CommitModal)
        await modal.dismiss(None)  # cancela sem mensagem
        await pilot.pause(0.2)
        assert app.focused is app.query_one("#prompt-field", Input)


# ---------- menu do header (☰) + gitSecurity ----------

async def test_menu_abre_e_alterna_gitsecurity(repo: Path):
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.session.git_security is True  # padrão: ligado
        assert app.query_one("#btn-menu") is not None  # botão no canto direito
        await pilot.click("#btn-menu")
        await pilot.pause(0.2)
        assert any(isinstance(s, MenuModal) for s in app.screen_stack)
        modal = app.screen_stack[-1]
        assert isinstance(modal, MenuModal)
        cb = modal.query_one("#menu-gitsecurity", Checkbox)
        assert cb.value is True
        cb.value = False  # desliga
        modal.query_one("#btn-menu-close").press()
        await pilot.pause(0.2)
        assert app.session.git_security is False
        assert app.config.get("git_security") is False  # persistido


async def test_gitsecurity_desligado_pula_scan_no_push(repo: Path, monkeypatch):
    import controol.tui.app as appmod

    calls: list[str] = []

    async def _fake_git(self, action, message=None):
        calls.append(action)
        from controol.application.use_cases import GitResult

        return GitResult(ok=True)

    monkeypatch.setattr(appmod.ControolApp, "_run_git", _fake_git)
    app = _make_app(repo)
    app.session.git_security = False
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#git-push")
        await pilot.pause(0.3)
        assert calls == ["push"]  # foi direto, sem scan/alert
        assert not any(isinstance(s, SecurityAlertModal) for s in app.screen_stack)


async def test_push_com_segredo_abre_alerta_e_ignorar_continua(repo: Path, monkeypatch):
    import subprocess

    import controol.tui.app as appmod

    (repo / "seg.py").write_text("TOKEN = 'ghp_1234567890abcdefghij'\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    calls: list[str] = []

    async def _fake_git(self, action, message=None):
        calls.append(action)
        from controol.application.use_cases import GitResult

        return GitResult(ok=True)

    monkeypatch.setattr(appmod.ControolApp, "_run_git", _fake_git)
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#git-push")
        await pilot.pause(0.3)  # scan (to_thread) + push_screen
        assert any(isinstance(s, SecurityAlertModal) for s in app.screen_stack)
        modal = app.screen_stack[-1]
        assert isinstance(modal, SecurityAlertModal)
        modal.query_one("#btn-sec-ignore").press()
        await pilot.pause(0.3)
        assert calls == ["push"]  # ignorou e continuou o push


async def test_push_com_segredo_aceitar_vira_prompt_do_agente(repo: Path, monkeypatch):
    import subprocess

    import controol.tui.app as appmod

    (repo / "seg.py").write_text("TOKEN = 'ghp_1234567890abcdefghij'\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    queued: list[str] = []
    calls: list[str] = []

    async def _fake_git(self, action, message=None):
        calls.append(action)
        from controol.application.use_cases import GitResult

        return GitResult(ok=True)

    def _fake_enqueue(self, prompt):
        queued.append(prompt)  # não roda o harness de verdade

    monkeypatch.setattr(appmod.ControolApp, "_run_git", _fake_git)
    monkeypatch.setattr(appmod.ControolApp, "_enqueue_or_run", _fake_enqueue)
    app = _make_app(repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#git-push")
        await pilot.pause(0.3)
        modal = app.screen_stack[-1]
        assert isinstance(modal, SecurityAlertModal)
        modal.query_one("#btn-sec-fix").press()
        await pilot.pause(0.3)
        assert queued, "o aceite deveria virar um prompt para o agente"
        assert "SEGURANÇA" in queued[0]
        assert "seg.py" in queued[0]
        assert calls == []  # push NÃO roda quando o usuário aceita corrigir
