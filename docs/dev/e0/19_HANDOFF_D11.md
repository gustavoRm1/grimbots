# 19 — Hand-off D11 ao motor (idempotência por `request_id`)

> Pacote executável em `handoff/d11/`. **Não altera o repo do motor.** Aguarda
> **contra-assinatura** do dev da IA. Sem merge/deploy/ativação.

## Conteúdo do pacote

| Arquivo | Papel |
|---|---|
| `handoff/d11/d11_acceptance.py` | 6 cenários (stdlib), sobe mock Ollama + motor; imprime esperado × observado |
| `handoff/d11/README.md` | contrato `message_id`×`request_id`, garantias/limites, como rodar |
| `handoff/d11/EXPECTED.md` | resultado esperado por cenário + critério de aceite |
| `handoff/d11/SIGNATURE.md` | bloco de contra-assinatura Grimbots ⇄ Motor |
| `handoff/d11/results/observed.{json,md}` | resultado OBSERVADO na execução contra o motor |

## Relação `message_id` × `request_id`

- `message_id` (Telegram) identifica a **mensagem do lead** — dedupe na **Grimbots**.
- `request_id` identifica **uma tentativa** — dedupe no **motor**. O motor **não**
  recebe `message_id`.
- `request_id` é reutilizado **dentro** de uma tentativa (retries HTTP do
  `GrimbotsAIService`). Reentrega após a janela D11 → **novo `request_id`**.

## Resultado OBSERVADO (motor atual, sem dedupe): **3/6 PASS**

| ID | Cenário | Esperado | Observado | Resultado |
|---|---|---|---|---|
| S1 | Mensagem duplicada | 1 chamada ao modelo | **2 chamadas** | FAIL |
| S2 | Falha após reservar | retry mesmo id → 200 | 502 → 200 | PASS |
| S3 | Timeout do motor | 504 → retry 200 | 504 `AI_TIMEOUT` → 200 | PASS |
| S4 | Retry após sucesso | replay, 0 chamadas novas | resposta igual, **1 nova chamada** | FAIL |
| S5 | Falha antes de concluir | 502 → retry 200 | 502 → 200 | PASS |
| S6 | Concorrência (2 entregas) | 1 chamada (ou 409) | **2 chamadas** | FAIL |

→ S1/S4/S6 são exatamente o **efeito duplo** que o motor precisa eliminar.

## Preparo do lado Grimbots para o contrato

- `REQUEST_IN_PROGRESS` (409 do motor, entrega concorrente) tratado como
  **retryável** (`_RETRYABLE_CODES`) e **sem fallback** (`_handle_ai_turn`).
- Teste: `tests/test_d11_dedupe.py::test_request_in_progress_is_retryable_and_has_no_fallback`.

## Garantias / limitações (resumo)

- **At-most-once**, não exactly-once (queda entre efeito e conclusão pode reprocessar).
- Motor multi-instância exige store compartilhado para a dedupe.
- Documentado por completo em `handoff/d11/README.md` §5 e `16_D11_AT_MOST_ONCE.md`.

## Critério de aceite

`d11_acceptance.py` → **6/6 PASS** + assinatura do motor em `SIGNATURE.md`.
