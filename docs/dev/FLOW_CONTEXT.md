# 🧠 FLOW CONTEXT — Dossiê de Desenvolvimento

> **Fonte única de verdade** para qualquer dev (humano ou IA) tocar no Flow Builder.
> Leia ANTES de commitar. Atualize ao encerrar sua tarefa.
> Última atualização: 2026-08-22

---

## 1. Arquitetura em 60 segundos

| Peça | Arquivo | Papel |
|---|---|---|
| Editor standalone | `templates/flow_editor.html` | Página completa (Alpine + Drawflow). Rota: `/bots/<id>/flow-editor` |
| Adapter | `static/js/drawflowAdapter.js` | Tradução bidirecional Drawflow ⇄ schema grimbots. **FONTE ÚNICA** de `target_step` e `flow_start_step_id` |
| Bridge (inline) | `static/js/grim_flow_bridge.js` | Versão embutida usada pelo `bot_config.html` (fachada `window.flowEditor`) |
| Engine | `bot_manager.py` | `_execute_flow_recursive` / `_execute_step` / `_evaluate_conditions`. Intocável sem ler seção 4 |
| Rota | `dashboard/routes.py` | GET/PUT `/api/bots/<id>/config` (**retornam config PLANO**, sem envelope) |

**Regra de ouro:** o canvas (Drawflow) é a fonte durante a edição; o banco só recebe
o que o adapter exportar em `save()`.

## 2. Contratos de dados

- Schema do banco/engine: ver `_execute_flow_recursive` — `step.config`,
  `step.connections = {next,pending,retry}` (DICT),
  `step.conditions[].target_step/fallback_step`.
- Aliases que o engine entende no payment step: `amount` (= price do bloco),
  `description` (= product_name). O adapter grava esses aliases.
- Subscription: anexada ao **payment** (`config.subscription`); a injeção
  payment↔assinatura acontece no `toGrimbots()`. ⚠️ `has_subscription`
  no Payment ainda NÃO é setado no caminho do fluxo (hotfix `c825bae`
  removeu o kwarg que estourava TypeError). Reabrir com atributo pós-criação.

## 3. Armadilhas que JÁ morderam (não reabra!)

| Sintoma | Causa raiz | Correção vigente |
|---|---|---|
| Cards pelados ao reabrir funil | adapter salva `html:''`; `import()` renderiza vazio | `rebuildImportedDom()` após todo import |
| Card "atrasa" do mouse / linha cola no cursor | Alpine chama `init()` automático + `x-init="init()"` = 2 Drawflows | Sem `x-init`; guard `if(this.editor) return` |
| Salvar → `flow_steps of null` | API GET devolve config PLANO; página esperava `{success,config}` | loadConfig aceita ambos + `gfCfg()` auto-reparo nos 9 pontos |
| "Erro desconhecido" ao salvar com sucesso | PUT devolve config plano em 2xx | Sucesso = HTTP status (`d.__ok`) |
| HTML velho intermitente pós-deploy | Jinja compila template 1x por worker gunicorn e nunca relê | `TEMPLATES_AUTO_RELOAD=True` (extensions.py) + restart no deploy |
| Erros silenciosos / perda de edições | sem rede global de erros e sem dirty tracking | gfCfg+try/catch+timeout, 401/403 PT-BR, dirty modal/canvas com confirm, beforeunload, debounce paleta, syncOutputs defensivo |
| Dirty do modal não ativava | setter _gfDirty=true perdido num patch que falhou + listener por-open acumularia | listener delegado ÚNICO em #mFields (dataset.gfHooked) + chips despacham input sintético |
| time_elapsed com 2 saídas / nunca disparava | sem timer e sem gravação de timestamp | saída ÚNICA 'APÓS X MIN' + rq-scheduler (enqueue_in) + setex low_step_timestamp na entrada |

## 4. Checklist de DEPLOY (VPS)

```bash
git pull origin main
sudo systemctl RESTART grimbots      # obrigatório p/ templates
```

No navegador: **Ctrl+Shift+R**. Verificação instantânea:
1. Console mostra `[flow] build 61a76aa-hardening`
2. Subtítulo da página mostra o mesmo build (se mostrar "build antigo!" → cache/deploy)
3. `curl -sI https://dominio/bots/1/flow-editor | grep X-Flow-Build`

## 5. Em aberto (donos/status)

- [ ] downsell/upsell como STEP: precisa localizar último Payment pago p/
      `offer_sender.schedule_offers`. Proposta validada, aguardando PR.
- [ ] `has_subscription` no fluxo (ver §2) — prioridade média.
- [ ] Validação pré-save (payment sem PAGO/PENDENTE, nós órfãos, msg vazia).
- [ ] Personalizar ofertas (`offer_sender`) com {nome}.
- [ ] Simulador/teste de fluxo para o seller.

## 6. Como trabalhar aqui (protocolo entre devs)

1. Branch a partir do `main` atualizado: `feat/...`, `fix/...`
2. Commits no padrão `tipo(escopo): resumo` + corpo explicando o PORQUÊ
3. Antes de push: `node test_adapter.js` (19 PASS) e `py_compile bot_manager.py`
4. Se mexeu em contrato (adapter/routes): atualize a seção 2 deste arquivo NO MESMO commit
5. Merge no main só com os checks acima verdes
