# 14 — Preparação E-P0 (clamps defensivos) e E-P1 (memória/contexto)

> **Status:** **plano** — NENHUM código foi alterado. Depende do acordo D1/D5/D6
> (`13_RESPOSTA_DECISOES_PENDENTES.md`). Enquanto não houver consenso: sem merge,
> deploy, ativação ou alteração do contrato compartilhado.
>
> **Invariante:** com as flags **off**, o payload e o comportamento permanecem
> **v1.0 byte-a-byte** (golden do cliente intacto).

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
| **E-P0** | nada (defensivo) | **sim** — decisão-independente |
| **E-P1a** | nada (persiste, não envia) | **sim** — decisão-independente |
| **E-P1b** (enviar) | **D1** (rótulo) + **D6** (limites) | **não** — aguarda acordo |
| **E-P2** (ler resposta) | **D5** (whitelist) + **D10** (resumo) + motor **E2** | **não** |
| **D12** (mapa `intent`) | acordo do mapa | **não** |

> Observação: o motor **já aceita** memória e contexto — E-P1b **não** exige mudança
> no motor; exige só o acordo de rótulo/limites.

---

## Critérios de aceite (antes de qualquer rollout)

1. Golden do cliente v1.0 **byte-a-byte** com flags off.
2. Golden do motor (`tests/golden/prompts/*`) intacto.
3. Suíte unit do motor 100% verde (sem regressão).
4. Nenhum `422` por clamp/limite (testes de fronteira).
5. Merge RMW não perde estado; isolamento por lead preservado.
6. Só então: medição offline (E4) → shadow (E5) → rollout (E6), com aprovação
   explícita a cada passo.
