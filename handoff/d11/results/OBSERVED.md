# D11 — resultados OBSERVADOS

> 2026-10-19T15:53:29Z · motor `http://127.0.0.1:51798`
> versao_reportada `1.6.0` · commit `b81dcad`
> **CONTRATO: 9/9 PASS**

## S1 — mensagem duplicada (mesmo request_id, 2 envios) — PASS
- **esperado:** 1o=200 (1 chamada ao modelo); 2o=200 SEM nova chamada (replay idempotente)
- **observado:** 1o=200 chamadas=1; 2o=200 chamadas=1

## S2 — falha apos reservar (backend 5xx -> retry MESMO request_id) — PASS
- **esperado:** 1o=5xx (AI_BACKEND_ERROR); retry mesmo request_id=200 (reserva liberada)
- **observado:** 1o=502 code=AI_BACKEND_ERROR; 2o=200

## S3 — timeout do motor (Ollama lento -> 504 AI_TIMEOUT) — PASS
- **esperado:** 1o=504 AI_TIMEOUT; retry mesmo request_id=200 (nada concluido -> liberado)
- **observado:** 1o=504 code=AI_TIMEOUT; 2o=200

## S4 — retry com o mesmo request_id apos SUCESSO — PASS
- **esperado:** 2o=200 com a MESMA resposta (replay); 0 novas chamadas ao modelo
- **observado:** 2o=200 novas_chamadas_apos_sucesso=0 resposta_identica=True

## S5 — falha antes de concluir (modelo invalido -> 502) — PASS
- **esperado:** 1o=502 AI_INVALID_RESPONSE; retry MESMO request_id=200 (reserva liberada)
- **observado:** 1o=502 code=AI_INVALID_RESPONSE; 2o=200

## S6 — concorrencia: 2 entregas da MESMA mensagem/request_id — PASS
- **esperado:** modelo chamado 1x; 2 respostas 200 (1 real + 1 replay) OU 2o=409 REQUEST_IN_PROGRESS
- **observado:** status=[200, 409] chamadas_ao_modelo=1 respostas_200=1

## S7 — 409 REQUEST_IN_PROGRESS (Retry-After) + replay apos conclusao — PASS
- **esperado:** em andamento -> 409 REQUEST_IN_PROGRESS com header Retry-After; 1o=200; apos concluir -> 200 replay (X-D11-Replay=true); modelo 1x
- **observado:** em_andamento=409 code=REQUEST_IN_PROGRESS retry_after=1; 1o=200; apos=200 replay=true; chamadas=1

## S9 — D6: payload com TODOS os campos no limite do motor — PASS
- **esperado:** 200 (limites do motor respeitados; nenhum 422 por tamanho)
- **observado:** 200 code=

## S10 — D6: message.content=4001 (1 acima do limite do motor) — PASS
- **esperado:** 422 VALIDATION_ERROR (motor rejeita >4000 -> Grimbots deve clamar em 4000)
- **observado:** 422 code=VALIDATION_ERROR

## S8 — durabilidade do dedupe apos restart (store in-memory) — PASS
- **esperado:** LIMITE CONHECIDO: store in-memory -> apos restart o mesmo request_id NAO tem replay; o modelo re-executa
- **observado:** 1o=200; apos_restart=200; chamadas_antes=1 chamadas_depois=2

