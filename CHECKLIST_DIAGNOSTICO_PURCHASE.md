# 🔥 CHECKLIST DIAGNÓSTICO - PURCHASE NÃO ESTÁ SENDO ENVIADO

## 📊 SITUAÇÃO

**Meta Events Manager:**
- ✅ PageView: Active (Multiple) - 119 eventos
- ❌ Purchase: **NÃO APARECE** - 0 eventos

---

## ✅ CHECKLIST DE VERIFICAÇÃO

### **1. Pool Configurado Corretamente?**

Verificar no banco de dados:
```sql
SELECT id, name, meta_tracking_enabled, meta_pixel_id, 
       meta_access_token IS NOT NULL as has_token,
       meta_events_purchase
FROM redirect_pools
WHERE id = [pool_id];
```

**Requisitos:**
- ✅ `meta_tracking_enabled = true`
- ✅ `meta_pixel_id IS NOT NULL`
- ✅ `meta_access_token IS NOT NULL`
- ✅ `meta_events_purchase = true` **← CRÍTICO!**

---

### **2. Payment Tem delivery_token?**

```sql
SELECT id, payment_id, delivery_token, status,
       meta_purchase_sent, meta_event_id
FROM payments
WHERE status = 'paid'
ORDER BY created_at DESC
LIMIT 10;
```

**Requisitos:**
- ✅ `delivery_token IS NOT NULL` (página foi acessada)
- ✅ `status = 'paid'`

---

### **3. Logs do Sistema**

Verificar logs para ver se Purchase está sendo enfileirado:
```bash
grep -i "purchase.*enfileirado\|purchase.*sent\|delivery.*purchase" logs/app.log | tail -20
```

**Procurar por:**
- ✅ `"[META DELIVERY] Delivery - Purchase via Server enfileirado com sucesso"`
- ✅ `"📤 Purchase enfileirado"`
- ❌ `"⚠️ [META DELIVERY] Delivery - Purchase NÃO foi enfileirado"`
- ❌ `"❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO"`

---

### **4. Client-Side Purchase**

Verificar console do browser ao acessar `/delivery/<token>`:
- ✅ `console.log('[META PIXEL] Purchase disparado (client-side)')`
- ✅ Network tab mostra request para `connect.facebook.net`

---

### **5. Celery Está Rodando?**

```bash
# Verificar se Celery está processando tasks
celery -A celery_app inspect active

# Verificar tasks falhadas
celery -A celery_app inspect stats
```

---

## 🎯 PROBLEMAS COMUNS

### **Problema #1: `meta_events_purchase = false`**
**Solução:** Ativar "Purchase Event" nas configurações do pool

### **Problema #2: Pool não associado ao bot**
**Solução:** Verificar `pool_bots` table - bot deve estar associado ao pool

### **Problema #3: Client-side não dispara**
**Causa:** `payment.meta_purchase_sent = true` antes de renderizar template
**Solução:** Já corrigido - template renderiza antes

### **Problema #4: Server-side não enfileira**
**Causa:** `send_meta_pixel_purchase_event` retorna `False`
**Verificar:** Logs para ver qual validação está falhando

---

**PRÓXIMO PASSO:** Executar checklist acima para identificar o problema real.

