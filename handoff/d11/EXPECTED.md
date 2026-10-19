# D11 — resultado esperado por cenário (critério de aceite)

> Aceite: `d11_acceptance.py` → **CONTRATO 9/9 PASS** (S1–S7, S9, S10).
> S8 é cenário de **limitação** documentada (não conta para o aceite).
> A chave de dedupe é `request_id` (o motor **não** recebe `message_id`).

## Cenários de CONTRATO

| ID | Cenário | Esperado | Métrica observada |
|---|---|---|---|
| S1 | mensagem duplicada (mesmo `request_id`, 2 envios) | 200 + 200; **1** chamada ao modelo | contador de `POST /api/generate` no mock |
| S2 | falha após reservar (backend 5xx) | 1º `502 AI_BACKEND_ERROR`; retry mesmo id → `200` | status + `error.code` |
| S3 | timeout do motor (Ollama lento) | 1º `504 AI_TIMEOUT`; retry mesmo id → `200` | status + `error.code` |
| S4 | retry mesmo `request_id` após **sucesso** | 2º `200` com **mesma** resposta; **0** chamadas novas | igualdade de `message`/`action` + contador |
| S5 | falha antes de concluir (modelo inválido) | 1º `502 AI_INVALID_RESPONSE`; retry → `200` | status + `error.code` |
| S6 | concorrência (2 entregas simultâneas) | modelo **1×**; `200` + (`200` replay **ou** `409`) | contador + status |
| S7 | **em andamento** durante a geração | 2ª entrega → `409 REQUEST_IN_PROGRESS` com header **`Retry-After`**; após concluir → `200` com `X-D11-Replay: true`; modelo **1×** | status + headers + contador |
| S9 | **D6**: payload com **todos** os campos no limite do motor | `200` (nenhum 422 por tamanho) | status |
| S10 | **D6**: `recent_messages[].content = 4001` (1 acima) | `422 VALIDATION_ERROR` (motor rejeita > 4000 → Grimbots clampa em 4000) | status + code |

## Cenário de LIMITAÇÃO

| ID | Cenário | Esperado | Por quê |
|---|---|---|---|
| S8 | mesmo `request_id` após **restart** do motor | **re-executa** (sem replay): `chamadas 1 → 2` | store **in-memory** (single-instance). Correção: store compartilhado + `complete()` write-ahead. |

## Semântica exigida do motor

- **Chave de dedupe:** `request_id` (janela TTL de conclusão ≥ 10 min; sugerido 1 h).
- **Sucesso repetido:** replay da resposta gravada, sem re-executar o modelo.
- **Em andamento:** `409 REQUEST_IN_PROGRESS` + `Retry-After` — **retryável**.
- **Falha/timeout/erro:** **liberar** a reserva (retry legítimo permitido).
