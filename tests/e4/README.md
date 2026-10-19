# E4 — Avaliação offline (v1.0 × v1.1)

Avaliação **offline** e **reproduzível** do bloco de IA, com **corpus versionado**.
Serve para validar o *encanamento* do contrato (payload, memória, ações, D12) —
**não** para medir conversão real.

## Separação explícita: observado × simulado

| Tipo | Métricas | Fonte |
|---|---|---|
| **OBSERVADO** (não depende do modelo) | `payload_has_context_pct`, aderência a `allowed_actions`, qualidade mínima (`message_nonempty`, `question_when_asked`), consistência de memória (turn_count/dedup/merge/whitelist D5-D10), `intent_alias_normalized` (D12) | funções REAIS da plataforma (`build_payload`, `AIResult.from_dict`, `apply_state_update`, `BotManager._ai_memory_updates`) |
| **SIMULADO** (modelo roteirizado) | `objection_handled_pct`, trajetória comercial (`ask_question`/`present_offer`/`send_checkout`/`handoff_human`) | respostas **scripted** por cenário (NÃO é LLM) |

> Os números "comerciais" **não** provam ganho de conversão. Isso exige E5 (shadow
> com dados reais). Confira a coluna **SIMULADO**.

## Corpus (versionado)

`scenarios.json` — 6 cenários multi-turno, cada turno define `v10` e `v11`
(ação/pergunta/objeção). Alterar o corpus exige bump de versão no `meta`.

## Comandos

```
# roda o harness e (re)gera tests/e4/out/*
python3 tests/e4/e4_runner.py

# asserção executável dos invariantes (não escreve em out/)
python3 -m pytest tests/e4/test_e4_offline.py -q
```

## Artefatos gerados (`tests/e4/out/`)

| Arquivo | Conteúdo |
|---|---|
| `report.md` | resumo por versão + consistência de memória + falhas (com disclaimer) |
| `results.json` | logs estruturados por versão/turno |
| `failures.md` | turnos com falha por versão |
| `run.log` | linha por turno |

## Baseline observado (v1.0 × v1.1)

| Métrica | v1.0 | v1.1 | Tipo |
|---|---|---|---|
| turns | 12 | 12 | — |
| payload_has_context_pct | 0.0 | 100.0 | observado |
| action_allowed_pct | 100.0 | 100.0 | observado |
| question_when_asked_pct | 100.0 | 100.0 | observado |
| memory_consistent | True | True | observado |
| intent_alias_normalized | 2 | 2 | observado |
| objection_handled_pct | 0.0 | 100.0 | **simulado** |
| failed_turns | 2 | 0 | observado |

## Não-objetivos

- Não cobre LLM real (latência/variação) — ver `tests/integration/test_motor_live.py`.
- Não mede conversão real — ver E5.
