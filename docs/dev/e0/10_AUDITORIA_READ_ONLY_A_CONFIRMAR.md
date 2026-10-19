# 10 — Auditoria Read-Only: Grimbots ↔ grimbots-ai (Out/2026)

**Escopo**: somente leitura. Nenhum arquivo funcional foi alterado, nenhuma feature foi
ativada. Este documento formaliza as regras permanentes de colaboração entre os dois
repos e audita o estado atual da integração do bloco Atendimento IA.

**Atualização (2026-10-18)**: acesso ao repo do motor obtido (`grimbots-ai`, commit
`8db1de7`); os itens antes marcados **[A CONFIRMAR]** foram re-validados contra o código
real do motor (seção 4). Resultado: **9 CONFIRMAM**, **2 MUDAM** (C3 e C8 — o motor
evoluiu e hoje aceita o contrato v1.1) e **1 MUDA parcialmente** (C10 — dois caminhos de
prompt). Divergências a apresentar na seção 4.1.

---

## 1. Regras permanentes de colaboração (adotadas pelo dono do projeto)

Válidas para **todo o projeto**, a partir de Out/2026:

1. **Cada dev é responsável exclusivamente pelo próprio repo.**
   - Dev Grimbots: este repo (`gustavoRm1/grimbots`).
   - Dev motor: repo do `grimbots-ai` (AI Gateway / agente de vendas).
   - Proibido alterar código do outro repo.

2. **Antes de CADA tarefa relacionada à IA na Grimbots**, consultar o Git remoto do
   `grimbots-ai` (commits recentes, contratos, schemas, exemplos de request/response).

3. **Consultar antes de implementar.** Se houver divergência ou documentação
   insuficiente, **apresentar antes de implementar** — nunca presumir comportamento.

4. **Mudança publicada pelo motor que afete a integração**: identificar os
   arquivos/campos/contratos da Grimbots afetados; **não alterar automaticamente**;
   apresentar o impacto e implementar somente o necessário, com testes.

5. **Mudança interna do motor sem impacto de contrato**: nada a fazer na Grimbots.
   Impacto em contrato/schemas/ações/memória/resposta → **identificar explicitamente**.

6. **Repos independentes**: não copiar código entre projetos, não modificar o repo do
   motor, não presumir que proposta documental está implementada.

7. **Tarefa desta fase (E0)**: APENAS documento de auditoria read-only; marcar "a
   confirmar" tudo não verificado em código; sem alterações funcionais nem ativação;
   apresentar o PR e aguardar aprovação.

---

## 2. Acesso ao repositório do motor — RESOLVIDO (regra 2 cumprida)

O dono do projeto forneceu o remoto: `git@github.com:gustavoRm1/grimbots-ai.git`.

| Tentativa | Resultado |
|---|---|
| SSH `git@github.com:gustavoRm1/grimbots-ai.git` | chave SSH local **não registrada** no GitHub (publickey denied) |
| Clone HTTPS `https://github.com/gustavoRm1/grimbots-ai.git` | **OK** (credencial HTTPS já salva no helper local) |
| Clone local efetuado | diretório temporário, commit `8db1de7` (2026-10-18) |

> **Nota de ambiente**: o repo é privado (por isso o 404 via HTTPS sem credencial na
> auditoria anterior). A credencial HTTPS desta máquina tem acesso de leitura.

**Resultado desta consulta** foi a re-avaliação de C1–C12 (seção 4) contra o código
real do motor — vários itens **mudaram** em relação à suposição anterior. Nenhuma
alteração funcional foi feita na Grimbots (regras 4 e 7).

---

## 3. Evidências VERIFICADAS no código Grimbots (Out/2026, leitura direta)

### 3.1 Contrato enviado ao motor (lado Grimbots)

| Fato | Status | Local |
|---|---|---|
| Enum de ações canônico: `continue`, `ask_question`, `present_offer`, `send_checkout`, `handoff_human`, `pause`, `do_not_respond` — **sem `no_reply`** | [EXISTS] | `internal_logic/services/ai_service.py:25-33` |
| Enums `INTENTS`, `LEAD_TEMPERATURES`, `FUNNEL_STAGES`, `RISKS`, `MODES`, `ROLES` | [EXISTS] | `ai_service.py:34-42` |
| `build_payload` monta body do `POST /v1/agent/respond`; campos v1.1 (`contract_version`, `agent_profile`, `flow_resources`, `context_policy`) entram **somente quando não-None** (default = v1.0 byte-a-byte) | [EXISTS] | `ai_service.py:170-245` |
| Endpoint `{GRIMBOTS_AI_API_URL}/v1/agent/respond` | [EXISTS] | `ai_service.py:430` |
| `allowed_actions` enviado pelo bloco: `step_config.get('allowed_actions') or None` | [EXISTS] | `bot_manager.py:4242` |
| `allowed_actions` no payload sanitizado (filtra só ações do enum) | [EXISTS] | `ai_service.py:308-311` |
| Retry: códigos `RATE_LIMITED`/`AI_BUSY`/`AI_TIMEOUT`/`AI_INVALID_RESPONSE`, 3 tentativas, backoff (2,4,8)s, `Retry-After` cap 30s | [EXISTS] | `ai_service.py:77-83, 458+` |
| Marcadores anti-injeção de persona no `agent_profile` | [EXISTS] | `ai_service.py:60-74` |

### 3.2 Resposta do motor → execução (lado Grimbots)

| Fato | Status | Local |
|---|---|---|
| `AIResult.action` **clamp**: ação inválida → `"continue"` (`no_reply` do motor viraria `continue`) | [EXISTS] | `ai_service.py:117` |
| `AIResult.risk` clamp: risco inválido → `"low"` | [EXISTS] | `ai_service.py:121` |
| MockAIService clamp extra à `allowed_actions` do payload | [EXISTS] | `ai_service.py:541, 562-563` |
| **Caminho real (`_handle_ai_turn`) NÃO valida** a ação retornada contra `allowed_actions` (busca por "allowed" entre L4280–L4370 = 0 ocorrências) | [EXISTS] (gap) | `bot_manager.py:4169-4403` |
| `do_not_respond` → silencio, permanece no bloco | [EXISTS] | `bot_manager.py:4313-4315` |
| `send_checkout` → saida CHECKOUT (gera PIX); sem conexão → warning | [EXISTS] | `bot_manager.py:4331-4347` |
| `handoff_human` (ação ou flag) → saida HUMANO; sem conexão → warning | [EXISTS] | `bot_manager.py:4352-4364` |
| Bloco `enabled=false` → encaminha HUMANO (ou fallback), **antes** de chamar a API | [EXISTS] | `bot_manager.py:4193-4199` |
| Ação desconhecida (fora dos branches) → método termina sem ação explícita | [EXISTS] (gap) | após `bot_manager.py:4403` |

### 3.3 Estado, entrada do bloco e ofertas

| Fato | Status | Local |
|---|---|---|
| Chave de estado Redis: `gb:{user_id}:flow_ai_state:{bot_id}:{telegram_user_id}`, TTL 7 dias | [EXISTS] | `bot_manager.py:3839-3841, 3869-3875` |
| `_ai_state_set` faz **merge RMW** (`get` → `update` → `setex`), fail-open | [EXISTS] (scaffolding local, não commitado) | `bot_manager.py:3858-3875` |
| Histórico: últimas 20 mensagens do `BotMessage` | [EXISTS] | `bot_manager.py:3877-3905` |
| `conversation_id` = `c{bot_id}-{telegram_user_id}` | [EXISTS] | `bot_manager.py:4238` |
| `intro_message` enviada **incondicionalmente** na entrada do bloco `ai` (antes de qualquer lógica de IA), desde que não vazia | [EXISTS] | `bot_manager.py:4787-4800` |
| Ofertas do bloco (`step_config.offers`): preserva `active` do input, **sem filtrar inativas** no envio | [EXISTS] (gap) | `bot_manager.py:4076-4089` |
| Oferta derivada do bloco Pagamento (saida CHECKOUT): sempre `active: true` | [EXISTS] | `bot_manager.py:4090-4110` |

### 3.4 Flags e scaffolding v1.1 (desligado)

| Fato | Status | Local |
|---|---|---|
| Flag global `GRIMBOTS_AI_CONTRACT` (default `v1.0`) | [EXISTS] | `internal_logic/core/config.py:78`; `.env.example:33` |
| Gate duplo `_ai_contract_v11_enabled`: exige global `v1.1` **E** `step_config.contract_v11=true` | [EXISTS] (scaffolding local, não commitado) | `bot_manager.py:3909-3917` |
| Payload v1.1 construído por `_ai_v11_payload_kwargs` (profile/resources/policy) | [EXISTS] (scaffolding local, não commitado) | `bot_manager.py:4041-4053` |
| Orçamento de recursos: estourou → reduz `flow_resources` (nunca trunca perfil) | [EXISTS] (scaffolding local, não commitado) | `bot_manager.py:4249-4250` (referência) |
| `.env.example` documenta URL ngrok do motor e flag v1.0 | [EXISTS] | `.env.example:23-33` |

### 3.5 Testes (suíte local, verde no momento da auditoria)

| Suíte | Resultado |
|---|---|
| pytest completo (unitários existentes) | 48/48 |
| Contrato v1.0 (payload/normalização) | 10/10 |
| Dedup de mensagens | 11/11 |
| Fase 6A scaffolding v1.1 (offline) | 21/21 |
| Adapter | 39/39 |

---

## 4. Re-validação de C1–C12 contra o motor (commit `8db1de7`, 2026-10-18)

Legenda: **CONFIRMA** (fato anterior correto) · **MUDA** (fato anterior estava
desatualizado) · **MOTOR** = local no repo `grimbots-ai`.

| # | Resultado | Evidência no motor | Impacto na Grimbots |
|---|---|---|---|
| C1 | **CONFIRMA** | `api/schemas.py:84-148` (`AgentRespondRequest`) | Payload v1.0 casa campo a campo |
| C2 | **CONFIRMA** | `api/schemas.py:85` (`extra="forbid"` só na raiz; submodelos `extra="ignore"` L38/50/59/67/74); handler `api/app.py:80-85` → 422 `VALIDATION_ERROR` genérico | Campo desconhecido **na raiz** → 422 |
| C3 | **MUDA** | `api/schemas.py:126` — `contract_version` **existe** (opcional, só metadado; sozinho não altera o prompt — `api/prompt_builder.py:111-117`) | Versionamento agora tem contraparte no motor (Fase 5, v1.4.0) |
| C4 | **CONFIRMA** | Nenhum código dedicado a incompatibilidade; tabela de erros `docs/API.md:462-474`; sem negociação de versão | Downgrade anti-422 segue inviável |
| C5 | **CONFIRMA** | `no_reply` **fora** do enum `Action` (`api/schemas.py:22-25`); `validator.py:85-86` trata ação fora do enum como **fatal** → 502 `AI_INVALID_RESPONSE` | Motor nunca devolve `no_reply` num 200; o clamp da Grimbots é defesa redundante (bom) |
| C6 | **CONFIRMA** | `api/validator.py:125-134` rebaixa `send_checkout` → `handoff_human` (e força `handoff_human=true`; risk sobe low→medium) quando **não há oferta ativa**; `prompt_builder.py:91` só mostra ofertas `active` | Comentário `bot_manager.py:4071-4073` estava correto |
| C7 | **CONFIRMA** | `docs/HANDOFF-GRIMBOTS.md:41`; `docs/CONTRATO-MOTOR-COMERCIAL-ALINHAMENTO.md:100-102` (ADR 0003); `api/app.py` sem DB/sessão | Grimbots é dona da memória (ADR alinhado) |
| C8 | **MUDA** | `api/schemas.py:120-129` — motor **JÁ ACEITA** `contract_version`/`agent_profile`/`flow_resources`/`context_policy` (opcionais; Fase 5, v1.4.0). Prompt estendido `api/prompt_builder.py:111-130,186-191`. Garantia byte-a-byte quando ausentes | O bloqueio "`extra=forbid` → 422" **não se aplica mais** a esses 4 campos. Ordem de ativação ainda exige coordenação (ver seção 4.1) |
| C9 | **CONFIRMA** | `AgentResponse` (`api/schemas.py:163-175`) **não** tem `reason`/`offer_id`/`state_update` — proposta v1.2 (E0 docs do motor, não implementada) | Formato proposto em `CONTRATO-MOTOR-COMERCIAL-ALINHAMENTO.md:§3` |
| C10 | **MUDA** | Caminho único virou **dois**: legado (byte-a-byte) + estendido `[CONTEXTO ADICIONAL]` (`prompt_builder.py:133-191`); golden byte-a-byte `tests/unit/test_prompt_builder.py:115` + `tests/golden/prompts/` | Legado segue determinístico; mudança é aditiva e testada |
| C11 | **CONFIRMA** | `docs/HANDOFF-GRIMBOTS.md:11` — mesma URL ngrok de `.env.example:23`; header `ngrok-skip-browser-warning: true` (Grimbots já envia) | Endpoint continua válido |
| C12 | **CONFIRMA** | `RATE_LIMITED` 429+Retry-After (`app.py:147-153`), `AI_BUSY` 503 (`app.py:179-184`), `AI_TIMEOUT` 504 (`ollama_client.py:64`→`app.py:185-192`), `AI_INVALID_RESPONSE` 502 (`app.py:226-231`) | Os 4 códigos de retry do cliente são reais |

### 4.1 Divergências a apresentar (regra 3) — nada implementado

1. **Motor aceita v1.1 (C8)** — a premissa do scaffold (`extra=forbid` bloquearia os 4
   campos) está **desatualizada**. O motor os aceita desde a Fase 5. **Ainda assim**,
   a ordem de ativação do próprio motor (`ALINHAMENTO:§1.3`) só permite **enviar** os
   campos após aprovação conjunta e atualização do golden do cliente — não ativamos nada.
3. **Motor tem 6 campos de memória** (`last_assistant_message`, `collected_information`,
   `questions_already_asked`, `offers_already_presented`, `turn_count`, `last_action`) —
   `api/schemas.py:103-118`, **consumidos no prompt** (`prompt_builder.py:159-164`). A
   Grimbots **não os envia** hoje (o próprio motor registra isso como gap —
   `ALINHAMENTO:§2`). Isso é a fase **E-P1** do motor, que depende da plataforma.
4. **O motor publicou o próprio E0 hoje** (`eb328c7`, `8db1de7`): proposta v1.2
   (`docs/CONTRATO-MOTOR-COMERCIAL.md`) + alinhamento (`CONTRATO-MOTOR-COMERCIAL-ALINHAMENTO.md`),
   incluindo ADRs 0008-0011 e **7 decisões abertas** (§9) para revisão conjunta.
5. **O motor já analisou nosso `origin/main`** = `d41b527` e concluiu corretamente que
   o cliente não envia memória nem campos v1.1 (o scaffold v1.1 é **local, não commitado**).
6. **Validator do motor enforça `allowed_actions`** (`validator.py:104-108`: ação fora
   da lista = fatal → 502). Isso **mitiga** o gap G1 da Grimbots (a ação inválida não
   chega a ser executada; vira erro → fallback), mas às custas de retry×3 antes do fallback.
7. **Novos códigos do motor** que o cliente trata como não-retryáveis → fallback:
   `AI_DISABLED_FOR_BOT` 409 (`ai_enabled=false`), `HUMAN_TAKEOVER_ACTIVE` 409
   (`human_takeover=true`), `HISTORY_TOO_LONG` 422 (>20 msgs), `PAYLOAD_TOO_LARGE` 413,
   `VALIDATION_ERROR` 422, `AI_GLOBALLY_DISABLED` 503, `API_KEY_NOT_CONFIGURED` 503.
   Observação: a Grimbots sempre envia `ai_enabled=true`, mas envia `human_takeover`
   do estado (`bot_manager.py:4231`) — se `true` (sticky), o próximo turno receberia
   409. **[A CONFIRMAR em runtime]** se o fluxo volta ao bloco AI nesse estado.

### 4.2 Itens ainda [A CONFIRMAR] (deployment, não código)

| Fato | Por que a confirmar |
|---|---|
| Versão **implantada** no ngrok é a v1.4.0 (com Fase 5)? | O repo tem o código; o ambiente ngrok pode estar em versão anterior. Confirmar via `GET /health` (`version`) |
| A chave `X-API-Key` ativa em `.env` | Não está no repo (`logs/api_key.txt` no lado do motor) |
| Códigos de incompatibilidade futuros (§13) | Dependem de proposta v1.2 aprovada conjuntamente |

---

## 5. Gaps conhecidos do lado Grimbots (resumo; detalhes em `docs/dev/AI_BLOCK_AUDIT_READONLY.md`)

Verificados por leitura direta; **não dependem do motor** para existir. A coluna
"Pós-revalidação do motor" incorpora o resultado da seção 4:

| Gap | Efeito | Local | Pós-revalidação do motor |
|---|---|---|---|
| G1 — `allowed_actions` só é enforced no Mock | Ação do motor fora da lista não é bloqueada **localmente** no caminho real | `ai_service.py:562-563` vs `bot_manager.py:4280-4403` | **Mitigado pelo motor**: `validator.py:104-108` rejeita (fatal→502) → fallback. Ainda assim, gastaria retry×3 |
| G2 — alias `no_reply` inexistente | `no_reply` do motor → `continue` (clamp) | `ai_service.py:25-33,117` | **Inexistente na prática**: motor nunca emite `no_reply` (C5, enum `schemas.py:22-25` + fatal L85-86) |
| G3 — ofertas inativas não filtradas | `active=false` vai no payload | `bot_manager.py:4076-4089` | **Inócuo**: motor filtra na origem (`prompt_builder.py:91`); validator usa só ofertas ativas |
| G4 — `intro_message` incondicional | Enviada mesmo se o bloco/logo depois cair em erro; enviada na entrada sem checar `enabled` (o `enabled` só é checado no turno, em `_handle_ai_turn`) | `bot_manager.py:4787-4800` vs `4193` | Inalterado — gap puramente local |
| G5 — modo `shadow`/`suggestion` sem ramificação | `mode` vai no payload (`bot_manager.py:4243`), mas execução local não muda por modo | `bot_manager.py:4280-4403` | Inalterado; **decisão conjunta**: motor trata `mode` no prompt, não no cliente |

---

## 6. Próximos passos

1. ~~Dono do projeto fornece acesso do repo `grimbots-ai`~~ — **feito** (seção 2).
2. ~~Consultar o Git do motor e re-validar C1–C12~~ — **feito** (seção 4).
3. **Divergências a apresentar/aprovar** (regra 3, seção 4.1): (a) motor já aceita v1.1;
   (b) campos de memória não enviados (E-P1); (4) E0 do motor publicado com 7 decisões
   abertas; (5) canário de `human_takeover` 409.
4. Aguardar aprovação conjunta; **só então** planejar Fase 1 (enforcement local de
   `allowed_actions`, `intro_message`, memória por lead, UI) com testes.

**Nada disto foi implementado. Nenhuma flag foi ativada. O default permanece v1.0
byte-a-byte.**

**Nada disto foi implementado. Nenhuma flag foi ativada. O default permanece v1.0
byte-a-byte.**
