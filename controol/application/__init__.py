"""Camada de aplicação do Controol (Clean pragmático).

Regras de negócio (use cases), estado da sessão e ports de saída — **sem
nenhum import de Textual**. A apresentação (`controol/tui`) conversa com esta
camada através dos use cases e implementa os ports (`PromptPresenter`,
`LogSink`).
"""
from .ports import LogSink, PromptPresenter
from .session import Session, persist_session
from .tokens import count_text_tokens, fmt_tokens, tokens_from_data

__all__ = [
    "LogSink",
    "PromptPresenter",
    "Session",
    "persist_session",
    "count_text_tokens",
    "fmt_tokens",
    "tokens_from_data",
]
