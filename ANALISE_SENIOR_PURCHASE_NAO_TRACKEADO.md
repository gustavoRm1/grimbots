# 🔍 ANÁLISE SÊNIOR QI 500 - Purchase Events não aparecem no Meta Event Manager

## 🎯 PROBLEMA REPORTADO

**8 vendas feitas hoje e nenhuma aparece no Meta Event Manager**
- ✅ PageView está funcionando (811 eventos, último há 17 minutos)
- ❌ Purchase não aparece no Event Manager
- ❌ Vendas não estão sendo atribuídas às campanhas

---

## 📊 ARQUITETURA ATUAL DO PURCHASE EVENT

### **Fluxo Completo:**

```
1. Lead clica em anúncio Meta → PageView disparado → tracking_token salvo no Redis
2. Lead compra via bot Telegram → webhook confirma pagamento → payment.status = 'paid'
3. send_payment_delivery() é chamado → delivery_token gerado → link enviado via Telegram
4. Lead acessa /delivery/<token> → delivery_page() é chamado
5. send_meta_pixel_purchase_event() é chamado (server-side) → Purchase enviado via Conversions API
6. fbq('track', 'Purchase') é disparado (client-side) → Purchase enviado via Pixel JS
7. Meta deduplica eventos (mesmo event_id) → Purchase aparece no Event Manager
```

### **Pontos Críticos:**

1. **Purchase só é enviado quando usuário acessa `/delivery/<token>`**
   - Se usuário não acessar, Purchase não será enviado

2. **Delivery token é gerado apenas quando payment é confirmado**
   - Se payment não tem `delivery_token`, link não pode ser enviado

3. **Link de delivery é enviado via Telegram**
   - Se envio falhar, usuário não recebe link

---

## 🔍 POSSÍVEIS CAUSAS RAIZ

### **CAUSA 1: Delivery Token não está sendo gerado**

**Sintoma:**
- `delivery_token` é `NULL` para vendas recentes
- Link não pode ser gerado

**Verificação:**
```sql
SELECT id, payment_id, delivery_token, created_at
FROM payments
WHERE status = 'paid'
AND delivery_token IS NULL
AND created_at >= NOW() - INTERVAL '24 hours';
```

**Causa Possível:**
- `send_payment_delivery()` não está sendo chamado quando payment é confirmado
- Erro ao gerar `delivery_token`

**Solução:**
- Verificar se `send_payment_delivery()` está sendo chamado após confirmação de pagamento
- Verificar logs de erro ao gerar `delivery_token`

---

### **CAUSA 2: Link de Delivery não está sendo enviado via Telegram**

**Sintoma:**
- `delivery_token` existe mas link não foi enviado
- Logs não mostram "Entregável enviado"

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -i "Entregável enviado\|delivery_token"
```

**Causa Possível:**
- `send_payment_delivery()` falha ao enviar mensagem via Telegram
- Bot bloqueado pelo usuário
- Token do bot inválido

**Solução:**
- Verificar logs de erro ao enviar mensagem
- Verificar se bot está ativo e válido

---

### **CAUSA 3: Página de Delivery não está sendo acessada**

**Sintoma:**
- Link foi enviado mas usuário não acessa
- Logs não mostram acessos a `/delivery/<token>`

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "Delivery.*Renderizando|delivery_page|/delivery/"
```

**Causa Possível:**
- Usuário não clica no link
- Link está incorreto ou quebrado
- Link expirou (não deveria acontecer, mas verificar)

**Solução:**
- Verificar se link está sendo enviado corretamente
- Verificar se link está funcionando (testar manualmente)

---

### **CAUSA 4: Purchase está sendo bloqueado por verificação**

**Sintoma:**
- Página de delivery é acessada mas Purchase não é enviado
- Logs mostram erros bloqueando Purchase

**Verificações que podem bloquear:**

#### **A. Bot não associado a pool**
```python
if not pool_bot:
    logger.error(f"❌ Bot {payment.bot_id} não está associado a nenhum pool")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **B. Meta tracking desabilitado**
```python
if not pool.meta_tracking_enabled:
    logger.error(f"❌ Meta tracking DESABILITADO para pool {pool.id}")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **C. Evento Purchase desabilitado**
```python
if not pool.meta_events_purchase:
    logger.error(f"❌ Evento Purchase DESABILITADO para pool {pool.id}")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **D. Sem pixel_id ou access_token**
```python
if not pool.meta_pixel_id or not pool.meta_access_token:
    logger.error(f"❌ Pool {pool.id} tem tracking ativo mas SEM pixel_id ou access_token")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **E. Purchase já enviado (anti-duplicação)**
```python
if payment.meta_purchase_sent and getattr(payment, 'meta_event_id', None):
    logger.info(f"⚠️ Purchase já enviado via CAPI, ignorando")
    return  # ❌ BLOQUEIA PURCHASE (se já foi enviado com sucesso)
```

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "Bot.*não está associado|Meta tracking DESABILITADO|Evento Purchase DESABILITADO|SEM pixel_id ou access_token|Purchase já enviado via CAPI"
```

**Solução:**
- Corrigir configuração do pool (ativar tracking, purchase event, configurar pixel_id/access_token)
- Verificar se bot está associado a pool

---

### **CAUSA 5: Purchase está sendo enviado mas Meta está rejeitando**

**Sintoma:**
- Purchase é enviado com sucesso (logs mostram "Purchase ENVIADO")
- Mas não aparece no Event Manager

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "Purchase ENVIADO|Purchase.*Events Received|Meta API error"
```

**Causa Possível:**
- Token de acesso inválido ou expirado
- Pixel ID incorreto
- Payload inválido (faltando campos obrigatórios)
- Meta API rejeitando eventos por validação

**Solução:**
- Verificar logs de erro da API Meta
- Validar token de acesso e pixel ID
- Verificar payload enviado (event_id, user_data, custom_data)

---

## 🔧 COMANDOS DE DIAGNÓSTICO

### **1. Executar Script Completo de Diagnóstico**

```bash
chmod +x verificar_porque_purchase_nao_aparece.sh
bash verificar_porque_purchase_nao_aparece.sh
```

### **2. Verificar Vendas Recentes**

```bash
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.payment_id,
    p.status,
    p.amount,
    p.created_at,
    p.delivery_token IS NOT NULL as tem_delivery_token,
    p.meta_purchase_sent,
    p.meta_event_id IS NOT NULL as tem_meta_event_id,
    b.name as bot_name
FROM payments p
JOIN bots b ON p.bot_id = b.id
WHERE p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY p.created_at DESC;
"
```

### **3. Verificar Configuração do Pool**

```bash
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.name,
    p.meta_tracking_enabled,
    p.meta_events_purchase,
    CASE WHEN p.meta_pixel_id IS NOT NULL THEN '✅' ELSE '❌' END as has_pixel_id,
    CASE WHEN p.meta_access_token IS NOT NULL THEN '✅' ELSE '❌' END as has_access_token
FROM pools p
WHERE p.meta_tracking_enabled = true;
"
```

### **4. Verificar Logs em Tempo Real**

```bash
tail -f logs/gunicorn.log | grep -iE "Purchase|Delivery|delivery_token|Entregável enviado"
```

---

## 📋 CHECKLIST DE DIAGNÓSTICO

Execute este checklist na ordem:

- [ ] **1. Verificar se delivery_token foi gerado**
  - Se `delivery_token` é `NULL`, problema é na geração do token
  
- [ ] **2. Verificar se link foi enviado**
  - Se logs não mostram "Entregável enviado", problema é no envio
  
- [ ] **3. Verificar se página foi acessada**
  - Se logs não mostram acessos a `/delivery/<token>`, usuário não está acessando
  
- [ ] **4. Verificar se Purchase está sendo chamado**
  - Se logs não mostram "Purchase - Iniciando", função não está sendo chamada
  
- [ ] **5. Verificar erros bloqueando Purchase**
  - Se há erros, corrigir configuração do pool
  
- [ ] **6. Verificar se Purchase está sendo enviado**
  - Se logs mostram "Purchase ENVIADO" mas não aparece no Event Manager, problema é na API Meta

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **Execute o script de diagnóstico** (`verificar_porque_purchase_nao_aparece.sh`)
2. ✅ **Identifique qual seção está com problema** (usar checklist acima)
3. ✅ **Corrija o problema identificado** (configuração do pool, envio de link, etc)
4. ✅ **Teste com uma nova venda** para confirmar correção
5. ✅ **Verifique Meta Event Manager** para confirmar que Purchase aparece

---

## ⚠️ NOTAS IMPORTANTES

1. **Purchase só é enviado quando usuário acessa `/delivery/<token>`**
   - Se usuário não acessar, Purchase não será enviado
   - PageView funciona porque é enviado no `/public_redirect`

2. **Verificações são feitas na ordem mostrada acima**
   - Primeira verificação que falhar bloqueia o Purchase

3. **meta_purchase_sent é marcado ANTES de enviar (lock pessimista)**
   - Segunda chamada será bloqueada (anti-duplicação)

4. **Event Manager pode levar até 24-48 horas para mostrar eventos**
   - Se Purchase foi enviado recentemente, pode não aparecer imediatamente

---

## ✅ STATUS

- ✅ Script de diagnóstico completo criado
- ✅ Análise sistemática de todas as causas possíveis
- ✅ Checklist de diagnóstico criado
- ⚠️ **Aguardando execução do script para identificar causa raiz específica**

