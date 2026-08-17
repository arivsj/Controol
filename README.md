# Controol CLI

CLI cyberpunk (estilo bashtop) que orquestra um **harness de IA por trás**
(opencode por padrão, `claude -p` como alternativa) e transforma a atividade
dele em ferramentas de trabalho:

- **Memória de conhecimento** — ao commitar, pergunta se quer salvar memória
  em `.controol/memory/` (documentação de software, bugs raros ou categoria
  customizada). As notas usam frontmatter + wikilinks `[[...]]` + `index.md`,
  para consulta futura de IAs e leitura humana.
- **Revisão de diff** — painel superior direito mostra o código do arquivo
  selecionado com adições em **verde ("canetinha")** e remoções em **vermelho**,
  para você **aceitar** ou **rejeitar**.
- **Modo Trabalho** — gera/atualiza `controol-report.html`: lista colapsável
  de tudo que mudou na sessão, com as **classes/funções completas** (extraídas
  **sem IA**, via `ast`/scanner) e botão **copiar** com feedback "Copiado ✓".
- **Modo Estudo** — gera `controol-estudo.html`: explicação didática do código
  alterado, como se fosse para um estudante, com perguntas e respostas.

## Layout (neon estilo bashtop)

Fundo quase preto, caixas com **borda neon colorida por painel** e banner de
cabeçalho — como o bashtop/btop:

```
┌─ CONTROOL CLI · harness · modos · cwd ────────────┐  (banner ciano)
├─ esquerda (54) ─────────┬─ direita (diff) ────────┤
│ ▸ MODOS                 │ ▸ DIFF — arquivo sel.    │
│ [✓ Trabalho][ ]Estudo   │      [<] [>]             │
│ ▸ ARQUIVOS ALTERADOS    │  + código novo (verde)   │
│  ~ banco.py             │  - código removido (verm)│
│  ~ outro.py             │  [✓ Aceitar][✗ Rejeitar] │
│  ~ mais um.py           │  [✓ Aceitar tudo]        │
│  (até ~18, com scroll)  │  (coluna mais estreita,  │
│ status add commit push  │   liberando largura p/   │
│    fetch pull           │   modos e resposta)      │
│ ▸ EXECUÇÃO · RESPOSTA   │                          │
│ 🏭 ═██─═ construindo…  │                          │
│   [edit] banco.py       │                          │
│   (card alto: ocupa o   │                          │
│    espaço que sobra)    │                          │
├────────────────────────────────────────────────────┤
│ ▸ FALE COM O AGENTE   ❯ seu pedido…     [ Enviar ]  │
│ ⏳ 1. segundo pedido (fila enquanto o agente ocupa)  │
├────────────────────────────────────────────────────┤
│ ▌MODELO … ▌CONTEXTO 1.2k (entrada) ▌TOKENS 1.7k [Clear] │
└────────────────────────────────────────────────────┘
```

- **Layout em colunas**: a esquerda tem **54 colunas** — card **modos** (com o
  subcard **ARQUIVOS ALTERADOS** — **4x maior**: até ~18 linhas com scroll, se
  passar disso), a **barra git**
  (status/add/commit/push/fetch/pull, centralizada, **cabe em 54**) e o card
  **`▸ EXECUÇÃO · RESPOSTA DO AGENTE`** (mesma largura do card modos, **alto**:
  ocupa todo o espaço que sobra na coluna). A direita é o **diff** (borda
  ciano), **mais estreito** — a coluna esquerda (modos + resposta) ficou mais
  larga para melhorar a leitura das alterações.
- **No canto direito do banner**, o botão **`☰`** abre o **menu** do Controol
  (uma dialog) com as opções da ferramenta. Hoje ele tem o toggle do
  **gitSecurity**.
- **No topo do card de diff**, no **centro**, ficam os botões **`<` `>`** que
  **alternam entre os arquivos alterados** (com volta no fim da lista); com um
  único arquivo eles ficam desabilitados. Você também pode trocar clicando num
  arquivo da lista à esquerda.
- **Margens mínimas**: títulos e botões com margem mínima, painéis **colados**
  (só as bordas separam as seções). Não há card roxo vazio: o antigo **log
  violeta foi removido** e fundido no card de execução.

- Os botões **Aceitar / Rejeitar / Aceitar tudo** são de **revisão local**
  (não mexem no opencode): só aparecem enquanto houver **aceite pendente**
  (alteração ainda não aceita) e somem quando tudo é aceito ou a working tree
  fica limpa. Rejeitar restaura o arquivo do HEAD no disco.
- Todos os botões são **compactos (1 linha, sem borda, cor de fundo)**.
- **Trabalho** e **Estudo** são botões de mesmo tamanho; o modo ativo ganha
  **contorno verde**. São independentes: os dois podem ficar verdes ao mesmo
  tempo.
- Artefatos do próprio Controol (`.controol/`, `controol-report.html`) não
  contam como alteração para revisão — só o que o opencode mudou de verdade.
- **Footer rosa** na parte de baixo mostra em linha: `▌MODELO`, `▌CONTEXTO`
  (tokens de entrada) e `▌TOKENS` (total usado), atualizados ao vivo conforme
  o harness reporta o uso. Sem relatório do harness, é usada uma estimativa
  (caracteres ÷ 4).
- **O painel de conversa** (borda rosa, título `▸ FALE COM O AGENTE`) é onde
  você fala com o agente: digite e aperte Enter (ou **Enviar**). **O campo não
  trava durante o trabalho** — se você digitar um novo pedido enquanto o agente
  roda, ele entra numa **fila** (mostrada em amarelo dentro do próprio card) e é
  processado assim que o agente terminar. Ao terminar (ou falhar), o foco volta
  sozinho para o campo — pronto para o próximo pedido.
- **Na coluna esquerda (54)**, o painel azul `▸ EXECUÇÃO · RESPOSTA DO AGENTE`
  tem a **mesma largura do card modos** e **ocupa todo o espaço vertical que
  sobra na coluna** (com scroll): **absorveu o log de atividade** — mostra o
  que foi executado (tool
  calls, arquivos alterados em verde, passos, feedback do app) e, no fim, a
  **resposta do agente**. Enquanto o agente trabalha, o topo mostra uma
  **animação de fábrica** (engrenagem girando + caixa deslizando na esteira)
  com a ação corrente (ex.: `[edit] banco.py`); a resposta vai **entrando por
  baixo** da animação. No fim, fica a explicação final + quantos arquivos foram
  alterados.
- Depois de **commitar**, a captura de memória pergunta na hora (o modal de
  memória abre e toma o foco); ao dispensá-lo ("Agora não" ou salvar), o foco
  volta ao campo do prompt. Em qualquer outra operação git (ou ao cancelar o
  modal de commit), o foco também volta ao prompt — você nunca "perde" a
  digitação.
- O **`MODELO` do footer é o modelo real** do harness (ex.:
  `deepseek/deepseek-v4-flash`), **nunca o nome do harness** — detectado sem
  custo logo na abertura (config do opencode ou última sessão no banco) e
  confirmado pela sessão real do opencode via `opencode export` após o primeiro
  run.
- O botão **`[ Clear ]`** no fim do footer **limpa o contexto da conversa**
  (interações, tokens e a resposta do agente) para **economizar token** em
  sessões longas.

| Atalho | Ação |
|---|---|
| `Ctrl+R` | alterna modo Trabalho |
| `Ctrl+E` | alterna modo Estudo |
| `Ctrl+A` | aceita o arquivo selecionado |
| `Ctrl+X` | rejeita (restaura do HEAD) |

> A **captura de memória não é um modo**: ela vigia os commits **sempre**
> (na abertura da TUI e a cada interação). Não há toggle para desligar.

## Instalação

```bash
pip install -e .
controol init            # prepara .controol/, config e o git hook de memória
controol                 # abre a TUI
```

> O `init` instala um **hook post-commit** que registra commits pendentes de
> memória em `.controol/pending_commits`. Se você já tiver um hook, ele faz
> backup do atual em `post-commit.bak`.

## Como usar

1. Dentro de um repositório git, rode `controol`.
2. Digite um prompt na parte de baixo — o harness roda por trás e a CLI
   acompanha texto, tool calls e arquivos alterados ao vivo.
3. Ao terminar, use o painel direito para **aceitar** (`Ctrl+A`),
   **rejeitar** (`Ctrl+X`) cada arquivo, ou **Aceitar tudo** num clique.
4. Com o **modo Trabalho** ligado, `controol-report.html` é gerado (e
   realimentado) a cada interação. Com o **modo Estudo**, `controol-estudo.html`.
5. Quando houver commits pendentes, um modal pergunta se quer salvar a memória.

## Requisitos faltando? (o que acontece)

O Controol **abre mesmo sem o harness**, mas cada recurso tem um comportamento
se o binário/ambiente dele não existir:

| Faltando | O que acontece |
|---|---|
| **Python 3.10+** | Não dá nem para instalar (`pip install -e .` falha). É o próprio runtime do Controol. |
| **opencode** | O app abre normal. Na primeira mensagem, o log mostra em vermelho: `⚠ opencode não encontrado no PATH. Instale com: curl -fsSL https://opencode.ai/install \| bash`. Git, revisão, relatórios e memória continuam funcionando — só o prompt falha com a instrução. |
| **claude** (`harness: "claude"`) | Mesma ideia: `⚠ claude não encontrado no PATH. Veja: https://docs.anthropic.com/...`. |
| **git** | `controol` nem abre: `Não é um repositório git. Rode \`controol init\` dentro de um repositório.` (sai com código 1). Dentro da TUI, operações git mostram `⚠ git não encontrado no PATH`. |
| **não estar num repositório git** | `controol` avisa e sai; `controol init` configura mas não instala o hook (`! Não é um repositório git — hook não instalado`). |
| **`.controol/config.json`** | Não é problema: o `Config.load` usa os padrões (harness `opencode`, `auto_approve: false`). O `controol init` cria o arquivo. |
| **repositório vazio (sem commits)** | O app abre; a captura de memória simplesmente não tem commits para vigiar. |

O único "requisito duro" é o **git** (a TUI é feita para rodar dentro de um
repositório). O **harness** é opcional para abrir — só é necessário quando você
manda um prompt ou pede o relatório de estudo.

## Git direto da TUI

Na coluna esquerda, acima do card de execução, fica a **barra git**
(`status`, `add`, `commit`, `push`, `fetch`, `pull`) — os 6 botões **cabem na
largura de 54** da coluna, sem invadir o diff. Cada ação roda em background e
o resultado aparece no card de execução:

- `status` — mostra o estado compacto da working tree (`git status --short
  --branch`: branch + arquivos modificados/adicionados/untracked, até 13
  linhas no card).
- `add` — prepara tudo (`git add -A`, inclui untracked); mostra quantos
  arquivos entraram no stage.
- `commit` — se não houver nada no stage, avisa (`rode add antes`); caso
  contrário abre um **modal** para digitar a mensagem (Enter commita) e mostra
  o hash + subject criado.
- `push` — envia para o upstream; sem upstream configurado, sugere
  `git push -u origin <branch>`. Com o **gitSecurity** ligado (padrão), antes
  de enviar o Controol **varre os arquivos do push** (commits não enviados +
  stage) procurando key/token/chave de segurança. Se achar algo, abre um
  **alerta**: você pode **aceitar a correção** (o aviso vira um prompt para o
  agente remover os segredos e substituir por variáveis de ambiente) ou
  **ignorar o alerta e continuar o push**.
- `fetch` / `pull` — buscam o remoto (o pull integra no branch atual);
  "já atualizado" é tratado como sucesso e conflitos aparecem em vermelho.

Enquanto uma operação roda, os botões ficam travados (`disabled`). Após cada
ação a lista de arquivos e o painel de diff são atualizados — um commit limpo
faz os botões Aceitar/Rejeitar desaparecerem.

## Memória

Estrutura do vault (versionada em `.controol/`):

```
AGENTS.md                # resumo do projeto p/ futuras IAs (na raiz, junto ao código)
.controol/
├── config.json            # harness, model, idioma…
├── pending_commits        # hashes capturados pelo hook post-commit
├── state.json             # contador MEM-* e commits já processados
├── session.json           # última sessão (para `controol report`)
└── memory/
    ├── nodes/<slug>.md    # notas com frontmatter + wikilinks [[...]]
    ├── bugsRaras.md       # bugs raros (sintoma/contexto/causa/fix)
    ├── doc-conhecimento.md # parágrafos para leitura humana
    └── index.md           # índice das notas
```

Categorias ao salvar memória de um commit:

1. **Documentação de software** — um agente lê o commit e: adiciona uma seção
   no `AGENTS.md`, cria uma nota `.md` resumida (para buscas de IA) e um
   parágrafo em `doc-conhecimento.md` (leitura humana).
2. **Bugs raros** — bugs que só ocorrem em situações/usuários/servidor
   específicos. Anota `bugsRaras.md` (para consulta quando a IA falhar muito)
   + parágrafo na documentação.
3. **Categoria customizada** — você dá um nome e a nota é criada com essa tag.

Para scripts/CI: `controol remember --category documentacao` processa commits
pendentes sem interação.

## Comandos

```bash
controol                  # abre a TUI
controol init             # .controol/ + config + hook post-commit
controol config           # mostra/altera config (--harness, --model, --agent…)
controol remember         # captura memória de commit(s) headless
  --category documentacao|bugs|custom   --name <nome>  --commit <hash>
controol report           # regenera controol-report.html (+ --study)
controol debug "oi"       # despeja eventos do harness (--raw p/ ver o schema JSON)
```

## Configuração

`.controol/config.json` (criado pelo `init`):

```json
{
  "harness": "opencode",
  "model": null,
  "agent": null,
  "auto_approve": false,
  "language": "pt",
  "git_security": true
}
```

- `harness`: `opencode` (padrão) ou `claude`.
- `model` / `agent`: repassados ao harness (ex.: `anthropic/claude-sonnet-4-5`).
- `auto_approve`: autoriza tool calls automaticamente (opencode `--auto`).
- `git_security`: liga/desliga a verificação de segredos antes do push (também
  alternável pelo menu `☰` do header).

## Relatórios

### Trabalho (`controol-report.html`)

Seção por interação (com a explicação do agente) → `<details>` por arquivo
(cabeçalho = caminho) → **código completo** de cada classe/função (extraído
**sem IA** — `ast` para Python, scanner genérico de chaves para outras
linguagens) → botão **📋 Copiar** que dá feedback "Copiado ✓" e reverte em 1,5s
→ diff em verde/vermelho. Auto-realimentado a cada interação; também
regenerável com `controol report`.

### Estudo (`controol-estudo.html`)

O harness vira "professor": explica cada arquivo alterado passo a passo para
um estudante e gera perguntas com resposta oculta (clicável). Auto-realimentado
no modo Estudo.

## Arquitetura

Arquitetura **Clean pragmática**: as regras de negócio vivem na camada de
aplicação, independente da interface (sem Textual), e a TUI só orquestra e
renderiza.

```
controol/
├── harness/          # adapters do harness (opencode / claude -p) → Event stream
├── application/      # CAMADA DE APLICAÇÃO (sem Textual)
│   ├── session.py    #   Session (estado da sessão) + persist_session (session.json)
│   ├── ports.py      #   Protocol: PromptPresenter + LogSink (saída p/ a TUI)
│   ├── tokens.py     #   tokens_from_data / count_text_tokens / fmt_tokens (puras)
│   └── use_cases/    #   git, review, memory, report, model, prompt
├── memory/           # vault .controol/memory/ (store, manager, curator)
├── report/           # class_extractor (SEM IA) + diffing + relatórios HTML
└── tui/              # APRESENTAÇÃO
    ├── app.py        #   ControolApp: coordenador/presenter (delega aos use cases)
    ├── theme.css     #   tema cyberpunk
    └── widgets/      #   modos, diff, gitbar, prompt, execução, footer, modais
```

Fluxo: a TUI recebe o gesto → chama o use case (muta a `Session`, lê
git/harness) → o resultado volta pelos ports e o app renderiza os widgets. O
`ControolApp` vira um **coordenador/presenter fino**: a orquestração de prompt,
git, revisão, relatórios, memória e modelo vive nos use cases
(`application/use_cases/`); os dados da sessão, na `Session`.

## Testes

```bash
python3 -m pytest tests/
```

- `tests/test_class_extractor.py` — extração de classes sem IA (Python `ast`,
  decorators, JS, Go, fallback genérico).
- `tests/test_diffing.py` — parser do diff unificado (adições/remoções/números
  de linha).
- `tests/test_git_tools.py` — untracked como adição, diff de arquivo novo,
  reject (remover/restaurar) e operações assíncronas `git add`/`commit`.
- `tests/test_tui.py` — fumaça headless (Textual pilot): montagem, toggles,
  aceitar/rejeitar, **navegação `<` `>` entre arquivos no diff**, modal de
  memória, barra git (6 botões, inclui `status`) e commit pelo modal, footer de
  estatísticas, **card de execução unificado** (log + animação de fábrica +
  resposta), fila de pedidos, input digitável (regressão do `height: 1`), foco
  voltando ao prompt, botão Clear, detecção de modelo via `opencode export` e
  probe via banco da última sessão.
