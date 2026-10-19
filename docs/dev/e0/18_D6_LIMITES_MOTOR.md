# 18 — D6: limites do REQUEST alinhados ao schema do motor

> **Status:** implementado. Fonte autoritativa = `api/schemas.py` do Grimbots AI
> Gateway. Grimbots clampa **exatamente no limite do motor** (nunca acima);
> valores no limite passam **inalterados**. Ativação v1.1 inalterada.

## Tabela canônica (`MOTOR_REQUEST_LIMITS` em `ai_service.py`)

| Campo | Limite do motor | Grimbots | Ajuste |
|---|---|---|---|
| `request_id` / `seller_id` / `bot_id` / `conversation_id` / `bot_user_id` | 80 | 80 | — |
| `bot_config.name` | 60 | 60 | — |
| `bot_config.personality` (itens) | 12 | **12** | 6 → 12 |
| `bot_config.tone` | 60 | **60** | 40 → 60 |
| `bot_config.boldness` | 1..5 | 1..5 | — |
| `bot_config.message_length` | 20 | 20 | — |
| `bot_config.emoji_level` | 20 | 20 | — |
| `bot_config.commercial_goal` | 80 | **80** | 60 → 80 |
| `lead.name` / `lead.interest` / `lead.objection` | 60 / 120 / 120 | 60 / 120 / 120 | — |
| `recent_messages[].content` | 4000 | **4000** | 1200 → 4000 |
| `conversation_summary` | 4000 | 4000 | — |
| `available_offers` | 20 | 20 | — |
| `offer.id` / `offer.name` / `offer.price` / `offer.checkout_url` | 64 / 120 / 40 / 400 | 64 / 120 / 40 / 400 | — |
| `last_assistant_message` | 2000 | 2000 | — |
| `questions_already_asked` (itens / item) | 20 / 300 | 20 / 300 | — |
| `offers_already_presented` (itens / item) | 20 / 120 | 20 / 120 | — |
| `collected_information` (chaves / key / value) | 20 / 60 / 200 | 20 / 60 / 200 | 30 / 300 → 20 / 200 |
| `turn_count` | 0..100 | 0..100 | — |
| `contract_version` | 10 | 10 | — |

**Stricter (permitido, documentado):** `bot_config.personality[]` item ≤ 40
(o motor não impõe limite por item; 40 é defesa de payload).

## Casos de teste (limite e limite excedido)

Em `tests/test_phase6a_contract_v11.py`:
- `test_bot_config_clamps_match_motor_limits` — excedido → clamp exato.
- `test_bot_config_at_limit_is_untouched` — no limite → inalterado.
- `test_message_content_clamps_match_motor_limit` — 4000 inalterado; 4001 → 4000.
- `test_lead_clamps_match_motor_limits` / `test_offer_clamps_match_motor_limits`.
- `test_d6_request_limits_table_stays_within_motor` — tabela ↔ constantes.
- `tests/test_agent_respond_contract.py::test_history_and_offers_limits`.

## Garantia

Para **qualquer** campo do request, `len(valor_enviado) ≤ limite_do_motor`, logo
um payload montado pela Grimbots **nunca** gera `422 VALIDATION_ERROR` por
tamanho. Confirmado também por integração (`tests/integration/test_motor_live.py`).
