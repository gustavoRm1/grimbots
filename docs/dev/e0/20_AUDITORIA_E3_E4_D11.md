# 20 — Auditoria de integração e aceitação E3 / E4 / D11

> **Escopo:** auditoria (somente leitura no repo do motor) da integração Grimbots ↔
> `grimbots-ai` sobre os commits E3/E4/D11. Correções aplicadas **apenas** no repo
> Grimbots. **Sem merge, sem deploy, sem ativação** (`D11_STORE=sqlite` NÃO habilitado).
>
> **Data:** 19/10/2026 · **Branch:** `feat/e4-offline-d11-hardening`

## 1. Commits

| Repo | Commit | Papel |
|---|---|---|
| Motor (analisado, read-only) | `a3ccecf` (`origin/main`) | baseline auditado (E3 multi-turno + E4 + D11 durável) |
| Motor (analisado) | `a461cb0` | E3 memória multi-turno |
| Motor (analisado) | `a4ea380` | E4 baseline offline |
| Motor (analisado) | `dbe5a93` | D11 store SQLite opt-in |
| Motor (analisado) | `c8d8e67` | E3 ligado ao endpoint (validação anterior) |
| Grimbots (auditado) | `f3b7c0f` | HEAD na abertura da auditoria |
| Grimbots (correções) | _ver relatório de entrega_ | E-P0 + F1 + E3 live + `context_policy.allowed_actions` |

## 2. Testes executados (resultados reais)

| Suíte | Comando | Resultado |
|---|---|---|
| Contrato v1.1 (offline) | `python3 tests/test_phase6a_contract_v11.py` | **66/66 OK** (54 base + E-P0 2 + F1 7 + context_policy 2) |
| D11 dedupe (offline) | `python3 tests/test_d11_dedupe.py` | **14/14 OK** |
| Integração HTTP (v1.0/v1.1/E2/E3/D11) | `test_motor_live.py` vs `a3ccecf` | **10/10 OK** |
| Integração E3 multi-turno | `test_e3_multiturn_live.py` vs `a3ccecf` | **9/9 OK** |
| Aceitação D11 (harness) | `handoff/d11/d11_acceptance.py` vs `a3ccecf` | **CONTRATO 9/9 + LIMITE 1/1** |

## 3. Matriz PASS/FAIL (por item do pedido)

| # | Item | Método / evidência | Resultado |
|---|---|---|---|
| 1 | Contexto enviado + `state_update` aplicado | E3 live #4 (`su={'funnel_stage':'qualification'}`, state + payload do turno 2) | **PASS** |
| 1 | Campos sobrevivem entre turnos | E3 live #3 (pergunta já feita não se repete no t2) | **PASS** |
| 1 | Objeção ativa não fecha checkout | E3 live #1 (`present_offer`) | **PASS** |
| 1 | Objeção antiga não é bloqueio permanente | E3 live #2 (`send_checkout` após resolução) | **PASS** |
| 1 | `funnel_stage` não dispara efeito externo | E3 live #7 + F1 offline `test_f1_stage_change_alone_has_no_effects` | **PASS** |
| 2 | E4: 3 cenários não triviais | revisão de `tests/acceptance/e4_observed.json` (3/3, 1 falso-positivo semântico) | **PASS (escopo 3/3)** |
| 3 | D11 `REQUEST_IN_PROGRESS` sem efeitos | `test_d11_dedupe.py` (+ S7 do harness) | **PASS** |
| 4 | Clamps 20/200 (sem 422 evitável) | offline `test_memory_collected_information_*` + E3 live #8 (motor 200) | **PASS** |

## 4. Diferenças de comportamento (antes → depois)

| Tema | Antes | Depois |
|---|---|---|
| `collected_information` (chaves/valor) | clamp Grimbots 30/300 (além do schema do motor) | **20/200** alinhado ao motor — payload nunca estoura o schema |
| `funnel_stage` no `_persist` | `apply_state_update` aplicava o avanço e `result.funnel_stage` o **sobrescrevia** (podendo regredir) | **monotônico**: `resolve_funnel_stage(prev, modelo, state_update)` — a proposta do motor prevalece, nunca regride, nunca cria estágios |
| `context_policy.allowed_actions` | descartado pelo cliente → interseção E2 **não chegava** ao motor | repassado (clampado a `ACTIONS`) → interseção E2 honrada fim-a-fim |

## 5. Achados e correções

- **F2 (Alto, corrigido):** clamps de `collected_information` divergentes (30/300 vs
  schema 20/200) → risco de 422. Corrigido em `ai_service.py` (`MOTOR_REQUEST_LIMITS`,
  `MAX_COLLECTED_*`, `_clamp_collected_information`), `bot_manager.py`
  (`_AI_MAX_COLLECTED_*`), doc 18 e testes.
- **F1 (Médio, corrigido):** `funnel_stage` do modelo sobrescrevia a proposta do motor.
  Reproduzido (4 testes F1 falham no código anterior), corrigido com `resolve_funnel_stage`
  (monotônico) e coberto por regressão.
- **F3 (Baixo, corrigido):** `context_policy.allowed_actions` não era transmitido →
  interseção E2 parcial. Repassado (opt-in; default inalterado).

## 6. Bloqueios remanescentes

| Gravidade | Bloqueio |
|---|---|
| Bloqueante p/ produção | Store de D11 **in-memory por padrão**; `sqlite` é **opt-in** e **single-host**; **sem exactly-once** (janela geração→persistência). Ativação não autorizada. |
| Assinatura | `handoff/d11/SIGNATURE.md`: contra-assinatura do dev do motor **pendente**. |
| Alinhamento conjunto | Persistência compartilhada (Redis) multi-instância não entregue; restart/recuperação/multi-host não validados. |
| Escopo de evidência | E4 = 3/3 **offline** (não é validação ampla); E5/E6 (shadow/rollout) não iniciados. |
| Flag | v1.1 permanece **desligada por padrão** (ativação exige confirmação). |

## 7. Notas de honestidade

- A integração E3 depende do motor real + Ollama **mock roteirizado** — não é teste
  offline nem medição de qualidade comercial.
- Não declarar "integração aprovada": há itens de escopo/assinatura pendentes (§6).
