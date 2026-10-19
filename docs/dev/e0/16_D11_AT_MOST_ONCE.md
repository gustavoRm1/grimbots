# 16 — D11: deduplicação de turno (at-most-once) no lado Grimbots

> **Status:** implementado (`_ai_turn_claim/_ai_turn_complete/_ai_turn_release`
> em `bot_manager.py`). **Ativação de produção inalterada.** Complementa o
> hand-off E1/E2 (doc 15 §6): o motor ainda **não** deduplica por `request_id`.
>
> **Escopo:** garantir que **um mesmo `message_id` de entrada Telegram** produza
> **no máximo um turno de IA**, mesmo com redelivery/duplicidade/retry.

## Modelo de 2 fases

A chave é `gb:{user_id}:ai_turn_done:{bot_id}:{telegram_user_id}:{inbound_message_id}`.

| Fase | Operação | TTL | Objetivo |
|---|---|---|---|
| **Reserva** | `SET key "reserved" NX EX 120` | 120 s (`_AI_TURN_RESERVE_TTL`) | barra duplicata concorrente durante o processamento |
| **Conclusão** | `SET key "done" EX 86400` | 24 h (`_AI_TURN_DONE_TTL`) | barra replay do mesmo `message_id` após sucesso |
| **Liberação** | `DEL key` | — | só em falha **antes** de efeito observável; permite retry legítimo |

Ordem no `_handle_ai_turn`:
`enabled check → D9 guard (human_takeover) → D11 reserve → try: <gateway + efeitos> → finally: complete`.

**Fail-open:** sem `message_id` ou sem Redis (ausente/erro) → **processa
normalmente** (nunca descarta turno por indisponibilidade do dedupe).

## Casos de falha validados (`tests/test_d11_dedupe.py`, 8/8)

| Caso | Cenário | Resultado esperado |
|---|---|---|
| Reserva | 1º turno `reserved`; 2º (mesmo `message_id`) **bloqueado** | 1 efeito |
| Conclusão durável | após `complete`, duplicata continua bloqueada (24 h) | 1 efeito |
| **Falha após reserva** | gateway lança `AI_BUSY` **após** a reserva | chave fica `reserved` e **bloqueia só até o TTL (120 s)**; depois novo processamento é permitido |
| Release | falha **sem** efeito → `release` (`DEL`) | retry **imediato** permitido |
| Concorrência | 20 threads no mesmo `message_id` | **1 vencedor** |
| Fail-open | `message_id` ausente / Redis `None` / Redis lança | **processa** (nunca perde turno) |
| Efeito antes da falha | resposta enviada e depois erro de persistência | reserva é **concluída** no `finally` (dedupe preservado) |

## Limites conhecidos (at-most-once, **não** exactly-once)

1. **Não é exactly-once.** Se o processo cair **entre enviar a mensagem e marcar
   `done`**, o TTL de 120 s expira e a duplicata **pode reprocessar** →
   **possível mensagem duplicada**. Mitigação plena depende do **motor deduplicar
   por `request_id`** (hand-off D11 / doc 15 §6).
2. **Ventana de 120 s** para falha-após-reserva. `processamento > TTL` reabre a
   janela caso o `complete` nunca ocorra.
3. **Retenção de `done` = 24 h.** Replay após 24 h não é barrado pelo lado
   Grimbots (aceitável para redelivery de Telegram; não é anti-abuso de longo prazo).
4. **Chave por `message_id` de entrada.** Dois `message_id` distintos com o mesmo
   texto **não** são deduplicados (por design).
5. **Fail-open** prioriza disponibilidade: se o Redis cair, o dedupe deixa de agir
   (trade-off explícito, alinhado a "nunca engolir turno do cliente").
6. **Não cobre** estados de conversa / idempotência de efeitos colaterais de
   negócio (ex.: criar pedido) — fora do escopo desta camada.

## Pendência do motor (fora deste repo)

- **D11 no motor:** deduplicar por `request_id` (janela de idempotência) para
  fechar o limite (1) acima. Aceite descrito no doc 15 §6 (E1/E2 + D11).
