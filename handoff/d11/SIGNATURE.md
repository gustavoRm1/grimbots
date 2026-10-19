# D11 — Contra-assinatura (Grimbots ⇄ Motor)

Contrato: idempotência por `request_id` (ver `EXPECTED.md` e `README.md`).
Aceite: `d11_acceptance.py` → **CONTRATO 9/9 PASS** (S1–S7, S9, S10).

## Lado Grimbots (plataforma) — implementado

- Dedupe por **`message_id`** na entrada (`bot_manager._ai_turn_*`): reserva → conclusão durável.
- D11 2 fases: reserva (`SET NX EX`, 120s) → conclusão (24h) → **release**.
- `409 REQUEST_IN_PROGRESS`: **retryável**, **sem fallback**, **libera a reserva**
  (permite reentrega); **não** envia mensagem, **não** avança fluxo/checkout/handoff.
- Cliente honra o header **`Retry-After`** (429/503/409).
- Evidências: `tests/test_d11_dedupe.py` (**14/14**) — inclui
  `test_client_honors_retry_after_header`,
  `test_request_in_progress_releases_and_has_no_effects`,
  `test_request_in_progress_then_redelivery_succeeds`.

Assinatura Grimbots: **✅ implementado e verificado**.

## Lado Motor (AI Gateway) — implementado pelo dev

- Commit **`444d4a2`** (D11) / crosscheck **`4898325`**; docs: v1.6.0.
- [x] Deduplicar por `request_id` (TTL conclusão 1 h; em-andamento `max(120, timeout+30)`).
- [x] Sucesso repetido → replay (header `X-D11-Replay`), sem nova execução.
- [x] Em andamento → `409 REQUEST_IN_PROGRESS` + `Retry-After`.
- [x] Falha/timeout → `release` (retry permitido).
- [x] Verificação **independente** Grimbots: **CONTRATO 9/9 PASS** (commit `4898325`).

Divergências reportadas (não bloqueiam o aceite):
- `service_version` ainda reporta `1.0.0` (docs dizem v1.6.0).
- Store **in-memory** (single-instance) — limitação S8 documentada.

Assinatura Motor: **⏳ pendente** — nome/data:

```
Assinado por: ______________________  Data: ____-__-__
Resultado d11_acceptance.py: __/9 CONTRATO PASS
```
