# D11 — matriz esperado × observado

> Gerado em **2026-10-19T15:23:27Z** pelo harness `handoff/d11/d11_acceptance.py`.
> Reproduzível: ver §2. **Não** substitui os testes internos do motor.

## 1. Identificação (commits exatos)

| Item | Valor |
|---|---|
| Motor — commit | `48983253a3b42db22dd43866cfb16ae53cbe3a66` (`4898325`) |
| Motor — assunto | D11 crosscheck: re-run acceptance 6/6; document 12.4 limits; add matrix/evidence |
| Motor — versão reportada (`/health`) | `1.0.0` |
| Motor — modelo | `grimbots-sales:latest` |
| Motor — describe | `4898325` |
| Grimbots — commit | `c17df8a5bd993ce95a03e7fcb18adea527e5a19a` (`c17df8a`) |
| `REQUEST_TIMEOUT` (execução) | 5 |

## 2. Comandos de reprodução

```bash
# 1) checkout do motor no commit acima (NÃO alterar o repo do motor)
git -C <motor> checkout 4898325 && cd api && GRIMBOTS_API_KEY=... OLLAMA_BASE_URL=... uvicorn app:app
# 2) aceite D11 (independente)
MOTOR_DIR=<motor> MOTOR_VENV_PY=<venv>/bin/python python3 handoff/d11/d11_acceptance.py
# 3) testes Grimbots (409 sem efeitos, D6, E4)
python3 tests/test_d11_dedupe.py  # e tests/test_phase6a_contract_v11.py
```

**Resultado: CONTRATO 9/9 PASS.** Cenários `limitation` documentam limites arquiteturais conhecidos.

## 3. Cenários de CONTRATO (S1–S7, S9, S10)

| ID | cenário | esperado | observado | evidência | resultado |
|---|---|---|---|---|---|
| S1 | mensagem duplicada (mesmo request_id, 2 envios) | 1o=200 (1 chamada ao modelo); 2o=200 SEM nova chamada (replay idempotente) | 1o=200 chamadas=1; 2o=200 chamadas=1 | contador POST /api/generate: 1ª=1 e 2ª=1 (sem 2ª execução) | PASS |
| S2 | falha apos reservar (backend 5xx -> retry MESMO request_id) | 1o=5xx (AI_BACKEND_ERROR); retry mesmo request_id=200 (reserva liberada) | 1o=502 code=AI_BACKEND_ERROR; 2o=200 | status 502 AI_BACKEND_ERROR → 200 com o MESMO request_id | PASS |
| S3 | timeout do motor (Ollama lento -> 504 AI_TIMEOUT) | 1o=504 AI_TIMEOUT; retry mesmo request_id=200 (nada concluido -> liberado) | 1o=504 code=AI_TIMEOUT; 2o=200 | status 504 AI_TIMEOUT → 200 com o MESMO request_id | PASS |
| S4 | retry com o mesmo request_id apos SUCESSO | 2o=200 com a MESMA resposta (replay); 0 novas chamadas ao modelo | 2o=200 novas_chamadas_apos_sucesso=0 resposta_identica=True | resposta idêntica (message/action) e 0 chamadas novas ao modelo | PASS |
| S5 | falha antes de concluir (modelo invalido -> 502) | 1o=502 AI_INVALID_RESPONSE; retry MESMO request_id=200 (reserva liberada) | 1o=502 code=AI_INVALID_RESPONSE; 2o=200 | status 502 AI_INVALID_RESPONSE → 200 com o MESMO request_id | PASS |
| S6 | concorrencia: 2 entregas da MESMA mensagem/request_id | modelo chamado 1x; 2 respostas 200 (1 real + 1 replay) OU 2o=409 REQUEST_IN_PROGRESS | status=[200, 409] chamadas_ao_modelo=1 respostas_200=1 | chamadas ao modelo == 1; status [200, 409] | PASS |
| S7 | 409 REQUEST_IN_PROGRESS (Retry-After) + replay apos conclusao | em andamento -> 409 REQUEST_IN_PROGRESS com header Retry-After; 1o=200; apos concluir -> 200 replay (X-D11-Replay=true); modelo 1x | em_andamento=409 code=REQUEST_IN_PROGRESS retry_after=1; 1o=200; apos=200 replay=true; chamadas=1 | 2ª entrega=409 REQUEST_IN_PROGRESS + header Retry-After; após concluir 200 X-D11-Replay=true; chamadas==1 | PASS |
| S9 | D6: payload com TODOS os campos no limite do motor | 200 (limites do motor respeitados; nenhum 422 por tamanho) | 200 code= | 200 (nenhum 422 por tamanho) | PASS |
| S10 | D6: message.content=4001 (1 acima do limite do motor) | 422 VALIDATION_ERROR (motor rejeita >4000 -> Grimbots deve clamar em 4000) | 422 code=VALIDATION_ERROR | 422 VALIDATION_ERROR (motor rejeita > 4000) | PASS |

## 4. Cenário de LIMITAÇÃO (S8)

| ID | cenário | esperado | observado | resultado |
|---|---|---|---|---|
| S8 | durabilidade do dedupe apos restart (store in-memory) | LIMITE CONHECIDO: store in-memory -> apos restart o mesmo request_id NAO tem replay; o modelo re-executa | 1o=200; apos_restart=200; chamadas_antes=1 chamadas_depois=2 | PASS |

## 5. Assinatura D11

**Assinatura D11: compatibilidade validada nos cenários testados.** Os cenários de contrato S1–S7, S9 e S10 passaram (9/9) contra o commit do motor registrado abaixo. **Isto NÃO equivale a aprovação para produção** — as limitações abaixo permanecem e a ativação exige decisão explícita.

## 6. Limitações documentadas (permanecem)

- **Reinício do motor:** o store de dedupe é in-memory. Após restart, o mesmo `request_id` NÃO tem replay e o modelo re-executa (evidência: S8, chamadas 1→2).
- **Store em memória:** a conclusão vive só no processo; sem persistência durável não há exactly-once.
- **Múltiplas instâncias / workers:** a dedupe é por processo. Com >1 worker ou instância, o mesmo `request_id` pode cair em processos diferentes e executar 2×.
- **Falha entre geração e persistência:** se o processo morrer DEPOIS de gerar a resposta e ANTES de gravar a conclusão, a reserva expira e o retry re-executa (at-most-once, não exactly-once).
- **Correção concreta sugerida (motor):** gravar a resposta *write-ahead* logo após o modelo (antes de serializar a saída) e usar store compartilhado com `complete()` atômico.

## 7. Pendência do motor (próximo passo)

Quando o motor entregar **(a)** persistência do store de dedupe e **(b)** correção da versão do `/health`: **re-executar** §2 contra a nova versão e **atualizar esta matriz** (o harness registra o novo commit).

