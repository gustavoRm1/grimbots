# Proposta v1.2 — campos novos de memória e resposta

> **Classificação:** [PROPOSAL] + [JOINT]. NADA abaixo está implementado ou
> aprovado. Este documento é a **proposta da Grimbots** para negociação com o
> dev do `grimbots-ai`. Nomes, formatos e limites **podem mudar** após a revisão
> conjunta. Nenhum campo será implementado antes do contrato ser aprovado.

## 0. Contexto de versionamento

- O scaffolding já escrito no lado Grimbots rotula a preparação como **v1.1**
  (flag `GRIMBOTS_AI_CONTRACT`, campos `agent_profile`/`flow_resources`/
  `context_policy`/`contract_version`).
- O motor propõe evoluir para o que chamamos aqui de **v1.2** (campos de memória
  + `reason`/`offer_id`/`state_update`).
- Estratégia de compatibilidade: ver `04_ADR_VERSIONAMENTO.md`. Resumo: tudo
  aditivo e opcional; ausência de `contract_version` = v1.0; um único salto de
  versão no payload (`"1.2"`) cobre ambos os blocos de campos, **ou** mantemos
  `"1.1"` para o scaffolding e `"1.2"` para o pacote completo — **decisão [JOINT]**.

## 1. Princípios (invariantes propostos)

1. **Grimbots dona da memória persistente por lead** (ver `03_ADR_MEMORIA_POR_LEAD.md`).
   O motor continua stateless: recebe contexto por chamada, devolve sugestões.
2. **Nenhuma mudança byte-a-byte no v1.0.** Campos novos só viajam quando
   explicitamente fornecidos e com as flags ligadas.
3. **O motor não executa nada.** A Grimbots valida permissões e executa ações.
4. **Valores comerciais são da Grimbots.** O motor referencia ofertas por id;
   preço/condição vêm do catálogo enviado, nunca do motor.

## 2. Campos de memória por lead (payload — Grimbots → motor)

> Persistência: Redis, chave `gb:{user_id}:flow_ai_state:{bot_id}:{telegram_user_id}`
> (TTL 7 dias, existente). Envio: novos campos dentro de um objeto dedicado
> (sugestão: `memory`), **ou** campos soltos no `conversation_state` — formato
> final é [JOINT].

| Campo proposto | Tipo | Limite proposto | Semântica | Dono da fonte |
|---|---|---|---|---|
| `collected_information` | object | ≤ 20 chaves, valor string ≤ 200 chars cada | dados coletados do lead (nome, cidade, contexto...) | Grimbots persiste; motor sugere |
| `questions_already_asked` | array[string] | ≤ 40 itens, item ≤ 200 | perguntas já feitas (dedup) | Grimbots persiste; motor sugere |
| `offers_already_presented` | array[string] | ≤ 20 itens (ids) | ofertas já apresentadas (evita repetir) | Grimbots persiste; motor sugere |
| `turn_count` | int | ≥ 0 | nº de turnos da conversa | Grimbots calcula |
| `last_action` | enum ACTIONS | 1 | última ação executada | Grimbots calcula |
| `last_assistant_message` | string | ≤ 1200 | última resposta enviada (referência) | Grimbots calcula |
| `conversation_summary` | string | ≤ 4000 (limite já existe) | resumo persistente de conversas longas | motor gera (via `state_update`); Grimbots persiste |

**Observações [PROPOSAL]:**

- O `recent_messages` (20 msgs) continua sendo a janela curta. O
  `conversation_summary` é a memória de longo prazo: para conversas > 20 msgs,
  a Grimbots pede/aceita um resumo e o envia no próximo turno. Avaliação de
  privacidade: o resumo não deve conter dados sensíveis beyond o necessário —
  limitar e sanitizar no lado Grimbots antes de persistir.
- `questions_already_asked` e `offers_already_presented` são anti-repetição
  baratos no lado Grimbots; o motor usa-os como restrição, não como memória
  semântica.
- Nunca persistir/em enviar: senha, token, cartão, CPF. Sanitização obrigatória
  (reuso do padrão anti-injeção já existente no perfil: `ai_service.py:61-70`).

## 3. Campos de resposta novos (motor → Grimbots)

| Campo proposto | Tipo | Limite proposto | Semântica | Uso pela Grimbots |
|---|---|---|---|---|
| `reason` | string | ≤ 200 | motivo/contexto da decisão | log/auditoria; nunca exposto cru ao lead |
| `offer_id` | string | ≤ 80 | oferta referenciada em `present_offer`/`send_checkout` | **validar** contra `available_offers`; se inválido → cair para ação segura |
| `state_update` | object | ≤ 20 chaves | sugestões de atualização de estado | Grimbots valida chave a chave, faz merge (RMW) e **ignora chaves não permitidas** |

### 3.1 `state_update` — chaves permitidas (proposta)

| Chave | Tipo | Efeito |
|---|---|---|
| `collected_information` | object (merge raso) | merge por chave |
| `questions_already_asked` | array (append + dedup) | append com normalização |
| `offers_already_presented` | array (append + dedup por id) | append |
| `conversation_summary` | string ≤ 4000 | substitui (único caso de replace) |
| `lead_temperature` | enum | já existe hoje |
| `funnel_stage` | enum | já existe hoje |
| `objection` | string ≤ 200 | já existe hoje |
| `interest` | string ≤ 200 | **NOVO** — hoje `lead.interest` só é eco; com v1.2 o motor pode sugerir |

**Chaves NEGADAS (nunca aceitas do motor) [PROPOSAL]:**
`human_takeover` (sticky, só a Grimbots seta), `last_intent` (interno),
`turn_count`/`last_action`/`last_assistant_message` (calculados pela Grimbots),
qualquer chave fora da lista (silenciosamente descartada + log).

### 3.2 Normalização de ação [PROPOSAL — JOINT]

- Se o motor passar a usar o alias `no_reply`, a Grimbots normaliza para
  `do_not_respond` (canônico) antes de executar. **Hoje:** `no_reply` cairia na
  normalização `AIResult` → vira `continue` (mascaramento). Decisão de
  introduzir o alias é [JOINT] — não mudar enums sem acordo.
- Ação fora de `allowed_actions` → não executar; comportamento (clamp para
  ação segura vs. fallback) é [JOINT] (`05_ADR_VALIDACAO_DEFENSIVA.md`).

## 4. Mudanças de configuração do bloco (produto)

> Avaliação (Fase 3 do briefing), NÃO implementação. Compatibilidade obrigatória.

- Campos de "estilo fino" atuais (`message_length`, `emoji_level`, `boldness`,
  `funnel_stage` fixo) podem ser reclassificados como **preferências/limites**
  enviados ao motor, não como personalidade rígida. O motor decide adaptação.
- Campos novos de produto sugeridos (todos opcionais, default preserva v1.0):
  - `mission` (missão comercial, texto livre) — mapeável para o já existente
    `commercial_goal` + novo campo opcional.
  - `knowledge` (materiais de conhecimento do seller) — candidato a
    `agent_profile` do scaffolding v1.1.
  - `rules` (regras/limites comerciais) — texto com validação anti-injeção.
- **Nenhum campo antigo será removido** sem plano de migração e compatibilidade
  com bots já publicados. Migração: leitura com fallback para defaults atuais.

## 5. Dependência de ponta a ponta

A memória só entrega valor quando os três elos funcionarem juntos
(detalhado em `00_E0_SUMMARY.md`): Grimbots persiste → Grimbots envia → motor
consome e devolve `state_update`. Enquanto o motor não consumir, os campos
adicionam payload sem benefício — por isso a ativação é gated por flag e
rollout incremental (bot piloto).

## 6. Checklist de negociação com o dev do `grimbots-ai`

- [ ] Nomes finais: objeto `memory` vs campos soltos?
- [ ] `contract_version` enviado como `"1.2"`, `"1.1"`, `"1.0"` ou omitido para v1.0?
- [ ] Formato exato de `collected_information` (object livre vs schema fechado)?
- [ ] O motor passará a emitir `reason`/`offer_id`/`state_update`? Em quais ações?
- [ ] Alias `no_reply`: adotar ou manter `do_not_respond`?
- [ ] Política de ação fora de `allowed_actions` (clamp vs fallback)?
- [ ] Filtrar ofertas `active=false` no payload? (hoje: não)
- [ ] Quem gera o `conversation_summary` (motor via `state_update` vs Grimbots pedir)?
- [ ] Critérios de rollout e quem aprova a ativação.
