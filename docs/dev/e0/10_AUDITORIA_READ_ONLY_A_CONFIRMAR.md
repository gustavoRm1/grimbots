# 10 — Auditoria Read-Only: Grimbots ↔ grimbots-ai (Out/2026)

**Escopo**: somente leitura. Nenhum arquivo funcional foi alterado, nenhuma feature foi
ativada. Este documento formaliza as regras permanentes de colaboração entre os dois
repos e audita o estado atual da integração do bloco Atendimento IA, marcando como
**[A CONFIRMAR]** tudo que não pôde ser verificado no código neste momento.

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

## 2. Divergência de acesso ao repositório do motor — BLOQUEIO

Conforme regra 2, o Git remoto do `grimbots-ai` deveria ser consultado antes desta
auditoria. **Não foi possível acessá-lo:**

| Tentativa | Resultado |
|---|---|
| Clone local (`~/Documents`, home, `find` amplo) | **Não encontrado** — nenhum diretório `grimbots-ai` existe nesta máquina |
| `https://github.com/gustavoRm1/grimbots-ai` | **404** (inexistente ou privado) |
| `gh` CLI | **Não autenticado** nesta máquina — não é possível listar/buscar repos privados |

**Consequência**: toda afirmação sobre o comportamento **do motor** (schemas, validação,
códigos de erro, aceitação de campos novos) é **[A CONFIRMAR]** nesta auditoria, mesmo
quando registrada em documentos anteriores como "fato confirmado" — essa confirmação
foi feita em Out/2026 via investigação direta no projeto do motor, e **não pôde ser
re-verificada agora contra o Git do motor** (regra 3).

**Dado necessário do dono do projeto**: URL/acesso correto do repo `grimbots-ai`
(ex.: `github.com/<owner>/grimbots-ai`, ou instruções de acesso). Sem isso, as regras
2–5 ficam bloqueadas para tarefas futuras de IA.

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

## 4. Itens [A CONFIRMAR] — dependem do motor (repo `grimbots-ai` inacessível)

Nenhum destes itens pôde ser re-verificado contra o Git do motor nesta auditoria.
Marcados como "fato confirmado" apenas em documentos da Grimbots (investigação anterior
de Out/2026, `docs/dev/FASE_6A_CONTRATO.md:§13-14`); **re-consultar o repo do motor
(regras 2–3) antes de qualquer decisão**:

| # | Fato a confirmar | Origem da afirmação atual | Por que importa |
|---|---|---|---|
| C1 | Schema `AgentRespondRequest` em `api/schemas.py:84` (nomes/campos exatos) | `FASE_6A_CONTRATO.md:§14` | Payload Grimbots precisa casar campo a campo |
| C2 | `extra=forbid` na raiz do request → campo desconhecido = **422 VALIDATION_ERROR** genérico | `FASE_6A_CONTRATO.md:§13-14`; comentário `bot_manager.py:3905-3907` | Motivo do bloqueio de ativação v1.1 |
| C3 | Motor **não possui** `contract_version` (identificação de v1.0 = ausência de campos) | `FASE_6A_CONTRATO.md:§13-14` | Sem isso, versionamento proposto não tem contraparte |
| C4 | Motor **não possui** códigos de erro dedicados de incompatibilidade de contrato, nem negociação de versão | `FASE_6A_CONTRATO.md:§13` | Downgrade anti-422 fica inviável (whitelist §13) |
| C5 | Motor emite/aceita **`no_reply`** como action? | Ausente no lado Grimbots; sem acesso ao motor | Se emitir, vira `continue` (clamp `ai_service.py:117`) — mascaramento |
| C6 | Motor **rebaixa `send_checkout` → `handoff_human` quando não há oferta ativa** | Comentário `bot_manager.py:4071-4073` (afirmação sobre o motor) | Define se filtrar ofertas inativas localmente quebra venda |
| C7 | Motor é **stateless** (sem memória entre requests; tudo vem no payload) | `ai_service.py:9` (docstring); `FASE_6A_CONTRATO.md` | Define dono da memória por lead (decisão ADR: Grimbots-owned) |
| C8 | Motor aceita hoje os campos v1.1 (`agent_profile`/`flow_resources`/`context_policy`/`contract_version`)? **Status mudou desde Out/2026?** | Scaffolding Grimbots assume que **não** (flag off) | Pré-condição para ativar v1.1 (regra 4) |
| C9 | Motor emite campos novos (`reason`, `offer_id`, `state_update`)? | Proposta v1.2 (não implementada no Grimbots, não aprovada) | Nomes/formato precisam de contrato conjunto |
| C10 | Prompt builder do motor (`api/prompt_builder.py:107`, caminho único determinístico) — mudou? | `FASE_6A_CONTRATO.md:§14` | Golden tests de prompt dependem disso |
| C11 | URL atual do motor (ngrok em `.env.example:23` ainda é válida?) | `.env.example` | Endpoint do amb. de teste |
| C12 | Códigos `RATE_LIMITED`/`AI_BUSY`/`AI_TIMEOUT`/`AI_INVALID_RESPONSE` são os códigos **reais** emitidos pelo motor? | Definição client-side `ai_service.py:77-80` | Retry só dispara de verdade se o motor emitir esses códigos |

---

## 5. Gaps conhecidos do lado Grimbots (resumo; detalhes em `docs/dev/AI_BLOCK_AUDIT_READONLY.md`)

Verificados por leitura direta; **não dependem do motor** para existir, mas o
comportamento observado em produção depende de C5/C6/C8:

| Gap | Efeito | Local |
|---|---|---|
| G1 — `allowed_actions` só é enforced no Mock | Ação do motor fora da lista não é bloqueada no caminho real | `ai_service.py:562-563` vs `bot_manager.py:4280-4403` |
| G2 — alias `no_reply` inexistente | `no_reply` do motor → `continue` (clamp) | `ai_service.py:25-33,117` |
| G3 — ofertas inativas não filtradas | `active=false` vai no payload (comportamento depende de C6) | `bot_manager.py:4076-4089` |
| G4 — `intro_message` incondicional | Enviada mesmo se o bloco/logo depois cair em erro; enviada na entrada sem checar `enabled` (o `enabled` só é checado no turno, em `_handle_ai_turn`) | `bot_manager.py:4787-4800` vs `4193` |
| G5 — modo `shadow`/`suggestion` sem ramificação | `mode` vai no payload (`bot_manager.py:4243`), mas execução local não muda por modo | `bot_manager.py:4280-4403` |

---

## 6. Próximos passos (bloqueados até desbloqueio)

1. **Dono do projeto fornece URL/acesso do repo `grimbots-ai`** (seção 2).
2. Consultar o Git do motor (regras 2–3) e **re-validar C1–C12**; atualizar este
   documento com o resultado real.
3. Apresentar divergências (se houver) antes de qualquer implementação (regra 3).
4. Só então planejar Fase 1 (enforcement de `allowed_actions`, `intro_message`,
   memória por lead, UI) com testes e aprovação explícita.

**Nada disto foi implementado. Nenhuma flag foi ativada. O default permanece v1.0
byte-a-byte.**
