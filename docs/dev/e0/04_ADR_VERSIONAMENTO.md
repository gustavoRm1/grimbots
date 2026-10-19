# ADR-002 — Estratégia de versionamento do contrato (v1.0 / v1.1 / v1.2)

> **Status:** Proposta [PROPOSAL], com um princípio já aceito (retrocompatibilidade
> byte-a-byte do v1.0). Detalhes de numeração são [JOINT] com o dev do
> `grimbots-ai`.

## Contexto

Três "versões" estão em jogo:

1. **v1.0** — contrato implementado e em produção (`01_CONTRATO_V1.0_ATUAL.md`).
2. **v1.1** — scaffolding já escrito no lado Grimbots: `agent_profile`,
   `flow_resources`, `context_policy`, `contract_version` (flag desligada).
3. **v1.2** — proposta do motor: campos de memória + `reason`/`offer_id`/
   `state_update` (`02_PROPOSTA_V1.2_MOTOR.md`).

O Gateway usa `extra=forbid`: qualquer campo desconhecido → 422. Por isso
**nenhum campo novo pode ser enviado antes de o motor aceitá-lo**.

## Princípios (invariantes, já seguros pelo código existente)

1. **v1.0 é o default byte-a-byte.** Com flags desligadas, o corpo enviado é
   idêntico ao atual (garantido por `tests/test_phase6a_contract_v11.py`).
2. **Campos novos são opcionais e só viajam quando explicitamente fornecidos.**
   `build_payload` só adiciona as chaves novas quando não-None
   (`ai_service.py:226-240`).
3. **Ausência de `contract_version` significa v1.0** (semântica do motor já
   confirmada em conversa). Envio de `contract_version` é opt-in.
4. **Dupla flag para ativação:** global `GRIMBOTS_AI_CONTRACT` (habilita
   suporte técnico) + `step_config.contract_v11` (ativa por bloco).
   `bot_manager.py:3909-3917`.
5. **Rollout incremental:** ativação por bot piloto antes de liberação geral.

## Decisão proposta [JOINT]

**Um único payload versado, dois blocos de campos aditivos:**

| Bloco | Campos | Flag |
|---|---|---|
| Scaffolding (rótulo interno "v1.1") | `contract_version`, `agent_profile`, `flow_resources`, `context_policy` | existente (dupla flag) |
| Motor (rótulo "v1.2") | objeto de memória, `reason`, `offer_id`, `state_update` | nova (a definir) |

**Numeração do campo `contract_version` — opções a decidir com o motor:**

| Opção | Payload | Prós | Contras |
|---|---|---|---|
| A) Um salto `"1.2"` cobre tudo | `contract_version="1.2"` quando qualquer campo novo estiver presente | simples; motor só precisa distinguir v1.0 vs v1.2 | rótulo interno "v1.1" do scaffolding vira cosmético |
| B) Versões granulares | `"1.1"` só com bloco scaffolding; `"1.2"` com motor | permite ativação incremental por bloco | motor precisa tratar 3 estados |
| C) Omitir para v1.0, enviar só o valor do bloco ativo | idem B, com v1.0 = ausente | semântica já confirmada | idem B |

**Recomendação da Grimbots:** Opção **B ou C** — permitem ativar o scaffolding
(`agent_profile` etc.) antes do pacote de memória, reduzindo a superfície de
risco por rollout. A numeração exata ("1.1"/"1.2" vs "2") é cosmética e fica
a cargo do motor.

## Compatibilidade e migração

- **Consumidor antigo (motor só v1.0) + Grimbots nova:** flags desligadas →
  payload v1.0. Nenhum problema.
- **Consumidor novo (motor v1.2) + Grimbots antiga:** payload sem campos novos →
  motor opera em v1.0. Nenhum problema (campos ausentes são tolerados).
- **Ativação parcial:** flag global ligada + flag por bloco desligada →
  v1.0 naquele bloco. Permite ativação bloco a bloco.
- **Remoção de campos antigos:** proibida nesta fase. Qualquer remoção futura
  exige ADR novo + migração com fallback para defaults atuais.

## Rollback

Desligar as flags (global e/ou por bloco) restaura o v1.0 byte-a-byte em
tempo de configuração, sem deploy de código. É o rollback primário.

## Não decidido aqui

- Valor literal de `contract_version` para cada bloco (Opção A/B/C).
- Nome/mecanismo da flag do bloco de memória (reutilizar `contract_v11`? nova?).
- Se o motor passará a anunciar sua versão na resposta (campo `contract_version`
  de resposta) — hoje não existe.
