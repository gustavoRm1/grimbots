# 🔥 CAUSA RAIZ IDENTIFICADA - POOL "red1"

## 📊 DADOS DAS ÚLTIMAS 24H

- **Total payments:** 91
- **Com delivery_token:** 91 (100%)
- **Purchase enviado:** 88 (96.70%)
- **❌ PROBLEMA: 3 payments com delivery_token mas SEM purchase enviado**

---

## 🎯 CAUSA RAIZ IDENTIFICADA

### **Os 3 payments problemáticos têm o MESMO problema:**

1. **BOT43_1764715026_1f7cdd5c**
   - ✅ Tem `delivery_token`
   - ❌ `meta_purchase_sent = false`
   - ❌ `tracking_token = NULL`
   - ❌ `bot_user.tracking_session_id = NULL`

2. **BOT44_1764704707_87ada355**
   - ✅ Tem `delivery_token`
   - ❌ `meta_purchase_sent = false`
   - ❌ `tracking_token = NULL`
   - ❌ `bot_user.tracking_session_id = NULL`

3. **BOT2_1764678075_f7ea94f9**
   - ✅ Tem `delivery_token`
   - ❌ `meta_purchase_sent = false`
   - ❌ `tracking_token = NULL`
   - ❌ `bot_user.tracking_session_id = NULL`

---

## 🔍 ANÁLISE

### **PROBLEMA REAL:**

**Todos os 3 payments problemáticos NÃO têm:**
- `tracking_token` (NULL)
- `bot_user.tracking_session_id` (NULL)

**Isso indica:**
1. ❌ Lead **NÃO passou pelo redirect** (não tem tracking_session_id)
2. ❌ Ou tracking **não foi salvo corretamente**
3. ❌ Quando lead acessa `/delivery`, sistema **não consegue recuperar tracking_data do Redis**

---

## 🔧 FLUXO ESPERADO vs FLUXO REAL

### **FLUXO ESPERADO:**
1. Lead clica no redirect → tracking_data salvo no Redis com UUID
2. tracking_session_id salvo no bot_user
3. Lead compra → payment.tracking_token salvo
4. Lead acessa `/delivery` → tracking_data recuperado do Redis
5. Purchase enviado para Meta

### **FLUXO REAL (payments problemáticos):**
1. ❌ Lead **NÃO passou pelo redirect** OU tracking não foi salvo
2. ❌ bot_user.tracking_session_id = NULL
3. ❌ Lead compra → payment.tracking_token = NULL
4. ❌ Lead acessa `/delivery` → **não consegue recuperar tracking_data**
5. ❌ Purchase **NÃO é enviado** porque não tem dados de tracking

---

## ✅ SOLUÇÃO

### **PROBLEMA IDENTIFICADO:**

No `delivery_page` (linha 9228-9237):
```python
# Prioridade 1: bot_user.tracking_session_id (token do redirect)
if bot_user and bot_user.tracking_session_id:
    tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}

# Prioridade 2: payment.tracking_token
if not tracking_data and payment.tracking_token:
    tracking_data = tracking_service_v4.recover_tracking_data(payment.tracking_token) or {}
```

**PROBLEMA:**
- Se `bot_user.tracking_session_id = NULL` E `payment.tracking_token = NULL`
- `tracking_data = {}` (vazio)
- Purchase **ainda pode ser enviado** se pool tem Meta Pixel configurado
- MAS sem `fbclid`, `fbp`, `fbc` do tracking_data, Meta pode não atribuir corretamente

**MAS O PROBLEMA REAL É:**
- Se não tem `tracking_data`, a função `send_meta_pixel_purchase_event` pode estar retornando `False`
- Ou pode estar enviando mas sem dados suficientes para Meta atribuir

---

## 🔧 CORREÇÕES NECESSÁRIAS

### **CORREÇÃO #1: Verificar se Purchase está sendo bloqueado quando não tem tracking_data**

**Verificar em `send_meta_pixel_purchase_event` se:**
- Função retorna `False` quando não tem tracking_data?
- Ou envia mas sem dados suficientes?

### **CORREÇÃO #2: Melhorar logs para identificar quando não tem tracking_data**

Adicionar logs claros quando:
- `tracking_data` está vazio
- `bot_user.tracking_session_id` é NULL
- `payment.tracking_token` é NULL

---

## 📋 PRÓXIMOS PASSOS

1. ✅ **Verificar código de `send_meta_pixel_purchase_event`** - está bloqueando quando não tem tracking_data?
2. ✅ **Verificar código de `delivery_page`** - está enviando Purchase mesmo sem tracking_data?
3. ✅ **Adicionar logs detalhados** para identificar quando não tem tracking_data

---

**STATUS:** Causa raiz identificada - 3 payments não têm tracking_data, Purchase não pode ser enviado corretamente

