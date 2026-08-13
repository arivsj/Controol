"""Interface de linha de comando do Controol."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from . import __version__
from .config import Config
from .git_tools import head_commit, install_hooks, is_repo
from .harness import create_harness


def _launch_tui() -> None:
    cfg = Config.load()
    if not is_repo(cfg.root):
        click.echo(
            "Não é um repositório git. Rode `controol init` dentro de um repositório.",
            err=True,
        )
        sys.exit(1)
    from .tui.app import ControolApp

    ControolApp(cfg, cfg.root).run()


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(__version__)
def main(ctx: click.Context) -> None:
    """Controol CLI — orquestra um harness de IA com memória de conhecimento."""
    if ctx.invoked_subcommand is None:
        _launch_tui()


@main.command()
@click.option(
    "--harness",
    type=click.Choice(["opencode", "claude"]),
    default=None,
    help="Harness padrão do projeto.",
)
@click.option(
    "--model", default=None, help="Modelo padrão (ex.: anthropic/claude-sonnet-4-5)."
)
@click.option("--no-hook", is_flag=True, help="Não instala o git hook post-commit.")
def init(harness: str | None, model: str | None, no_hook: bool) -> None:
    """Prepara o repositório: .controol/, config e git hook de memória."""
    cfg = Config.load()
    if harness:
        cfg.set("harness", harness)
    if model:
        cfg.set("model", model)
    cfg.save()
    (cfg.root / ".controol" / "memory" / "nodes").mkdir(parents=True, exist_ok=True)
    click.echo(f"✓ Controol CLI configurado: {cfg.path}")
    if not no_hook:
        if install_hooks(cfg.root):
            click.echo("✓ Hook post-commit instalado (captura de memória)")
        else:
            click.echo("! Não é um repositório git — hook não instalado", err=True)


@main.command(name="config")
@click.option("--harness", type=click.Choice(["opencode", "claude"]), default=None)
@click.option("--model", default=None)
@click.option("--agent", default=None)
@click.option("--auto-approve/--no-auto-approve", default=None)
def config_cmd(
    harness: str | None,
    model: str | None,
    agent: str | None,
    auto_approve: bool | None,
) -> None:
    """Mostra ou altera a configuração (.controol/config.json)."""
    cfg = Config.load()
    if harness:
        cfg.set("harness", harness)
    if model:
        cfg.set("model", model)
    if agent:
        cfg.set("agent", agent)
    if auto_approve is not None:
        cfg.set("auto_approve", auto_approve)
    click.echo(json.dumps(cfg._data, indent=2, ensure_ascii=False))


@main.command()
@click.option("--commit", default=None, help="Commit a processar (padrão: pendentes ou HEAD).")
@click.option(
    "--category",
    type=click.Choice(["documentacao", "bugs", "custom"]),
    default="documentacao",
    help="Categoria da memória.",
)
@click.option("--name", default=None, help="Nome da categoria customizada (com --category custom).")
def remember(commit: str | None, category: str, name: str | None) -> None:
    """Captura memória de commit(s) sem interação (para hook/scripts)."""
    if category == "custom" and not name:
        click.echo("--name é obrigatório quando --category custom.", err=True)
        sys.exit(1)
    from .memory import MemoryManager

    cfg = Config.load()
    mgr = MemoryManager(cfg.root)
    if commit:
        commits = [commit]
    else:
        commits = mgr.pending_commits() or [h for h in [head_commit(cfg.root)] if h]
    if not commits:
        click.echo("Nenhum commit para processar.")
        return
    harness = create_harness(cfg)

    async def _run() -> None:
        for c in commits:
            click.echo(f"→ salvando memória de {c[:8]} ({category}) …", err=True)
            result = await mgr.curate(c, category, harness, name)
            click.echo(f"✓ {result}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(130)


@main.command()
@click.option("--study/--no-study", default=True, help="Regenera também o relatório de estudo (usa o harness).")
@click.option("--out", default="controol-report.html", help="Nome do relatório de trabalho.")
def report(study: bool, out: str) -> None:
    """Regenera os relatórios a partir da sessão salva (.controol/session.json)."""
    import json

    from .report.work_report import write_work_report

    cfg = Config.load()
    session_path = cfg.root / ".controol" / "session.json"
    if not session_path.exists():
        click.echo("Nenhuma sessão salva. Rode `controol` e faça uma interação primeiro.", err=True)
        sys.exit(1)
    data = json.loads(session_path.read_text(encoding="utf-8"))
    interactions = data.get("interactions", [])
    harness_desc = data.get("harness", "")

    work = write_work_report(cfg.root, interactions, harness_desc, out)
    click.echo(f"✓ relatório de trabalho: {work}")
    if study:
        from .report.study_report import write_study_report

        async def _run() -> None:
            harness = create_harness(cfg)
            study_out = await write_study_report(cfg.root, interactions, harness)
            click.echo(f"✓ relatório de estudo: {study_out}")

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            sys.exit(130)


@main.command()
@click.argument("message", nargs=-1, required=False)
@click.option(
    "--raw",
    is_flag=True,
    help="Imprime os eventos JSON crus (para inspecionar o schema).",
)
@click.option("--model", default=None)
@click.option("--harness", default=None)
def debug(
    message: tuple[str, ...],
    raw: bool,
    model: str | None,
    harness: str | None,
) -> None:
    """Roda o harness com uma mensagem e despeja os eventos normalizados.

    Útil para depurar o schema do opencode/claude e ajustar os parsers.
    """
    cfg = Config.load()
    if harness:
        cfg.set("harness", harness)
    if model:
        cfg.set("model", model)
    prompt = " ".join(message)
    if not prompt:
        click.echo("Informe uma mensagem, ex.: controol debug 'oi'", err=True)
        sys.exit(1)

    async def _run() -> None:
        h = create_harness(cfg)
        click.echo(f"→ harness: {h.describe()}", err=True)
        async for ev in h.run(prompt):
            if raw:
                payload = ev.data.get("raw", {})
                click.echo(
                    json.dumps(payload, ensure_ascii=False)
                    if not isinstance(payload, str)
                    else payload
                )
            else:
                click.echo(f"[{ev.type}] {ev.tool or ev.file or ev.text[:120]}")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(130)
