# D11 — Contra-assinatura (Grimbots ⇄ Motor)

Contrato: idempotência por `request_id` (ver `EXPECTED.md` e `README.md`).
Aceite: `d11_acceptance.py` → **6/6 PASS**.

## Lado Grimbots (plataforma) — implementado

- D11 em 2 fases: reserva `SET NX EX` (120s) → conclusão (24h) → release.
- Guarda de efeito comercial: mensagem / avanço de fluxo / checkout / handoff
  não duplicam em replay.
- `REQUEST_IN_PROGRESS` tratado como **retryável** e **sem fallback**.
- Evidências: `tests/test_d11_dedupe.py` (12/12) e `docs/dev/e0/16_D11_AT_MOST_ONCE.md`.

Assinatura Grimbots: **✅ implementado e testado** (branch `feat/e4-offline-d11-hardening`).

## Lado Motor (AI Gateway) — pendente

- [ ] Deduplicar por `request_id` (janela TTL ≥ 10 min).
- [ ] Sucesso repetido → replay sem nova execução do modelo.
- [ ] Em andamento → `409 REQUEST_IN_PROGRESS` (retryável).
- [ ] Falha/timeout → liberar reserva (retry permitido).
- [ ] `d11_acceptance.py` → **6/6 PASS** no checkout do motor.

Assinatura Motor: **⏳ pendente** — nome/data:

```
Assinado por: ______________________  Data: ____-__-__
Resultado d11_acceptance.py: __/6 PASS
```
