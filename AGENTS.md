# AGENTS.md — Controol CLI

Guia para agentes de IA (e humanos) que trabalham neste repositório.
Leia antes de alterar código.

## O que é

**Controol CLI** é um programa em Python com TUI estilo **bashtop/cyberpunk** que roda um
**harness de IA por trás** (opencode por padrão; `claude -p` como alternativa)
e captura as ações dele em 4 capacidades:

1. **Memória de conhecimento** — quando o usuário faz um commit, a TUI pergunta
   se quer salvar memória (documentação / bugs raros / categoria custom) em
   `.controol/memory/`. **Sempre ativa** (não é um modo alternável): vigia a
   abertura da TUI, o fim de cada interação **e o commit/pull feito pela barra
   git** (o modal de memória abre na hora, tomando o foco).
2. **Revisão de diff** — painel superior direito com adições em verde e
   remoções em vermelho, para **aceitar/rejeitar** arquivos. Os botões
   Aceitar/Rejeitar/Aceitar tudo **só aparecem quando há alterações**. No
   **centro do topo** ficam os botões **`<` `>`** (`#btn-prev-file` /
   `#btn-next-file`, em `#diff-nav`) que **alternam entre os arquivos**
   (com wrap; desabilitados com ≤1 arquivo) — o `DiffPanel.set_files()` alimenta
   a navegação e o `show_diff()` sincroniza o índice com o arquivo exibido.
3. **Git na TUI** — barra na **coluna esquerda (54)**, entre o card modos e o
   card de execução (`git_bar.py`): status/add/commit/push/fetch/pull **cabem
   na largura de 54** (sem glifos +/↑/↓, centralizados; o `status` fica à
   esquerda do `add`) e rodam em workers assíncronos
   (`git_tools.py`) com feedback no card de execução;
   `commit` abre o `CommitModal` para a mensagem.
4. **Modo Trabalho** — gera/realimenta `controol-report.html`: lista colapsável
   da sessão, classes/funções **completas** (extraídas **sem IA**) e botão
   copiar com feedback.
5. **Modo Estudo** — gera `controol-estudo.html`: explicação didática do código
   alterado com perguntas e respostas (usa o harness).

- UI e conteúdo gerado em **Português (Brasil)**. Mantenha isso.
- Tema cyberpunk: fundo `#0F101D`, ciano `#00F5D4`, rosa `#F72585`, violeta
  `#9D4EDD`, amarelo `#FFB703`, vermelho `#FF2E63` (tokens em
  `controol/tui/theme.css` e nos HTMLs).

## Arquitetura (mapa de módulos)

```
controol/
├── cli.py            # click: controol (TUI) / init / config / remember / report / debug
├── config.py         # .controol/config.json (harness, model, agent, auto_approve, language)
├── git_tools.py      # diff, file_diff_text, reject_file (checkout do HEAD), install_hooks
├── jsontools.py      # extract_json(): extrai o 1º {..} de resposta do agente (com/sem ```fences)
├── harness/          # DOMÍNIO/infra: adapters do harness
│   ├── base.py       #   Event (type/text/tool/file/data) + Harness ABC (async run(prompt))
│   ├── opencode.py   #   spawn `opencode run --format json` → eventos normalizados
│   ├── claude_code.py#   spawn `claude -p --output-format stream-json` → eventos
│   └── factory.py    #   create_harness(config) escolhe o harness
├── application/      # CAMADA DE APLICAÇÃO (Clean pragmático): regras de negócio, SEM Textual
│   ├── session.py    #   Session (estado da sessão = fonte única) + persist_session (session.json)
│   ├── ports.py      #   Protocol: PromptPresenter + LogSink (saída p/ a TUI)
│   ├── tokens.py     #   tokens_from_data / count_text_tokens / fmt_tokens (funções puras)
│   └── use_cases/    #   git, review, memory, report, model, prompt (RunPromptUseCase)
├── memory/           # infra: vault .controol/memory/ (store, manager, curator)
├── report/           # infra: class_extractor (SEM IA) + diffing + work_report + study_report
└── tui/              # APRESENTAÇÃO: widgets + coordenador/presenter
    ├── app.py        #   ControolApp (Textual 8): mensagens → use case → renderiza;
    │                 #   proxy p/ Session (changed_files, interactions…) e ports (presenter/sink)
    ├── theme.css     #   tokens cyberpunk
    └── widgets/      #   modes_panel, diff_panel, git_bar, prompt_input, agent_summary,
                      #   status_footer, memory_modal, commit_modal
tests/              # pytest (46 testes): class_extractor, diffing, git_tools, tui
```

**Fluxo (Clean pragmático):** `tui/` recebe o evento de UI → chama o use case em
`application/use_cases/` (que muta a `Session` e lê git/harness) → o resultado
volta pelos ports (`PromptPresenter`/`LogSink`) e o app renderiza os widgets.
`app.py` não contém regra de negócio — só orquestração e renderização. A suíte
de testes pinou a superfície do app (construtor `ControolApp(Config.load(repo),
repo)`, atributos `changed_files`/`modes`/`interactions`… e métodos
`refresh_files()`/`_update_footer()`/`on_accept_all()`/`set_loading()`/
`_enqueue_or_run()`/`_on_run_done()`/`_tokens_from_data()`): eles continuam,
delegando à `Session`/use cases (facade de compatibilidade).

## Fluxo de dados

```
usuário digita prompt
  → ControolApp._handle_prompt (tui/app.py = coordenador: fila/foco/animação)
  → RunPromptUseCase.run(prompt, interaction) (application/use_cases/prompt.py)
      zera session.accepted (novo lote de revisão) e itera harness.run(prompt)
      despacha cada Event ao PromptPresenter (o próprio app implementa o port):
      agent_text  → on_agent_text  → append_reply + explanation + tokens estimados
      tool        → on_tool        → add_line no card (dim) + working label
      file_touched→ on_file_touched + on_files_changed → add_line verde + lista ao vivo
      step_done   → on_step_done   → tokens reais (data["tokens"]) + footer
      error       → on_error       → ⚠ no card
  → ControolApp._on_run_done: RunPromptUseCase.finish (ReviewUseCase.refresh +
      preenche interaction["files"][path] com o diff real) → renderiza resumo no card
      → persist session (.controol/session.json)
      modo Trabalho → ReportUseCase.write_work()  (síncrono, sem IA)
      modo Estudo   → ReportUseCase.write_study() (usa harness)
      _check_memory() → MemoryUseCase.pending() → modal de categoria → save()
```

## O modelo de Eventos (crítico)

```python
Event(type, text="", tool="", file="", data={})
# type: "agent_text" | "tool" | "file_touched" | "step_done" | "error"
```

- Os parsers de `opencode.py` e `claude_code.py` **normalizam** schemas
  diferentes para este modelo. Toda mudança de parsing deve ser validada com
  `controol debug "msg"` e `controol debug --raw "msg"`.
- Ferramentas que mutam arquivo (edit/write/patch/create/replace) emitem
  `file_touched` com `data["diff"]` (unified diff). Caminhos absolutos são
  normalizados para relativos.
- **O schema JSON do opencode varia por versão e foi pinado empiricamente**
  (não via docs). Ver [[opencode-json-schema]] na memória da sessão; use
  `controol debug --raw` para re-pinar se mudar.

## Convenções

- **`ast` para Python, scanner genérico para o resto**: nunca use IA para
  extrair código de classes nos relatórios (custo/tokens). `class_extractor.py`
  cuida disso (suporta padrão Go `type X struct` e decorators Python).
- Relatórios HTML são **autocontidos** (CSS/JS inline, sem CDN). Botão copiar
  usa `navigator.clipboard` com fallback `execCommand`.
- Textual **8.x**: `Option` vem de `textual.widgets.option_list`; `Static`
  expõe `.content` (não `.renderable`); `pilot.pause()` para sincronizar
  `push_screen` assíncrono em testes.
- Diffs vêm de `git diff` (unified). `reject_file()` restaura o arquivo do HEAD.
- **Revisão filtra artefatos internos**: `reviewable_changes()` (git_tools.py)
  exclui `.controol/` e os relatórios gerados — senão os próprios arquivos do
  Controol aparecem como "alterações" e os botões aceitar/rejeitar não somem.
- **Operações git são assíncronas** (`_git_async` em `git_tools.py`, rodadas
  via `run_worker(group="git")`); enquanto rodam, `GitBar.set_busy(True)` trava
  os botões. O `commit` exige stage — sem stage, o feedback manda usar `add`.
- Os botões aceitar/rejeitar são **locais** (não afetam o opencode): aceitar só
  marca o arquivo como mantido na sessão; rejeitar restaura o arquivo do HEAD
  no disco. `DiffPanel.set_has_changes()` mostra `#diff-actions` **apenas
  enquanto houver aceite pendente** (arquivo alterado ainda não aceito);
  `accepted` é zerado a cada novo run. Botões compactos: 1 linha, sem borda.
- Modos Trabalho/Estudo são **Checkbox em `#mode-row`** (lado a lado, `width:
  1fr` = mesmo tamanho); a classe `.selected` (verde) marca o ativo. São
  toggles independentes — os dois podem ficar verdes ao mesmo tempo.
- Modos: apenas **Trabalho** (`Ctrl+R`) e **Estudo** (`Ctrl+E`) são
  alternáveis. **Memória é sempre ativa** — não adicione toggle de volta.
- **Footer rosa** (`status_footer.py`, id `status-footer`, `Horizontal`) mostra
  `MODELO / CONTEXTO / TOKENS` em linha + botão **Clear** no fim. Atualizado por
  `app._update_footer()`: MODELO = `harness.model` detectado (ou o nome do
  harness); CONTEXTO = tokens de entrada; TOKENS = total. Tokens vêm de
  `step_done` → `data["tokens"]` (`application/tokens.py::tokens_from_data`
  retorna `(input, total)` — **o `total` inclui cache read**, é a métrica
  honesta); sem relatório do harness, `count_text_tokens` estima chars/4 e
  `_tokens_measured` só liga quando o uso real chega. O botão Clear (`on_clear_context`) zera interações,
  contadores e a resposta do agente — o usuário limpa o contexto p/ economizar
  token.
- **Modelo real do opencode**: o evento `step_done` traz `part.sessionID`, e o
  `opencode export <sessionID>` revela o modelo em `info.model` (NÃO no topo do
  JSON) — `{"id": "deepseek-v4-flash", "providerID": "deepseek"}`. O harness
  detecta 1x por app (`_model_detected`) e o footer mostra
  `deepseek/deepseek-v4-flash` (provedor/modelo) **em vez de "opencode"**.
  O footer nunca mostra o nome do harness: no startup um **probe sem custo**
  (`Harness.probe_model()`; no opencode, `_config_model()` — config do opencode
  global/projeto — e `_last_session_model()` — `session.model` da sessão mais
  recente, lida direto do banco `~/.local/share/opencode/opencode.db`) preenche
  `app._probe_model`; depois do primeiro run, o `harness.model` detectado tem
  prioridade. Fallback neutro: "—".
- **Card único de execução + resposta** (`agent_summary.py`, id
  `agent-summary`, borda azul, título `▸ EXECUÇÃO · RESPOSTA DO AGENTE`):
  **absorveu o antigo `RichLog #log` (removido)** — todo `app._write` agora vai
  para `add_line(text, style)`, então o log de execução (boas-vindas, prompts,
  tool calls, arquivos alterados em verde `dim #a6e22e`, passos, feedback do
  app) e a resposta do agente vivem no **mesmo card**. Fica na **coluna
  esquerda (largura 54, igual ao card modos)** com **`height: 1fr`** —
  **ocupa todo o espaço vertical que sobra** na coluna (com scroll). O
  **layout é em colunas** (`#columns`/`#left` no `compose`): esquerda =
  `#modes` (altura `auto`, com o subcard **ARQUIVOS ALTERADOS** — `#file-list`
  com `max-height: 20` (**4x** o antigo): cresce até ~18 linhas e rola se
  passar disso), `#gitbar` (centralizada) e `#agent-summary`
  (`height: 1fr`); direita = `#diff` (`width: 1fr`, **mais estreita** que a
  coluna esquerda — modos e resposta ficaram mais largos). **Margens mínimas**
  nos títulos (`.panel-title { margin-top: 0 }`) e botões (gitbar sem
  `margin-right`, centralizados nos 54). Enquanto o agente trabalha,
  `start_working()` liga uma **animação de fábrica** (engrenagem braille girando
  + esteira com caixa deslizando) e a ação corrente (`set_working_label`); o
  texto do agente (`agent_text`) vai **entrando por baixo** da animação via
  `append_reply` (acumulado em `app.agent_response` e **não logado de novo**).
  `stop_working()` move a resposta acumulada pro log e **devolve-a** — o
  `set_summary(reply, files)` só anexa a resposta se ela diferir da movida
  (senão duplicaria). `clear()` zera linhas e resposta (botão Clear).
  **NÃO defina um método chamado `_render`** — colide com `Widget._render()`
  interno do Textual (que retorna um `Visual`) e quebra o render com
  `'NoneType' object has no attribute 'render_strips'`. O desenho da animação é
  `_draw()`.
- **Foco no prompt**: `_focus_prompt()` foca `#prompt-field` (o container
  `PromptInput` NÃO é focável — focá-lo é no-op e o foco ficava perdido).
  Após git ops `_run_git` chama no fim; ao cancelar o commit, o foco precisa de
  `call_after_refresh` (senão o dismiss do modal restaura o botão por cima).
  No fim de cada run (`_handle_prompt`/finally) o foco volta ao campo.
- **Painel de conversa + fila** (`prompt_input.py`, id `prompt`): container
  `Vertical` com título `▸ FALE COM O AGENTE` + `#prompt-row` (Input
  `#prompt-field` + `#btn-send`) + `#queue-list`. O `#prompt-field` precisa de
  `height: 3` (borda `round` = border-box) — com `height: 1` a área de conteúdo
  fica em 0 e o texto digitado fica **invisível**.
  **O input NÃO é desabilitado durante o trabalho** (`set_loading` só troca o
  placeholder): o usuário pode digitar um novo pedido enquanto o agente roda e
  ele entra na **fila** (`app._queue`), mostrada amarela dentro do card
  (`set_queue`, até 3 itens + "+N na fila"). `app._enqueue_or_run` roda na hora
  se livre; senão enfileira. No fim do run, o `finally` drena a fila
  (seta `_busy=True` de volta **antes** de despachar o próximo — sem gap para
  um submit furar a fila).

## Comandos de desenvolvimento

```bash
pip install -e ".[dev]"      # instala com dependências de teste
python3 -m pytest tests/     # 46 testes
controol debug --raw "oi"    # ver o schema JSON real do harness
controol                     # abrir a TUI
```

## Testes

- `tests/test_class_extractor.py` — extração sem IA (Python/JS/Go, decorators,
  fallback genérico).
- `tests/test_diffing.py` — parse_unified_diff (adições/remoções, números de linha).
- `tests/test_git_tools.py` — untracked como adição, diff de arquivo novo,
  reject (remover/restaurar), `git add`/`commit` assíncronos.
- `tests/test_tui.py` — fumaça headless via Textual pilot (mount, toggles,
  aceitar/rejeitar restaurando do HEAD, **navegação `<` `>` entre arquivos no
  diff** (com wrap; desabilitados com 1 arquivo), modal de memória sem toggle,
  barra git (6 botões, inclui `status`), aceitar/rejeitar ocultos sem alterações,
  commit pelo modal, footer com modelo/contexto/tokens, **card de execução
  unificado** (log + **animação de fábrica + resposta entrando por baixo**, sem
  duplicação), **fila de pedidos quando ocupado**, **input do prompt digitável
  (regressão de `height: 1`)**, **foco inicial no prompt** e **foco voltando ao
  prompt após commit e cancelamento**, **botão Clear zerando o contexto (inclui
  resposta acumulada e fila)**, **detecção de modelo via `opencode export`→
  `info.model`** e **probe do modelo via banco da última sessão**).
