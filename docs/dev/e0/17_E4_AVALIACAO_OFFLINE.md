# 17 — E4: avaliação OFFLINE (baseline v1.0 × v1.1)

> **IMPORTANTE:** avaliação **offline** e **reproduzível**, com "modelo"
> **roteirizado** (não-LLM). Os números comerciais são **SIMULADOS** e **não**
> constituem ganho de conversão. Nenhuma ativação; `GRIMBOTS_AI_CONTRACT`
> permanece `v1.0`.

## Artefatos

| Arquivo | Papel |
|---|---|
| `tests/e4/scenarios.json` | corpus reproduzível de conversas (6 cenários, multi-turno) |
| `tests/e4/e4_runner.py` | runner + modelo roteirizado + métricas (escreve `tests/e4/out/*`) |
| `tests/e4/test_e4_offline.py` | asserção executável dos invariantes (pytest, 8/8) |
| `tests/e4/out/report.md` | relatório gerado (resumo, memória, falhas) |
| `tests/e4/out/results.json` | logs estruturados por versão/turno |
| `tests/e4/out/failures.md` | relatório de falhas por versão |

Comandos:
```
python3 tests/e4/e4_runner.py            # escreve tests/e4/out/*
python3 -m pytest tests/e4/test_e4_offline.py -q
```

## O que é medido de forma OBJETIVA (independe do script)

- **Aderência de contexto no payload**: v1.1 carrega
  `agent_profile/flow_resources/context_policy` + memória; v1.0 não.
- **Consistência de memória**: `turn_count`, dedup de `questions_already_asked`,
  merge de `collected_information`, e **whitelist de `state_update`** (D5/D10 —
  `conversation_summary` **nunca** é injetado pela IA).
- **Ações permitidas**, **qualidade mínima** (mensagem + `next_question`),
  **D12** (normalização de alias de `intent`).

## O que é SIMULADO (capacidade do modelo roteirizado)

- Tratamento de objeção e trajetória comercial (oferta/checkout/handoff). O
  script expressa uma **capacidade** ("se o modelo usar o contexto v1.1, ele
  consegue tratar objeção e não repetir pergunta"). **Não** é medição de conversão.

## Resultado (execução real, `tests/e4/out/report.md`)

| Métrica | v1.0 | v1.1 |
|---|---|---|
| turns | 12 | 12 |
| payload_has_context_pct | 0.0 | **100.0** |
| action_allowed_pct | 100.0 | 100.0 |
| message_nonempty_pct | 100.0 | 100.0 |
| question_when_asked_pct | 100.0 | 100.0 |
| objection_handled_pct (SIMULADO) | 0.0 | **100.0** |
| intent_alias_normalized (D12) | 2 | 2 |
| memory_consistent | True | True |
| failed_turns | 2 | 0 |

Trajetória SIMULADA (contagem por action): v1.0
`{ask_question:7, present_offer:2, send_checkout:1, handoff_human:2}` · v1.1
`{ask_question:4, present_offer:2, continue:3, send_checkout:1, handoff_human:2}`.

## Critério de sucesso (offline)

- [x] v1.1 carrega contexto+memória em 100% dos turnos; v1.0 em 0%.
- [x] memória consistente em **todos** os cenários/versões; `conversation_summary`
      nunca injetada (D5/D10).
- [x] 100% das ações dentro de `allowed_actions`; qualidade mínima 100%.
- [x] D12 exercitado (aliases normalizados).
- [x] determinismo (mesma entrada → mesma saída) e escrita de logs/relatório.

## Não-objetivos / limites

- **Não** prova ganho real de conversão → exige E5 (shadow com dados reais).
- **Não** cobre LLM real (latência/variação) → coberto pela integração
  `tests/integration/test_motor_live.py` (motor real, 5/5) e, futuramente, E5.
- Corpus pequeno e curado; ampliação recomendada antes de qualquer decisão.
