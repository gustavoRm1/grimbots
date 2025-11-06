# 🧹 PLANO DE LIMPEZA QI 500 - GRIMBOTS

**Data:** 2025-01-27  
**Engenheiro:** QI 500 - Limpeza Segura de Monólito Python  
**Objetivo:** Remover SOMENTE arquivos inúteis, SEM QUEBRAR produção

---

## 📊 RESUMO EXECUTIVO

### Estatísticas do Projeto
- **Total de arquivos Python:** 94
- **Arquivos essenciais (core):** ~35
- **Scripts de diagnóstico/temporários:** ~30
- **Documentação:** 20 arquivos .md
- **Pastas de implementação antigas:** 2
- **Arquivos de imagem duplicados:** 4
- **Arquivos PHP/JSON temporários:** 2

### Estratégia de Limpeza
✅ **REMOVER:** Scripts de diagnóstico, arquivos temporários, duplicatas, documentação obsoleta  
❌ **MANTER:** Core do sistema, migrations, gateways, utils, middleware, configs

---

## ✅ ARQUIVOS ESSENCIAIS (NÃO PODEM SER APAGADOS)

### Core da Aplicação
```
✅ app.py                          # Aplicação principal Flask
✅ bot_manager.py                  # Gerenciador de bots
✅ models.py                      # Modelos SQLAlchemy
✅ wsgi.py                        # Entry point produção
✅ init_db.py                     # Inicialização do banco
✅ gunicorn_config.py             # Config Gunicorn
✅ celery_app.py                  # Celery para async tasks
✅ requirements.txt               # Dependências Python
```

### Gateways (Sistema Multi-Gateway)
```
✅ gateway_adapter.py             # Adapter pattern (QI 500)
✅ gateway_factory.py             # Factory pattern
✅ gateway_interface.py           # Interface base
✅ gateway_syncpay.py             # Gateway SyncPay
✅ gateway_pushyn.py              # Gateway Pushyn
✅ gateway_paradise.py            # Gateway Paradise
✅ gateway_wiinpay.py             # Gateway WiinPay
✅ gateway_atomopay.py            # Gateway Átomo Pay
```

### Utils (Serviços Essenciais)
```
✅ utils/__init__.py
✅ utils/tracking_service.py      # TrackingServiceV4 (usado em app.py)
✅ utils/meta_pixel.py            # Meta Pixel Helper (usado em app.py)
✅ utils/encryption.py            # Criptografia (usado em app.py)
✅ utils/device_parser.py         # Parser de user-agent (usado em bot_manager.py)
```

### Middleware
```
✅ middleware/__init__.py
✅ middleware/gateway_validator.py
```

### Tasks (Celery)
```
✅ tasks/__init__.py
✅ tasks/health.py
✅ tasks/meta_sender.py
```

### Gamificação V2.0
```
✅ ranking_engine_v2.py           # Importado em app.py
✅ achievement_checker_v2.py      # Importado em app.py
✅ achievement_seed_v2.py          # Seed de conquistas
✅ gamification_websocket.py      # Importado em app.py
```

### Migrations
```
✅ migrations/migrations_add_tracking_token.py  # Última migration ativa
✅ migrations/archive/*                          # Migrations antigas (histórico)
```

### Templates e Static
```
✅ templates/**/*.html            # Todos os templates
✅ static/**/*                    # CSS, JS, imagens, manifest.json, sw.js
```

### Deploy
```
✅ deploy/Dockerfile
✅ deploy/docker-compose.yml
✅ deploy/ecosystem.config.js
```

### Scripts Úteis
```
✅ scripts/cleanup_vps_space.py  # Script de manutenção
✅ generate_vapid_keys.py         # Geração de chaves VAPID
✅ verify_vapid_keys.py           # Verificação de chaves
✅ setup_vapid_keys.py            # Setup de chaves
```

---

## 🗑️ ARQUIVOS PARA REMOÇÃO (SEGURAMENTE REMOVÍVEIS)

### 1. Scripts de Diagnóstico (NÃO usados em produção)

**Motivo:** Scripts temporários para debug/teste, não importados em nenhum módulo core.

```
❌ diagnose_meta_pixel_paradise.py
❌ diagnose_meta_purchase_completo.py
❌ diagnose_meta_purchase.py
❌ diagnose_paradise_missing_transactions.py
❌ diagnosticar_eventos_meta_gerenciador.py
❌ DIAGNOSTICO_URGENTE_META_PIXEL.py
```

**Impacto:** ZERO - Nenhum import encontrado em app.py, bot_manager.py ou módulos core.

---

### 2. Scripts de Teste/Verificação (NÃO usados em produção)

**Motivo:** Scripts de validação pontual, não parte do sistema.

```
❌ testar_celery_meta.py
❌ testar_meta_pixel_direto.py
❌ verificar_celery_meta_events.py
❌ verificar_eventos_meta_gerenciador.py
❌ verificar_implementacao_qi500.py
❌ verificar_logs_celery_meta.py
❌ verificar_meta_pixel_tempo_real.py
❌ validar_solucao_híbrida.py
```

**Impacto:** ZERO - Scripts standalone, não importados.

---

### 3. Scripts de Reenvio/Correção Temporários

**Motivo:** Scripts de correção pontual executados manualmente, não parte do sistema.

```
❌ reenviar_entregaveis_hoje.py
❌ reenviar_meta_pixel_hoje_v2.py
❌ reenviar_meta_pixel_hoje.py
❌ reenviar_meta_pixel.py
❌ reenviar_meta_purchase_forcado.py
❌ reenviar_meta_purchase.py
❌ reenviar_vendas_hoje_meta_grim.py
❌ corrigir_paradise_transaction_hash.py
❌ atualizar_vendas_syncpay_especificas.py
❌ reprocessar_vendas_syncpay.py
❌ enviar_entregaveis_meta_pixel_vendas_syncpay.py
```

**Impacto:** ZERO - Scripts de correção pontual, não importados.

---

### 4. Scripts de Monitoramento/Emergência

**Motivo:** Scripts de emergência executados manualmente, não parte do sistema.

```
❌ monitor_meta_pixel_health.py
❌ emergency_fix_pool.py
❌ enable_cloaker.py
❌ disable_cloaker_emergency.py
❌ paradise_payment_checker.py
❌ paradise_workaround.py
```

**Impacto:** ZERO - Scripts standalone de emergência.

---

### 5. Scripts de Migração/Recalculação Únicos

**Motivo:** Scripts executados uma vez, não mais necessários.

```
❌ migrate_add_producer_hash.py
❌ recalcular_gateway_stats.py
```

**Impacto:** ZERO - Migrações únicas já executadas.

---

### 6. Pastas de Implementação Antigas (Código Duplicado)

**Motivo:** Pastas com código de implementação antiga, já integrado no código principal.

```
❌ CODIGO_IMPLEMENTACAO_COMPLETA_QI200/
   - app_qi200_modifications.py          # Modificações já aplicadas
   - bot_manager_qi200_modifications.py  # Modificações já aplicadas
   - gateway_adapter.py                  # Versão antiga (QI 200)
   - models_qi200.py                      # Modificações já aplicadas
   - migrations_add_qi200_fields.py      # Migration já executada
   - tracking_service_qi200.py            # Versão antiga
   - *.md                                 # Documentação obsoleta

❌ IMPLEMENTACAO_QI500/
   - gateway_adapter.py                   # Versão antiga (já integrada)
   - migrations_add_tracking_token.py     # Migration já executada
   - README.md                            # Documentação obsoleta
```

**Impacto:** ZERO - Código já integrado no core. Nenhum import encontrado.

**Verificação:**
- `gateway_adapter.py` na raiz é a versão QI 500 (atual)
- `gateway_adapter.py` em `CODIGO_IMPLEMENTACAO_COMPLETA_QI200/` é versão QI 200 (antiga)
- `gateway_adapter.py` em `IMPLEMENTACAO_QI500/` é versão intermediária (antiga)

---

### 7. Arquivos PHP/JSON Temporários

**Motivo:** Arquivos de configuração temporários do Paradise, não parte do sistema Python.

```
❌ paradise.php                         # Proxy PHP temporário
❌ paradise.json                        # Config JSON temporário
```

**Impacto:** ZERO - Não são usados pelo sistema Python.

---

### 8. Imagens Duplicadas na Raiz

**Motivo:** Imagens já presentes em `static/img/`, duplicatas na raiz.

**Verificação:**
- ✅ Código usa `premio_50k.png`, `premio_100k.png`, etc. em `static/img/` (app.py linha 5529-5533)
- ✅ Template `ranking.html` usa `url_for('static', filename='img/' + award.image)` (linha 466)
- ✅ Nenhuma referência a "PLACA *.png" encontrada no código
- ✅ Imagens em `static/img/` são as únicas usadas pelo sistema

```
❌ PLACA 50 MIL.png                     # Duplicata de static/img/premio_50k.png (NÃO USADA)
❌ PLACA 100 MIL.png                    # Duplicata de static/img/premio_100k.png (NÃO USADA)
❌ PLACA 250 MIL.png                    # Duplicata de static/img/premio_250k.png (NÃO USADA)
❌ PLACA 500 MIL.png                    # Duplicata de static/img/premio_500k.png (NÃO USADA)
❌ atomopay.png                         # Duplicata de static/img/atomopay.png (NÃO USADA)
```

**Impacto:** ZERO - Apenas duplicatas. Sistema usa exclusivamente `static/img/`.

---

### 9. Documentação Obsoleta/Redundante

**Motivo:** Documentação de implementações antigas ou duplicada.

```
❌ CHECKLIST_VERIFICACAO_QI500.md
❌ DIAGNOSTICO_COMPLETO_QI500.md
❌ IMPLEMENTACAO_QI500_RESUMO_EXECUTIVO.md
❌ README_QI500.md
❌ PLANO_ACAO_DEFINITIVO_QI200.md
❌ RELATORIO_TECNICO_COMPLETO_QI200.md
❌ RESUMO_CORRECOES_PARADISE.md
❌ SOLUCAO_ATOMOPAY_401.md
❌ SOLUCAO_SENIOR_QI300_META_PIXEL.md
❌ TESTE_TRANSACAO_REAL.md
❌ VERIFICACAO_COMPLETA_TAXAS_PREMIUM.md
❌ CORRECAO_OFERTA_PENDENTE.md
❌ INTEGRACAO_ATOMOPAY_COMPLETA.md
❌ GUIA_INTEGRACAO_GATEWAY.md
```

**Manter:**
```
✅ HOMOLOGACAO_QI500_CONCLUIDA.md      # Documentação de homologação
✅ IMPLEMENTACAO_COMPLETA_QI600.md     # Documentação QI 600
```

**Impacto:** ZERO - Apenas documentação, não afeta código.

---

### 10. Script PowerShell de Arquivo (Já Executado)

**Motivo:** Script de arquivamento já executado, não mais necessário.

```
❌ EXECUTAR_ARQUIVAMENTO_SEGURO.ps1
```

**Impacto:** ZERO - Script de manutenção já executado.

---

### 11. Arquivos de Tracking/Elite Analytics (Não Usados)

**Motivo:** Arquivos não importados em nenhum lugar.

```
❌ tracking_elite_analytics.py
❌ meta_events_async.py              # Versão antiga, não usada (celery_app.py é a versão atual)
```

**Verificação:** 
- `tracking_elite_analytics.py`: Nenhum import encontrado
- `meta_events_async.py`: Nenhum import encontrado (celery_app.py implementa a funcionalidade)

**Impacto:** ZERO - Não usados.

---

### 12. Cache Python (__pycache__)

**Motivo:** Cache gerado automaticamente, pode ser regenerado.

```
❌ __pycache__/                        # Toda a pasta
❌ middleware/__pycache__/
❌ utils/__pycache__/
❌ *.pyc                                # Se houver na raiz
```

**Impacto:** ZERO - Cache regenerado automaticamente.

---

## 🔍 MAPA DE DEPENDÊNCIAS (IMPORT TREE)

### app.py → Dependências Críticas
```
app.py
├── models.py (db, User, Bot, Gateway, Payment, etc.)
├── bot_manager.py (BotManager)
├── ranking_engine_v2.py (RankingEngine)
├── achievement_checker_v2.py (AchievementChecker)
├── gamification_websocket.py (register_gamification_events)
├── celery_app.py (send_meta_event)
├── utils.tracking_service (TrackingService, TrackingServiceV4)
├── utils.meta_pixel (MetaPixelHelper, MetaPixelAPI)
├── utils.encryption (encrypt, decrypt)
└── middleware.gateway_validator
```

### bot_manager.py → Dependências Críticas
```
bot_manager.py
├── gateway_factory.py (GatewayFactory)
├── utils.meta_pixel (MetaPixelAPI)
├── utils.encryption (decrypt)
├── utils.device_parser (parse_user_agent, parse_ip_to_location)
└── utils.tracking_service (TrackingService, TrackingServiceV4)
```

### gateway_factory.py → Dependências Críticas
```
gateway_factory.py
├── gateway_interface.py (PaymentGateway)
├── gateway_syncpay.py (SyncPayGateway)
├── gateway_pushyn.py (PushynGateway)
├── gateway_paradise.py (ParadisePaymentGateway)
├── gateway_wiinpay.py (WiinPayGateway)
├── gateway_atomopay.py (AtomPayGateway)
└── gateway_adapter.py (GatewayAdapter) - QI 500
```

### gateway_adapter.py → Dependências Críticas
```
gateway_adapter.py
├── gateway_interface.py (PaymentGateway)
└── logging
```

---

## ✅ CHECKLIST ANTI-ACIDENTE

### Antes de Remover Qualquer Arquivo

- [x] Verificado que NÃO é importado em app.py
- [x] Verificado que NÃO é importado em bot_manager.py
- [x] Verificado que NÃO é importado em gateway_factory.py
- [x] Verificado que NÃO é importado em gateway_adapter.py
- [x] Verificado que NÃO é usado em utils/
- [x] Verificado que NÃO é usado em tasks/
- [x] Verificado que NÃO é usado em middleware/
- [x] Verificado que NÃO é migration ativa
- [x] Verificado que NÃO é template ou static file
- [x] Verificado que NÃO é arquivo de configuração (.env, requirements.txt, etc.)

### Garantias de Segurança

✅ **Nenhum arquivo core será removido**  
✅ **Nenhuma migration será removida** (apenas pastas de implementação antiga)  
✅ **Nenhum gateway será removido**  
✅ **Nenhum modelo será removido**  
✅ **Nenhum utils essencial será removido**  
✅ **Nenhum middleware será removido**  
✅ **Nenhum template/static será removido**  
✅ **Nenhum arquivo de config será removido**

---

## 📋 RESUMO DE REMOÇÕES

### Por Categoria

| Categoria | Quantidade | Impacto |
|-----------|------------|---------|
| Scripts de Diagnóstico | 6 | ZERO |
| Scripts de Teste/Verificação | 8 | ZERO |
| Scripts de Reenvio/Correção | 11 | ZERO |
| Scripts de Monitoramento/Emergência | 6 | ZERO |
| Scripts de Migração Única | 2 | ZERO |
| Pastas de Implementação Antiga | 2 pastas | ZERO |
| Arquivos PHP/JSON Temporários | 2 | ZERO |
| Imagens Duplicadas | 5 | ZERO |
| Documentação Obsoleta | 13 | ZERO |
| Script PowerShell | 1 | ZERO |
| Tracking/Meta Async Não Usado | 2 | ZERO |
| Cache Python | __pycache__ | ZERO |
| **TOTAL** | **~57 arquivos + pastas** | **ZERO** |

---

## 🎯 PLANO DE EXECUÇÃO

### Ordem de Remoção (Segurança Crescente)

1. **Fase 1:** Cache Python (`__pycache__/`)
2. **Fase 2:** Imagens duplicadas
3. **Fase 3:** Scripts de diagnóstico/teste
4. **Fase 4:** Scripts de reenvio/correção
5. **Fase 5:** Scripts de monitoramento/emergência
6. **Fase 6:** Arquivos PHP/JSON temporários
7. **Fase 7:** Documentação obsoleta
8. **Fase 8:** Pastas de implementação antiga
9. **Fase 9:** Scripts de migração única
10. **Fase 10:** Tracking/Meta Async não usado

---

## ✅ CONFIRMAÇÃO FINAL

**Total de arquivos a remover:** ~57 arquivos + 2 pastas completas  
**Total de arquivos essenciais mantidos:** ~35 arquivos core  
**Risco de quebra:** **ZERO** (todos os arquivos removidos são não-importados)

---

## 📝 NOTAS TÉCNICAS

1. **Migrations:** Apenas migrations em `migrations/archive/` são mantidas (histórico). Nenhuma migration ativa será removida.

2. **Gateways:** Todos os 5 gateways (SyncPay, Pushyn, Paradise, WiinPay, AtomPay) são mantidos.

3. **Utils:** Todos os utils usados (tracking_service, meta_pixel, encryption, device_parser) são mantidos.

4. **Gamificação:** Todos os módulos V2.0 são mantidos (ranking_engine_v2, achievement_checker_v2, gamification_websocket).

5. **Templates/Static:** Nenhum arquivo será removido.

---

**Pronto para execução após confirmação do usuário.**

