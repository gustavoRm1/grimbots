# Resultado — Bateria de Cenários Comerciais (Motor REAL)

- **Data:** 2026-10-20
- **Motor consumido (NÃO editado):** `github.com/gustavoRm1/grimbots-ai` @ `a54b9ddd383ae210fcae7d9e295425fc4fb88966` (branch `e4-subtle-buy-intent`)
- **Harness:** `tests/integration/test_commercial_scenarios_live.py`
- **Harness commit (esta branch):** `integrate/motor-a54b9dd` (a commitar nesta etapa)
- **Escopo:** apenas decisões comerciais do motor real. Sem Redis nesta bateria (persistência já auditada em etapa anterior, `test_persistence_real_redis_live.py` 11/11).
- **Resultado:** **19/21 verificações OK — 0 falhas técnicas, 2 observações de qualidade.**
- **Determinismo:** 2 execuções consecutivas → idênticas (19/21).

## O que é REAL vs MOCKADO

| Componente | Estado | Observação |
|---|---|---|
| Motor comercial `a54b9dd` | **REAL** (subprocess na porta efêmera) | decisões, guard_final_message, clamp/fallbacks reais |
| LLM (Ollama) | **MOCKADO** (HTTP roteirizado) | o motor *decide* com base nas saídas canônicas injetadas — os sinais de intenção/objeção/recusa são reais |
| Plataforma (`BotManager`) | **REAL** (`_ai_apply_objection_state`, `_ai_memory_updates`, `apply_state_update`) | persistência de objeção/memória exercitada pela plataforma |
| Telegram (`send_telegram_message`) | **MOCKADO** | `RoutingSpy` espelha os efeitos de `_handle_ai_turn` |
| Checkout (`_ai_route`) | **MOCKADO** | efeito `checkout`/`handoff` contabilizado pelo spy |
| Redis | **AUSENTE** nesta bateria | idempotência multi-turno já coberta em etapa anterior |

> Nenhuma validação ponta-a-ponta é declarada onde há mock. O veredito abaixo é sobre a **decisão comercial** do motor e os **efeitos roteados**.

## Matriz de veredito

| # | Cenário | Veredito | Evidência (ação / reason) |
|---|---|---|---|
| 1 | Lead curioso avança sem pressionar compra | ✅ APROVADO | `t1=ask_question` → `t2=continue` (nenhum checkout) |
| 2 | Intenção EXPLÍCITA + oferta ativa → checkout | ✅ APROVADO | `send_checkout`, efeito `['checkout']` |
| 2 | *Qualidade:* intenção SUTIL + oferta apresentada → checkout | ✅ APROVADO | `send_checkout` — honestidade sutil preservada |
| 3 | Objeção de preço detectada e **persistida pela plataforma** | ✅ APROVADO | `state.objection='achei muito caro'`, `ci.objection` espelhado |
| 3 | Objeção ativa + sinal de compra → checkout **BLOQUEADO** | ✅ APROVADO | `continue` / "Objecao de preco (price) ativa apos oferta: esclarecer sem reapresentar." |
| 3 | Resposta à objeção pertinente e **não reapresenta** oferta/checkout | ✅ APROVADO | `continue`, efeito `['message']` |
| 4 | Objeção **resolvida** + oferta ativa/permitida → libera checkout | ✅ APROVADO | `resolved=True`; `send_checkout`, efeito `['checkout']` |
| 4 | Resolvida mas oferta **inativa** → checkout bloqueado | ✅ APROVADO | `handoff_human` / efeito `['handoff']` |
| 4 | *Qualidade:* frase natural "pode mandar o link" como sinal de compra | ❌ OBSERVAÇÃO | `continue` / "Oferta ja apresentada; evitar repeticao sem motivo novo." |
| 5 | Recusa explícita → silêncio, sem oferta/pergunta/checkout | ✅ APROVADO | `do_not_respond`, efeito `['silence']` / "Recusa explicita do lead: nao insistir." |
| 6 | Pergunta repetida suprimida (memória respeitada) | ✅ APROVADO | 2º turno `next_question=None`; 1 pergunta registrada |
| 6 | Contexto/informação coletada preservados na conversa longa | ✅ APROVADO | histórico de perguntas íntegro |
| 7 | Alegação de ação externa concluída bloqueada/substituída | ✅ APROVADO | `guard_final_message` substitui / "Conteudo final bloqueado: alegacao nao comprovada/garantia/urgencia." |
| 7 | Garantia de resultado bloqueada/substituída | ✅ APROVADO | mensagem substituída |
| 7 | Urgência falsa (escassez) bloqueada/substituída | ✅ APROVADO | mensagem substituída |
| 7 | *Qualidade:* desconto inventado não é oferecido (guard dedicado ausente) | ✅ APROVADO* | sem alegação inventada na saída; *sem guard dedicado* (rótulo de qualidade) |
| 8 | Motor indisponível → erro tipado (fallback controlado, sem crash) | ✅ APROVADO | erro tipado `AIGatewayError` |
| 8 | IA desabilitada → 409 sem resposta (retomável sem duplicar) | ✅ APROVADO | HTTP 409; sem efeito colateral |
| 8 | Retomada preserva objeção (sem descarte) e mantém checkout bloqueado | ✅ APROVADO | `obj='achei caro'`; `continue` |
| 9 | *Qualidade:* "carro" NÃO tratado como objeção de preço | ❌ OBSERVAÇÃO | falso positivo — ver §Observações |
| 9 | *Qualidade:* "desinteressado" NÃO dispara sinal de compra | ✅ APROVADO* | não disparou; *risco latente* de match por substring |

## Observações de qualidade (reproduzíveis)

Estas **não são falhas técnicas** do motor: o motor se comporta exatamente conforme sua lógica publicada. São divergências do ideal comercial, com payload mínimo de reprodução para o dono do motor (sem editá-lo).

### Q1 — Variante natural de pedido de link não reconhecida
- **Turno:** `pode mandar o link` (após objeção resolvida, oferta ativa, `send_checkout` permitido)
- **Resultado:** `continue` / reason `Oferta ja apresentada; evitar repeticao sem motivo novo.`
- **Causa:** `"pode mandar o link"` não consta em `_DIRECT_PAYMENT_REQUEST_PHRASES` nem em `_SUBTLE_BUY_SIGNALS` (a lista tem `"manda o link"`, `"me passa o link"`, `"envia o link"`).
- **Payload mínimo:** `{"text":"pode mandar o link","available_offers":[oferta ativa],"allowed_actions":["send_checkout","..."]}` → esperado `send_checkout`, obtido `continue`.
- **Impacto:** perda de conversão em frase natural; exige reformulação pelo lead.

### Q2 — Falso positivo: "carro" aciona objeção de preço
- **Turno:** `vou comprar um carro novo, preciso juntar dinheiro`
- **Resultado:** `state.objection` **e** `ci.objection` = texto inteiro; reason `Objecao de preco ativa apos oferta: esclarecer sem reapresentar.`
- **Causa:** `"carro"` está em `_PRICE_WORDS` do motor **e** no gatilho `_AI_PRICE_OBJECTION_TRIGGERS` da plataforma (que espelha o motor) → `_is_price_text` verdadeiro.
- **Payload mínimo:** `{"text":"vou comprar um carro novo, preciso juntar dinheiro", "available_offers":[oferta ativa]}` → esperado sem objeção, obtido objeção persistida.
- **Impacto:** bot trava checkout e insiste em "esclarecer preço" em conversa sem objeção real; afeta também persistência da plataforma (objeção falsa gravada).

### Q3 (risco latente, não disparou) — match por substring
- `_SUBTLE_BUY_SIGNALS` contém `"interessado"`; `"desinteressado"` **contém** a substring. Na sonda `estou desinteressado nesse tipo de coisa` **não** disparou compra (outras regras precederam), mas o risco de falso positivo é estrutural (conferir se `_has_phrase` usa `in` sem limite de palavra).
- **Recomendação:** confirmar semântica de `_has_phrase` (match por substring vs token) no lado do motor.

## Reprodução

```bash
export GRIMBOTS_AI_MOTOR_DIR=/caminho/para/worktree-motor-a54b9dd
export GRIMBOTS_AI_VENV_PY=/caminho/para/venv/bin/python
python3 tests/integration/test_commercial_scenarios_live.py            # tabela + transcrições
python3 tests/integration/test_commercial_scenarios_live.py --json /tmp/scen.json
```

Sem `GRIMBOTS_AI_MOTOR_DIR`/`GRIMBOTS_AI_VENV_PY` o harness faz **SKIP** (exit 0).

## Regressão (toda verde vs `a54b9dd`)

- Offline: `d11_turn_release` 4/4, `e3_objection` 9/9, `d11_dedupe` 14/14, `e5_shadow_hardening` 22/22, `e5_shadow` 12/12, `phase6a` 66/66, `agent_respond` 10/10, `next_question` 11/11, `pytest tests/e4` 8/8.
- Integração: `persistence_redis` 11/11, `real_flow` 4/4, `motor_integration` 18/18, `e3_commercial` 12/12, `e3_multiturn` 9/9, `motor_live` 10/10, `e5_shadow_live` 4/4, `commercial_scenarios` 19/21 (0 técnicas).

## Limitações declaradas

- LLM mockado: as decisões refletem a lógica de sinal/guard do motor, não a variabilidade de um modelo real.
- Sem Redis nesta bateria; correlação `request_id`↔conversation↔checkout↔`Payment` não exercitada.
- `ai_generations` (Postgres, FK a `bots`) não exercitada (auditoria fail-open).
- Telegram/checkout reais não disponíveis — efeitos contabilizados por spy.
