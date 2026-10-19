# 16 — D11: deduplicação de turno (at-most-once) no lado Grimbots

> **Status:** implementado (`_ai_turn_claim/_ai_turn_complete/_ai_turn_release`
> em `bot_manager.py`). **Ativação de produção inalterada.** Complementa o
> hand-off E1/E2 (doc 15 §6): o motor **já deduplica** por `request_id`
> (commit `444d4a2`, verificado em `4898325` e re-verificado em `b81dcad` — doc 19).
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
`enabled check → D9 guard (human_takeover) → D11 reserve → try: <gateway + efeitos> → finally: release|complete`.

O `finally` **conclui** por padrão, mas **libera** quando a falha é **retryável e
sem efeito** (`409 REQUEST_IN_PROGRESS`): assim a reentrega do mesmo `message_id`
pode reprocessar em vez de o turno ser descartado por 24 h.

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

## Motor (fora deste repo) — implementado e verificado

- **D11 no motor:** deduplica por `request_id` (commit `444d4a2`; verificação
  independente em `4898325`, re-executada em `b81dcad`). **CONTRATO 9/9 PASS** no
  `handoff/d11/`.
- **Pacote de hand-off executável:** `handoff/d11/` (S1–S10 + matriz,
  esperado × observado, contra-assinatura) — ver **doc 19**.
- **Contrato 409 `REQUEST_IN_PROGRESS`** (entrega concorrente do mesmo
  `request_id`): a Grimbots trata como **retryável**, **sem fallback**, **sem
  efeitos** (msg/fluxo/checkout/handoff) e **libera a reserva** para a reentrega.
  O cliente respeita o header **`Retry-After`** (`_sleep`). Testes:
  `test_request_in_progress_releases_and_has_no_effects`,
  `test_request_in_progress_then_redelivery_succeeds`,
  `test_client_honors_retry_after_header`.
- **D6:** limites conferidos contra os schemas do motor (commit atual): campo no
  limite → 200; 1 acima → 422 (doc 18). Hand-off S9/S10 comprova end-to-end.

## Evidência de efeito comercial não duplicado (plataforma)

`tests/test_d11_dedupe.py` prova que um replay **não** repete: envio de mensagem,
avanço/persistência de fluxo, **checkout** e **handoff** (`_run_turn_twice` conta
`send_telegram_message`, `_ai_route`, `_ai_state_atomic`).
