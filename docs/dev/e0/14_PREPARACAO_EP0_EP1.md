# 14 — Preparação E-P0 (clamps defensivos) e E-P1 (memória/contexto)

> **Status (atualizado):** **E-P0, E-P1a e E-P1b implementados** (E-P1b atrás de
> flag, **desligada por padrão**). **E-P2** (reader defensivo de
> `reason`/`offer_id`/`state_update`), **D9** (guard de atendimento humano) e
> **D12** (mapa de `intent`) implementados no lado Grimbots. **D11** mitigação
> plena depende do motor (dedupe por `request_id`) — evidência reproduzida.
> A **ativação** (`GRIMBOTS_AI_CONTRACT=v1.1`) segue **bloqueada** por D1/D5/D6/
> D10/D12 (confirmação formal dos dois lados — `15_E0_1_PROPOSTA_RATIFICACAO.md`).
> Sem merge, deploy ou ativação.
>
> **Invariante:** com as flags **off**, o payload e o comportamento permanecem
> **v1.0 byte-a-byte** (golden do cliente intacto).

## Evidências (executadas)

| Suíte | Comando | Resultado |
|---|---|---|
| Unit contrato v1.1 | `python3 tests/test_phase6a_contract_v11.py` | **50/50 offline OK** |
| Golden cliente v1.0 | `python3 tests/test_agent_respond_contract.py` | **10/10** (byte-a-byte) |
| Dedup next_question | `python3 tests/test_ai_next_question_dedup.py` | **11/11** |
| D11 dedupe (2 fases) | `python3 tests/test_d11_dedupe.py` | **8/8** (ver doc 16) |
| E4 offline | `python3 -m pytest tests/e4/test_e4_offline.py -q` | **8/8** (ver doc 17) |
| Integração motor real | `python3 tests/integration/test_motor_live.py` | **5/5** (v1.0, v1.1, 409, 422 extra=forbid, D11) |

Concorrência do estado: `test_state_atomic_no_lost_update_under_concurrency`
(4 threads × 25 incrementos → `turn_count` = 100, sem lost update).


---

## E-P0 — Clamps defensivos (Grimbots, sem flag)

Corrige o risco de **422** por clamps do cliente **mais frouxos** que o schema do
motor (item §8.1 / D14). É puramente defensivo: só **aperta** limites; para valores
dentro do motor nada muda.

| Campo | Hoje (Grimbots) | → Alvo (motor) | Local |
|---|---|---|---|
| `lead.name` | 80 | **60** | `ai_service.py:227` |
| `lead.interest` | 200 | **120** | `ai_service.py:228` |
| `lead.objection` | 200 | **120** | `ai_service.py:229` |
| `Offer.id` | 80 | **64** | `ai_service.py:293` |
| `Offer.checkout_url` | 500 | **400** | `ai_service.py:302` |

Já conformes (sem mudança): `bot_config.tone` 40≤60, `commercial_goal` 60≤80,
`Message.content` 1200≤4000, `conversation_summary` 4000.

**Testes (fronteira):** `60/61`, `120/121`, `64/65`, `400/401` ⇒ nenhum `422`.
**Critério de aceite:** payload v1.0 byte-a-byte inalterado para entradas válidas.

---

## E-P1 — Memória/contexto atrás de flag (Grimbots)

### E-P1a — Persistir no Redis (ainda **não envia**)

- Chave existente: `gb:{user_id}:flow_ai_state:{bot_id}:{telegram_user_id}`
  (`bot_manager.py:3839-3841`, TTL 7 dias).
- Adicionar ao estado: `collected_information`, `questions_already_asked`,
  `offers_already_presented`, `turn_count`, `last_action`,
  `last_assistant_message`, `conversation_summary`.
- **Merge RMW** (hoje `_ai_state_set` sobrescreve o objeto inteiro — corrigir).
- Limites = os do motor (D6). Sanitização obrigatória (reuso `ai_service.py:61-70`).
- **Testes:** estado persiste; isolamento por lead; merge não apaga chaves; TTL.

### E-P1b — Enviar no payload (opt-in, **flag off por padrão**)

- Enviar os 6 campos de memória + 4 de contexto **somente** quando a flag ligar.
- `build_payload` já inclui os campos de contexto só quando não-`None`
  (`ai_service.py:236-245`); estender a mesma disciplina à memória.
- Flag: `GRIMBOTS_AI_CONTRACT` (global) **+** `step_config.contract_v11` (por bloco),
  já existentes (`config.py:78`, `bot_manager.py:3909-3917`). **Default off.**
- `contract_version`: **omitir** em v1.0; enviar o rótulo acordado (D1) só quando os
  campos forem enviados.
- **Testes:** G-T1 (golden v1.0 byte-a-byte com flag off), G-T4/G-T5 (limites),
  G-T12 (fronteira).

---

## Dependências (o que bloqueia o quê)

| Fase | Depende de | Pode começar? |
|---|---|---|
| **E-P0** | nada (defensivo) | **feito** |
| **E-P1a** | nada (persiste, não envia) | **feito** |
| **E-P1b** (enviar) | flag por bloco/global; **ativação** aguarda D1/D6 | **código feito**; ativação não |
| **E-P2** (ler resposta) | D5/D10; motor **E2** | **reader feito**; aplicação plena aguarda motor |
| **D9** (guard humano) | nada | **feito** (pré-check + 409 sticky) |
| **D12** (mapa `intent`) | mapa acordado | **feito** (registra original/normalizado) |

### Notas de implementação (lado Grimbots)

- `_ai_state_atomic` (bot_manager): WATCH/MULTI + retry (`WatchError`), merge RMW;
  `turn_count` sem lost update sob concorrência.
- E-P1b: `_ai_memory_payload(state)` → `build_payload(..., **memória)` só quando a
  flag liga; default `None` mantém v1.0 byte-a-byte.
- E-P2/D5/D10: `apply_state_update(state, delta, errors)` com **whitelist**
  (ignora `conversation_summary`, `last_action` e chaves desconhecidas, registrando
  em `errors`; nunca fatal).
- D12: `normalize_intent` → (`oferta`→`interesse`, `informacao`→`duvida`) com
  `intent_original`/`intent_kind`; valores fora do mapa → `outro` (invalid) e log.
- D9: pré-check `state['human_takeover']` (IA silenciosa) + `HUMAN_TAKEOVER_ACTIVE`
  409 do motor → marca sticky e **não** envia fallback.

> Observação: o motor **já aceita** memória e contexto — E-P1b **não** exige mudança
> no motor; exige só o acordo de rótulo/limites. O motor **ainda não emite**
> `reason`/`offer_id`/`state_update` (E2 pendente) — o reader Grimbots já os tolera.
> **D11:** o motor **não deduplica** por `request_id` (reproduzido na integração);
> mitigação plena depende do motor.

---

## Critérios de aceite (antes de qualquer rollout)

1. Golden do cliente v1.0 **byte-a-byte** com flags off.
2. Golden do motor (`tests/golden/prompts/*`) intacto.
3. Suíte unit do motor 100% verde (sem regressão).
4. Nenhum `422` por clamp/limite (testes de fronteira).
5. Merge RMW não perde estado; isolamento por lead preservado.
6. Só então: medição offline (E4) → shadow (E5) → rollout (E6), com aprovação
   explícita a cada passo.
