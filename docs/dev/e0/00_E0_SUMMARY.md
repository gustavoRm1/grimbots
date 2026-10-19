# Fase E0 — Evolução do Bloco Atendimento IA: Contrato e Documentação

> **Status:** PROPOSTA para revisão e aprovação conjunta com o projeto `grimbots-ai`.
> **Data:** Out/2026. **Branch:** `docs/evolucao-ai-block-e0`.
> **Escopo desta fase:** EXCLUSIVAMENTE documental. Nenhuma alteração funcional,
> nenhum deploy, nenhuma ativação em produção, nenhum teste com tráfego real.

## Índice

| # | Documento | Conteúdo |
|---|---|---|
| 01 | [CONTRATO_V1.0_ATUAL.md](01_CONTRATO_V1.0_ATUAL.md) | O contrato implementado hoje, com evidências `arquivo:linha` |
| 02 | [PROPOSTA_V1.2_MOTOR.md](02_PROPOSTA_V1.2_MOTOR.md) | Campos novos (memória + `reason`/`offer_id`/`state_update`) — PROPOSTA |
| 03 | [ADR_MEMORIA_POR_LEAD.md](03_ADR_MEMORIA_POR_LEAD.md) | ADR: Grimbots é dona da memória persistente por lead |
| 04 | [ADR_VERSIONAMENTO.md](04_ADR_VERSIONAMENTO.md) | ADR: estratégia v1.0 / v1.1 (scaffolding) / v1.2 (motor) |
| 05 | [ADR_VALIDACAO_DEFENSIVA.md](05_ADR_VALIDACAO_DEFENSIVA.md) | ADR: enforcement de `allowed_actions` no caminho real (proposta) |
| 06 | [MATRIZ_COMPATIBILIDADE.md](06_MATRIZ_COMPATIBILIDADE.md) | Matriz v1.0 ↔ v1.1 ↔ v1.2 campo a campo |
| 07 | [COMPORTAMENTO_ATUAL_REGRAS.md](07_COMPORTAMENTO_ATUAL_REGRAS.md) | Regras de hoje: ações, `do_not_respond`, ofertas, checkout, fallback, handoff |
| 08 | [PLANO_TESTES.md](08_PLANO_TESTES.md) | Plano de testes (não executados nesta fase) |
| 09 | [RISCOS_CRITERIOS_ACEITE.md](09_RISCOS_CRITERIOS_ACEITE.md) | Riscos, critérios de aceite, deploy e rollback |

## Classificação de cada afirmação

Todo documento usa estas marcações para não misturar fato, proposta e pendência:

- **[EXISTS]** — comportamento implementado e verificado no código (`arquivo:linha`).
- **[PROPOSAL]** — proposta desta fase; NÃO implementada; NÃO aprovada.
- **[JOINT]** — depende de decisão/aprovação conjunta com o dev do `grimbots-ai`
  antes de qualquer implementação.

## O que existe hoje (fato, verificado)

1. Bloco `ai` no Flow Builder com configuração rígida (tom, tamanho, emojis,
   intensidade, etapa fixa do funil) — `templates/flow_editor.html:403-436`.
2. Turnos via `POST /v1/agent/respond` (contrato v1.0, `extra=forbid`) —
   `internal_logic/services/ai_service.py:170-245`.
3. Sete ações no enum: `continue`, `ask_question`, `present_offer`,
   `send_checkout`, `handoff_human`, `pause`, `do_not_respond` —
   `internal_logic/services/ai_service.py:25-33`.
4. Estado por lead em Redis (`gb:{user_id}:flow_ai_state:{bot_id}:{telegram_user_id}`,
   TTL 7 dias) com campos `lead_temperature`, `funnel_stage`, `intent`,
   `objection`, `last_intent` (+ `human_takeover` no scaffolding) —
   `bot_manager.py:3839-3875`, `bot_manager.py:4287-4301`.
5. Histórico: últimas 20 mensagens de `BotMessage` por (bot_id, telegram_user_id) —
   `bot_manager.py:3877-3903`.
6. Identidade da conversa: `seller_id = user_id`, `bot_id`, `conversation_id = "c{bot_id}-{telegram_user_id}"`,
   `bot_user_id = telegram_user_id` — `bot_manager.py:4219-4222`.
7. Scaffolding v1.1 já escrito mas DESLIGADO por dupla flag
   (`GRIMBOTS_AI_CONTRACT` global + `step_config.contract_v11` por bloco) —
   `internal_logic/core/config.py:78`, `bot_manager.py:3909-3917`.
8. Auditoria de gerações em tabela `ai_generations` — `bot_manager.py:4140-4160`.

## O que é proposta (não implementado, não aprovado)

1. Campos de memória persistente por lead (`collected_information`,
   `questions_already_asked`, `offers_already_presented`, `turn_count`,
   `last_action`, `last_assistant_message`, `conversation_summary` expandido) —
   seção "Campos de memória" de `PROPOSTA_V1.2_MOTOR.md`.
2. Campos de resposta `reason`, `offer_id`, `state_update` — mesma fonte.
3. Enforcement defensivo de `allowed_actions` no caminho real de produção —
   `ADR_VALIDACAO_DEFENSIVA.md`.
4. Normalização de alias `no_reply` → `do_not_respond` — mesma fonte.
5. Correção da inconsistência de `intro_message` com `enabled=false` e
   proteção contra reenvio em reentradas — `07_COMPORTAMENTO_ATUAL_REGRAS.md`.

## O que depende de aprovação conjunta (bloqueia implementação)

1. Nomes, formatos e limites exatos dos campos de memória e de resposta.
2. Propriedade campo a campo: quem é a fonte de verdade (Grimbots vs motor).
3. Se `contract_version` deve ser omitido (v1.0), enviado como `"1.0"` ou `null`.
4. Comportamento do alias `no_reply` (normalizar vs tratar como erro).
5. Política de enforcement (clamp vs rejeição com fallback).
6. Se ofertas `active=false` passam a ser filtradas (hoje: NÃO são).
7. Ordem de rollout e critérios de ativação.

## Dependência de ponta a ponta (importante)

A memória por lead **só funcionará de ponta a ponta** quando:

1. A Grimbots persistir os campos acordados no estado por conversa
   (hoje: só `lead_temperature`/`funnel_stage`/`intent`/`objection`), **E**
2. A Grimbots enviá-los no payload conforme o formato negociado, **E**
3. O motor (`grimbots-ai`) os consumir corretamente e devolver `state_update`
   no formato acordado.

Se qualquer um dos três elos falhar, o comportamento deve degradar para o
v1.0 atual (sem quebra). A flag por versão garante isso.

## Regra de ouro desta fase

> Nenhum item classificado como [PROPOSAL] ou [JOINT] será implementado antes
> de aprovação explícita. A Fase E0 entrega apenas documentos para revisão.
