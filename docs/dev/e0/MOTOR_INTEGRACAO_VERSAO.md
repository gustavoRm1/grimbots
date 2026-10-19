# Registro de integração — versão/commit do motor consumido pela Grimbots

> Registro objetivo do motor AI (repo `gustavoRm1/grimbots-ai`) acompanhado pela
> integração Grimbots. **Somente leitura** no repo do motor — nenhuma alteração
> é feita lá. Atualizar a cada entrega funcional analisada.

## Motor consumido (atual)

| Item | Valor |
|---|---|
| Commit validado (consumido) | `c8d8e67` (`E3: integrate commercial decision into /v1/agent/respond ...`) |
| Commit anterior validado | `b81dcad` (store persistente docs) |
| Versão do serviço (`/health`) | `1.6.0` (corrigida em `daba546`) |
| Contrato | `contract_version` 1.0/1.1/1.2 (rastreabilidade; ativação por presença de campos) |
| Verificação Grimbots | `handoff/d11/d11_acceptance.py` → **CONTRATO 9/9 PASS** (b81dcad e c8d8e67) |
| Integração HTTP | `tests/integration/test_motor_live.py` → **10/10 OK** (c8d8e67); 8/10 em b81dcad (G/H exigem E3) |

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
| `cbdfa97` | **E3** (módulo, não exposto) | nenhum na interface HTTP — `commercial_decision.py` sem ligação | aguardar exposição |
| `c8d8e67` | **E3 ligado** ao `/v1/agent/respond` + precedência E2 | **refina `action`/`message`/`reason`/`next_question`/`state_update`** (mesmo schema; sem campo novo) | **validado** — ver §E3 |

## E3 (`c8d8e67`) — análise de impacto e validação

- **Arquivos:** `api/app.py` (usa `apply_decision`), `api/commercial_decision.py` (`decide` + `apply_decision`), docs/tests. **Schema de resposta inalterado** (mesmos campos); a camada **refina** `action`, `message`, `reason`, `next_question`, `state_update`.
- **Exposto:** `app.py` importa/usa `apply_decision` após validar a saída do modelo.
- **Precedência E2 (corrigida):** o conjunto efetivo é `allowed_actions ∩ context_policy.allowed_actions` (`validator._effective_allowed_actions`); a decisão é **clamped** ao conjunto permitido (fallback seguro), substituindo o whitelist local da versão anterior (`cbdfa97`). Ponto de atenção anterior **resolvido**.
- **Efeitos externos:** continuam exclusivos da Grimbots — o motor só devolve dados (documentado em `docs/API.md` §10.5).
- **Validação E2E na Grimbots** (`tests/integration/test_motor_live.py`, 10/10):
  - **G** — a decisão **altera a resposta real**: modelo propõe `present_offer` a frio → final `ask_question` (e `message == next_question`).
  - **H** — **E2 prevalece**: política aberta → decisão troca `continue`→`ask_question`; política só `continue` → decisão **clamped** para `continue`.
  - **I** — **memória/contexto v1.1** aceito e resposta útil.
  - **J** — **não responder**: `ai_enabled=false` → 409 `AI_DISABLED_FOR_BOT`, sem gerar resposta e **sem chamar o modelo** (0 chamadas → sem efeito).
  - Contra `b81dcad` (pré-E3): **8/10** (G/H falham) — confirma que os testes **detectam** E3 (não são vacuosos).
- **Sem regressão D11:** `d11_acceptance.py` → **CONTRATO 9/9** (b81dcad e c8d8e67).

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
