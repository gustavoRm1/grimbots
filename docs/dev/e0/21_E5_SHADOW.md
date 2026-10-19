# 21 — E5: execução SHADOW da decisão comercial (preparação, NÃO ativada)

> **Estado:** implementado e testado **apenas na branch de trabalho**.
> `GRIMBOTS_AI_SHADOW=off` (default), `GRIMBOTS_AI_CONTRACT=v1.0`,
> `D11_STORE=memory`. **Nenhuma ativação** em produção, sem merge/deploy.

## 1. Objetivo

Medir, em turnos **reais**, a decisão do motor com o payload **v1.1**
(novo contexto/memória) **sem produzir efeito**, e **comparar** com a ação que a
produção (**v1.0**) efetivamente executou — **sem presumir** que a ação real
estava correta. Pré-requisito de E6 (rollout).

## 2. Pontos de integração

| Ponto | Arquivo | O que faz |
|---|---|---|
| Gate (dupla flag) | `bot_manager.py:_ai_shadow_enabled` | global `GRIMBOTS_AI_SHADOW` **E** `step_config['shadow']` |
| Hook do turno | `bot_manager.py:_handle_ai_turn` (após `_ai_log_generation`) | captura a ação real (v1.0) e dispara o shadow |
| Dispatcher | `bot_manager.py:_ai_dispatch_shadow` | monta payload v1.1, decide fora do caminho crítico |
| Núcleo | `internal_logic/services/ai_shadow.py` | gate, redaction, comparação, persistência, fail-open |
| Auditoria | `internal_logic/core/models.py:AIShadowDecision` (`ai_shadow_decisions`) | 1 linha por request_id (UNIQUE) |

**Custo/latência/concorrência/idempotência:** nenhuma chamada extra acontece com
o flag desligado. Ligado, a chamada roda em **thread pool dedicado**
(`GRIMBOTS_AI_SHADOW_WORKERS`, default 2), **amostrada** (`GRIMBOTS_AI_SHADOW_SAMPLE`),
com **timeout** do próprio cliente e **idempotência** por `request_id` (UNIQUE).

## 3. Isolamento de efeitos (invariantes)

O shadow **só** chama `service.respond()`. Nunca:
`send_telegram_message`, `_ai_route` (checkout/handoff), `_ai_state_atomic`/`_ai_state_set`,
`_ai_turn_claim`. Não duplica a persistência de estado do bot. Provado em
`tests/test_e5_shadow.py::test_dispatch_shadow_has_no_side_effects_and_persists_only_shadow`
(métodos de efeito substituídos por veneno → nenhuma chamada).

## 4. Armazenamento

Tabela aditiva `ai_shadow_decisions` (migration `migrations/add_ai_shadow_decisions.py`,
idempotente). Campos principais: `bot_id`, `lead_ref` (HMAC), `request_id`,
`observed_source`, `motor_version`/`motor_commit`/`motor_model`,
`context_digest`/`context_json` (redigido), `proposed_*`, `observed_*`,
`action_match`, `funnel_delta`, `latency_ms`, `error_code`. Retenção: a definir
na ativação (`created_at` indexado para expurgo).

## 5. Privacidade (controles)

- `telegram_user_id` **nunca** cru: só `lead_ref` (HMAC-SHA256, segredo
  `GRIMBOTS_AI_SHADOW_SECRET` com fallback `SECRET_KEY`).
- Contexto por **allowlist**; `collected_information` só **chaves**; perguntas/
  ofertas só **contagem**; lead só **presença** de name/interest/objection.
- **Sem texto cru** por padrão; `GRIMBOTS_AI_SHADOW_INCLUDE_TEXT` + `_MAX_TEXT_CHARS`
  habilitam apenas trecho sanitizado/limitado (opt-in).
- `conversation_summary` **nunca** é registrado.
- `context_digest` é calculado **sem texto cru** (dedupe/comparação sem reter PII).

## 6. Comparação (não autoritativa)

`compare_decisions(proposta, observada)` retorna `action_match`,
`proposed_action`, `observed_action`, `funnel_delta`, estágios. Não há juízo de
correção: a linha registra ambas com `observed_source` (`v1.0_production`).

## 7. Testes

| Teste | Cobre |
|---|---|
| `tests/test_e5_shadow.py` (12/12 offline) | gate default-off; sem PII crua; HMAC; truncamento/sanitização; comparação; falha isolada; recorder isolado; idempotência; **zero efeito** na integração |
| `tests/integration/test_e5_shadow_live.py` (4/4) | v1.1 aceito pelo motor real (sem 422); comparação gravada; falha do motor fail-open; **versão via `/health`** (fonte `health`) |
| `tests/test_e5_shadow_hardening.py` (21/21 offline) | 2A retenção/expurgo (política, injeção, fail-open, preserva recentes); 2B limites (in-flight, taxa/min, teto/dia); 2C relatório (sem PII, neutro, comparáveis); 2D versão (health/env/unknown, cache) |
| Regressão | `test_phase6a_contract_v11` 66/66, `test_d11_dedupe` 14/14, `test_motor_live` 10/10, `test_e3_multiturn_live` 9/9 |

## 7b. Hardening (Fase 2) — controle operacional

**2A — Retenção/expurgo.** `purge_expired(retention_days, now, batch_size, fetch, delete)`
é idempotente, em lotes, **fail-open** (nunca propaga). `retention_days<=0`
desliga o expurgo. Fonte injetável (`fetch`/`delete`) para teste sem DB.

**2B — Limites operacionais.** `ShadowLimiter` (in-flight + taxa/min + teto/dia)
com relógio injetável. Ao atingir qualquer limite, a admissão é **negada** e o
turno shadow é **ignorado** — nunca bloqueia o fluxo real. Config:
`GRIMBOTS_AI_SHADOW_MAX_INFLIGHT` (8), `_MAX_PER_MINUTE` (120), `_MAX_PER_DAY`
(5000); `configure_limiter()` no boot/testes.

**2C — Relatório.** `internal_logic/services/ai_shadow_report.py` — `build_report(rows)`
puro/determinístico: total, comparáveis/não comparáveis, taxa de correspondência,
divergências por ação, diferenças de estágio, falhas/timeouts, versões do motor.
Sem PII (só contagens); divergências são **neutras** (a ação real não é a verdade).
CLI: `python -m internal_logic.services.ai_shadow_report --days 30 [--json]`.

**2D — Rastreabilidade da versão.** `resolve_motor_version()` consulta `/health`
(fonte **verificável**, cache TTL 300s) e cai para `GRIMBOTS_AI_MOTOR_VERSION`
(fonte `env`) ou `unknown` — **nunca inventa** versão. Cada linha grava
`motor_version` + `motor_version_source` (`health|env|unknown`).

## 8. Critérios de desligamento (kill-switch)

| Gatilho | Ação |
|---|---|
| Dúvida/incidente | `GRIMBOTS_AI_SHADOW=off` → no-op imediato (sem deploy) |
| Bot específico | remover `shadow` do bloco |
| Taxa de `SHADOW_ERROR` acima do limiar | desligar global |
| Latência/fila/custo acima do orçamento | desligar global ou baixar `_SAMPLE`/`_WORKERS`/limites (2B) |
| Acúmulo de dados além da política | ajustar `retention_days` e rodar `purge_expired` (2A) |

## 9. Riscos remanescentes

| # | Risco | Mitigação |
|---|---|---|
| S1 | Ação "real" = decisão v1.0 do turno (não o efeito final pós-fallback) | registrada com `observed_source`; comparação não autoritativa |
| S2 | Custo/volume do shadow | amostragem + workers limitados + flag global |
| S3 | Divergência de esquema do motor no v1.1 | validado contra `origin/main`; falha é fail-open |
| S4 | Linhas com PII | allowlist + HMAC + sem texto cru por padrão |
| S5 | Vazamento do contexto para o registro | `context_json` redigido; digest sem texto |

## 10. Fora de escopo (não habilitado)

`D11_STORE=sqlite`, `GRIMBOTS_AI_CONTRACT=v1.1`, E5 e E6 em produção. A ativação
exige autorização explícita e o gate anterior (E4 offline → E5 shadow).
