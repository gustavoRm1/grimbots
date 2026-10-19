# Registro de integração — versão/commit do motor consumido pela Grimbots

> Registro objetivo do motor AI (repo `gustavoRm1/grimbots-ai`) acompanhado pela
> integração Grimbots. **Somente leitura** no repo do motor — nenhuma alteração
> é feita lá. Atualizar a cada entrega funcional analisada.

## Motor consumido (atual)

| Item | Valor |
|---|---|
| Commit validado (consumido) | `a3ccecf` (`docs: E3 multi-turn memory, E4 baseline, D11 durable store`) |
| Commit anterior validado | `c8d8e67` (E3 ligado ao endpoint) |
| Versão do serviço (`/health`) | `1.6.0` (corrigida em `daba546`) |
| Contrato | `contract_version` 1.0/1.1/1.2 (rastreabilidade; ativação por presença de campos) |
| Verificação Grimbots | `handoff/d11/d11_acceptance.py` → **CONTRATO 9/9 PASS** (a3ccecf) |
| Integração HTTP | `tests/integration/test_motor_live.py` → **10/10 OK** (a3ccecf) |
| Integração E3 multi-turno | `tests/integration/test_e3_multiturn_live.py` → **9/9 OK** (a3ccecf) |

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
| `a461cb0` | **E3 memória multi-turno** (objeção persistida, não repetir pergunta, funil por evidência) | refina `state_update`/`action` (mesmo schema) | **validado** — ver §E3/E4/D11 |
| `a4ea380` | **E4** baseline offline (3 cenários + `e4_observed.json`) | nenhum na interface HTTP (só testes/evidência) | revisado (não confundir 3/3 com validação ampla) |
| `dbe5a93` | **D11 store durável opt-in** (`D11_STORE=sqlite`, WAL) | comportamento default inalterado (memory) | revisado; **ativação bloqueada** |
| `a3ccecf` | docs (E3/E4/D11) | nenhum (doc) | — |

## E3/E4/D11 (`a461cb0`/`a4ea380`/`dbe5a93`) — análise de impacto

- **E3 (`a461cb0`) — memória multi-turno:**
  - Lê a objeção de preço **persistida** em `collected_information` (chaves `objection`/`objecao*`), não só o turno atual; objeção antiga **não é bloqueio permanente** (`objection_resolved`/funil avançado liberam); nunca fecha `send_checkout` com objeção ativa.
  - Não repete a última pergunta do assistente (literal/contida).
  - Propõe avanço de `funnel_stage` via `state_update` **só com evidência**, **monotônico** e dentro da whitelist D5.
  - **Validação E2E** (`tests/integration/test_e3_multiturn_live.py`, 9/9): objeção ativa persiste → `present_offer` (não fecha); objeção resolvida → `send_checkout`; pergunta já feita não se repete no turno 2; `funnel_stage` persistido e reenviado; `context_policy.allowed_actions` restringe (interseção E2); `ai_enabled=false`/`human_takeover=true` → 409; funil não dispara efeito externo.
- **E4 (`a4ea380`):** harness offline com 3 cenários (objeção, pergunta repetida literal+semântica, progressão de funil); `tests/acceptance/e4_observed.json` = 3/3 (com 1 falso-positivo semântico registrado). **Não** constitui validação ampla.
- **D11 (`dbe5a93`):** `SqliteDedupe` opt-in (`D11_STORE=sqlite` + `D11_SQLITE_PATH`), WAL/BEGIN IMMEDIATE, sobrevive a restart de **processo**. Default permanece `memory`. **Single-host**, **sem exactly-once** (janela geração→`complete()`). **Ativação não autorizada.**
- **Correções Grimbots (E-P0/F1) decorrentes desta revisão:** clamps de `collected_information` alinhados a **20 chaves / 200 chars** (doc 18) e precedência monotônica do `funnel_stage` (a proposta do motor via `state_update` não é mais sobrescrita pelo modelo). Ver doc `20_AUDITORIA_E3_E4_D11.md`.

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
git -C <motor> worktree add --detach /tmp/motor-a3ccecf a3ccecf
MOTOR_DIR=/tmp/motor-a3ccecf MOTOR_VENV_PY=<venv>/bin/python \
  python3 handoff/d11/d11_acceptance.py            # CONTRATO 9/9
GRIMBOTS_AI_MOTOR_DIR=/tmp/motor-a3ccecf GRIMBOTS_AI_VENV_PY=<venv>/bin/python \
  python3 tests/integration/test_motor_live.py     # 10/10
GRIMBOTS_AI_MOTOR_DIR=/tmp/motor-a3ccecf GRIMBOTS_AI_VENV_PY=<venv>/bin/python \
  python3 tests/integration/test_e3_multiturn_live.py   # 9/9
```
