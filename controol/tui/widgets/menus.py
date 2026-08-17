"""Modais do menu do header: opções do Controol + alerta do gitSecurity.

`MenuModal` é o menu aberto pelo botão ☰ no canto direito do banner; hoje só
tem o toggle do **gitSecurity**. `SecurityAlertModal` é a dialog que o push
abre quando o scan encontra possíveis segredos: o usuário aceita a correção
(que vira um prompt para o agente) ou ignora e continua o push.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from ...application.use_cases import SecretFinding

# quantos achados aparecem no alerta antes do "+N"
_ALERT_MAX = 8


class MenuModal(ModalScreen[bool | None]):
    """Menu do header: alterna opções do Controol (gitSecurity liga/desliga).

    `dismiss` retorna o estado do checkbox na hora de fechar (ou None se o
    usuário só dispensou com Esc/fora).
    """

    def __init__(self, git_security: bool) -> None:
        super().__init__()
        self._git_security = git_security

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-modal"):
            yield Static("▸ MENU", classes="panel-title")
            yield Checkbox("gitSecurity", value=self._git_security, id="menu-gitsecurity")
            yield Static(
                "Verifica key/token/chave de segurança nos arquivos do push "
                "e avisa antes de enviar.",
                classes="menu-hint",
            )
            yield Button("Fechar", id="btn-menu-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-menu-close":
            self._close()

    def _close(self) -> None:
        cb = self.query_one("#menu-gitsecurity", Checkbox)
        self.dismiss(cb.value)


class SecurityAlertModal(ModalScreen[str]):
    """Alerta do gitSecurity: sugere a mudança e deixa o usuário decidir.

    `dismiss` devolve `"fix"` (corrigir com o agente — vira prompt) ou
    `"ignore"` (ignorar o alerta e continuar o push).
    """

    def __init__(self, findings: list[SecretFinding]) -> None:
        super().__init__()
        self.findings = findings

    def compose(self) -> ComposeResult:
        with Vertical(id="security-modal"):
            yield Static("▸ ALERTA DE SEGURANÇA", classes="panel-title")
            yield Static("Possíveis segredos indo para o repositório:")
            for f in self.findings[:_ALERT_MAX]:
                yield Static(f"  {f.path}:{f.line} — {f.kind}", classes="sec-finding")
            if len(self.findings) > _ALERT_MAX:
                yield Static(
                    f"  … e mais {len(self.findings) - _ALERT_MAX}",
                    classes="sec-finding",
                )
            yield Static(
                "Aceitar vira um prompt para o agente remover os segredos.",
                classes="menu-hint",
            )
            yield Button("✓ Aceitar: corrigir com o agente", id="btn-sec-fix")
            yield Button("✗ Ignorar alerta e continuar push", id="btn-sec-ignore")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-sec-fix":
            self.dismiss("fix")
        elif event.button.id == "btn-sec-ignore":
            self.dismiss("ignore")
