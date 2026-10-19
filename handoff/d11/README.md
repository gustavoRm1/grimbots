# Hand-off D11 — idempotência por `request_id` no Grimbots AI Gateway

> **De:** time Grimbots (bloco `ai` / Fase 6A) · **Para:** dev do AI Gateway (motor, repo local)
> **Escopo:** contrato + teste de aceite executável. **Este pacote NÃO altera o
> repositório do motor** — é para o dev rodar no checkout dele e **contra-assinar**.
> **Não** há merge, deploy ou ativação de v1.1.
>
> **Status:** o motor implementou D11 em `444d4a2` / `4898325` (docs: v1.6.0).
> Re-executamos este pacote de forma **independente**: **CONTRATO 9/9 PASS**
> (`results/OBSERVED.md`, `results/MATRIZ_ESPERADO_OBSERVADO.md`).

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

Motor **antes** do hand-off (stateless, sem dedupe): **3/6 PASS** — S1/S4/S6
falhavam com efeito duplicado. Motor **após** `4898325`: **CONTRATO 9/9 PASS**.

| ID | Cenário | Esperado | Antes (3/6) | Agora (9/9) |
|---|---|---|---|---|
| S1 | mensagem duplicada | modelo 1× | FAIL (2×) | **PASS** (1×) |
| S2 | falha após reservar | retry mesmo id = 200 | PASS | PASS |
| S3 | timeout do motor | 504 → retry 200 | PASS | PASS |
| S4 | retry após sucesso | replay, 0 novas chamadas | FAIL (1 nova) | PASS (0) |
| S5 | falha antes de concluir | 502 → retry 200 | PASS | PASS |
| S6 | concorrência (2 entregas) | modelo 1x (ou 409) | **FAIL** (2×) | PASS (1×) |
| S7 | 409 `REQUEST_IN_PROGRESS` + `Retry-After` + replay | 409 c/ `Retry-After`; replay após concluir | — | PASS |
| S9 | D6: todos os campos no limite | 200 | — | PASS |
| S10 | D6: `content=4001` (1 acima) | 422 | — | PASS |
| S8 | **limitação**: dedupe após restart | store in-memory → re-executa | — | documentado |

## 3. Como rodar

```
MOTOR_DIR=<checkout do motor> MOTOR_VENV_PY=<venv>/bin/python python3 d11_acceptance.py
# ou contra um motor já no ar:
MOTOR_BASE_URL=http://127.0.0.1:8000 GRIMBOTS_API_KEY=<chave> python3 d11_acceptance.py
```

O runner sobe um mock do Ollama (conta chamadas) + o motor via uvicorn, registra
**versão/commit/config** do motor (via `/health` e `git`) e ao final grava
`results/observed.json`, `results/OBSERVED.md` e
`results/MATRIZ_ESPERADO_OBSERVADO.md`. Exit code `0` se **CONTRATO 9/9 PASS**.

## 4. Critério de aceite

- Cenários de **contrato** S1–S6, S7, S9, S10 → **9/9 PASS**.
- **S1, S4, S6** provam idempotência (sucesso/concorrência/sem execução dupla).
- **S2, S3, S5** provam que falha **libera** a reserva (retry legítimo).
- **S7** prova `409 REQUEST_IN_PROGRESS` com **`Retry-After`** e replay após concluir.
- **S9/S10** provam D6 end-to-end no motor (limite exato→200; 1 acima→422).
- **S8** é cenário de **limitação** (não de aceite): documenta o store in-memory.
- Lado Grimbots: trata `REQUEST_IN_PROGRESS` como retryável, **sem fallback**, e
  **libera** a reserva para permitir reentrega
  (`tests/test_d11_dedupe.py::test_request_in_progress_releases_and_has_no_effects`,
  `::test_request_in_progress_then_redelivery_succeeds`,
  `::test_client_honors_retry_after_header`).

## 5. Garantias e limitações

**Garantias (após implementar):**
- Idempotência por `request_id`: o modelo é executado **no máximo uma vez** por
  janela; retries após sucesso recebem a **mesma resposta** (sem novo efeito).

**Limitações (documentadas, não são bugs):**
1. **At-most-once, não exactly-once.** Se o motor cair **depois de gerar** a
   resposta e **antes de gravar** a conclusão, o retry pode reprocessar (o modelo
   re-executa). Observado no **S8**: após restart, o mesmo `request_id` **não**
   tem replay (`chamadas 1 → 2`). O store atual é **in-memory** (single-instance);
   multi-instância/restart exige store **compartilhado** (Redis/DB).
   **Correção concreta:** gravar a resposta no store **imediatamente após o
   modelo** (write-ahead, antes de montar/serializar a saída) e usar store
   compartilhado com `complete()` atômico.
2. `message_id` **não** vai no contrato → correlação por mensagem é
   responsabilidade da plataforma (já feita em `bot_manager._ai_turn_*`).
3. Redelivery do Telegram **após** a janela da plataforma gera **novo
   `request_id`** → o motor trata como nova tentativa (possível efeito duplicado;
   mitigado reduzindo a exposição da reserva da plataforma).
4. Dois `message_id` distintos com o mesmo texto **não** são deduplicados (por design).

## 6. Contra-assinatura

Ver `SIGNATURE.md`. **O D11 só é considerado fechado com os dois lados assinados**
e **CONTRATO 9/9 PASS** no `d11_acceptance.py` (execução independente), com a
limitação S8 documentada e aceita.

## 7. Divergências registradas (lado motor — **não** corrigidas aqui)

1. **Versão reportada:** `/health` e OpenAPI retornam `service_version = "1.0.0"`
   (`api/config.py:27`) enquanto docs/CHANGELOG/badge dizem **v1.6.0**. O contrato
   versionado (`contract_version`) não é afetado, mas a versão do serviço diverge.
   **Correção sugerida (motor):** `service_version = "1.6.0"`.
2. **Store in-memory / single-instance** (limitação S8): documentada no ADR 0013;
   exige store compartilhado para >1 worker/instância e para durabilidade a restart.
