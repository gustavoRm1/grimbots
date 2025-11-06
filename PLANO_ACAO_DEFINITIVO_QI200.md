# 📋 PLANO DE AÇÃO DEFINITIVO - ARQUITETO SÊNIOR QI 200

**Data:** 2025-01-27  
**Sistema:** SaaS Bot Manager  
**Objetivo:** Corrigir problemas críticos identificados no relatório técnico  

---

## 🎯 VISÃO GERAL

Este plano define as ações necessárias para transformar o sistema atual em uma plataforma **verdadeiramente multi-gateway, multi-tenant, com tracking robusto e webhooks confiáveis**.

---

## 📊 MATRIZ DE PRIORIDADES

| Prioridade | Problema | Impacto | Esforço | ROI |
|------------|----------|---------|---------|-----|
| 🔴 CRÍTICA | Webhook Token | ALTO | Médio | ⭐⭐⭐⭐⭐ |
| 🔴 CRÍTICA | Payment_id único | ALTO | Baixo | ⭐⭐⭐⭐⭐ |
| 🔴 CRÍTICA | Tracking Token V4 | ALTO | Alto | ⭐⭐⭐⭐⭐ |
| 🟡 ALTA | Gateway_id FK | MÉDIO | Médio | ⭐⭐⭐⭐ |
| 🟡 ALTA | Multi-gateway real | MÉDIO | Médio | ⭐⭐⭐⭐ |
| 🟡 ALTA | Webhook Secret | MÉDIO | Médio | ⭐⭐⭐ |
| 🟢 MÉDIA | GatewayAdapter | BAIXO | Alto | ⭐⭐⭐ |

---

## 🚀 FASE 1: CORREÇÕES CRÍTICAS (SEMANA 1)

### TAREFA 1.1: Adicionar Webhook Token

**Objetivo:** Eliminar 90% das falhas de matching de webhook

**Arquivos a Modificar:**
1. `models.py` - Adicionar campo `webhook_token`
2. `bot_manager.py` - Gerar `webhook_token` ao criar Payment
3. `gateway_*.py` - Incluir `webhook_token` no payload
4. `app.py` - Usar `webhook_token` para matching

**Passos:**
1. ✅ Adicionar campo `webhook_token` no Payment (models.py)
2. ✅ Gerar UUID único ao criar Payment (bot_manager.py)
3. ✅ Modificar cada gateway para incluir `webhook_token` no payload
4. ✅ Modificar webhook handler para buscar por `webhook_token` (prioridade 0)
5. ✅ Testar em staging
6. ✅ Deploy em produção

**Código:**
[Ver seção de código completa]

**Estimativa:** 2-3 horas  
**Risco:** Baixo  
**Rollback:** Simples (remover campo se necessário)

---

### TAREFA 1.2: Corrigir Payment_id Único

**Objetivo:** Eliminar risco de colisão de payment_id

**Arquivos a Modificar:**
1. `bot_manager.py` - Modificar geração de `payment_id`

**Passos:**
1. ✅ Modificar linha 3638 para usar UUID completo
2. ✅ Testar geração de payment_id
3. ✅ Verificar constraint unique no banco
4. ✅ Deploy em produção

**Código:**
```python
# ANTES:
payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"

# DEPOIS:
payment_id = f"BOT{bot_id}_{uuid.uuid4().hex}"
```

**Estimativa:** 15 minutos  
**Risco:** Muito baixo  
**Rollback:** Não necessário (compatível com versão anterior)

---

### TAREFA 1.3: Adicionar Gateway_id FK

**Objetivo:** Garantir integridade referencial

**Arquivos a Modificar:**
1. `models.py` - Adicionar campo `gateway_id`
2. `bot_manager.py` - Salvar `gateway_id` ao criar Payment
3. `app.py` - Filtrar por `gateway_id` no webhook
4. `migrations/` - Criar migration

**Passos:**
1. ✅ Criar migration para adicionar coluna `gateway_id`
2. ✅ Popular `gateway_id` em Payments existentes (via gateway_type)
3. ✅ Modificar código para salvar `gateway_id`
4. ✅ Modificar webhook para filtrar por `gateway_id`
5. ✅ Testar em staging
6. ✅ Deploy em produção

**Código:**
[Ver seção de código completa]

**Estimativa:** 1-2 horas  
**Risco:** Médio (migration precisa popular dados existentes)  
**Rollback:** Possível (coluna pode ser removida)

---

### TAREFA 1.4: Implementar Tracking Token V4

**Objetivo:** Match Quality 8-10/10 (de 0-5/10)

**Arquivos a Modificar:**
1. `models.py` - Adicionar `tracking_token` em BotUser e Payment
2. `utils/tracking_service.py` - Adicionar funções de tracking_token
3. `app.py` - Gerar `tracking_token` no redirect
4. `bot_manager.py` - Salvar `tracking_token` no BotUser e Payment
5. `app.py` - Recuperar tracking via `tracking_token` no Purchase

**Passos:**
1. ✅ Adicionar campo `tracking_token` em BotUser e Payment
2. ✅ Criar funções `generate_tracking_token()`, `save_tracking_token()`, `recover_by_tracking_token()`
3. ✅ Modificar redirect handler para gerar `tracking_token`
4. ✅ Modificar `/start` handler para salvar `tracking_token` no BotUser
5. ✅ Modificar `_generate_pix_payment()` para copiar `tracking_token` para Payment
6. ✅ Modificar `send_meta_pixel_purchase_event()` para recuperar tracking via `tracking_token`
7. ✅ Testar em staging
8. ✅ Deploy em produção

**Código:**
[Ver seção de código completa]

**Estimativa:** 4-6 horas  
**Risco:** Médio (mudança em múltiplos pontos)  
**Rollback:** Possível (campos podem ser removidos)

---

## 🚀 FASE 2: MULTI-GATEWAY E MULTI-TENANT (SEMANA 2)

### TAREFA 2.1: Remover Restrição de Gateway Único

**Objetivo:** Permitir múltiplos gateways ativos simultaneamente

**Arquivos a Modificar:**
1. `app.py` - Remover código que desativa outros gateways
2. `models.py` - Adicionar `priority` e `weight` no Gateway
3. `bot_manager.py` - Implementar estratégia de seleção

**Passos:**
1. ✅ Remover código em `app.py:4594-4600`
2. ✅ Adicionar campos `priority` e `weight` no Gateway
3. ✅ Modificar `_generate_pix_payment()` para selecionar gateway baseado em estratégia
4. ✅ Implementar estratégia: prioridade > peso > round-robin
5. ✅ Testar com múltiplos gateways
6. ✅ Deploy em produção

**Código:**
[Ver seção de código completa]

**Estimativa:** 2-3 horas  
**Risco:** Médio (mudança de comportamento)  
**Rollback:** Possível (restaurar código antigo)

---

### TAREFA 2.2: Adicionar Webhook Secret

**Objetivo:** Garantir multi-tenant para todos os gateways

**Arquivos a Modificar:**
1. `models.py` - Adicionar `webhook_secret` no Gateway
2. `app.py` - Gerar `webhook_secret` ao criar Gateway
3. Cada gateway - Modificar `get_webhook_url()` para incluir secret
4. `app.py` - Validar `webhook_secret` no webhook handler

**Passos:**
1. ✅ Adicionar campo `webhook_secret` no Gateway
2. ✅ Gerar `webhook_secret` único ao criar Gateway
3. ✅ Modificar cada gateway para incluir `webhook_secret` na URL
4. ✅ Modificar webhook handler para validar `webhook_secret`
5. ✅ Atualizar webhooks existentes nos gateways (manual)
6. ✅ Testar em staging
7. ✅ Deploy em produção

**Código:**
[Ver seção de código completa]

**Estimativa:** 2-3 horas  
**Risco:** Médio (requer atualizar webhooks nos gateways)  
**Rollback:** Possível (remover validação)

---

## 🚀 FASE 3: ADAPTER LAYER E NORMALIZAÇÃO (SEMANA 3)

### TAREFA 3.1: Criar GatewayAdapter

**Objetivo:** Normalizar entrada/saída de todos os gateways

**Arquivos a Criar:**
1. `gateway_adapter.py` - Classe GatewayAdapter

**Arquivos a Modificar:**
1. Cada gateway - Usar adapter para normalizar retornos
2. `bot_manager.py` - Usar adapter ao processar retornos

**Passos:**
1. ✅ Criar arquivo `gateway_adapter.py`
2. ✅ Implementar métodos de normalização
3. ✅ Modificar cada gateway para usar adapter
4. ✅ Modificar `bot_manager.py` para usar adapter
5. ✅ Testar em staging
6. ✅ Deploy em produção

**Código:**
[Ver seção de código completa]

**Estimativa:** 6-8 horas  
**Risco:** Baixo (não muda comportamento, apenas estrutura)  
**Rollback:** Possível (remover adapter)

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### FASE 1: CORREÇÕES CRÍTICAS

- [ ] Tarefa 1.1: Adicionar Webhook Token
  - [ ] Modificar models.py
  - [ ] Modificar bot_manager.py
  - [ ] Modificar cada gateway
  - [ ] Modificar app.py (webhook handler)
  - [ ] Testar em staging
  - [ ] Deploy em produção

- [ ] Tarefa 1.2: Corrigir Payment_id Único
  - [ ] Modificar bot_manager.py
  - [ ] Testar geração
  - [ ] Deploy em produção

- [ ] Tarefa 1.3: Adicionar Gateway_id FK
  - [ ] Criar migration
  - [ ] Modificar models.py
  - [ ] Modificar bot_manager.py
  - [ ] Modificar app.py
  - [ ] Testar em staging
  - [ ] Deploy em produção

- [ ] Tarefa 1.4: Implementar Tracking Token V4
  - [ ] Modificar models.py
  - [ ] Modificar utils/tracking_service.py
  - [ ] Modificar app.py (redirect)
  - [ ] Modificar bot_manager.py
  - [ ] Modificar app.py (purchase event)
  - [ ] Testar em staging
  - [ ] Deploy em produção

### FASE 2: MULTI-GATEWAY E MULTI-TENANT

- [ ] Tarefa 2.1: Remover Restrição de Gateway Único
  - [ ] Modificar app.py
  - [ ] Modificar models.py
  - [ ] Modificar bot_manager.py
  - [ ] Testar com múltiplos gateways
  - [ ] Deploy em produção

- [ ] Tarefa 2.2: Adicionar Webhook Secret
  - [ ] Modificar models.py
  - [ ] Modificar app.py
  - [ ] Modificar cada gateway
  - [ ] Atualizar webhooks nos gateways
  - [ ] Testar em staging
  - [ ] Deploy em produção

### FASE 3: ADAPTER LAYER

- [ ] Tarefa 3.1: Criar GatewayAdapter
  - [ ] Criar gateway_adapter.py
  - [ ] Modificar cada gateway
  - [ ] Modificar bot_manager.py
  - [ ] Testar em staging
  - [ ] Deploy em produção

---

## 📝 NOTAS DE IMPLEMENTAÇÃO

### Ordem de Deploy

1. **Fase 1 primeiro** (correções críticas)
2. **Fase 2 depois** (multi-gateway/multi-tenant)
3. **Fase 3 por último** (melhorias de código)

### Testes Necessários

Para cada tarefa:
1. ✅ Testes unitários
2. ✅ Testes de integração
3. ✅ Testes em staging com dados reais
4. ✅ Testes de carga (se aplicável)

### Monitoramento

Após cada deploy:
1. ✅ Monitorar logs de erro
2. ✅ Monitorar taxa de sucesso de webhooks
3. ✅ Monitorar Match Quality do Meta Pixel
4. ✅ Monitorar taxa de criação de Payments

---

## 🎯 MÉTRICAS DE SUCESSO

### Antes das Correções

- ❌ Taxa de sucesso de webhook matching: ~90-95%
- ❌ Match Quality Meta Pixel: 0-5/10
- ❌ Multi-gateway: Não suportado
- ❌ Multi-tenant: Apenas Átomo Pay

### Depois das Correções

- ✅ Taxa de sucesso de webhook matching: >99.9%
- ✅ Match Quality Meta Pixel: 8-10/10
- ✅ Multi-gateway: Totalmente suportado
- ✅ Multi-tenant: Todos os gateways

---

**Plano gerado por:** Arquiteto Sênior QI 200  
**Data:** 2025-01-27  
**Versão:** 1.0

