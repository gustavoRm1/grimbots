# D11 — Contra-assinatura (Grimbots ⇄ Motor)

> **Assinatura D11 = compatibilidade validada nos cenários testados.**
> Isto **NÃO** equivale a **aprovação para produção** (sem merge/deploy/ativação).
> Ver limitações e a matriz em `results/MATRIZ_ESPERADO_OBSERVADO.md`.

Contrato: idempotência por `request_id` (ver `EXPECTED.md` e `README.md`).
Aceite: `d11_acceptance.py` → **CONTRATO 9/9 PASS** (S1–S7, S9, S10).

## Lado Grimbots (plataforma) — implementado

- Dedupe por **`message_id`** na entrada (`bot_manager._ai_turn_*`): reserva → conclusão durável.
- D11 2 fases: reserva (`SET NX EX`, 120s) → conclusão (24h) → **release**.
- `409 REQUEST_IN_PROGRESS`: **retryável**, **sem fallback**, **libera a reserva**
  (permite reentrega) e **sem efeitos** — não envia mensagem, não avança fluxo,
  não roteia **checkout**, não roteia **handoff**.
- Cliente honra o header **`Retry-After`** (429/503/409).
- Evidências: `tests/test_d11_dedupe.py` (**14/14**):
  `test_request_in_progress_releases_and_has_no_effects` (step com
  checkout+handoff ligados → `sent=route=state=0`),
  `test_request_in_progress_then_redelivery_succeeds`,
  `test_client_honors_retry_after_header`.

Assinatura Grimbots: **✅ compatibilidade validada nos cenários testados**.

## Lado Motor (AI Gateway) — implementado pelo dev

- Commit **`444d4a2`** (D11) / crosscheck **`4898325`**; docs: v1.6.0.
- [x] Deduplicar por `request_id` (TTL conclusão 1 h; em-andamento `max(120, timeout+30)`).
- [x] Sucesso repetido → replay (header `X-D11-Replay`), sem nova execução.
- [x] Em andamento → `409 REQUEST_IN_PROGRESS` + `Retry-After`.
- [x] Falha/timeout → `release` (retry permitido).
- [x] Verificação **independente** Grimbots: **CONTRATO 9/9 PASS**.

### Pendências do motor (bloqueiam "pronto para produção", não o contrato)

- [ ] **Persistência do store de dedupe** (hoje in-memory / single-instance) —
  cobre reinício, múltiplas instâncias/workers e falha entre geração e persistência.
- [ ] **Versão do `/health`**: hoje `version="1.0.0"` (docs dizem v1.6.0) → alinhar.

Assinado por (Grimbots): **✅ compatibilidade validada nos cenários testados** —
Data: 2026-10-19

Assinatura do motor (compatibilidade, não produção): **⏳ pendente**

```
Assinado por: ______________________  Data: ____-__-__
d11_acceptance.py: __/9 CONTRATO PASS
Ressalva: assinatura de COMPATIBILIDADE nos cenários testados — não é aprovação
          para produção (limitações §6 da matriz permanecem).
```
