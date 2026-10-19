# D11 — Resultado ESPERADO por cenário (critério de aceite)

Cada cenário é executado por `d11_acceptance.py` contra o motor. A coluna
**observado** é preenchida pelo próprio script em `results/OBSERVED.md`.

| ID | Cenário | Entrada | Esperado | Mecanismo observado |
|----|---------|---------|----------|---------------------|
| S1 | Mensagem duplicada | 2 POST idênticos, mesmo `request_id` | `200` e `200`; **1** chamada ao modelo | contador de `POST /api/generate` no mock |
| S2 | Falha após reservar | 1º POST com Ollama em erro (5xx); retry mesmo `request_id` | 1º `502` `AI_BACKEND_ERROR`; 2º `200` | status + `error.code` |
| S3 | Timeout do motor | 1º POST com Ollama lento (> `REQUEST_TIMEOUT`); retry mesmo `request_id` | 1º `504` `AI_TIMEOUT`; 2º `200` | status + `error.code` |
| S4 | Retry após sucesso | 1º POST ok; 2º POST idêntico (mesmo `request_id`) | 2º `200` com **mesma** resposta; **0** chamadas novas | comparação de `message`/`action` + contador |
| S5 | Falha antes de concluir | 1º POST com resposta inválida do modelo; retry mesmo `request_id` | 1º `502` `AI_INVALID_RESPONSE`; 2º `200` | status + `error.code` |
| S6 | Concorrência | 2 POST simultâneos, mesmo `request_id` | modelo chamado **1x**; `200` (real) + `200` (replay) **ou** 2º `409` `REQUEST_IN_PROGRESS` | contador + status |

## Semântica exigida do motor

- **Chave de dedupe:** `request_id` (o motor **não** recebe `message_id`).
- **Janela:** TTL sugerido ≥ 10 min para a resposta concluída.
- **Sucesso:** gravar a resposta; repetição devolve a **mesma** resposta, sem
  re-executar o modelo.
- **Em andamento:** `409 REQUEST_IN_PROGRESS` (`Retry-After`) — retryável.
- **Falha/timeout:** **liberar** a reserva para permitir retry legítimo.

## Critério de aceite

`6/6 PASS`. S1/S4/S6 provam a idempotência; S2/S3/S5 provam que falha não
"trava" a chave. Hoje (motor sem dedupe): **3/6** (ver `results/OBSERVED.md`).
