# Plano de testes — evolução do bloco Atendimento IA

> **Status:** PLANO. Nenhum teste novo foi implementado nesta fase (E0 é
> documental). Os testes existentes estão listados como base. Os planejados
> serão escritos apenas após aprovação do contrato e separados por fase
> funcional.

## 1. Base existente (verde nesta branch)

| Suite | Resultado | Cobre |
|---|---|---|
| `pytest` (suíte completa) | 48 passed | regressões gerais |
| `tests/test_agent_respond_contract.py` | 10/10 | contrato v1.0: payload golden, limites, campos proibidos |
| `tests/test_ai_next_question_dedup.py` | 11/11 | dedup P1 de `next_question` |
| `tests/test_phase6a_contract_v11.py` (scaffolding local) | 21/21 | v1.0 byte-a-byte, helpers v1.1, projeção segura, orçamento |
| `node test_adapter.js` | 39 PASS | adapter Drawflow ↔ fluxo (Flow Builder) |

## 2. Testes planejados (a implementar por fase funcional, após aprovação)

### 2.1 Fase 1 — proteção da integração (segurança)

| # | Teste | Cenário | Esperado |
|---|---|---|---|
| T1 | Ação fora de `allowed_actions` | motor devolve `send_checkout` com `allowed_actions=["continue"]` | checkout **não** executado; política A: clamp p/ `continue`; log `ACTION_CLAMPED` |
| T2 | `handoff_human=true` fora de `allowed_actions` | mesmo cenário com flag de handoff | handoff não roteado pelo motor |
| T3 | Checkout sem saída conectada | `send_checkout` com `connections.checkout` vazio | aviso + fallback; nenhum PIX gerado |
| T4 | Handoff sem saída conectada | `handoff_human` com `connections.handoff` vazio | aviso + fallback |
| T5 | `enabled=false` na entrada do bloco | entrar no bloco com IA pausada | **sem** `intro_message` (após correção aprovada); primeiro turno → humano/fallback |
| T6 | Reenvio da abertura (reentrada) | entrar duas vezes no mesmo bloco | `intro_message` enviada uma vez (após proteção aprovada) |
| T7 | `do_not_respond` | motor devolve `do_not_respond` | silêncio total; step permanece ativo |
| T8 | Alias `no_reply` (se aprovado) | motor devolve `no_reply` | normalizado → silêncio; **nunca** vira `continue` |
| T9 | Ação desconhecida | motor devolve ação fora do enum | `AIResult` normaliza → `continue` (comportamento preservado) ou fallback, conforme decisão |

### 2.2 Fase 2 — memória por lead

| # | Teste | Cenário | Esperado |
|---|---|---|---|
| T10 | Isolamento entre leads | dois `telegram_user_id` no mesmo bot | estados independentes; zero vazamento |
| T11 | Isolamento entre bots | mesmo lead em dois bots | estados independentes |
| T12 | Isolamento entre vendedores | mesmo bot id numérico de tenants diferentes | chaves distintas (`user_id` na chave); zero vazamento |
| T13 | Persistência e recuperação | turno 1 grava, turno 2 lê | campos recuperados corretamente |
| T14 | Retomada após "reinício" | apagar processo (mock), novo turno | estado do Redis + `flow_current_step` restauram a conversa |
| T15 | `state_update` com chaves permitidas | motor devolve `collected_information` etc. | merge RMW aplicado; nada apagado |
| T16 | `state_update` com chaves negadas | motor devolve `human_takeover`, `turn_count` etc. | descartadas + log; `human_takeover` não alterado |
| T17 | `state_update` malformado | tipos errados, excesso de chaves | descartado com segurança; turno não quebra |
| T18 | Histórico longo + resumo | > 20 mensagens | resumo persistido e enviado; janela curta ≤ 20 |
| T19 | Sanitização da memória | tentativa de injeção de prompt em `collected_information`/resumo | sanitizado (padrão anti-injeção) |

### 2.3 Fase 3 — compatibilidade e contrato

| # | Teste | Cenário | Esperado |
|---|---|---|---|
| T20 | v1.0 byte-a-byte | flags desligadas | payload idêntico ao golden v1.0 (já coberto; manter) |
| T21 | Compatibilidade com configurações antigas | bloco salvo sem campos novos | defaults aplicados; sem crash |
| T22 | `offer_id` inválido | motor devolve `offer_id` inexistente | ação degrada com segurança (nunca checkout com oferta fantasma) |
| T23 | Ofertas `active=false` | conforme decisão [JOINT] | comportamento esperado conforme contrato aprovado |
| T24 | Timeout | Gateway lento (mock) | retries conforme política; fallback após esgotar |
| T25 | Duplicidade de turno | mesma mensagem entregue duas vezes | sem cobrança duplicada; comportamento definido (hoje: sem request-dedup — limitação conhecida) |
| T26 | Ausência de regressão no Flow Builder | `node test_adapter.js` + testes de fluxo | 39+ PASS |

### 2.4 Teste integrado com o motor (opt-in)

| # | Teste | Condição de execução |
|---|---|---|
| T27 | Integração real Grimbots → motor (v1.0 legado) | só com credenciais via env (`GRIMBOTS_AI_INTEGRATION=1`); skip caso contrário |
| T28 | Integração real com campos v1.2 | idem; só após motor aceitar |
| T29 | Campo desconhecido → 422 | idem; valida `extra=forbid` do lado do motor |

**Regra:** nenhum teste integrado roda com tráfego real de lead sem autorização
expressa. Ambiente: staging/bot piloto.

## 3. Critérios de execução

- Suites offline (`pytest`, `node test_adapter.js`) rodam em CI/local a cada PR.
- Testes integrados são opt-in por env var e nunca rodam por default.
- A suíte completa deve continuar verde antes e depois de cada mudança
  funcional (incluindo as 48 + 10 + 11 + 21 + 39 atuais).
