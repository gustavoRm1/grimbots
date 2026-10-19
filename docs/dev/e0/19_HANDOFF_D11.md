# 19 — Hand-off D11 ao motor (idempotência por `request_id`)

> Pacote executável em `handoff/d11/`. **Não altera o repo do motor.**
> Motor implementou D11 (`444d4a2` / crosscheck `4898325`, docs: v1.6.0).
> Re-executado contra **`b81dcad`** (versão corrigida em `daba546`): **CONTRATO
> 9/9 PASS**. Verificação **independente** Grimbots: **CONTRATO 9/9 PASS**. Sem
> merge/deploy/ativação.
>
> **Assinatura D11 = compatibilidade validada nos cenários testados** — **não**
> é aprovação para produção (limitações permanecem; ver §Limitações).

## Conteúdo do pacote

| Arquivo | Papel |
|---|---|
| `handoff/d11/d11_acceptance.py` | cenários S1–S10 (stdlib): sobe mock Ollama + motor, registra versão/commit, imprime esperado × observado |
| `handoff/d11/README.md` | contrato `message_id`×`request_id`, garantias/limites, divergências |
| `handoff/d11/EXPECTED.md` | resultado esperado por cenário + critério de aceite |
| `handoff/d11/SIGNATURE.md` | bloco de contra-assinatura Grimbots ⇄ Motor |
| `handoff/d11/results/observed.json` | resultado bruto + metadados do motor |
| `handoff/d11/results/OBSERVED.md` | resultado observado legível |
| `handoff/d11/results/MATRIZ_ESPERADO_OBSERVADO.md` | **matriz final** para o motor validar |

## Relação `message_id` × `request_id`

- `message_id` (Telegram) identifica a **mensagem do lead** — dedupe na **Grimbots**.
- `request_id` identifica **uma tentativa** — dedupe no **motor**. O motor **não**
  recebe `message_id`.
- `request_id` é reutilizado **dentro** de uma tentativa (retries HTTP do
  `GrimbotsAIService`). Reentrega após a janela D11 → **novo `request_id`**.

## Resultado: 3/6 → **CONTRATO 9/9 PASS** (independente dos testes internos do motor)

Primeira execução (motor stateless, `454d37c`): **3/6**. Re-execução contra
`4898325` (`results/OBSERVED.md`):

| ID | Cenário | Esperado | Observado | Resultado |
|---|---|---|---|---|
| S1 | Mensagem duplicada | 1 chamada ao modelo | 1 chamada | PASS |
| S2 | Falha após reservar | retry mesmo id → 200 | 502 `AI_BACKEND_ERROR` → 200 | PASS |
| S3 | Timeout do motor | 504 → retry 200 | 504 `AI_TIMEOUT` → 200 | PASS |
| S4 | Retry após sucesso | replay, 0 chamadas novas | resposta idêntica, 0 novas | PASS |
| S5 | Falha antes de concluir | 502 → retry 200 | 502 `AI_INVALID_RESPONSE` → 200 | PASS |
| S6 | Concorrência (2 entregas) | 1 chamada (ou 409) | 1 chamada; `[200, 409]` | PASS |
| S7 | Em andamento | 409 `REQUEST_IN_PROGRESS` + `Retry-After`; replay após concluir | 409 + `retry_after=1`; replay `X-D11-Replay=true`; 1 chamada | PASS |
| S9 | D6 no limite | 200 | 200 | PASS |
| S10 | D6 1 acima | 422 | 422 `VALIDATION_ERROR` | PASS |
| S8 | **Limitação** (restart) | store in-memory → re-executa | chamadas 1 → 2 | documentado |

→ S1/S4/S6 (efeito duplo) **eliminados**; S8 documenta o limite arquitetural.

## Divergências reportadas ao motor (não corrigidas aqui)

1. **Versão reportada — RESOLVIDA** em `daba546`/`b81dcad`: `service_version`
   agora é `1.6.0` (`api/config.py:27`); `/health` confere (verificado pelo
   harness e por `tests/integration/test_motor_live.py` cenário F).
2. **Store in-memory / single-instance** (S8) — **em aberto**: exige store
   compartilhado (ex.: Redis) para multi-worker/instância e para durabilidade a
   restart. Decisão registrada pelo motor em §12.5 de
   `docs/CONTRATO-MOTOR-COMERCIAL-ALINHAMENTO.md` (mantém sucesso-only em memória
   por ora; documenta a janela pós-geração/antes de `complete()`).

## Preparo/correção do lado Grimbots

- `REQUEST_IN_PROGRESS` (409): **retryável**, **sem fallback**, **sem efeitos**
  (msg/fluxo/checkout/handoff) e **libera a reserva** para reentrega.
- Cliente honra **`Retry-After`** (`_sleep`).
- Testes: `tests/test_d11_dedupe.py` (14/14) —
  `test_request_in_progress_releases_and_has_no_effects`,
  `test_request_in_progress_then_redelivery_succeeds`,
  `test_client_honors_retry_after_header`.

## Garantias / limitações (resumo)

- **At-most-once**, não exactly-once (queda entre gerar resposta e gravar a
  conclusão → re-execução; ver S8).
- Motor multi-instância exige store compartilhado.
- Detalhado em `handoff/d11/README.md` §5 e `16_D11_AT_MOST_ONCE.md`.

## Critério de aceite

`d11_acceptance.py` → **CONTRATO 9/9 PASS** + assinatura (**compatibilidade
validada nos cenários testados**) em `SIGNATURE.md`. **Não** é aprovação para produção.

## Próximo passo (quando o motor evoluir)

**(b) versão do `/health`** — **concluído** (`daba546`): re-executado e conferido
(`version=1.6.0`).

**(a) persistência do store de dedupe** — **pendente**. Quando entregue:
**re-executar** o pacote contra a nova versão e **atualizar**
`handoff/d11/results/MATRIZ_ESPERADO_OBSERVADO.md` (o harness grava o commit
novo). Nessa ocasião, validar explicitamente **concorrência, replay, restart e
múltiplas instâncias** (S6/S8). Bloqueio residual → falha reproduzível +
correção no repo Grimbots.

## Evidências (artefatos)

`handoff/d11/results/MATRIZ_ESPERADO_OBSERVADO.md` (matriz completa: commits do
motor e da Grimbots, comandos de reprodução, evidência por cenário, assinatura,
limitações, pendência), `results/observed.json` (bruto + metadados) e
`results/OBSERVED.md`.
