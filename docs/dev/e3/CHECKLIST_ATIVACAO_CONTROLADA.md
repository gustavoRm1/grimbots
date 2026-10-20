# Checklist — Ativação Controlada da IA para Leads Reais

- **Data:** 2026-10-20
- **Motor alvo:** `a54b9dd` (`github.com/gustavoRm1/grimbots-ai`)
- **Branch plataforma:** `integrate/motor-a54b9dd`
- **Base obrigatória:** `docs/dev/e3/RESULTADO_CENARIOS_COMERCIAIS.md` (19/21, 0 falhas técnicas, 2 observações de qualidade)

> Objetivo: ligar a IA em **produção controlada** (percentual pequeno de bots/leads) com **kill-switch imediato**, sem migrações, sem mudar default de contrato, sem `D11_STORE=sqlite`.
> **Nada neste checklist foi ativado.** Todos os itens são pré-condições a cumprir antes do piloto.

Estrutura: **(A) Pré-condições bloqueantes** → **(B) Configuração de ativação** → **(C) Rollout limitado + kill-switch** → **(D) Monitoramento** → **(E) Rollback** → **(F) Garantias comportamentais exigidas**.

---

## (A) Pré-condições BLOQUEANTES (não ligar sem todas)

- [ ] **A1. Contrato do AI Gateway confirmado.** Envio v1.1 (`agent_profile`, `flow_resources`, `context_policy`, `contract_version`) só após confirmação de que o Gateway aceita os campos (`extra=forbid` → 422). Manter `GRIMBOTS_AI_CONTRACT=v1.0` até lá.
- [ ] **A2. Observações de qualidade do relatório endereçadas ou aceitas por escrito.**
  - [ ] Q1: variante natural de pedido de link não reconhecida (perda de conversão).
  - [ ] Q2: falso positivo de objeção por palavra `"carro"` (bloqueia checkout + grava objeção falsa).
  - [ ] Q3: risco de match por substring em `_SUBTLE_BUY_SIGNALS` (`interessado` ⊂ `desinteressado`).
  - (Correções no **lado do motor**; a plataforma **não** deve manter 2ª cópia concorrente das listas — hoje ela espelha `_AI_PRICE_OBJECTION_TRIGGERS`. Alinhar em uma única fonte quando o motor for ajustado.)
- [ ] **A3. Kill-switch operacional existe.** ✅ **Implementado** (`GRIMBOTS_AI_KILL_SWITCH` + `GRIMBOTS_AI_ROLLOUT_PERCENT`, ver §C). Pendente apenas a validação operacional em ambiente real.
- [ ] **A4. Credenciais/segredos no ambiente de produção** (não em código): `GRIMBOTS_AI_API_URL`, `GRIMBOTS_AI_API_KEY`, `GRIMBOTS_AI_SHADOW_SECRET` (se shadow ligado).
- [ ] **A5. `GRIMBOTS_AI_MOCK=false`** em produção (confirmar; mock nunca em prod).
- [ ] **A6. `GRIMBOTS_AI_MOTOR_VERSION` e `GRIMBOTS_AI_MOTOR_COMMIT` preenchidos** com a versão real do motor em produção (hoje default vazio → auditoria fica sem rastro de versão).
- [ ] **A7. Persistência da objeção validada em produção** (a plataforma é dona do dado — contrato motor L668-669). Confirmar `_ai_apply_objection_state` em pre-payload (`~L4620`) e em `_persist` (`~L4770`); cobrir Redis real (etapa anterior: 11/11 em db isolado).
- [ ] **A8. D11 (at-most-once) confirmado em produção.** `D11_STORE=memory` é por-processo/single-node. Se houver >1 worker/processo, idempotência não está garantida — documentar como limitação ou aguardar `D11_STORE` distribuído (não autorizado hoje).
- [ ] **A9. Auditoria `ai_generations` (Postgres) funcional.** Hoje fail-open e FK a `bots`; validar escrita e não regressão. Definir retenção.
- [ ] **A10. Observabilidade mínima pronta** (§D): log de decisão, métrica de ação, alerta de erro do motor.

---

## (B) Configuração de Ativação (valores propostos)

```
GRIMBOTS_AI_API_URL=<endpoint do AI Gateway v1.0>
GRIMBOTS_AI_API_KEY=<segredo>
GRIMBOTS_AI_MOCK=false
GRIMBOTS_AI_CONTRACT=v1.0            # NÃO subir para v1.1 antes de A1
GRIMBOTS_AI_TIMEOUT=90
GRIMBOTS_AI_MOTOR_VERSION=<tag>
GRIMBOTS_AI_MOTOR_COMMIT=a54b9ddd383ae210fcae7d9e295425fc4fb88966

# Rollout controlado (piloto) — ver §C
GRIMBOTS_AI_KILL_SWITCH=false
GRIMBOTS_AI_ROLLOUT_PERCENT=5        # onda 1; 100 numa onda 0 (canário)

# Shadow: manter OFF no piloto inicial (evita dupla flag de decisão)
GRIMBOTS_AI_SHADOW=off
```

- **Gate por bloco:** ligar a IA apenas nos blocos explicitamente selecionados (`step_config.enabled != False`). Blocos desligados → `handoff` humano (comportamento atual, `bot_manager.py:4576`).
- **Contrato:** permanece **v1.0 byte-a-byte** por padrão.

---

## (C) Rollout Limitado + Kill-Switch

### Mecanismo implementado (branch `q2-objection-contextual-detection`)
- **`GRIMBOTS_AI_KILL_SWITCH`** (bool, default `false`): quando ligado, **todo** bloco `ai` é desviado para HUMANO pelo mesmo caminho de `enabled=False` (`_handle_ai_turn`, logo após o gate do bloco, antes de ler estado/reservar turno/efeito). Sem resposta, sem coleta de decisão, sem efeito.
- **`GRIMBOTS_AI_ROLLOUT_PERCENT`** (0–100, default `100`): leads **fora** do bucket determinístico `sha256("rollout:{bot}:{lead}")` mod 100 vão para HUMANO (mesmo caminho seguro). Dentro do bucket, o fluxo normal continua (e todas as proteções a jusante permanecem).
- **Config ausente/inválida => fail-safe:** kill-switch off; percentual inválido/fora da faixa clampa para 0–100 e valor ilegível cai em `100` (não reduz exposição silenciosamente). Nunca >100 nem negativo.
- **NUNCA amplia** exposição: o gate só REMOVE leads da IA. Não reativa bloco `enabled=False`, não contorna `human_takeover` sticky, permissões efetivas, oferta ativa nem guardas de conteúdo (todos verificados a jusante).
- **Testes:** `tests/test_ai_rollout_kill_switch.py` (13/13) — desligamento imediato, elegibilidade determinística, limites 0/100/50%, config ausente/inválida, e não-contorno de `enabled=False`/`human_takeover`.

### Plano de exposição (ondas)
1. **Onda 0 (canário fechado):** 1 bot interno / 1 interlocutor de teste por N dias. `GRIMBOTS_AI_ROLLOUT_PERCENT=100` num único bloco/bot. Coletar decisões e efeitos.
2. **Onda 1:** `GRIMBOTS_AI_ROLLOUT_PERCENT=5` no(s) bloco(s) habilitado(s). Janela curta e vigiada.
3. **Onda 2:** `GRIMBOTS_AI_ROLLOUT_PERCENT=25` se métricas de §D sem alerta.
4. **Sem onda 3 (100%) antes de:** A2 resolvido, A8 documentado, ≥1 ciclo completo de monitoramento estável.

> O rollout é **por processo**: o percentual é lido do ambiente na inicialização. Trocar o valor exige restart do serviço (não é hot-reload). Planejar janelas.

### Kill-switch imediato (rollback operacional)
- **Imediato:** `GRIMBOTS_AI_KILL_SWITCH=true` + restart do serviço → IA vira `handoff`, sem coleta de decisão (ver §Procedimento Operacional).
- **Por bloco:** `step_config.enabled=false` (deploy de config) + restart.
- **Contingência dura:** `GRIMBOTS_AI_API_URL` inválido → motor indisponível → erro tipado + fallback controlado (cenário 8, sem crash), mas **sem** IA. Preferir kill-switch explícito.

---

## (D) Monitoramento (obrigatório durante o piloto)

- [ ] **Log de decisão por turno:** `action`, `reason`, `funnel_stage`, `request_id` (sem texto do lead em claro por padrão).
- [ ] **Métricas:** distribuição de `action`; taxa de `handoff_human`; taxa de `do_not_respond`; taxa de `send_checkout`; erros do motor; timeouts.
- [ ] **Alertas:** erro/timeout do motor acima do limiar; pico de `handoff` inesperado; `send_checkout` sem oferta ativa (deve ser 0 — ver §F); objeção persistida sem gatilho real (medir Q2).
- [ ] **Correlação de funil:** `request_id` ↔ conversa ↔ checkout ↔ `Payment` (hoje **inexistente** — implementar ou declarar como lacuna de observabilidade).

---

## (E) Rollback

1. Kill-switch (§C) / `step_config.enabled=false`.
2. Confirmar que blocos afetados voltam a `handoff` humano (comportamento pré-IA).
3. Não reverter dados de memória/objeção (dados do lead são da plataforma); apenas parar novas coletas de decisão.
4. Registrar incidente + payload de reprodução e encaminhar ao dono do motor (sem editar motor).

---

## (F) Garantias comportamentais exigidas (verificar em produção)

| Garantia | Como verificar | Status (bateria mock) |
|---|---|---|
| **Anti-duplicidade** (sem resposta/efeito duplicado) | métrica de mensagens/efeito por `request_id`; D11 at-most-once | validado offline/Redis isolado; **revalidar em prod** |
| **Respeito a recusa / handoff humano** | cenário recusa → `do_not_respond`; bloco off → `handoff` | ✅ aprovado (cenário 5 / gate L4576) |
| **Bloqueio de checkout sem oferta ativa/permissão efetiva** | `send_checkout` só com oferta ativa **e** ação permitida | ✅ aprovado (cenário 4b) |
| **Proibição de alegações não comprovadas** | `guard_final_message` substitui/bloqueia | ✅ aprovado (cenário 7) |
| **Sem desconto inventado** | ausência de desconto na saída | ⚠️ aprovado *sem guard dedicado* — observar |
| **Objeção persistida corretamente** | `state.objection`/`ci.objection` coerentes; resolvida limpa estado | ✅ aprovado (cenários 3/4/8) |
| **Q2 — falso positivo "carro novo"** | detecção contextual (limite de palavra) | ✅ corrigido na plataforma (`test_q2_objection_contextual.py` 13/13) |
| **Rollout não contorna proteções** | `enabled=False` e `human_takeover` vencem o gate | ✅ `test_ai_rollout_kill_switch.py` 13/13 |

---

## (G) Procedimento Operacional — Ativação Controlada

> Executar **somente após autorização**. Nenhum passo abaixo foi executado.

### G1. Pré-ativação (checklist)
1. Fechar itens A1–A10 (§A).
2. Garantir `GRIMBOTS_AI_CONTRACT=v1.0`, `GRIMBOTS_AI_SHADOW=off`, `GRIMBOTS_AI_MOCK=false`.
3. Definir `GRIMBOTS_AI_KILL_SWITCH=false` e `GRIMBOTS_AI_ROLLOUT_PERCENT=<onda>`.
4. Registrar baseline de métricas (pré-IA) para comparação.

### G2. Onda 0 (canário fechado)
1. `.env`: `GRIMBOTS_AI_ROLLOUT_PERCENT=100` + habilitar **um** bloco/bot de teste.
2. `pm2 restart <api>` (rollout é lido na inicialização).
3. Validar: lead de teste recebe decisão da IA; demais blocos seguem `handoff`.
4. Observar §D por N dias; confirmar ausência de alertas e de falso handoff.

### G3. Onda 1 (≤5%)
1. `.env`: `GRIMBOTS_AI_ROLLOUT_PERCENT=5`.
2. `pm2 restart <api>`.
3. Confirmar em logs `🎯 [IA] lead fora do rollout (5%) - seguindo para HUMANO` para ~95% dos leads.
4. Observar métricas/alerta; janela curta.

### G4. Onda 2 (≤25%)
- Mesmo procedimento, `GRIMBOTS_AI_ROLLOUT_PERCENT=25`, somente se Onda 1 sem alerta e A2/A8 resolvidos/aceitos.

### G5. Kill-switch / rollback (qualquer momento)
1. `.env`: `GRIMBOTS_AI_KILL_SWITCH=true`.
2. `pm2 restart <api>`.
3. Verificar log `⛔ [IA] kill-switch global ligado - desviando para HUMANO`.
4. Confirmar: nenhuma mensagem da IA, nenhum checkout, blocos afetados em `handoff`.
5. Não reverter dados de memória/objeção (dados do lead são da plataforma).
6. Registrar incidente + payload de reprodução; encaminhar ao dono do motor.

### G6. Verificação pós-mudança
- [ ] Log de gate correto (kill-switch/fora-do-rollout).
- [ ] Zero `send_checkout` sem oferta ativa.
- [ ] `human_takeover` ainda respeitado (IA silenciosa).
- [ ] Recusas → `do_not_respond` (nenhum insistência).
- [ ] Sem duplicidade de efeito por `request_id` (D11).
- [ ] Percentual efetivo ≈ configurado (contagem de elegíveis vs total).

---

## Resumo do gate de ativação
**Ligar o piloto SOMENTE quando A1–A10 estiverem marcados e a autorização for dada.** Onda 0/1 com kill-switch disponível; sem onda 100% enquanto A2/Q1–Q3 (motor), A8 e a correlação de funil (§D) não estiverem resolvidos ou formalmente aceitos como risco.
