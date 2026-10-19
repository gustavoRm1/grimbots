# Matriz de compatibilidade v1.0 ↔ v1.1 (scaffolding) ↔ v1.2 (proposta)

> Legenda: **[E]** existe hoje (v1.0) · **[S]** scaffolding v1.1 escrito,
> desligado · **[P]** proposta v1.2 (não implementada) · **[J]** detalhe pendente
> de decisão conjunta.

## 1. Payload — request (Grimbots → motor)

| Campo | v1.0 | v1.1 scaffolding | v1.2 proposta | Compatibilidade |
|---|---|---|---|---|
| `request_id`, `seller_id`, `bot_id`, `conversation_id`, `bot_user_id` | [E] | inalterado | inalterado | total |
| `mode` | [E] | inalterado | inalterado | total |
| `bot_config.{name,personality,tone,boldness,message_length,emoji_level,commercial_goal}` | [E] | inalterado | pode ganhar campos opcionais (`mission`, `rules`) [P] | aditivo |
| `conversation_state.{funnel_stage,lead_temperature,human_takeover,ai_enabled}` | [E] | inalterado | inalterado | total |
| `lead.{name,interest,objection}` | [E] | inalterado | `interest` passa a ser sugestível via `state_update` [P] | aditivo |
| `recent_messages` (≤20) | [E] | inalterado | inalterado (janela curta) | total |
| `conversation_summary` (≤4000) | [E] | inalterado | ganha semântica de resumo persistente [P] | total (semântica nova) |
| `available_offers` (≤20, com `active`) | [E] | inalterado | filtro de `active=false` é [J] (hoje: não filtra) | [J] |
| `allowed_actions` | [E] | inalterado | enforcement no caminho real é [P]/[J] | [J] |
| `contract_version` | ausente | [S] `"1.1"` (opt-in) | [P] valor final [J] | opt-in |
| `agent_profile` | ausente | [S] (validação + anti-injeção) | [P] pode absorver `knowledge`/`rules` do seller | opt-in |
| `flow_resources` | ausente | [S] (projeção segura, sem URLs) | inalterado | opt-in |
| `context_policy` | ausente | [S] | inalterado | opt-in |
| objeto de memória (`memory` ou campos soltos) | ausente | ausente | [P] nome/formato [J] | opt-in |

## 2. Resposta — response (motor → Grimbots)

| Campo | v1.0 | v1.1 scaffolding | v1.2 proposta | Compatibilidade |
|---|---|---|---|---|
| `message`, `intent`, `lead_temperature`, `funnel_stage`, `action`, `next_question`, `handoff_human`, `risk`, `validation`, `usage` | [E] | inalterado | inalterado | total |
| `reason` | ausente | ausente | [P] string ≤200, uso em auditoria | aditivo; Grimbots ignora se ausente |
| `offer_id` | ausente | ausente | [P] string ≤80, validado contra ofertas | aditivo; validação defensiva se inválido |
| `state_update` | ausente | ausente | [P] chaves permitidas apenas; merge RMW; chaves negadas descartadas | aditivo; ausência = hoje |
| alias `no_reply` | não existe (vira `continue`) | — | [P]/[J] | mudança de enum é [J] |

## 3. Estado persistido por lead (Redis)

| Chave | v1.0 | v1.1 scaffolding | v1.2 proposta |
|---|---|---|---|
| `lead_temperature`, `funnel_stage`, `intent`, `last_intent`, `objection` | [E] | inalterado | inalterado |
| `human_takeover` | não persistido | [S] sticky (gated) | inalterado |
| `collected_information` | — | — | [P] merge por chave |
| `questions_already_asked` | — | — | [P] append + dedup |
| `offers_already_presented` | — | — | [P] append |
| `turn_count` | — | — | [P] calculado pela Grimbots |
| `last_action` | — | — | [P] calculado pela Grimbots |
| `last_assistant_message` | — | — | [P] calculado pela Grimbots |
| `conversation_summary` (persistido) | — | — | [P] motor gera / Grimbots persiste |

Nota: no `main` commitado, `_ai_state_set` sobrescreve o objeto inteiro; o
merge RMW está no scaffolding local. A v1.2 depende do merge para não apagar
chaves — incluído no escopo funcional futuro, gated.

## 4. Compatibilidade de cenários

| Cenário | Resultado |
|---|---|
| Grimbots nova + motor só v1.0, flags off | v1.0 byte-a-byte [E/garantido por teste] |
| Grimbots nova + motor v1.2, flags off | v1.0 byte-a-byte |
| Grimbots nova + motor v1.2, flag scaffolding on, flag memória off | v1.0 + `agent_profile`/`flow_resources`/`context_policy` |
| Grimbots nova + motor v1.2, ambas on | pacote completo |
| Grimbots antiga + motor v1.2 | motor opera em v1.0 (campos ausentes tolerados) |
| Rollback de flags | restaura v1.0 sem deploy |

## 5. O que NÃO muda nesta evolução

- Enums de ação/intenção/temperatura/funil/risco/modo (sem novo valor sem [J]).
- Endpoints, auth, limites de bytes do servidor.
- Comportamento de fallback, `do_not_respond`, roteamento por conexão.
- Integração de pagamento (checkout continua sendo bloco `payment`).
