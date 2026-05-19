# 🔍 DIAGNÓSTICO - Por que Purchase Events não estão aparecendo no Meta Event Manager?

## 🎯 PROBLEMA REPORTADO

**8 vendas feitas hoje e nenhuma aparece no Meta Event Manager**
- ✅ PageView está funcionando (811 eventos, último há 17 minutos)
- ❌ Purchase não aparece no Event Manager
- ❌ Vendas não estão sendo atribuídas às campanhas

---

## 🔍 ANÁLISE SISTEMÁTICA - CAUSA RAIZ

### **1. FLUXO DE PURCHASE EVENT**

```
1. Payment confirmado (status='paid')
2. Usuário acessa /delivery/<token>
3. send_payment_delivery() é chamado
4. send_meta_pixel_purchase_event() é chamado (server-side)
5. fbq('track', 'Purchase') é disparado (client-side)
6. Evento é enviado para Meta via Conversions API
```

### **2. VERIFICAÇÕES QUE PODEM BLOQUEAR PURCHASE**

#### **A. Verificação 1: Bot não associado a pool**
```python
if not pool_bot:
    logger.error(f"❌ Bot {payment.bot_id} não está associado a nenhum pool")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **B. Verificação 2: Meta tracking desabilitado**
```python
if not pool.meta_tracking_enabled:
    logger.error(f"❌ Meta tracking DESABILITADO para pool {pool.id}")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **C. Verificação 3: Evento Purchase desabilitado**
```python
if not pool.meta_events_purchase:
    logger.error(f"❌ Evento Purchase DESABILITADO para pool {pool.id}")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **D. Verificação 4: Sem pixel_id ou access_token**
```python
if not pool.meta_pixel_id or not pool.meta_access_token:
    logger.error(f"❌ Pool {pool.id} tem tracking ativo mas SEM pixel_id ou access_token")
    return  # ❌ BLOQUEIA PURCHASE
```

#### **E. Verificação 5: Purchase já enviado (anti-duplicação)**
```python
if payment.meta_purchase_sent and getattr(payment, 'meta_event_id', None):
    logger.info(f"⚠️ Purchase já enviado via CAPI, ignorando")
    return  # ❌ BLOQUEIA PURCHASE (se já foi enviado com sucesso)
```

---

## 🔧 COMANDOS DE DIAGNÓSTICO

### **1. Verificar Vendas Recentes**

```bash
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.payment_id,
    p.status,
    p.amount,
    p.created_at,
    p.meta_purchase_sent,
    p.meta_event_id,
    b.name as bot_name
FROM payments p
JOIN bots b ON p.bot_id = b.id
WHERE p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY p.created_at DESC;
"
```

### **2. Verificar Logs de Purchase**

```bash
tail -500 logs/gunicorn.log | grep -iE "Purchase|META PURCHASE"
```

### **3. Verificar Erros Bloqueando Purchase**

```bash
# Bot não associado a pool
tail -1000 logs/gunicorn.log | grep -i "Bot.*não está associado a nenhum pool"

# Meta tracking desabilitado
tail -1000 logs/gunicorn.log | grep -i "Meta tracking DESABILITADO"

# Evento Purchase desabilitado
tail -1000 logs/gunicorn.log | grep -i "Evento Purchase DESABILITADO"

# Sem pixel_id ou access_token
tail -1000 logs/gunicorn.log | grep -i "SEM pixel_id ou access_token"
```

### **4. Verificar Configuração do Pool**

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

### **5. Verificar se Purchase está sendo enviado**

```bash
tail -1000 logs/gunicorn.log | grep -iE "Purchase ENVIADO|Purchase.*Events Received"
```

### **6. Verificar se delivery.html está sendo acessado**

```bash
tail -1000 logs/gunicorn.log | grep -iE "Delivery.*Renderizando|delivery.*token"
```

---

## 🎯 POSSÍVEIS CAUSAS RAÍZ

### **CAUSA 1: Evento Purchase DESABILITADO no Pool**
**Sintoma:** Purchase events não são enviados
**Solução:** Ativar `meta_events_purchase = true` no pool

### **CAUSA 2: Página de Delivery não está sendo acessada**
**Sintoma:** `send_meta_pixel_purchase_event()` nunca é chamado
**Solução:** Garantir que usuários acessem `/delivery/<token>` após pagamento

### **CAUSA 3: meta_purchase_sent já está marcado (bloqueado por anti-duplicação)**
**Sintoma:** Purchase é bloqueado por verificação de duplicação
**Solução:** Resetar `meta_purchase_sent` e `meta_event_id` se necessário

### **CAUSA 4: Bot não está associado a pool**
**Sintoma:** `pool_bot` não encontrado
**Solução:** Associar bot a um pool no dashboard

### **CAUSA 5: Pool não tem pixel_id ou access_token**
**Sintoma:** Pool tem tracking habilitado mas sem credenciais
**Solução:** Configurar `meta_pixel_id` e `meta_access_token` no pool

### **CAUSA 6: Purchase está sendo enviado mas Meta está rejeitando**
**Sintoma:** Purchase é enviado mas não aparece no Event Manager
**Solução:** Verificar logs de erro da API Meta, validar token e pixel_id

---

## 📋 SCRIPT DE DIAGNÓSTICO COMPLETO

Execute o script `diagnostico_purchase_nao_trackeado.sh`:

```bash
chmod +x diagnostico_purchase_nao_trackeado.sh
bash diagnostico_purchase_nao_trackeado.sh
```

O script verificará:
1. ✅ Vendas recentes
2. ✅ Logs de Purchase
3. ✅ Se Purchase está sendo chamado
4. ✅ Erros bloqueando Purchase
5. ✅ Se Purchase está sendo enviado com sucesso
6. ✅ Configuração do pool
7. ✅ Se delivery.html está sendo acessado
8. ✅ Se meta_purchase_sent está sendo marcado
9. ✅ Últimas linhas de logs

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **Execute o script de diagnóstico** para identificar a causa raiz
2. ✅ **Verifique logs** para confirmar qual verificação está bloqueando
3. ✅ **Corrija a causa identificada** (configuração do pool, etc)
4. ✅ **Teste com uma nova venda** para confirmar correção
5. ✅ **Verifique Meta Event Manager** para confirmar que Purchase aparece

---

## ⚠️ NOTAS IMPORTANTES

1. **Purchase é enviado APENAS quando usuário acessa `/delivery/<token>`**
   - Se usuário não acessar a página de delivery, Purchase não será enviado

2. **Verificações são feitas na ordem mostrada acima**
   - Primeira verificação que falhar bloqueia o Purchase

3. **PageView funciona porque é enviado no `/public_redirect`**
   - Purchase depende de usuário acessar `/delivery/<token>`

4. **meta_purchase_sent é marcado ANTES de enviar (lock pessimista)**
   - Segunda chamada será bloqueada (anti-duplicação)

