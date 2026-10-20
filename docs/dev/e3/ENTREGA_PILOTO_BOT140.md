# Entrega — Piloto IA Comercial (bot 140 · Cristinha OVP)

Data: 2026-10-20
Autor: implementação assistida
Escopo: ativar e testar a IA comercial EXCLUSIVAMENTE no bot 140, sem alterar
o comportamento normal da Grimbots.

---

## 1. Commit efetivamente implantado

- **`f4c3a8d196506e30bbf31291a540db0899ae1a85`**
  (`feat(piloto): allowlist explicita por bot (GRIMBOTS_AI_BOT_ALLOWLIST) para isolar IA ao bot 140`)
- Branch: `q2-objection-contextual-detection` (fast-forward puro a partir de `main @ d41b527`).
- **Produção (container LXC `grimbots`, host 173.249.0.206):** `HEAD = f4c3a8d` (verificado).
- Consolidação por `git merge --ff-only` — **sem** sobrescrever trabalho e **sem** conflitos.
- Untracked preservados: `.env.bak_20261015_165923`, `.env.pilot_backup_20261020_150047`, `run_migration.py`.

## 2. Configuração exata que restringe a IA ao bot 140

Mecanismo: **allowlist explícita por bot** (nova, mínima e aditiva).

`.env` de produção (3 chaves adicionadas; demais intactas):
```
GRIMBOTS_AI_KILL_SWITCH=false
GRIMBOTS_AI_ROLLOUT_PERCENT=100
GRIMBOTS_AI_BOT_ALLOWLIST=140
```

Código:
- `internal_logic/core/config.py`: `GRIMBOTS_AI_BOT_ALLOWLIST` (set de IDs via env, separados por vírgula) + registro em `app.config`.
- `bot_manager.py`: `_ai_bot_allowlisted(bot_id)` + gate no início de `_handle_ai_turn`, **antes** do rollout percentual:
  - allowlist vazia/ausente → sem trava por bot;
  - allowlist não vazia → **SOMENTE** os IDs listados; os demais vão para HUMANO (mesmo caminho de `enabled=False`);
  - fail-safe: erro de leitura → `False` (nunca amplia exposição).

Verificação em runtime (no servidor):
```
ALLOWLIST: [140]
KILL_SWITCH: False
ROLLOUT_PERCENT: 100.0
allowlisted(140): True
allowlisted(141): False
allowlisted(1): False
```

Estrutural (defesa em profundidade): **apenas o bot 140 possui um step `type='ai'`** (verificado em todos os 86 `BotConfig`; `bot_id=140`, step_id=1, `enabled=true`, `mode=auto`). Nenhum outro bot tem bloco IA.

## 3. Por que o relatório anterior encontrou "zero bots com etapa ai"

Erro de varredura no relatório anterior: `flow_steps` é armazenado como **string JSON**, e a checagem anterior serializava o objeto como dict — não casava o padrão. Re-verificação correta (parse de string → lista) aponta **1 bot com step `ai`**: o **140**. Bot 140 = `Ana Cristina` / username `cristinhiaovipobot`, `flow_enabled=true`, `flow_start_step_id=1`, fluxo `step1(ai) → checkout → step2(payment)`.

## 4. Testes executados e resultados

### 4.1 Automatizados (offline — sem motor/Telegram/Redis reais)
| Suíte | Resultado |
|---|---|
| `tests/test_ai_rollout_kill_switch.py` (13 + **7 novos** allowlist) | **20/20** |
| `tests/test_ai_non_ai_isolation.py` (**novo**, 8 testes) | **8/8** |
| `test_q2_objection_contextual.py` | 13/13 |
| `test_e3_objection_persistence.py` | 9/9 |
| `test_d11_turn_release.py` + `test_d11_dedupe.py` | 4/4 + 14/14 |
| `test_ai_next_question_dedup.py` | 11/11 |
| `test_phase6a_contract_v11.py` | 66/66 |
| `test_e5_shadow.py` + `test_e5_shadow_hardening.py` | 22/22 + 12/12 |
| `test_agent_respond_contract.py` + `pytest tests/e4` | 10/10 + 8/8 |

Novos testes cobrem: allowlist (vazia/listada/múltiplos/parsing env/fail-safe), bot fora da allowlist desviado, bot permitido não desviado, e **isolamento de bots convencionais** (todos os tipos de step convencionais nunca acionam a IA; `_is_ai_step` só é `True` para `type='ai'`).

### 4.2 Integração/integrais (motor real `a54b9dd`, Redis real)
| Suíte | Resultado |
|---|---|
| `test_grimbots_real_flow_live.py` (dirige o `_handle_ai_turn` REAL) | **4/4** |
| `test_persistence_real_redis_live.py` | 11/11 |
| `test_motor_integration_live.py` | 18/18 |
| `test_commercial_scenarios_live.py` | 20/21 (1 observação = **Q1** do motor) |
| `test_e3_commercial_live.py` | 12/12 |
| `test_e3_multiturn_live.py` | 9/9 |

> Nota de honestidade: `test_grimbots_real_flow_live` contra o motor **default** (`grimbots-ai @ 8db1de7`) dá 3/4 (T2 falha). Contra o motor **`a54b9dd`** dá **4/4**. O T2 é sensível à versão do motor (bloqueio de checkout por objeção persistida). **Não** é regressão do nosso código (o teste não usa a allowlist).

### 4.3 Verificações no motor REAL de produção (via endpoint configurado)
- `GET /health` → 200 · `service=grimbots-ai-gateway` · `version=1.6.0` · `ollama=reachable` · `model=grimbots-sales:latest`.
- Sonda comportamental via `build_payload` + `respond` (cliente real):
  - `"tenho um carro velho"` → `ask_question`, `intent=interesse` (**não** é objeção de preço → comportamento Q2 ✓)
  - `"achei muito caro"` → `intent=objecao` ✓
  - `"quero fechar agora"` → `send_checkout`, `intent=compra` ✓
- Conclusão: o motor servido tem o comportamento do `a54b9dd` (Q2 presente). `version 1.6.0` = mesma do `a54b9dd`.

## 5. Estado do serviço, workers, filas e tarefas (pós-restart)

- `grimbots.service`: **active (running)** desde 2026-10-20 15:01:30 UTC; gunicorn `--workers 4 --worker-class eventlet`.
- `GET /health` (127.0.0.1:5000) → **HTTP 200**.
- Redis: **PONG**.
- Workers: **23** unidades ativas (grimbots, celery, rq-scheduler, rq-worker-gateway/tasks/webhook + rq-worker@gateway/marathon/tasks).
- Filas Redis: `default=0, gateway=0, tasks=0, webhook=0, marathon=0`; **failed registry = 0**.
- **0 erros `[IA]`** no `error.log` desde o restart.

## 6. Evidências de que bot sem IA continua normal

- `POST /webhook/telegram/47` (bot convencional) → **HTTP 200** (access log também mostra `/webhook/telegram/45` → 200).
- No servidor: bot convencional 47 (`message/payment/access`) → `_is_ai_step` = False para todos os seus steps; `_ai_bot_allowlisted(47)` = False.
- Um bloco `ai` em bot NÃO listado (141) → **desviado para HUMANO**, sem mensagem, sem checkout, sem estado.
- `ai_generations` continua sendo gravada apenas no caminho IA (fail-open), como antes.

> Erros 401/429 no `error.log` são de **sincronização de token do Telegram** (`sincronizar Bot N`) — **pré-existentes** e sem relação com a IA.

## 7. Resultado do primeiro teste real da Cristinha OVP (140)

Teste controlado: `_handle_ai_turn` REAL em produção, motor REAL, Redis REAL; **Telegram stubado** (nenhum lead real contatado) e **checkout apenas observado** (nenhum pagamento executado).

Lead sintético `pilot_988799af`:
| Turno | Entrada | Saída (simulada) | Rota |
|---|---|---|---|
| 0 | `oi, tudo bem?` | saudação + pergunta de qualificação | — |
| 1 | `quanto custa?` | redireciona à qualificação (sem preço precoce) | — |
| 2 | `achei muito caro` | acolhe objeção, sem checkout | — |
| 3 | `entendi, vale a pena, pode mandar o link` | ainda em qualificação (**Q1**: link não reconhecido) | — |

Estado persistido (Redis real): `lead_temperature=warm`, `funnel_stage=qualification`, `turn_count=4`, `questions_already_asked` deduplicado, `collected_information={objection:"achei muito caro", objection_resolved:true}`.
Auditoria: 4 novas linhas em `ai_generations` (ids 37–40), bot 140, `response_valid=t`, intents `saudacao`/`interesse`/`objecao`/`interesse`.

**Observação aberta (Q1, motor):** `"pode mandar o link"` não é reconhecido como sinal de compra → não houve checkout. Documentado em `docs/dev/e3/HANDOFF_MOTOR_Q1_Q3.md` (responsabilidade do motor). Não é bug da plataforma.

## 8. Desligamento da IA e rollback

### Desligar a IA (sem rollback de código)
Adicionar/alterar no `.env` de produção e reiniciar o serviço:
```
GRIMBOTS_AI_KILL_SWITCH=true
```
Efeito **verificado no servidor**: TODO bloco `ai` (inclusive o bot 140) é desviado para HUMANO, sem responder, sem coletar decisão e sem efeito.

Alternativa de escopo (só remover o piloto, mantendo a IA desligada):
```
GRIMBOTS_AI_BOT_ALLOWLIST=
```

### Rollback de código
```
cd /root/grimbots
git checkout d41b5275c281ac627ee5050c92606c407643a60d
systemctl restart grimbots.service
```
Backup do `.env` pré-piloto: `/root/grimbots/.env.pilot_backup_20261020_150047`.
(`.env` é recriável a partir do backup; nenhum dado de banco é apagado.)

## 9. Garantias de escopo / não-tocado

- E5/shadow e a migration `add_ai_shadow_decisions.py`: **NÃO ativados** (tabela `ai_shadow_decisions` inexistente; `GRIMBOTS_AI_SHADOW`/`CONTRACT` ausentes → defaults off/v1.0).
- D11: mantido em Redis (não alterado; não habilitado SQLite).
- Nenhum worker desativado; nenhuma mudança arquitetural; nenhuma remoção de funcionalidade.
- Segredos (API keys, tokens) **não** foram expostos em relatórios/logs deste trabalho.

## 10. Bloqueios / limitações remanescentes

1. **Q1 (motor):** `"pode mandar o link"` não dispara checkout — decisão do dono: publicar documentado.
2. **Endpoint:** `GRIMBOTS_AI_API_URL` continua apontando para túnel **ngrok** (`majority-joyfully-mama.ngrok-free.dev`). Funcional e com o comportamento `a54b9dd` confirmado, porém é um host temporário — risco operacional se o túnel mudar.
3. **Checkout real:** step 2 (payment) de bot 140 tem `product_name=''` e `price=None`; validar a geração de PIX quando for testar o caminho de compra completo (não executado — sem autorização para pagamento).
4. **Ativação ampliada:** NÃO fazer sem autorização explícita (allowlist permanece `140`).

---

### Critério de sucesso
✔ A Grimbots continua operacional em todas as funções existentes (health 200, workers/filas/scheduler ativos, webhook convencional 200).
✔ Somente a Cristinha OVP (bot **140**) usa a IA — garantido por allowlist explícita + único bloco `ai` existente.
