# 19 — Hand-off D11 ao motor (idempotência por `request_id`)

> Pacote executável em `handoff/d11/`. **Não altera o repo do motor.**
> Motor implementou D11 (`444d4a2` / crosscheck `4898325`, docs: v1.6.0).
> Verificação **independente** Grimbots: **CONTRATO 9/9 PASS**. Sem
> merge/deploy/ativação.

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

1. **Versão reportada:** `/health` e OpenAPI devolvem `version="1.0.0"`
   (`api/config.py:27`) enquanto docs/badge/CHANGELOG dizem **v1.6.0**.
   **Sugestão (motor):** `service_version = "1.6.0"`.
2. **Store in-memory / single-instance** (S8): exige store compartilhado para
   multi-worker/instância e para durabilidade a restart.

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

`d11_acceptance.py` → **CONTRATO 9/9 PASS** + assinatura do motor em `SIGNATURE.md`.
