# 11 — Revisão conjunta E0: Grimbots ↔ `grimbots-ai`

> **Status:** documento de **revisão conjunta** para o dev do motor. **APENAS
> documentação** — nenhuma alteração funcional, nenhum deploy, nenhuma ativação em
> produção. A v1.0 permanece intacta. Nada aqui está implementado.
>
> **Bases analisadas (verificadas por leitura direta):**
> - **Grimbots:** `origin/main` = `d41b527`; branch `docs/evolucao-ai-block-e0`.
> - **Motor:** `grimbots-ai` = `8db1de7` (E0 do motor: `eb328c7` + `8db1de7`,
>   2026-10-18); pacote `1.4.0`.
>
> **Documentos contrapostos:** Grimbots `docs/dev/e0/00`–`10`; motor
> `docs/CONTRATO-MOTOR-COMERCIAL.md`, `docs/CONTRATO-MOTOR-COMERCIAL-ALINHAMENTO.md`,
> `docs/API.md`, `docs/HANDOFF-GRIMBOTS.md`.

Legenda de classificação (mantida de `00_E0_SUMMARY.md`):

- **[EXISTS]** — implementado e verificado no código (`arquivo:linha`).
- **[PROPOSAL]** — proposto nesta fase; NÃO implementado; NÃO aprovado.
- **[JOINT]** — depende de acordo explícito entre os dois devs.
- **[RUNTIME]** — comportamento ainda **não confirmado em execução**; precisa de
  validação em runtime antes de virar fato.

---

## 1. Contrato e versões — nomenclatura canônica proposta (decisão pendente)

Hoje há **três conceitos distintos** sendo chamados informalmente de "versão".
Esta seção os separa e propõe uma nomenclatura canônica. **A decisão fica
pendente até o alinhamento dos dois lados [JOINT].**

| Conceito | O que é | Hoje | Fonte |
|---|---|---|---|
| **Versão do pacote** | Semver do app motor (FastAPI) | `1.4.0` | motor `CHANGELOG.md`, `docs/API.md` |
| **Prefixo de rota** | Versão da URL da API | `/v1` | motor `api/app.py` |
| **Versão do contrato** | Conjunto de campos request/response; rótulo em `contract_version` | ambíguo | ver tabela abaixo |
| **Versão do bloco (Grimbots)** | Feature-flag do bloco no Flow Builder | v1.0 / scaffolding `contract_v11` | `config.py:78`, `bot_manager.py:3909` |

**Ambiguidade atual [JOINT]:** o motor dá dois usos distintos ao rótulo `v1.1`:

- `ROADMAP.md:12` — **Fase 1 / pacote v1.1.0**: campos de **memória operacional**.
- `CONTRATO-MOTOR-COMERCIAL-ALINHAMENTO.md:§1.1` — **contrato v1.1**: os **4 campos
  de contexto** (`contract_version`, `agent_profile`, `flow_resources`,
  `context_policy`), entregues na **Fase 5 / pacote v1.4.0**.

A Grimbots, por sua vez, agrupa memória **+** resposta no rótulo proposto **v1.2**
(`02_PROPOSTA_V1.2_MOTOR.md:§0`). Resultado: **o mesmo rótulo "v1.1" nomeia coisas
diferentes em cada lado.**

### 1.1 Proposta de nomenclatura (NÃO decidida)

Separar os três eixos e nomear o **contrato** apenas pelo conjunto de campos:

| Contrato (rótulo proposto) | Conteúdo | Status motor | Grimbots |
|---|---|---|---|
| `1.0` | base (sem memória, sem contexto, sem resposta nova) | vigente | default atual |
| `1.1` | + 4 campos de contexto | aceito (`schemas.py:120-129`) | scaffolding (flag off) |
| `1.2` | + `reason`/`offer_id`/`state_update` (resposta) + formalização | **proposto (E0)** | proposto |

**Ponto em aberto**: onde entram os **6 campos de memória** (existem desde a Fase 1).
Opções: (a) incluir em `1.1`; (b) criar `1.1a`; (c) tratar como "campos opcionais
transversais" sem rótulo. **[JOINT]**

`contract_version` permanece **metadado de tracing** (≤ 10 chars, string livre, sem
enum) — sozinho **não** altera prompt (`schemas.py:125-126`, `prompt_builder.py:111-117`).

---

## 2. Campos de entrada — matriz (Grimbots → motor)

| Campo | Motor aceita hoje | Grimbots envia hoje | Compat |
|---|---|---|---|
| `request_id`,`seller_id`,`bot_id`,`conversation_id`,`bot_user_id` (≤80) | [EXISTS] `schemas.py:87-91` | sim | total |
| `mode` (`shadow`/`suggestion`/`auto`) | [EXISTS] `schemas.py:92` | sim | total |
| `bot_config` (`name`≤60,`personality`≤12,`tone`≤60,`boldness`1-5,`message_length`≤20,`emoji_level`≤20,`commercial_goal`≤80) | [EXISTS] `schemas.py:36-46` | sim | total (ver §9 D14) |
| `conversation_state` (`funnel_stage`,`lead_temperature`,`human_takeover`,`ai_enabled`) | [EXISTS] `schemas.py:49-55` | sim | total |
| `lead` (`name`≤60,`interest`≤120,`objection`≤120) | [EXISTS] `schemas.py:58-63` | sim | **ver §9 D14** |
| `recent_messages` (não-vazio, `content`≤4000) | [EXISTS] `schemas.py:66-70,131-136` | sim (≤1200) | total |
| `conversation_summary` (≤4000) | [EXISTS] `schemas.py:99` | sim (hoje `""`) | total |
| `available_offers` (≤20; `id`≤64,`name`≤120,`price`≤40,`checkout_url`≤400) | [EXISTS] `schemas.py:73-80,100` | sim | **ver §9 D14/D13** |
| `allowed_actions` (lista de `Action`) | [EXISTS] `schemas.py:101` | sim | total |
| **`contract_version`** | [EXISTS] `schemas.py:126` | scaffolding (flag off) | opt-in |
| **`agent_profile`/`flow_resources`/`context_policy`** | [EXISTS] `schemas.py:127-129` | scaffolding (flag off) | opt-in |
| **6 campos de memória** | [EXISTS] `schemas.py:103-118` | **não envia** | ver §4 |

> **Correção importante**: os 4 campos de contexto **já são aceitos** pelo motor
> (Fase 5); a hipótese de "`extra=forbid` → 422" **não se aplica mais** a eles
> (§9 D2). `extra="forbid"` vale **só na raiz**; submodelos usam `extra="ignore"`.

---

## 3. Campos de saída — matriz (motor → Grimbots)

| Campo | Motor hoje | Proposta motor | Proposta Grimbots | Compat |
|---|---|---|---|---|
| `message`,`intent`,`lead_temperature`,`funnel_stage`,`action`,`next_question`,`handoff_human`,`risk`,`validation`,`usage` | [EXISTS] `schemas.py:163-175` | inalterado | inalterado | total |
| `reason` | **não existe** | ≤ 300 (`CONTRATO:§7`) | ≤ 200 (`02:§3`) | **divergência D3** |
| `offer_id` | **não existe** | ≤ 64 (`CONTRATO:§7`) | ≤ 80 (`02:§3`) | **divergência D4** |
| `state_update` | **não existe** | whitelist §8.3 | whitelist `02:§3.1` | **divergência D5** |

Ambos os lados concordam que: campos são **opcionais/aditivos**; cliente antigo
ignora desconhecidos (`AIResult`); quem **aplica** o `state_update` é a **Grimbots**
(motor **não** persiste — stateless).

---

## 4. Memória: campos **persistidos pela Grimbots** × **atualizações sugeridas pelo motor**

> Regra de ouro (concordam os dois lados): **a Grimbots é dona da memória
> persistente por lead**; o motor é **stateless** e apenas **sugere**. Nada é
> persistido pelo motor.

### 4.1 Campos enviados pela Grimbots (persistidos por ela)

Fonte: motor `schemas.py:103-118`. Limites **reais do schema** × limites
**propostos pela Grimbots** (`02:§2`):

| Campo | Tipo/enum (motor) | Limite real do motor | Grimbots propõe | Dono da fonte |
|---|---|---|---|---|
| `last_assistant_message` | string | ≤ **2000** | sem limite proposto | Grimbots |
| `collected_information` | dict escalar | ≤ **30** campos; chave ≤60; valor str ≤300 | ≤ 20 chaves; valor ≤200 | Grimbots persiste; motor sugere |
| `questions_already_asked` | list[str] | ≤ **20** itens; item ≤300 | ≤ 40 itens; item ≤200 | Grimbots persiste |
| `offers_already_presented` | list[str] | ≤ **20** itens; item ≤120 | ≤ 20 itens (ids) | Grimbots persiste |
| `turn_count` | int | **0–100** | ≥ 0 | Grimbots calcula |
| `last_action` | `Action` | enum | enum | Grimbots calcula |
| `conversation_summary` | string | ≤ 4000 | ≤ 4000 (persistido) | **divergência D10 (quem gera)** |

**Todos os limites divergem ou não estão acordados → [JOINT] (§9 D6).** Enquanto
não houver limite acordado, a Grimbots **não deve enviar** os campos (evita 422).

### 4.2 Atualizações sugeridas pelo motor (`state_update`)

**Whitelist divergente [JOINT] (§9 D5) — RATIFICADO: final = 7 chaves** (as 5
comuns + `objection` + `interest`; `last_action` e `conversation_summary` fora):

| Chave | Motor (`CONTRATO:§8.3`) | Grimbots (`02:§3.1`) | Confronto |
|---|---|---|---|
| `collected_information` | ✅ objeto de escalares | ✅ merge raso | ok |
| `questions_already_asked` | ✅ list[str] | ✅ append+dedup | ok |
| `offers_already_presented` | ✅ list[str] | ✅ append+dedup | ok |
| `funnel_stage` | ✅ enum | ✅ já existe | ok |
| `lead_temperature` | ✅ enum | ✅ já existe | ok |
| `last_action` | ✅ enum | ❌ **negado** (Grimbots calcula) | **conflito** |
| `conversation_summary` | ❌ ausente | ✅ substitui (replace) | **conflito** |
| `objection` | ❌ ausente | ✅ ≤200 (já existe) | **conflito** |
| `interest` | ❌ ausente | ✅ ≤200 (novo) | **conflito** |
| `turn_count` | ❌ ausente | ❌ negado | ok (ambos negam) |

### 4.3 Requisitos antes de implementar memória (NÃO implementado)

1. **Validação** de `state_update` chave a chave (whitelist única acordada).
2. **Merge** RMW (read-modify-write) no Redis — hoje `_ai_state_set` sobrescreve o
   objeto inteiro (`06:§3` nota); o merge está só no scaffolding local.
3. **Persistência** só na Grimbots; motor nunca persiste.
4. **Dedup/append** explícito para listas (`questions_already_asked`,
   `offers_already_presented`).
5. **Sanitização** (nunca persistir/enviar senha, token, cartão, CPF —
   `02:§2`; reuso do padrão anti-injeção `ai_service.py:60-74`).
6. **Degradação segura**: qualquer falha → v1.0 (flag off).

---

## 5. `allowed_actions` e validação de ações

Duas camadas **independentes** — as duas devem existir:

| Camada | Onde | Comportamento | Evidência |
|---|---|---|---|
| **Motor (server-side)** | `validator.py` | `action ∉ allowed_actions` (raiz) → **fatal → 502** | motor `validator.py:104-108`; `API.md:§8.5` |
| **Grimbots (defensiva) [PROPOSAL]** | `bot_manager._handle_ai_turn` | **hoje só o Mock** valida (gap G1); o caminho real **não** valida | `ai_service.py:562-563` vs `bot_manager.py:4280-4403` |

> **Decisão pedida**: incluir na Grimbots a **validação defensiva** de
> `allowed_actions` no caminho real (além da validação do motor), com política de
> **clamp vs fallback** a definir (`ADR_VALIDACAO_DEFENSIVA.md`, [JOINT]).

Efeito colateral atual: ação inválida no motor → `502` → retry×3 → fallback
(§7). Se a Grimbots validar antes de executar, evita-se executar ação não permitida
quando o motor (por falha conhecida) devolver algo fora da lista.

**Alias `no_reply`** (§9 D8): o motor **não** tem esse valor no enum (`Action`,
`schemas.py:22-25`) e **não expande enums** (`CONTRATO:§4.6`); se o modelo emitir
`no_reply`, o motor trata como **fatal 502**. A Grimbots propõe normalizar
`no_reply`→`do_not_respond` (`02:§3.2`). Decisão conjunta.

---

## 6. `human_takeover=true` e HTTP 409 — [RUNTIME] (não confirmado)

**Fato do motor (código/docs):** `conversation_state.human_takeover=true` →
**409 `HUMAN_TAKEOVER_ACTIVE`** e a IA para (`app.py:161-165`; `API.md:322-323,462-463,585`).

**Situação na Grimbots:** a Grimbots envia `human_takeover` do estado
(`bot_manager.py:4231`) e **não há guard pré-chamada** que impeça chamar o motor
quando `human_takeover=true` (o valor só é escrito em `state_updates`).

**[RUNTIME] — a confirmar em execução:** não está comprovado que o fluxo volte ao
bloco AI com `human_takeover=true` sticky. Se voltar, o turno receberia **409**
(não-retryável) → **fallback**. Precisa de **reprodução em runtime** antes de
tratar como bug. Decisão: quem cria o guard (Grimbots, pré-chamada) — §9 D9.

---

## 7. Retries, idempotência e fallback

**Códigos reais do motor (verificados):**

| Código | HTTP | Retryável? | Evidência motor | Grimbots (hoje) |
|---|---|---|---|---|
| `RATE_LIMITED` (+`Retry-After`) | 429 | sim | `app.py:147-153`; limite 30/min `config.py:63` | retry (cap 30s) |
| `AI_BUSY` | 503 | sim | `app.py:179-184` | retry |
| `AI_TIMEOUT` | 504 | sim | `ollama_client.py:64` → `app.py:185-192` | retry |
| `AI_INVALID_RESPONSE` | 502 | sim | `app.py:226-231` | retry |
| `VALIDATION_ERROR` | 422 | não | `app.py:80-85` | fallback |
| `PAYLOAD_TOO_LARGE` | 413 | não | `API.md:462-474` | pré-check local |
| `HISTORY_TOO_LONG` | 422 | não | `API.md:462-474` | fallback |
| `AI_DISABLED_FOR_BOT` | 409 | não | `app.py:156-160` | fallback |
| `HUMAN_TAKEOVER_ACTIVE` | 409 | não | `app.py:161-165` | fallback |
| `AI_GLOBALLY_DISABLED` | 503 | não | `config.py:67` | fallback |
| `API_KEY_NOT_CONFIGURED` | 503 | não | `API.md:462-474` | fallback |

**Política Grimbots [EXISTS]:** 3 tentativas, backoff (2,4,8)s, `Retry-After` cap
30s (`ai_service.py:77-83,458+`).

### 7.1 Idempotência e efeitos duplicados — risco documentado [JOINT]

- **O motor NÃO deduplica `request_id`** — ele é apenas ecoado/logado
  (`app.py:180,186,202,217,235`). Não há chave de idempotência.
- **Risco de retries**: como o motor é **stateless** e **não executa nada**, um
  retry **não** duplica efeitos no motor. Porém:
  - a Grimbots **retenta** em 429/503/504 (até 3×) e **executa** a ação vencedora;
    se houver qualquer entrega parcial (ex.: mensagem enviada e timeout no
    registro), pode haver **efeito duplicado do lado da plataforma**;
  - não há contrato de **idempotência por `request_id`** — **[JOINT]** definir se
    o motor deve deduplicar e/ou se a Grimbots precisa de chave de idempotência.
- **[RUNTIME]**: verificar em teste se um retry pode gerar **ação duplicada**
  (ex.: dois `send_checkout`) no lado da Grimbots.

**Fallback da Grimbots:** erro não-retryável ou esgotamento → mensagem de fallback
(e, quando configurado, roteamento HUMAN). Mantido.

---

## 8. Compatibilidade com o comportamento atual (v1.0)

Concordância dos dois lados:

| Garantia | Motor | Grimbots |
|---|---|---|
| Ausência de campos novos ⇒ prompt **byte a byte** igual | golden `tests/golden/prompts/*.txt` (`CHANGELOG 1.4.0`) | teste de contrato fixa v1.0 (`tests/`), flag off |
| Novos campos sempre **opcionais** | `schemas.py:103-129` | `build_payload` só inclui se não-`None` |
| **Response** aditivo (cliente ignora desconhecidos) | `CONTRATO:§5` | `AIResult` |
| Enums **não** se expandem | `CONTRATO:§4.6` | enums em `ai_service.py:34-42` |
| Prompt estendido é **aditivo** (seção `[CONTEXTO ADICIONAL]`) | `prompt_builder.py:133-191` | n/a |

**Ordem obrigatória de ativação (ambos concordam):**
Gateway aceita → plataforma envia → Gateway consome → plataforma lê → avalia →
shadow → rollout. Nenhum passo sem o gate anterior (`ALINHAMENTO:§5`).

---

## 8.1 Compatibilidade v1.0 — riscos de campos (D14)

Clamps do cliente **mais frouxos** que o schema do motor → risco de **422**:

| Campo | Clamp Grimbots | Limite motor | Situação |
|---|---|---|---|
| `lead.name` | 80 (`ai_service.py:227`) | 60 (`schemas.py:61`) | **risco 422** |
| `lead.interest` | 200 (`ai_service.py:228`) | 120 (`schemas.py:62`) | **risco 422** |
| `lead.objection` | 200 (`ai_service.py:229`) | 120 (`schemas.py:63`) | **risco 422** |
| `Offer.id` | 80 (`ai_service.py:293`) | 64 (`schemas.py:76`) | **risco 422** |
| `Offer.checkout_url` | 500 (`ai_service.py:302`) | 400 (`schemas.py:79`) | **risco 422** |
| `bot_config.tone` | 40 | 60 | ok (mais estrito) |
| `bot_config.commercial_goal` | 60 | 80 | ok |
| `Message.content` | 1200 | 4000 | ok |
| `conversation_summary` | 4000 | 4000 | ok |

Responsável: **Grimbots** (apertar clamps). Validação: teste de fronteira por campo.

---

---

## 9. Matriz de divergências

> **Regra:** nenhum item abaixo é tratado como fato de runtime. Responsável:
> **M** = dev do motor · **D** = dev da Grimbots · **J** = conjunto · **P** = dono
> do produto.

| # | Divergência | Evidência | Resp. | Impacto | Validação |
|---|---|---|---|---|---|
| **D1** | Rótulo de versão (memória = "v1.1" motor × "v1.2" Grimbots) | motor `ROADMAP:12`; alinhamento §1.1; Grimbots `02:§0` | **J** | `contract_version` ambíguo | §1 aprovada nos dois lados |
| **D2** | Contexto v1.1 **já aceito** pelo motor; Grimm. assume bloqueio | motor `schemas.py:120-129`; Grimbots `config.py:78`/`bot_manager.py:3909` | **D** | Ativação não é mais barrada por 422 | T3–T5 (motor) + golden cliente |
| **D3** | `reason` ≤300 (motor) × ≤200 (Grimbots) | motor `CONTRATO:§7`; Grimbots `02:§3` | **J** | truncamento/observabilidade | teste de limite |
| **D4** | `offer_id` ≤64 (motor) × ≤80 (Grimbots) | motor `CONTRATO:§7`; Grimbots `02:§3` | **J** | validação de oferta | teste de limite |
| **D5** | Whitelist `state_update` (6 chaves motor × 8 Grimbots; `last_action` e `conversation_summary`/`objection`/`interest` divergem) | motor `CONTRATO:§8.3`; Grimbots `02:§3.1` | **J** | delta de memória inconsistente | **RATIFICADO: whitelist final = 7 chaves** (5 comuns + `objection` + `interest`) + testes |
| **D6** | Limites dos campos de memória divergem (ver §4.1) | motor `schemas.py:107-117`; Grimbots `02:§2` | **J** | risco de 422 | testes de fronteira |
| **D7** | `allowed_actions`: motor fatal 502; Grimbots só Mock | motor `validator.py:104-108`; Grimbots `bot_manager.py:4280-4403` | **D** (+pol. **J**) | ação inválida → retry×3 → fallback | ADR-05 + testes |
| **D8** | Alias `no_reply` | Grimbots `02:§3.2`; motor `CONTRATO:§4.6`/`§6` | **J** | sem alias → fatal 502 | teste de enum |
| **D9** | `human_takeover=true` → 409 sem guard na Grimbots | motor `app.py:161-165`; Grimbots `bot_manager.py:4231` | **D** (+**[RUNTIME]**) | turno cai em fallback | reprodução em runtime |
| **D10** | Quem gera `conversation_summary` | motor `CONTRATO:§6.5` ("plataforma"); Grimbots `02:§2` ("motor sugere") | **J** | responsabilidade indefinida | decisão + teste |
| **D11** | Idempotência: motor não dedup `request_id` | motor `app.py:180` | **J/M** | efeitos duplicados possíveis | teste de retry |
| **D12** | Enum `intent` (`oferta`/`informacao`) → fatal 502 | motor `API.md:§8` (known_failure); Grimbots `09` | **M** | perda de turno | teste reproduzível (§12-T15) |
| **D13** | Ofertas `active=false`: motor filtra; Grimbots envia | motor `prompt_builder.py:91`; Grimbots gap G3 | **D** | inócuo hoje | teste de filtro |
| **D14** | Clamps do cliente > limites do schema do motor | Grimbots `ai_service.py:227-229,293,302`; motor `schemas.py:59-80` | **D** | **risco 422** | teste de fronteira |

**Sem divergência (concordância registrada):** stateless + memória na Grimbots;
ordem de ativação request(estrito)/response(aditivo); garantia v1.0 byte-a-byte;
`available_offers` como fonte única de checkout (`flow_resources` só descritivo);
precedência `bot_config` × `agent_profile`; os 3 elos (persistir → enviar → consumir).

---

## 10. Sequência de implementação proposta (tudo atrás de flag; v1.0 intacta)

Nenhuma etapa é implementada antes da **Gate 0** (contrato aprovado
conjuntamente). Cada fase tem critérios de aceite e mantém a v1.0 quando a flag
está **off** (byte-a-byte).

| Fase | Lado | Entrega | Depende | Testes |
|---|---|---|---|---|
| **Gate 0** | J | D1–D14 decididos e documentados | — | revisão |
| **E-P0** | D | Apertar clamps (§8.1 D14) — *correção defensiva, default preserva v1.0* | Gate 0 | fronteira por campo |
| **E-P1a** | D | Persistir memória completa no Redis (merge RMW) — **ainda não envia** | Gate 0 | estado + isolamento por lead |
| **E-P1b** | D | **Enviar** memória + contexto (opt-in, flag) | **E1 (motor)** | compat + regressão byte-a-byte |
| **E1** | M | Schema aceita contexto (já aceito) + golden intacto | Gate 0 | T1–T7 (motor) |
| **E-P2** | D | Ler `reason`/`offer_id`/`state_update` (opt-in) | **E2 (motor)** | merge + whitelist |
| **E2** | M | Response aditiva + validação não-fatal | E1 | T8–T12 (motor) |
| **D7** | D | Enforcement defensivo de `allowed_actions` + fallback | Gate 0 | ação fora da lista |
| **D9/G4** | D | Guard `human_takeover` pré-chamada + fix `intro_message` | D9 runtime | não chamar com takeover |
| **Aceitação** | J | goldens verdes, retrocompat, sem regressão | todas | §10.1 |

### 10.1 Matriz de testes (Grimbots, propostos)

| # | Teste | Esperado |
|---|---|---|
| G-T1 | Flag off → payload v1.0 byte-a-byte (golden cliente) | idêntico |
| G-T2 | Flag off → prompt/response inalterados | idêntico |
| G-T3 | `contract_version` sozinho | sem efeito |
| G-T4 | Memória enviada dentro dos limites acordados | 200 |
| G-T5 | Memória acima do limite acordado | bloqueada localmente (não envia) |
| G-T6 | `state_update` com chave fora da whitelist | ignorada + log |
| G-T7 | `state_update` merge RMW não apaga chaves | preserva estado |
| G-T8 | Ação fora de `allowed_actions` (motor devolve) | clamp/fallback conforme ADR-05 |
| G-T9 | `human_takeover=true` | não chama o motor (guard) |
| G-T10 | Retry 429/503/504 | máx 3 tentativas + backoff + `Retry-After` |
| G-T11 | Retry sem efeito duplicado | 1 ação executada |
| G-T12 | Clamps de fronteira (`lead.name` 60/61, `interest` 120/121, `Offer.id` 64/65, `checkout_url` 400/401) | sem 422 |
| G-T13 | `intent` fora do enum (resposta do motor) | ver §12-T15 |

---

## 11. Decisões que dependem do dev do motor

1. **D1** — nomenclatura canônica de versão (onde entram os campos de memória).
2. **D3/D4** — limites finais de `reason` e `offer_id`.
3. **D5** — whitelist final de `state_update` e quem aplica o delta.
4. **D6** — limites numéricos dos campos de memória.
5. **D10** — quem gera o `conversation_summary`.
6. **D11** — semântica de idempotência/`request_id`.
7. **D12** — correção do enum `intent` (`oferta`/`informacao`).
8. **D14** / §8.1 — confirmar limites de schema (`lead`, `Offer`) que exigem
   ajuste no cliente.
9. **D8** — manter ou não o alias `no_reply`.
10. Confirmar que **E_1/E_2** (schema/resposta) não regridem o golden byte-a-byte.
11. Confirmar URL/estado do deploy (ngrok) — ver Anexo §3.

## 12. Decisões que dependem do dono do produto (Grimbots)

1. Aprovar a nomenclatura canônica (§1 / D1).
2. Aprovar **E-P0** (apertar clamps) como correção defensiva.
3. Quando ligar **E-P1** (persistir + enviar memória) e **E-P2** (ler resposta).
4. Política de **clamp vs fallback** para ação fora de `allowed_actions` (D7).
5. Filtrar ofertas `active=false` no payload (D13)?
6. Retenção/privacidade do `conversation_summary` e TTL.
7. Critérios/rolo de ativação (shadow → piloto) e quem aprova.
8. Como compartilhar este documento e o Anexo com o dev do motor.

---

## 13. Referências

- Grimbots: `docs/dev/e0/00`–`10`; `docs/dev/AI_BLOCK_AUDIT_READONLY.md`.
- Motor: `docs/CONTRATO-MOTOR-COMERCIAL.md`,
  `docs/CONTRATO-MOTOR-COMERCIAL-ALINHAMENTO.md`, `docs/API.md`,
  `docs/HANDOFF-GRIMBOTS.md`, ADRs 0002–0011.
- Anexo para o motor: [`12_ANEXO_MOTOR_DIVERGENCIAS.md`](12_ANEXO_MOTOR_DIVERGENCIAS.md).
