# E4 — Avaliacao OFFLINE (v1.0 x v1.1)

> Gerado em 2026-10-19T13:19:41Z. **Numeros comerciais sao SIMULADOS** (modelo
> roteirizado). **Nao** constituem ganho de conversao — exige E5/E6 com
> dados reais. Nenhuma ativacao de producao.

## Resumo por versao

| Metrica | v1.0 | v1.1 |
|---|---|---|
| turns | 12 | 12 |
| action_allowed_pct | 100.0 | 100.0 |
| message_nonempty_pct | 100.0 | 100.0 |
| ask_question_turns | 7 | 4 |
| question_when_asked_pct | 100.0 | 100.0 |
| payload_has_context_pct | 0.0 | 100.0 |
| objection_handled_pct | 0.0 | 100.0 |
| intent_alias_normalized | 2 | 2 |
| memory_consistent | True | True |
| failed_turns | 2 | 0 |

## Trajetoria SIMULADA (contagem por action)

- v1.0: `{'ask_question': 7, 'present_offer': 2, 'send_checkout': 1, 'handoff_human': 2}`
- v1.1: `{'ask_question': 4, 'present_offer': 2, 'continue': 3, 'send_checkout': 1, 'handoff_human': 2}`

## Consistencia de memoria (por cenario)

- v1.0 · s1-qualificacao: consistent=True turn_count=3/3 dedup=True summary_not_injected=True
- v1.0 · s2-objecao-preco: consistent=True turn_count=3/3 dedup=True summary_not_injected=True
- v1.0 · s3-duvida-tecnica: consistent=True turn_count=2/2 dedup=True summary_not_injected=True
- v1.0 · s4-lead-frio: consistent=True turn_count=2/2 dedup=True summary_not_injected=True
- v1.0 · s5-handoff-risco: consistent=True turn_count=1/1 dedup=True summary_not_injected=True
- v1.0 · s5b-handoff-duvida: consistent=True turn_count=1/1 dedup=True summary_not_injected=True
- v1.1 · s1-qualificacao: consistent=True turn_count=3/3 dedup=True summary_not_injected=True
- v1.1 · s2-objecao-preco: consistent=True turn_count=3/3 dedup=True summary_not_injected=True
- v1.1 · s3-duvida-tecnica: consistent=True turn_count=2/2 dedup=True summary_not_injected=True
- v1.1 · s4-lead-frio: consistent=True turn_count=2/2 dedup=True summary_not_injected=True
- v1.1 · s5-handoff-risco: consistent=True turn_count=1/1 dedup=True summary_not_injected=True
- v1.1 · s5b-handoff-duvida: consistent=True turn_count=1/1 dedup=True summary_not_injected=True

## Falhas

### v1.0: 2 turno(s) com falha
- s2-objecao-preco t1 action=ask_question failed=['objection_handled']
- s3-duvida-tecnica t1 action=ask_question failed=['objection_handled']

### v1.1: 0 turno(s) com falha

