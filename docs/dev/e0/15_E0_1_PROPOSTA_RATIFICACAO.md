# E0.1 — Ratificação conjunta (Gate 0)

> **Status:** **RATIFICADO** — D1, D5, D6, D10 e D12 adotadas conforme a proposta
> consolidada, por orientação do proprietário do projeto (Gate 0 fechado).
> **Assinaturas:** Grimbots ✅ · motor ⏳ (contra-assinatura abaixo).
> **Nada foi mesclado, implantado ou ativado em produção** — a ativação de produção
> permanece **bloqueada** até a revisão final.
>
> **Regra de trabalho:** cada desenvolvedor atua **exclusivamente no seu repositório**
> (Grimbots ≠ motor `grimbots-ai`). O motor já aceita memória e contexto, então
> **E-P1b não exige mudança no motor** — exige apenas o acordo de rótulo/limites.

### Assinaturas

| Lado | Decisões | Data | Assinatura |
|---|---|---|---|
| Grimbots | D1, D5, D6, D10, D12 | 2026-10-19 | ✅ ratificado (implementado sob flag) |
| Motor (`grimbots-ai`) | D1, D5, D6, D10, D12 + E1/E2 | — | ⏳ aguardando contra-assinatura |

---

## 1. Decisões ratificadas

| # | Tema | Decisão | Status |
|---|---|---|---|
| **D1** | Rótulo de contrato | `1.0` base / `1.1` = memória+contexto / `1.2` = resposta; `contract_version` só rastreabilidade — a **presença dos campos** habilita o caminho v1.1 | ✅ **RATIFICADO** |
| **D5** | Whitelist de `state_update` | **7 chaves permitidas** (abaixo). `last_action` **removido** (interno da plataforma); `conversation_summary` **fora** (D10). Chave fora da whitelist → ignora + registra `validation.errors`; valor aninhado em `collected_information` → descarta + registra | ✅ **RATIFICADO** |
| **D6** | Limites de memória | **Schema do motor é autoritativo**; Grimbots **clampa ≤** (nunca acima) | ✅ **RATIFICADO** |
| **D10** | Resumo persistido | **Plataforma** gera/possui o resumo; o motor **não** o substitui; permanece `""` até implementação/medição | ✅ **RATIFICADO** |
| **D12** | Mapa de `intent` | `oferta → interesse` e `informacao → duvida`, registrando **valor original, normalizado, erro e métrica**; demais inválidos → **fatal** no motor | ✅ **RATIFICADO** |

**Whitelist final de `state_update` (7 chaves):**
`collected_information`, `questions_already_asked`, `offers_already_presented`,
`funnel_stage`, `lead_temperature`, `objection`, `interest`.

> Limites autoritativos referenciados (schema do motor): `lead.name ≤ 60`,
> `lead.interest/objection ≤ 120`, `Offer.id ≤ 64`, `checkout_url ≤ 400`;
> `last_assistant_message ≤ 2000`, `collected_information` (≤20 chaves / key ≤60 /
> value ≤200), `questions_already_asked` (≤20 / item ≤300),
> `offers_already_presented` (≤20 / item ≤120), `turn_count 0..100`,
> `last_action ∈ Action`.
>
> **Correção pós-E0 (E-P0):** o valor originalmente anotado para
> `collected_information` era ≤30 chaves / value ≤300, divergente do schema
> autoritativo do motor (`api/schemas.py`, `≤20` / `≤200`). Alinhado em E-P0 —
> ver `18_D6_LIMITES_MOTOR.md` (fonte canônica) e o registro de auditoria E3/E4/D11.

---

## 2. Implementado neste repositório (sob flag; ativação bloqueada)

### E-P0 — Clamps defensivos (sem flag)
- `ai_service.py`: `lead.name` 80→**60**, `lead.interest` 200→**120**,
  `lead.objection` 200→**120**, `Offer.id` 80→**64**, `Offer.checkout_url` 500→**400**
  (constantes nomeadas `MAX_LEAD_*`/`MAX_OFFER_*`).
- Só **aperta** limites; para entradas válidas o payload v1.0 **não muda**
  (golden `tests/payloads/agent_respond_request.json` intacto).

### E-P1a — Memória persistida (merge atômico, **não envia**)
- `_ai_state_atomic`: **WATCH/MULTI + retry** (`WatchError`) — merge RMW **sem lost
  update** sob concorrência; `_ai_state_set` delega para o mesmo caminho.
- Estado passa a persistir: `collected_information`, `questions_already_asked`,
  `offers_already_presented`, `turn_count`, `last_action`,
  `last_assistant_message`, `conversation_summary` (limites do motor, D6).

### E-P1b — Enviar memória/contexto (flag **desligada** por padrão)
- `build_payload` só inclui os campos de memória/contexto quando **fornecidos**;
  `_ai_memory_payload` monta a memória a partir do estado; envio só com
  `GRIMBOTS_AI_CONTRACT=v1.1` **+** `step_config.contract_v11`.
- Com a flag off o payload segue **v1.0 byte-a-byte** (golden intacto).

### E-P2 / D5 / D10 — Aplicar `state_update` (opt-in)
- `apply_state_update`: **whitelist de 7 chaves** (D5); `conversation_summary` e
  `last_action` **nunca** aplicados; chave/valor inválido → **ignora + registra**
  (nunca fatal). `AIResult` lê `reason`/`offer_id`/`state_update` (tolerante à
  ausência — E2 do motor ainda pendente).

### D9 — Guard de atendimento humano
- Pré-check `state['human_takeover']` → IA silenciosa; `409 HUMAN_TAKEOVER_ACTIVE`
  → marca **sticky** e **não** envia fallback (sem spam / sem atropelar humano).

### D11 — Proteção contra efeito duplicado em retries
- `_ai_turn_claim` (`SET NX EX`, TTL 24h) por `(bot_id, telegram_user_id,
  message_id)`: um **turno por mensagem do lead** (at-most-once). Reentrega/retry
  não repete mensagem/checkout/incremento de estado. Fail-open sem Redis/id.

### D12 — Mapa de `intent`
- `normalize_intent`: `oferta → interesse`, `informacao → duvida`, com
  `intent_original`/`intent_kind` e **registro** (log) de original/normalizado;
  desconhecido → `outro` (invalid).

### Testes
- `tests/test_phase6a_contract_v11.py`: fronteiras E-P0 (`60/61`, `120/121`,
  `64/65`, `400/401`), limites de memória, merge/concorrência WATCH, D9, D11,
  D12, whitelist de `state_update` e prova de que a memória **só** entra quando
  fornecida. **50/50**.
- `tests/test_agent_respond_contract.py`: golden v1.0 byte-a-byte (**10/10**).
- `tests/integration/test_motor_live.py`: integração controlada contra o motor
  real (mock Ollama + uvicorn + `GrimbotsAIService`) — v1.0, v1.1, 409,
  `extra=forbid` 422 e D11 (**5/5**).

---

## 3. Bloqueado (não liberado)

| Item | Depende de | Situação |
|---|---|---|
| **Ativação v1.1** (`GRIMBOTS_AI_CONTRACT=v1.1`) | critérios da §4 + autorização explícita | **não** liberado |
| **Aplicação plena de E-P2** | motor **E2** (emitir `reason`/`offer_id`/`state_update`) | reader pronto; emissão no motor pendente |
| **Dedupe por `request_id` (motor)** | motor | evidência reproduzida (motor **não** deduplica) — mitigação Grimbots via D11 |

O caminho de envio v1.1 **existe no código, porém protegido por flag e desligado
por padrão**. **Não ativar** antes da revisão final. Motor deve concluir **E1/E2**
(novos campos de resposta + validação de contrato) no repositório próprio.

---

## 3.1 Runtime (verificado)

- **D9** — 409 `HUMAN_TAKEOVER_ACTIVE`: **verificado** na integração; guard +
  sticky implementados.
- **D11** — duplicidade em retry: **reproduzida** na integração (motor **não**
  deduplica `request_id`); mitigação **Grimbots** = `_ai_turn_claim` (at-most-once
  por mensagem). Dedupe pleno no motor segue recomendado.

---

## 4. Critérios de aceite (v1.0/v1.1) — todos atendidos no lado Grimbots

1. Golden do cliente v1.0 **byte-a-byte** com flags off ✅.
2. Nenhum **422** por clamp/limite (testes de fronteira) ✅.
3. Merge/WATCH não perde estado; isolamento por lead ✅ (teste de concorrência).
4. D9 (409) e D11 (duplicidade) tratados ✅ (unit + integração).
5. **Ratificação** de D1/D5/D6/D10/D12 ✅ (Grimbots).
6. **Motor:** golden de prompts intacto + suíte unit verde + **E1/E2** ⏳ (motor).

Ativação em produção só após: medição offline (E4) → shadow (E5) → rollout (E6),
com autorização explícita a cada passo.

---

## 5. Próximos passos

1. ~~Confirmar formalmente as posições da §1~~ — ✅ ratificado (D1/D5/D6/D10/D12).
2. ~~Validar em runtime D9 (409) e D11 (duplicidade)~~ — ✅ verificado.
3. **E-P1b** implementado atrás de flag; **ativação bloqueada** até revisão final.
4. **Motor:** concluir **E1/E2** (novos campos de resposta + validação de contrato)
   e **contra-assinar** D1/D5/D6/D10/D12 neste documento (repositório próprio).
5. **Sem merge, deploy ou ativação em produção** sem autorização explícita.

---

### Referências internas
- `13_RESPOSTA_DECISOES_PENDENTES.md` — respostas às decisões.
- `14_PREPARACAO_EP0_EP1.md` — plano de E-P0/E-P1 e dependências.
- `12_ANEXO_MOTOR_DIVERGENCIAS.md` — divergências D1–D14 e T15.
- `11_REVISAO_CONJUNTA_MOTOR_GRIMBOTS.md` — matriz conjunta.

---

## 6. Hand-off ao motor (`grimbots-ai`) — E1/E2

> Escopo do **desenvolvedor do motor** (repositório próprio). O lado Grimbots já
> **tolerante** aos campos abaixo (reader defensivo): implementar não quebra o
> cliente atual.

**E1 — Contrato de request v1.1**
- Aceitar `contract_version`, `agent_profile`, `flow_resources`, `context_policy`
  e os 6 campos de memória (já no schema) — **aditivo**; ausência = v1.0.
- Validar `state_update` do modelo contra a **whitelist de 7 chaves** (D5).

**E2 — Campos novos na resposta (aditivo)**
- Emitir `reason` (string), `offer_id` (string|null, ≤64) e `state_update`
  (objeto) — todos **opcionais**; ausência mantém v1.0.
- `state_update` só com as 7 chaves; `conversation_summary`/`last_action` **nunca**.

**D11 — Idempotência do motor**
- Deduplicar por `request_id` (janela TTL), retornando a resposta anterior em
  replay. Evidência: hoje o motor **não** deduplica (2× 200 com mesmo id).

**Aceite:** golden de prompts intacto + suíte unit do motor 100% verde + testes de
regressão v1.0/v1.1 + `state_update` fora da whitelist ignorado (não fatal no
request, aplicação na plataforma).
