# D11 — matriz esperado × observado

> 2026-10-19T15:04:57Z · motor commit `4898325` · versao_reportada `1.0.0`

| ID | tipo | cenário | esperado | observado | resultado |
|---|---|---|---|---|---|
| S1 | contract | mensagem duplicada (mesmo request_id, 2 envios) | 1o=200 (1 chamada ao modelo); 2o=200 SEM nova chamada (replay idempotente) | 1o=200 chamadas=1; 2o=200 chamadas=1 | PASS |
| S2 | contract | falha apos reservar (backend 5xx -> retry MESMO request_id) | 1o=5xx (AI_BACKEND_ERROR); retry mesmo request_id=200 (reserva liberada) | 1o=502 code=AI_BACKEND_ERROR; 2o=200 | PASS |
| S3 | contract | timeout do motor (Ollama lento -> 504 AI_TIMEOUT) | 1o=504 AI_TIMEOUT; retry mesmo request_id=200 (nada concluido -> liberado) | 1o=504 code=AI_TIMEOUT; 2o=200 | PASS |
| S4 | contract | retry com o mesmo request_id apos SUCESSO | 2o=200 com a MESMA resposta (replay); 0 novas chamadas ao modelo | 2o=200 novas_chamadas_apos_sucesso=0 resposta_identica=True | PASS |
| S5 | contract | falha antes de concluir (modelo invalido -> 502) | 1o=502 AI_INVALID_RESPONSE; retry MESMO request_id=200 (reserva liberada) | 1o=502 code=AI_INVALID_RESPONSE; 2o=200 | PASS |
| S6 | contract | concorrencia: 2 entregas da MESMA mensagem/request_id | modelo chamado 1x; 2 respostas 200 (1 real + 1 replay) OU 2o=409 REQUEST_IN_PROGRESS | status=[200, 409] chamadas_ao_modelo=1 respostas_200=1 | PASS |
| S7 | contract | 409 REQUEST_IN_PROGRESS (Retry-After) + replay apos conclusao | em andamento -> 409 REQUEST_IN_PROGRESS com header Retry-After; 1o=200; apos concluir -> 200 replay (X-D11-Replay=true); modelo 1x | em_andamento=409 code=REQUEST_IN_PROGRESS retry_after=1; 1o=200; apos=200 replay=true; chamadas=1 | PASS |
| S9 | contract | D6: payload com TODOS os campos no limite do motor | 200 (limites do motor respeitados; nenhum 422 por tamanho) | 200 code= | PASS |
| S10 | contract | D6: message.content=4001 (1 acima do limite do motor) | 422 VALIDATION_ERROR (motor rejeita >4000 -> Grimbots deve clamar em 4000) | 422 code=VALIDATION_ERROR | PASS |
| S8 | limitation | durabilidade do dedupe apos restart (store in-memory) | LIMITE CONHECIDO: store in-memory -> apos restart o mesmo request_id NAO tem replay; o modelo re-executa | 1o=200; apos_restart=200; chamadas_antes=1 chamadas_depois=2 | PASS |

**CONTRATO: 9/9 PASS.** Cenários de `limitation` documentam limites arquiteturais conhecidos.

