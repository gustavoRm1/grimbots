# Contrato v1.0 — estado atual implementado

> **Classificação:** [EXISTS] — tudo abaixo foi verificado no código desta branch.
> Este documento descreve o contrato **como está hoje**, não como deveria ser.
> O Gateway `grimbots-ai` é stateless, usa `extra=forbid` (campo desconhecido → 422)
> e a Grimbots é dona do estado por conversa.

## 1. Transporte e autenticação

| Item | Valor | Evidência |
|---|---|---|
| Endpoint | `POST /v1/agent/respond` | `ai_service.py:6` |
| Auth | header `X-API-Key: gp_...` (+ `ngrok-skip-browser-warning`) | `ai_service.py:8` |
| Statelessness | motor não guarda estado; contexto vai no payload | `ai_service.py:7` |
| `extra=forbid` | nunca enviar `model`/`system_prompt`; campo extra → 422 | `ai_service.py:7` |
| Timeout padrão | 90s (`GRIMBOTS_AI_TIMEOUT`) | `ai_service.py` Config |
| Retry | só códigos 5xx `RATE_LIMITED`, `AI_BUSY`, `AI_TIMEOUT`, `AI_INVALID_RESPONSE`; backoff 2/4/8s, máx. 3 tentativas, `Retry-After` ≤ 30s | `ai_service.py:63-68` |

## 2. Identificadores enviados (payload)

Montados em `bot_manager.py:4217-4222`:

| Campo | Formato | Dono |
|---|---|---|
| `request_id` | `gb-{bot_id}-{telegram_user_id}-{uuid10}` (≤80) | Grimbots |
| `seller_id` | `user_id` do vendedor (dono do bot) | Grimbots |
| `bot_id` | id do bot | Grimbots |
| `conversation_id` | `c{bot_id}-{telegram_user_id}` | Grimbots |
| `bot_user_id` | `telegram_user_id` do lead | Grimbots |

**Isolamento [EXISTS]:** a combinação (seller, bot, telegram_user) define a
conversa. Estado em Redis usa a chave
`gb:{user_id}:flow_ai_state:{bot_id}:{telegram_user_id}` (TTL 7 dias) —
`bot_manager.py:3839-3841`. Histórico lido de `BotMessage` filtrando por
`(bot_id, telegram_user_id)` — `bot_manager.py:3877-3885`. Não há compartilhamento
entre leads, bots ou vendedores.

## 3. Payload v1.0 (body exato)

Construído por `build_payload()` — `ai_service.py:170-245`. Todos os campos
abaixo são **sempre** enviados (v1.0 byte-a-byte):

```
request_id, seller_id, bot_id, conversation_id, bot_user_id, mode,
bot_config: {name, personality[], tone, boldness(1-5), message_length,
             emoji_level, commercial_goal},
conversation_state: {funnel_stage, lead_temperature, human_takeover, ai_enabled},
lead: {name, interest, objection},
recent_messages: [{role, content}] máx 20, content ≤ 1200 chars,
conversation_summary: ≤ 4000 chars,
available_offers: [{id, name, price, checkout_url, active}] máx 20,
allowed_actions: [enum] (vazio ⇒ todas as 7)
```

Limites do servidor: payload ≤ 65536 bytes; `request_id` ≤ 80 —
`ai_service.py:49-55`.

### Enums do contrato [EXISTS] (`ai_service.py:25-42`)

- **ACTIONS (7):** `continue`, `ask_question`, `present_offer`, `send_checkout`,
  `handoff_human`, `pause`, `do_not_respond`
- **INTENTS (8):** `saudacao`, `duvida`, `interesse`, `objecao`, `compra`,
  `suporte`, `risco`, `outro`
- **LEAD_TEMPERATURES (3):** `cold`, `warm`, `hot`
- **FUNNEL_STAGES (7):** `new`, `connection`, `qualification`, `offer`,
  `checkout`, `customer`, `human`
- **RISKS (3):** `low`, `medium`, `high`
- **MODES (3):** `shadow`, `suggestion`, `auto`
- **ROLES (3):** `user`, `assistant`, `system`

## 4. Resposta v1.0 (campos interpretados)

Normalizada em `AIResult` — `ai_service.py:94-163`:

| Campo | Tipo | Uno na Grimbots |
|---|---|---|
| `message` | string | enviada ao lead (personalizada) |
| `intent` | enum | persistido em estado (`last_intent`) |
| `lead_temperature` | enum | persistido em estado |
| `funnel_stage` | enum | persistido em estado |
| `action` | enum | **executado** (ver §5) |
| `next_question` | string | enviada como 2ª mensagem se `action=ask_question`, com dedup P1 |
| `handoff_human` | bool | força roteamento HUMANO (mesmo sem `action`) |
| `risk` | enum | logado |
| `validation` | `{valid, errors}` | se `valid=false`, logado (turno segue) |
| `usage` | dict | logado (latência) |

**Normalização defensiva [EXISTS]:** `action` fora do enum vira `continue`;
`risk` desconhecido vira `low` — `ai_service.py:115-117, 121`.

## 5. Execução de ação no caminho real [EXISTS]

Fluxo em `_handle_ai_turn` — `bot_manager.py:4166-4367`:

1. `do_not_respond` → silêncio intencional, permanece no bloco
   (`bot_manager.py:4313-4315`).
2. `continue` / `ask_question` / `present_offer` / `pause` → envia `message`
   (e `next_question` com dedup) e permanece no bloco
   (`bot_manager.py:4317-4330`).
3. `send_checkout` → segue pela saída `checkout`; se não conectada → aviso +
   fallback (`bot_manager.py:4331-4347`).
4. `handoff_human` (ou `handoff_human=true`) → segue pela saída `handoff`; se
   não conectada → aviso + fallback (`bot_manager.py:4349-4360`).
5. Ação desconhecida (defensivo) → fallback (`bot_manager.py:4362-4367`).

**GAP conhecido [EXISTS]:** o `allowed_actions` vai no payload
(`bot_manager.py:4242`), mas a resposta **não é validada contra ele** no caminho
real. Só o `MockAIService` faz o clamp (`ai_service.py:562-563`). Se o motor
devolver uma ação dentro do enum mas fora de `allowed_actions`, a Grimbots
executa. Documentado em `05_ADR_VALIDACAO_DEFENSIVA.md`.

## 6. Checkout e segurança [EXISTS]

- O checkout é roteado para o bloco `payment` já conectado, que gera o PIX pela
  integração de pagamento existente (`bot_manager.py` — branch `payment` em
  `_execute_flow_recursive`).
- A IA **não** inventa valores: valores vêm das ofertas do bloco ou do bloco
  Pagamento. A IA não confirma pagamentos; só roteia.
- Valores das ofertas digitadas no bloco são strings normalizadas em
  `_ai_build_offers` (`bot_manager.py:4070-4110`).

## 7. Fallback e erros [EXISTS]

| Situação | Comportamento |
|---|---|
| `enabled=false` no turno | tenta saída HUMANO; senão fallback (`bot_manager.py:4193-4199`) |
| Payload inválido (local) | fallback (`bot_manager.py:4262-4268`) |
| Erro do Gateway (códigos) | log + fallback; retry automático para 5xx retryables (`ai_service.py`) |
| Erro inesperado | log + fallback (`bot_manager.py:4275-4281`) |
| Resposta `valid=false` | log; turno segue normalmente (`bot_manager.py:4283-4285`) |
| Saída `checkout`/`handoff` não conectada | aviso + fallback |

## 8. Modos `shadow` / `suggestion` / `auto` [EXISTS]

O `mode` é enviado no payload (`bot_manager.py:4243`) e **apenas isso**. A
Grimbots **não** ramifica execução por modo: qualquer ação retornada é
executada. O efeito do modo (se houver) é do lado do motor. Portanto, hoje,
`suggestion` não impede a Grimbots de agir se o motor devolver ação de checkout.
Documentado como risco em `09_RISCOS_CRITERIOS_ACEITE.md`.

## 9. Ofertas [EXISTS]

- Fonte 1: `step_config.offers` digitadas no bloco.
- Fonte 2: bloco `payment` ligado na saída `checkout` (catálogo).
- Ofertas com `active=false` **são enviadas** (flag `active` vai no payload,
  mas nada filtra). [EXISTS] — decisão de filtrar é [JOINT]
  (`07_COMPORTAMENTO_ATUAL_REGRAS.md`).

## 10. Auditoria [EXISTS]

Cada turno é gravado em `ai_generations` (payload, result ou `error_code`) —
`bot_manager.py:4140-4160`, chamado em `bot_manager.py:4264, 4272, 4286`.

## 11. Estado persistido por lead (hoje) [EXISTS]

| Chave | Origem | Observação |
|---|---|---|
| `lead_temperature` | resposta do motor | |
| `funnel_stage` | resposta do motor (ou config fixa do bloco) | |
| `intent` | resposta do motor | |
| `last_intent` | resposta do motor | interno, nunca vai no payload |
| `objection` | payload enviado | eco do turno anterior |
| `human_takeover` | só no scaffolding v1.1 | sticky (nunca volta a false) |

Escrito por `_ai_state_set` (`bot_manager.py:3859-3875`). No scaffolding local
(não commitado nesta branch base) faz merge read-modify-write; na versão
commitada (`d41b527`) o `setex` sobrescreve o objeto inteiro.

## 12. Mensagem de abertura [EXISTS]

Enviada incondicionalmente na entrada do bloco (`bot_manager.py:4790-4800`),
mesmo com `enabled=false` (que só age no primeiro turno). Sem proteção de
reenvio em reentradas do bloco.

## 13. Scaffolding v1.1 presente mas desligado [EXISTS nesta branch de trabalho]

Presente nos arquivos modificados locais (não commitados em `main`):

- Flag global `GRIMBOTS_AI_CONTRACT` (default `v1.0`) — `config.py:78`.
- Flag por bloco `step_config.contract_v11` — `bot_manager.py:3909-3917`.
- Campos opcionais no payload: `contract_version`, `agent_profile`,
  `flow_resources`, `context_policy` — só entram quando fornecidos
  (`ai_service.py:226-240`).
- `human_takeover` sticky gated por v1.1 — `bot_manager.py:4294-4301`.

**Nada disso é enviado ao Gateway com as flags desligadas** (default). O corpo
v1.0 permanece byte-a-byte (garantido por `tests/test_phase6a_contract_v11.py`).
