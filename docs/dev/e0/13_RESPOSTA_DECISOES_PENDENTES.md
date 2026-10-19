# 13 — Resposta às decisões pendentes E0 (Grimbots → motor)

> **De:** dev do Grimbots. **Para:** dev do motor `grimbots-ai`.
> **Bases:** Grimbots `origin/main` = `d41b527`; motor `8db1de7` (pacote `1.4.0`).
> **Escopo:** **apenas decisão/documentação**. Nada implementado; sem merge,
> deploy, ativação ou alteração do contrato compartilhado até o acordo.
>
> **Formato pedido:** cada item recebe **Aceito**, **Contraproposta** ou
> **Precisa de teste**, com a proposta concreta para ratificação.

Contexto: o motor **já aceita** os 6 campos de memória (`schemas.py:103-118`) e os
4 de contexto (`schemas.py:120-129`). Portanto **E-P0/E-P1 não dependem de mudança
no motor** — dependem apenas do acordo de rótulo (D1) e limites/whitelist (D5/D6).

---

## D1 — Nomenclatura de versão

**Veredicto: ACEITO** (separação dos três eixos) + **contraproposta de mapeamento**.

**Aceito integralmente** separar:

| Eixo | Definido por | Não confundir com |
|---|---|---|
| **Versão da rota** | `/v1` (URL) | contrato |
| **Versão do pacote** | semver do app motor (`1.4.0`) | contrato |
| **Versão do contrato** | rótulo em `contract_version` | pacote/rota |

**Contraproposta (mapeamento do rótulo de contrato):**

| Rótulo | Conteúdo | Base |
|---|---|---|
| `1.0` | legado (sem memória, sem contexto, sem resposta nova) | atual |
| `1.1` | **memória (6 campos) + contexto (4 campos)** | motor já aceita (`schemas.py:103-129`) |
| `1.2` | + `reason`/`offer_id`/`state_update` (resposta) | proposto (E0) |

Justificativa: o motor entregou memória (Fase 1 / pacote `v1.1.0`) e contexto
(Fase 5 / pacote `v1.4.0`) **sem rótulo de contrato**; a Grimbots agrupa os dois
blocos de **entrada** em `1.1` e reserva `1.2` para a **resposta**. **Aceito não
tratar numeração como decisão unilateral** — fica `[JOINT]` até ratificação.

**Regra operacional proposta (não vinculante até acordo):**
- `contract_version` é **metadado de tracing** (`schemas.py:126`,
  `prompt_builder.py:111-117`); o que ativa o caminho novo é a **presença** dos campos.
- Grimbots **omite** `contract_version` no v1.0 e o envia **só** quando envia os
  campos correspondentes.

**Teste:** o motor já cobre "`contract_version` sozinho não altera o prompt"
(`CONTRATO:§12 T2`). **Sem teste adicional necessário** além de ratificar o rótulo.

---

## D5 — Whitelist de `state_update`

**Veredicto: CONTRAPROPOSTA.**

| Chave | Motor (`CONTRATO:§8.3`) | Grimbots (`02:§3.1`) | Proposta Grimbots |
|---|---|---|---|
| `collected_information` | ✅ | ✅ | **manter** |
| `questions_already_asked` | ✅ | ✅ | **manter** |
| `offers_already_presented` | ✅ | ✅ | **manter** |
| `funnel_stage` | ✅ | ✅ | **manter** |
| `lead_temperature` | ✅ | ✅ | **manter** |
| `last_action` | ✅ | ❌ negado | **remover do `state_update`** — é **calculado pela Grimbots** na execução; permanece apenas como **campo de request** |
| `conversation_summary` | ❌ | ✅ | **fora da whitelist** (ver D10: resumo é da plataforma) |
| `objection` | ❌ | ✅ | **incluir** (já existe no estado hoje) — não-fatal |
| `interest` | ❌ | ✅ | **incluir** — não-fatal |
| `turn_count`, `last_assistant_message` | ❌ | ❌ | **fora** (Grimbots calcula) |

**Regras que acompanham a proposta:** aplicar por **merge RMW**; chave fora da
whitelist → **ignora + registra `validation.errors`** (não silencioso); valor
aninhado em `collected_information` → descarta + registra. `objection`/`interest`
com limite ≤120 (igual a `lead.objection`/`lead.interest`, motor `schemas.py:62-63`).

---

## D6 — Limites dos campos de memória

**Veredicto: ACEITO os limites do motor (autoritativos).**

O schema do motor é a fonte da verdade; a Grimbots **clampa ≤** o motor (nunca
acima). Adotar exatamente:

| Campo | Limite do motor (`schemas.py`) | Grimbots passa a clamp |
|---|---|---|
| `last_assistant_message` | ≤ 2000 (`:107`) | 2000 |
| `collected_information` | ≤ 30 chaves; chave ≤60; valor str ≤300 (`:141-147`) | 30 / 60 / 300 |
| `questions_already_asked` | ≤ 20 itens; item ≤300 (`:111-113`) | 20 / 300 |
| `offers_already_presented` | ≤ 20 itens; item ≤120 (`:114-116`) | 20 / 120 |
| `turn_count` | 0–100 (`:117`) | 0–100 |
| `conversation_summary` | ≤ 4000 (`:99`) | 4000 |

**Contraproposta menor:** a proposta Grimbots anterior (20 chaves / 40 perguntas /
200 chars) era **mais frouxa** que o server em `questions_already_asked` (40 > 20) e
geraria **422** — **descartada**; adotamos os valores do motor. Testes de fronteira
(60/61, 20/21, 30/31, 100/101) a criar no lado Grimbots.

---

## D10 — Quem gera o `conversation_summary`

**Veredicto: CONTRAPROPOSTA** (plataforma gera) + **precisa de medição**.

O motor é **stateless** e só expõe `/v1/agent/respond`; gerar resumo exigiria uma
etapa de sumarização no motor (chamada de modelo extra), fora do escopo E0/E1 e
contrário ao `CONTRATO:§6.5` (que já diz "a plataforma é a dona do resumo").

**Proposta:**
- **Grimbots gera e persiste** o `conversation_summary` (a partir das últimas 20
  mensagens + estado), com **gatilho** definido (estouro de histórico ou a cada N
  turnos) — gatilho exato a ratificar.
- O motor **não** gera o resumo. Opcionalmente pode incluir `conversation_summary`
  em `state_update` como **sugestão**, mas a Grimbots só aplica se decidir.
- **Precisa de medição/teste:** qualidade e custo do resumo gerado pela plataforma
  (baseline offline, E4). Sem isso, mantém-se resumo **vazio** (hoje a Grimbots
  envia sempre `""`) e nada muda.

---

## D12 — Mapa explícito de `intent` (sem mascarar)

**Veredicto: ACEITO o princípio; mapa concreto para ratificação.**

Os vocabulários já são **idênticos** nos dois lados (8 valores):
`saudacao | duvida | interesse | objecao | compra | suporte | risco | outro`
(motor `schemas.py:13-16`; Grimbots `ai_service.py:34-37`).

Falha conhecida (motor `API.md:131-140`): o modelo emite `"oferta"` e
`"informacao"` → **fatal 502**. Proposta de **mapa explícito, visível e versionado**
(nunca silencioso):

| Valor inventado | → canônico | Registro |
|---|---|---|
| `oferta` | `interesse` | `validation.errors`: *"intent 'oferta' mapeado para 'interesse'"* + métrica |
| `informacao` | `duvida` | idem |
| qualquer outro fora do vocabulário | — | **fatal `502 AI_INVALID_RESPONSE`** (mantém) |

**Regras:** (1) o mapeamento **sempre** aparece em `validation.errors` (rastreável);
(2) `validator.py` **não** expande o enum silenciosamente; (3) monitorar
`intent_invalid_rate` — se cair após o ajuste de prompt (Fase 3), pode-se **não**
aplicar o mapa; se permanecer, o mapa evita perda de turno.

**Precisa de teste:** o teste reproduzível T15 (Anexo §4) já comprova o **502 atual**;
falta um teste do mapa (alias → 200 com `validation.errors`) **após** acordo.

---

## Resumo

| # | Veredicto |
|---|---|
| D1 | **Aceito** (separação) + contraproposta de rótulo `1.1 = memória+contexto` |
| D5 | **Contraproposta** (remover `last_action`; incluir `objection`/`interest`; resumo fora) |
| D6 | **Aceito** os limites do motor (Grimbots clampa ≤) |
| D10 | **Contraproposta** (plataforma gera) + precisa de medição |
| D12 | **Aceito** o princípio; mapa concreto (`oferta→interesse`, `informacao→duvida`) com registro visível |

**Itens já resolvidos na rodada anterior** (declarados pelo dono do projeto):
D3, D4, D8, D9, D11, D14. Permanecem `[RUNTIME]` (não são fato): D9 (409
`HUMAN_TAKEOVER_ACTIVE`) e D11 (efeito duplicado em retry).

**Nada de merge, deploy, ativação ou alteração de contrato compartilhado até o
acordo explícito.**
