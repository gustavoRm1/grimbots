# Hand-off D11 — idempotência por `request_id` no Grimbots AI Gateway

> **De:** time Grimbots (bloco `ai` / Fase 6A) · **Para:** dev do AI Gateway (motor, repo local)
> **Escopo:** contrato + teste de aceite executável. **Este pacote NÃO altera o
> repositório do motor** — é para o dev rodar no checkout dele e **contra-assinar**.
> **Não** há merge, deploy ou ativação de v1.1.

---

## 1. Objetivo

Garantir que **uma mesma tentativa** (`request_id` idêntico) **não dispare duas
vezes o efeito que ela dirige** (mensagem, avanço de fluxo, checkout, handoff).

Hoje o motor é **stateless**: reenvios com o mesmo `request_id` chamam o modelo
de novo e devolvem uma nova resposta → **efeito duplicado**. Este hand-off fecha
esse limite.

O motor é quem governa o efeito porque devolve a `action` que a plataforma executa.

---

## 2. `message_id` × `request_id` (definição)

| Identificador | Onde vive | O que identifica | Quem deduplica |
|---|---|---|---|
| **`message_id`** | Telegram (inbound update id) | **a mensagem do lead** (uma mensagem do usuário) | **Grimbots** (D11 plataforma, já implementado) |
| `request_id` | enviado no payload ao motor (`gb-{bot_id}-{telegram_user_id}-{uuid}`) | **uma tentativa de processamento** | **Motor** (este hand-off) |

- O motor **nunca vê** `message_id` (não faz parte do contrato).
- **Chave de dedupe do motor = `request_id`.**

### Quando o `request_id` é reutilizado?
- **Dentro de uma mesma tentativa:** o `request_id` é gerado **uma vez** por
  `_handle_ai_turn` e **reutilizado em todos os retries HTTP** do
  `GrimbotsAIService` (transporte/backoff) — é exatamente onde a dedupe do motor
  importa.
- **Reentrega do Telegram após a janela de dedupe da plataforma (D11 expirada):**
  nova tentativa ⇒ **novo `request_id`**. O motor não tem como correlacionar
  (limitação conhecida; ver §5).

## 2.1 Quando uma nova tentativa é permitida (contrato)

| Situação | Mesmo `request_id` | Comportamento exigido do motor |
|---|---|---|
| Tentativa **concluída** (200) | repetido | **Replay** da resposta; **não** re-executa o modelo |
| Tentativa **em andamento** | repetido | **409 `REQUEST_IN_PROGRESS`** (`Retry-After`) — retryável |
| Tentativa **falhou** (5xx/timeout/erro) | repetido | **Reserva liberada** → processa como nova |
| Sem tentativa anterior | — | Processa normalmente |
| **Novo `request_id`** | — | Sempre permitido |

**Dedupe key** = `request_id`. **Janela sugerida TTL:** ≥ 10 min (cobrir retries
de transporte); sugerimos ≤ 1h para respostas e liberação imediata em falha.

---

## 3. Como rodar o teste de aceite

Sem dependências externas (stdlib). Duas formas:

```bash
# (A) contra o checkout do motor (sobe mock Ollama + uvicorn automaticamente):
MOTOR_DIR=/caminho/para/grimbots-ai \
MOTOR_VENV_PY=/caminho/para/venv/bin/python \
python3 d11_acceptance.py

# (b) contra um motor já em execução:
MOTOR_BASE_URL=http://127.0.0.1:8000 GRIMBOTS_API_KEY=<sua-chave> \
python3 d11_acceptance.py
```

Saída: tabela **ESPERADO × OBSERVADO** por cenário + arquivos
`results/observed.json` e `results/OBSERVED.md`. Exit code `0` se **6/6 PASS**.

**Como o efeito é observado sem tocar no motor:** o mock do Ollama conta as
chamadas a `POST /api/generate`. Se o mesmo `request_id` chamar o modelo 2x,
houve efeito duplicado.

## 2.2 Resultado observado (execução de referência)

Rodado contra o clone atual do motor (`results/OBSERVED.md`): **3/6 PASS** — o
gap que este hand-off fecha.

| ID | Cenário | Esperado | Observado | Status |
|---|---|---|---|---|
| S1 | mensagem duplicada | modelo 1× | modelo **2×** | **FAIL** |
| S2 | falha após reservar | retry mesmo id = 200 | 502 → 200 | PASS |
| S3 | timeout do motor | 504 → retry 200 | 504 `AI_TIMEOUT` → 200 | PASS |
| S4 | retry após sucesso | replay, 0 novas chamadas | resposta igual, **1 nova chamada** | FAIL |
| S5 | falha antes de concluir | 502 → retry 200 | 502 `AI_INVALID_RESPONSE` → 200 | PASS |
| S6 | concorrência (2 entregas) | modelo 1x (ou 409) | **modelo 2x** | FAIL |

## 3. Como rodar

```
MOTOR_DIR=<checkout do motor> MOTOR_VENV_PY=<venv>/bin/python python3 d11_acceptance.py
# ou contra um motor já no ar:
MOTOR_BASE_URL=http://127.0.0.1:8000 GRIMBOTS_API_KEY=<chave> python3 d11_acceptance.py
```

O runner sobe um mock do Ollama (conta chamadas) + o motor via uvicorn. Ao final:
`results/observed.json` e `results/OBSERVED.md`.

## 4. Critério de aceite

- **S1, S4, S6** devem passar (idempotência de sucesso/concorrência).
- **S2, S3, S5** devem continuar passando (reserva liberada em falha).
- `409 REQUEST_IN_PROGRESS` (se adotado) deve ser **retryável**.
- Lado Grimbots: já trata `REQUEST_IN_PROGRESS` como retryável e **sem fallback**
  (`tests/test_d11_dedupe.py::test_request_in_progress_is_retryable_and_has_no_fallback`).

## 5. Garantias e limitações

**Garantias (após implementar):**
- Idempotência por `request_id`: o modelo é executado **no máximo uma vez** por
  janela; retries após sucesso recebem a **mesma resposta** (sem novo efeito).

**Limitações (documentadas, não são bugs):**
1. **At-most-once, não exactly-once.** Se o motor cair **depois de enviar** e
   **antes de gravar** a conclusão, o retry pode reprocessar. Idempotência exige
   persistência da conclusão (Redis/DB) — se o motor for **multi-instância**, o
   store precisa ser **compartilhado**.
2. `message_id` **não** vai no contrato → correlação por mensagem é
   responsabilidade da plataforma (já feita em `bot_manager._ai_turn_*`).
3. Redelivery do Telegram **após** a janela da plataforma gera **novo
   `request_id`** → o motor trata como nova tentativa (possível efeito duplicado;
   mitigado reduzindo a exposição da reserva da plataforma).
4. Dois `message_id` distintos com o mesmo texto **não** são deduplicados (por design).

## 6. Contra-assinatura

Ver `SIGNATURE.md`. **O D11 só é considerado fechado com os dois lados assinados**
e `3/6 → 6/6` no `d11_acceptance.py`.
