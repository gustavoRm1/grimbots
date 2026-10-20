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
- [ ] **A3. Kill-switch operacional existe.** Hoje **não** há flag global de rollout nem de porcentagem. O único gate é `step_config.get('enabled', True) is False` por bloco (`bot_manager.py:4576`). Ver §(C) para a opção sem código vs. implementação proposta.
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

# Shadow: manter OFF no piloto inicial (evita dupla flag de decisão)
GRIMBOTS_AI_SHADOW=off
```

- **Gate por bloco:** ligar a IA apenas nos blocos explicitamente selecionados (`step_config.enabled != False`). Blocos desligados → `handoff` humano (comportamento atual, `bot_manager.py:4576`).
- **Contrato:** permanece **v1.0 byte-a-byte** por padrão.

---

## (C) Rollout Limitado + Kill-Switch

### Estado atual (limitação)
- **Não existe** flag de porcentagem de rollout nem kill-switch global. Alternativas sem código:
  - **C-sem-código:** ativar a IA em pouquíssimos **blocos** e/ou poucos **bots** manualmente, contando leads atingidos; desligar = `step_config.enabled=false` por bloco.
  - **C-com-código (proposta, requer autorização):** flag `GRIMBOTS_AI_ROLLOUT_PERCENT` (0–100) + `GRIMBOTS_AI_KILL_SWITCH` (bool) avaliados no início de `_handle_ai_turn`, com hash estável de `bot_id/telegram_user_id` para amostragem. **Não implementar sem autorização.**

### Proposta de plano de exposição
1. **Onda 0 (canário fechado):** 1 bot interno / 1 interlocutor de teste por N dias. Coletar decisões e efeitos.
2. **Onda 1:** ≤5% dos leads do(s) bloco(s) habilitado(s) (via C-com-código) ou poucos bots (C-sem-código). Janela curta e vigiada.
3. **Onda 2:** ≤25% se métricas de §D sem alerta.
4. **Sem onda 3 (100%) antes de:** A2 resolvido, A8 documentado, ≥1 ciclo completo de monitoramento estável.

### Kill-switch imediato (rollback operacional)
- **Imediato (segundos):** `GRIMBOTS_AI_KILL_SWITCH=true` (se C-com-código) → IA vira `handoff`/`do_not_respond`, sem coleta de decisões.
- **Sem código:** `step_config.enabled=false` nos blocos (deploy de config) + restart do serviço. Latência de configuração, não instantânea.
- **Contingência dura:** `GRIMBOTS_AI_API_URL` inválido → motor indisponível → erro tipado + fallback controlado (comportamento validado no cenário 8 — sem crash), mas **sem** IA. Preferir kill-switch explícito.

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

---

## Resumo do gate de ativação
**Ligar o piloto SOMENTE quando A1–A10 estiverem marcados.** Onda 0/1 com kill-switch disponível; sem onda 100% enquanto A2/Q1–Q3, A8 e a correlação de funil (§D) não estiverem resolvidos ou formalmente aceitos como risco.
