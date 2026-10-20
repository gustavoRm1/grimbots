# Handoff ao dono do motor — Observações Q1–Q3 (motor `a54b9dd`)

- **Data:** 2026-10-20
- **Origem:** bateria de cenários comerciais (`docs/dev/e3/RESULTADO_CENARIOS_COMERCIAIS.md`)
- **Motor:** `github.com/gustavoRm1/grimbots-ai` @ `a54b9ddd383ae210fcae7d9e295425fc4fb88966` (branch `e4-subtle-buy-intent`)
- **Repo do motor NÃO foi alterado.** Este documento é o pedido formal de correção.
- **Divisão de responsabilidades:** a plataforma Grimbots é dona da **persistência** da objeção (contrato motor L668-669). O motor é dono da **classificação** dos sinais. Q2 foi corrigido no lado da plataforma (não regra comercial duplicada); Q1/Q3 são do motor.

Cada item traz: **payload mínimo**, **resultado atual**, **resultado esperado** e **impacto**.

---

## Q1 — Variante natural de pedido de link não reconhecida

**Entrada (payload mínimo):**
```json
{
  "text": "pode mandar o link",
  "available_offers": [{"id": "of1", "name": "Curso Pro", "price": "R$ 97",
                         "checkout_url": "https://x/y", "active": true}],
  "allowed_actions": ["send_checkout", "continue", "ask_question"],
  "conversation_state": {"funnel_stage": "offer"},
  "collected_information": {"objection": "achei caro", "objection_resolved": true}
}
```
**Resultado atual:** `action=continue`, `reason="Oferta ja apresentada; evitar repeticao sem motivo novo."`
**Resultado esperado:** `action=send_checkout`.
**Causa:** `"pode mandar o link"` não consta em `_DIRECT_PAYMENT_REQUEST_PHRASES` (que tem `"manda o link"`, `"me passa o link"`, `"envia o link"`) nem em `_SUBTLE_BUY_SIGNALS`.
**Impacto:** perda direta de conversão — o lead pede o link de forma natural e o bot não fecha.

**Sugestão (não vinculante):** adicionar variantes naturais/equivalentes (ex.: `"pode mandar"`, `"pode enviar o link"`, `"manda ai"`, `"manda pra mim"`, `"quero o link"`) ou aplicar normalização que reduza pedidos diretos a uma forma canônica.

---

## Q2 — Falso positivo: palavra "carro" (veículo) aciona objeção de preço
*(corrigido no lado PLATAFORMA; permanece no MOTOR)*

**Entrada (payload mínimo):**
```json
{
  "text": "vou comprar um carro novo, preciso juntar dinheiro",
  "available_offers": [{"id": "of1", "name": "Curso Pro", "price": "R$ 97",
                         "checkout_url": "https://x/y", "active": true}],
  "allowed_actions": ["send_checkout", "continue", "ask_question"]
}
```
**Resultado atual (motor):** a palavra `"carro"` pertence a `_PRICE_WORDS = {"preco","preço","custo","valor","caro","carro"}`; `_is_price_text` faz interseção de tokens → `{carro}` ⇒ objeção de preço ativa → checkout bloqueado ("Objecao de preco (price) ativa apos oferta").
**Resultado esperado:** sem objeção; `send_checkout` permitido.
**Causa:** `"carro"` no conjunto de palavras de preço (provável tolerância a erro de digitação de "caro").
**Impacto:** conversa sem objeção real é tratada como objeção → bot insiste em "esclarecer preço" e trava o fechamento.

**Contexto da correção na plataforma:** removemos `"carro"` dos gatilhos e passamos a casar por **limite de palavra/frase** (evitando também `"caro"` ⊂ `"caroteno"`). Se o motor remover/ajustar `"carro"`, plataforma e motor voltam a ficar alinhados sem regra duplicada divergente.

**Sugestão (não vinculante):** remover `"carro"` de `_PRICE_WORDS` ou tratá-lo apenas como candidato a typo de "caro" com confirmação contextual.

---

## Q3 — Risco latente: match por substring em sinais de compra

**Entrada (payload mínimo):**
```json
{
  "text": "estou desinteressado nesse tipo de coisa",
  "available_offers": [{"id": "of1", "active": true}],
  "allowed_actions": ["send_checkout", "continue"]
}
```
**Resultado atual:** neste caso **não** disparou compra (outras regras precederam), mas `_has_phrase` usa `phrase in text` (substring) e `"interessado"` ∈ `_SUBTLE_BUY_SIGNALS` **está contido** em `"desinteressado"`.
**Resultado esperado:** `"desinteressado"` nunca conta como sinal de compra.
**Impacto:** risco estrutural de falso positivo (fechar para um lead que recusou). Não reproduzido como falha no harness, mas latente.

**Sugestão (não vinculante):** trocar `_has_phrase` por casamento com limite de palavra (mesma abordagem adotada na plataforma: `_ai_phrase_boundary_match`), ou revisar a lista.

---

## Resumo
| ID | Lado | Severidade | Estado |
|---|---|---|---|
| Q1 | Motor | Conversão | Aberto — encaminhado |
| Q2 | Motor (persistência: plataforma) | Fechamento indevido | **Plataforma corrigido**; ajuste do motor opcional p/ alinhar |
| Q3 | Motor | Risco latente | Aberto — encaminhado |

**Referência de repro:** `tests/integration/test_commercial_scenarios_live.py` (cenários 4 e 9) + `tests/test_q2_objection_contextual.py` (plataforma).
