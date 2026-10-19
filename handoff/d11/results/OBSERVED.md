# D11 — resultados OBSERVADOS

> 2026-10-19T13:17:51Z · motor `http://127.0.0.1:64258`
> **3/6 PASS**

## S1 — mensagem duplicada (mesmo request_id, 2 envios) — FAIL
- **esperado:** 1o=200 (1 chamada ao modelo); 2o=200 SEM nova chamada (replay idempotente)
- **observado:** 1o=200 chamadas=1; 2o=200 chamadas=2

## S2 — falha apos reservar (backend 5xx -> retry MESMO request_id) — PASS
- **esperado:** 1o=5xx (AI_BACKEND_ERROR); retry mesmo request_id=200 (reserva liberada)
- **observado:** 1o=502 code=AI_BACKEND_ERROR; 2o=200

## S3 — timeout do motor (Ollama lento -> 504 AI_TIMEOUT) — PASS
- **esperado:** 1o=504 AI_TIMEOUT; retry mesmo request_id=200 (nada concluido -> liberado)
- **observado:** 1o=504 code=AI_TIMEOUT; 2o=200

## S4 — retry com o mesmo request_id apos SUCESSO — FAIL
- **esperado:** 2o=200 com a MESMA resposta (replay); 0 novas chamadas ao modelo
- **observado:** 2o=200 novas_chamadas_apos_sucesso=1 resposta_identica=True

## S5 — falha antes de concluir (modelo invalido -> 502) — PASS
- **esperado:** 1o=502 AI_INVALID_RESPONSE; retry MESMO request_id=200 (reserva liberada)
- **observado:** 1o=502 code=AI_INVALID_RESPONSE; 2o=200

## S6 — concorrencia: 2 entregas da MESMA mensagem/request_id — FAIL
- **esperado:** modelo chamado 1x; 2 respostas 200 (1 real + 1 replay) OU 2o=409 REQUEST_IN_PROGRESS
- **observado:** status=[200, 200] chamadas_ao_modelo=2 respostas_200=2

