# Anexo — Divergências para o dev do `grimbots-ai`

> **Para:** dev do motor `grimbots-ai`. **De:** dev do Grimbots.
> **Base motor:** `8db1de7` (E0: `eb328c7` + `8db1de7`), pacote `1.4.0`.
> **Base Grimbots:** `origin/main` = `d41b527`.
>
> **Escopo:** apenas o que precisa de **decisão conjunta**. Documento **curto** —
> não exige ler os docs E0 da Grimbots. Nada aqui está implementado; nada será
> implementado sem acordo explícito. Contexto completo em
> `11_REVISAO_CONJUNTA_MOTOR_GRIMBOTS.md`.

## 1. Divergências que bloqueiam acordo

| # | Ponto | Lado motor (verificado) | Lado Grimbots (proposto) |
|---|---|---|---|
| D1 | **Rótulo de versão** | Fase 1 (`v1.1.0`) = memória; contrato "v1.1" = 4 campos de contexto (`ROADMAP:12`, alinhamento §1.1) | chama memória+resposta de "v1.2" (`02:§0`) |
| D3 | `reason` | ≤ **300** (`CONTRATO:§7`) | ≤ **200** |
| D4 | `offer_id` | ≤ **64** | ≤ **80** |
| D5 | **`state_update` whitelist** | 6 chaves: `collected_information`, `questions_already_asked`, `offers_already_presented`, `funnel_stage`, `lead_temperature`, `last_action` (`CONTRATO:§8.3`) | 8 chaves: as mesmas **sem `last_action`** + `conversation_summary`, `objection`, `interest` |
| D6 | **Limites da memória** | `last_assistant_message`≤2000; `collected_information`≤30 campos (chave≤60, val≤300); `questions_already_asked`≤20 (item≤300); `offers_already_presented`≤20 (item≤120); `turn_count` 0–100 (`schemas.py:103-118`) | ≤20 chaves (val≤200); questões ≤40 (item≤200); ofertas ≤20; turn_count ≥0 |
| D8 | **Alias `no_reply`** | fora do enum; não se expande enum; modelo emitindo isso → **fatal 502** (`schemas.py:22-25`, `CONTRATO:§4.6`) | propõe normalizar `no_reply`→`do_not_respond` |
| D10 | **`conversation_summary`** | gerado pela **plataforma** (`CONTRATO:§6.5`) | propõe que o **motor** gere via `state_update` |
| D11 | **Idempotência** | motor **não** deduplica `request_id` (só log, `app.py:180`) | precisa saber se pode contar com dedup |
| D12 | **Enum `intent`** | `oferta`/`informacao` fora do enum → **fatal 502** (known_failure, `API.md:§8`) | cliente não mascara; perde o turno |
| D14 | **Limites de schema × cliente** | `lead.name`≤60, `interest`/`objection`≤120, `Offer.id`≤64, `checkout_url`≤400 | clamps atuais: 80 / 200 / 80 / 500 → **risco 422** (a Grimbots vai apertar) |

## 2. Perguntas objetivas (sim/não ou valor)

1. **D1** — Adotamos o rótulo de **contrato** `1.0/1.1/1.2` (independente do pacote
   e da rota)? Onde entram os **6 campos de memória** no rótulo?
2. **D3/D4** — Valores finais de `reason` e `offer_id`?
7. **D5** — Whitelist final de `state_update`? Aceitam `conversation_summary`,
   `objection`, `interest`? Aceitam **excluir** `last_action` (calculado pela
   Grimbots)?
5. **D6** — Os limites de §4.1 do doc principal são os finais? Algum pode ser
   negociado?
6. **D10** — Quem gera o `conversation_summary`? (motor sugere via `state_update`
   ou Grimbots gera por conta?)
7. **D11** — O motor vai deduplicar `request_id` (idempotência) ou isso fica
   **inteiramente** com a plataforma?
8. **D8** — Adotar `no_reply` como alias, ou manter `do_not_respond` como único?
9. **D12** — Haverá correção do vocabulário oficial de `intent` (fase própria)?
10. **D14** — Confirmam os limites do schema (`lead.name` 60, `interest`/`objection`
    120, `Offer.id` 64, `checkout_url` 400) para eu apertar os clamps do cliente?
11. **D9** — `human_takeover=true` → 409: pretendem manter? (hoje a Grimbots envia
    o campo e não tem guard pré-chamada.)

## 2-A. Itens [RUNTIME] (não são fato até reproduzir)

- **D9/§6** — se o fluxo volta ao bloco AI com `human_takeover=true` sticky e
  recebe **409 HUMAN_TAKEOVER_ACTIVE**. Precisa de reprodução em execução.
- **D11/§7** — se um retry (429/503/504) pode causar **efeito duplicado** na
  plataforma (ex.: ação executada 2×).

## 3. Runtime a confirmar (lado motor)

- URL/base atual do deploy (ngrok) — o `HANDOFF-GRIMBOTS.md:11` ainda é a vigente?
- `ai_enabled`/`human_takeover` → 409: comportamento estável?
- Rate limit `30/min` (`config.py:63`) é o valor de produção?

## 4. Testes reproduzíveis pedidos

### T15 — divergência de enum `intent` (reprodutível) — **corrigido e validado**

**Objetivo:** tornar determinístico o `known_failure: invalid_intent_oferta`.

**Correção (válida no repo do motor):**
- o mock correto é a função **`ollama_client.generate`** (async), pois `app.py:19`
  faz `import ollama_client` e chama `await ollama_client.generate(prompt)`
  (`app.py:176`). **Não** existe `ollama_client.query`, e o alvo **não** é
  `api.ollama_client.*` (a suíte roda com `pythonpath = ["api"]`, `pyproject.toml`).
- `generate` devolve `{"response": "<texto JSON do modelo>", ...}` — o mock deve
  devolver a **string JSON**, não um dict já parseado (`app.py:196`).
- auth: override da dependência `require_api_key` (o `.env` de teste pode não ter chave).

```python
# tests/unit/test_intent_enum.py  (motor)
import json
import typing

from fastapi.testclient import TestClient

import app as app_module
import ollama_client
from auth import require_api_key
from schemas import Intent

app_module.app.dependency_overrides[require_api_key] = lambda: "test"
client = TestClient(app_module.app)

PAYLOAD_V1_0 = {
    "request_id": "req-t15-0001", "seller_id": "s1", "bot_id": "b1",
    "conversation_id": "c1", "bot_user_id": "u1",
    "bot_config": {"name": "Maya"}, "conversation_state": {},
    "recent_messages": [{"role": "user", "content": "oi"}],
}

def test_intent_enum_has_no_oferta_nem_informacao():
    vals = typing.get_args(Intent)
    assert "oferta" not in vals
    assert "informacao" not in vals

async def _fake_generate(prompt: str) -> dict:
    return {"response": json.dumps({
        "message": "ok", "intent": "oferta", "lead_temperature": "warm",
        "funnel_stage": "offer", "action": "continue", "next_question": None,
        "handoff_human": False, "risk": "low",
    })}

def test_intent_fora_do_enum_e_fatal_502(monkeypatch):
    monkeypatch.setattr(ollama_client, "generate", _fake_generate)
    r = client.post("/v1/agent/respond", json=PAYLOAD_V1_0,
                    headers={"X-API-Key": "test"})
    assert r.status_code == 502, r.text
    assert r.json()["error"]["code"] == "AI_INVALID_RESPONSE"
```

**Validação executada (2026-10-18)** em clone do motor (`8db1de7`) com venv
isolado (Python 3.11 + `fastapi==0.115.6`/`pydantic==2.10.4`), sem alterar o repo:

```
STATUS 502 BODY {"error":{"code":"AI_INVALID_RESPONSE",
                         "message":"Resposta invalida do modelo: intent invalido."}}
```

⇒ reprodução **confirmada**; a causa é `validator.py:78` ("intent invalido") →
fatal → `app.py:226-231` (`502 AI_INVALID_RESPONSE`).

**Lado Grimbots (alinhamento):** teste que garante que o cliente **não** envia nem
espera valores fora do enum, e que um `intent` inválido na resposta **não** é
mascarado (degrada para fallback, não executa ação). O mapa explícito proposto em
`13_RESPOSTA_DECISOES_PENDENTES.md` (D12) só vira teste **após** acordo.

### T16 — retry sem efeito duplicado (D11)

```python
# tests/unit/test_retry_idempotency.py  (Grimbots)
def test_retry_apos_503_executa_acao_uma_vez(monkeypatch):
    # 1a chamada: 503 AI_BUSY; 2a: 200 com action=send_checkout
    # espera: exatamente 1 ação executada; request_id inalterado entre tentativas
    ...
```

### T17 — compatibilidade byte-a-byte (ambos)

- **Motor:** `T1/T2` já especificados (`CONTRATO:§12`) — sem campos novos ⇒ prompt
  byte-a-byte.
- **Grimbots:** flag off ⇒ payload v1.0 idêntico ao golden
  (`tests/payloads/agent_respond_request.json`).
- **Conjunto:** nenhum campo novo obrigatório; response aditiva.

### T3–T7 / T8–T12 (motor, já especificados)

Contexto (`CONTRATO:§12`) e resposta (§12) — sem alteração; usá-los como gate de E1/E2.

## 5. Sequência acordada proposta (resumo)

```
Gate 0 (acordo D1–D14)
  → E-P0  Grimbots: apertar clamps (defensivo)
  → E1    Motor: schema aceita contexto + golden intacto
  → E-P1  Grimbots: persistir + ENVIAR memória/contexto (flag)
  → E2    Motor: response aditiva + validação não-fatal
  → E-P2  Grimbots: LER reason/offer_id/state_update (opt-in)
  → E4–E6 avaliação → shadow → rollout
```

Regra invariável: **v1.0 byte-a-byte com flag off** até a aceitação; nenhum passo
avança sem o gate anterior; nenhum deploy/ativação sem acordo explícito.
