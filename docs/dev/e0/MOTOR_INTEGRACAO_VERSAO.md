# Registro de integração — versão/commit do motor consumido pela Grimbots

> Registro objetivo do motor AI (repo `gustavoRm1/grimbots-ai`) acompanhado pela
> integração Grimbots. **Somente leitura** no repo do motor — nenhuma alteração
> é feita lá. Atualizar a cada entrega funcional analisada.

## Motor consumido (atual)

| Item | Valor |
|---|---|
| Commit validado (consumido) | `b81dcad` (`docs(alinhamento): add 12.5 persistent store decision + limits`) |
| Commit monitorado mais recente | `cbdfa97` (E3) — analisado, **não exposto** no HTTP (sem impacto) |
| Commit anterior analisado | `4898325` (crosscheck D11) |
| Versão do serviço (`/health`) | `1.6.0` (corrigida em `daba546`) |
| Contrato | `contract_version` 1.0/1.1/1.2 (rastreabilidade; ativação por presença de campos) |
| Verificação Grimbots | `handoff/d11/d11_acceptance.py` → **CONTRATO 9/9 PASS** |
| Integração HTTP | `tests/integration/test_motor_live.py` → **6/6 OK** |

## Histórico de entregas analisadas

| Commit | Assunto | Impacto na integração | Ação Grimbots |
|---|---|---|---|
| `c9f179d` | docs: divergências E0.1 | nenhum (doc) | — |
| `2330b16` | E0.1/E1/E2 (contexto v1.1, resposta v1.2) | interface HTTP | compat validada |
| `e54a5b8` | D5/D9/D12 + D6 | schema/clamps | clamps D6 alinhados |
| `4976d1e` | docs Gate 0 | nenhum (doc) | — |
| `444d4a2` | **D11 dedupe** (`request_id`) | dedupe/erros | cliente honra `Retry-After`; 409 libera reserva sem efeitos |
| `4898325` | crosscheck + matriz | nenhum (doc/teste) | re-execução 3/6 → 9/9 |
| `daba546` | **fix `service_version` → 1.6.0** + testes | `/health` (informacional) | cenário F em `test_motor_live.py` |
| `b81dcad` | docs §12.5 (store persistente) | nenhum (doc) | — |
| `cbdfa97` | **E3**: camada de decisão comercial contextual | **nenhum na interface HTTP** — `api/commercial_decision.py` **não está ligado** ao path de resposta (único importador é o próprio teste unitário) | aguardar exposição; ver §E3 |

## E3 (`cbdfa97`) — análise de impacto

- **Arquivos:** `api/commercial_decision.py` (+ `tests/unit/test_commercial_decision.py`). **Sem** mudança de schema, rota ou resposta.
- **Não exposto:** `decide()` não é chamado por `app.py`/rotas (`git grep commercial_decision` → só o teste). Logo, **não há entrega funcional exercitável via HTTP** nesta versão.
- **Superfície que E3 já lê do request** (estável, sem novo campo): `conversation_state.human_takeover/ai_enabled/funnel_stage/lead_temperature`, `lead.objection/interest`, `collected_information`, `questions_already_asked`, `offers_already_presented`.
- **Devolve** `CommercialDecision(action, reason, next_question, state_update, message_override)`.
- **Ponto de atenção (pré-integração):** E3 usa um conjunto **local fixo** `allowed = (continue, ask_question, present_offer, send_checkout, handoff_human, pause, do_not_respond)` em vez de derivar de `req.allowed_actions` (precedência E2). A resolver **quando E3 for ligado** ao path, para não divergir do contrato.
- **Validação E2E:** **bloqueada até E3 ser exposto** no endpoint. Rodar `test_motor_live.py` agora não prova E3 (passa idêntico).

## Interface consumida (contrato HTTP)

- **Endpoint:** `POST /api/v1/respond` (ver `internal_logic/services/ai_service.py`).
- **Erros retryáveis:** `RATE_LIMITED` 429, `AI_BUSY` 503, `AI_TIMEOUT` 504,
  `AI_INVALID_RESPONSE` 502, `REQUEST_IN_PROGRESS` 409.
- **Erros não-retryáveis:** `VALIDATION_ERROR` 422, `PAYLOAD_TOO_LARGE` 413,
  `HISTORY_TOO_LONG` 422, `HUMAN_TAKEOVER_ACTIVE` 409, `AI_BACKEND_UNAVAILABLE` 502.
- **Limites de payload (D6):** canônicos em `docs/dev/e0/18_D6_LIMITES_MOTOR.md`
  (espelhados do schema do motor).

## Limitações/campos em aberto

- **Store de dedupe in-memory** (S8): não durável a restart nem compartilhado
  entre instâncias. Motor decidiu manter sucesso-only em memória por ora (§12.5);
  para produção multi-instância, planejar Redis/equivalente. **Re-executar
  concorrência/replay/restart/multi-instância quando entregue.**

## Como reproduzir

```bash
# motor em worktree detached (NÃO alterar o repo do motor)
git -C <motor> worktree add --detach /tmp/motor-b81dcad b81dcad
MOTOR_DIR=/tmp/motor-b81dcad MOTOR_VENV_PY=<venv>/bin/python \
  python3 handoff/d11/d11_acceptance.py            # CONTRATO 9/9
GRIMBOTS_AI_MOTOR_DIR=/tmp/motor-b81dcad GRIMBOTS_AI_VENV_PY=<venv>/bin/python \
  python3 tests/integration/test_motor_live.py     # 6/6
```
