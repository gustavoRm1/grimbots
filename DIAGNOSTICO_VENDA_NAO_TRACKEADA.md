# 🔍 DIAGNÓSTICO - Venda Não Trackeada

## 🎯 PROBLEMA

**Venda foi feita mas não foi marcada na campanha Meta**

---

## ✅ CHECKLIST DE VERIFICAÇÃO

### **1. Verificar se venda existe**

```bash
psql -U postgres -d grimbots -c "
SELECT 
    id,
    payment_id,
    bot_id,
    status,
    TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid,
    CASE WHEN meta_purchase_sent THEN '✅' ELSE '❌' END as purchase_sent,
    pageview_event_id,
    fbclid,
    utm_campaign
FROM payments 
WHERE status = 'paid' 
  AND paid_at >= NOW() - INTERVAL '2 hours'
ORDER BY paid_at DESC 
LIMIT 5;
"
```

**O que verificar:**
- ✅ Venda tem `status='paid'`
- ✅ Venda tem `paid_at` recente (últimas 2 horas)
- ✅ Venda tem `fbclid` ou `utm_campaign`

---

### **2. Verificar se delivery_token foi gerado**

```bash
psql -U postgres -d grimbots -c "
SELECT 
    payment_id,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    delivery_token
FROM payments 
WHERE status = 'paid' 
  AND paid_at >= NOW() - INTERVAL '2 hours'
ORDER BY paid_at DESC 
LIMIT 5;
"
```

**O que verificar:**
- ✅ Venda tem `delivery_token` gerado
- ✅ `delivery_token` não é NULL

**Se `delivery_token` é NULL:**
- ❌ **PROBLEMA**: Link de entrega não foi gerado
- ✅ **SOLUÇÃO**: Verificar logs de `send_payment_delivery`

---

### **3. Verificar se link foi enviado via Telegram**

```bash
tail -5000 logs/gunicorn.log | grep -iE "Delivery URL enviado|Entregável enviado|send_payment_delivery" | tail -20
```

**O que verificar:**
- ✅ Log `"✅ Delivery URL enviado para payment X"`
- ✅ Log `"✅ Entregável enviado para X"`

**Se não há logs:**
- ❌ **PROBLEMA**: Link não foi enviado via Telegram
- ✅ **SOLUÇÃO**: Verificar se `send_payment_delivery` foi chamado

---

### **4. Verificar se cliente acessou /delivery**

```bash
tail -5000 logs/gunicorn.log | grep -iE "/delivery/|Delivery.*Renderizando|Purchase.*disparado" | tail -20
```

**O que verificar:**
- ✅ Log `"Delivery - Renderizando página para payment X"`
- ✅ Log `"Purchase disparado (client-side)"`
- ✅ Log `"Purchase via Server enfileirado"`

**Se não há logs:**
- ❌ **PROBLEMA**: Cliente **NÃO acessou** a página `/delivery/<token>`
- ✅ **SOLUÇÃO**: Cliente precisa clicar no link enviado via Telegram

---

### **5. Verificar se Pool tem Pixel configurado**

```bash
psql -U postgres -d grimbots -c "
SELECT 
    b.id as bot_id,
    pb.pool_id,
    p.name as pool_name,
    p.meta_pixel_id,
    CASE WHEN p.meta_tracking_enabled THEN '✅' ELSE '❌' END as tracking_enabled,
    CASE WHEN p.meta_events_purchase THEN '✅' ELSE '❌' END as purchase_enabled
FROM payments pay
JOIN bots b ON pay.bot_id = b.id
JOIN pool_bots pb ON b.id = pb.bot_id
JOIN redirect_pools p ON pb.pool_id = p.id
WHERE pay.status = 'paid' 
  AND pay.paid_at >= NOW() - INTERVAL '2 hours'
ORDER BY pay.paid_at DESC 
LIMIT 5;
"
```

**O que verificar:**
- ✅ Pool tem `meta_pixel_id` configurado
- ✅ Pool tem `meta_tracking_enabled = True`
- ✅ Pool tem `meta_events_purchase = True`

**Se pool não tem pixel:**
- ❌ **PROBLEMA**: Pool não tem pixel configurado
- ✅ **SOLUÇÃO**: Configurar Meta Pixel no pool

---

### **6. Verificar se fbclid/fbc foi capturado**

```bash
tail -5000 logs/gunicorn.log | grep -iE "fbclid.*encontrado|fbc.*retornado|fbc.*gerado|VENDA SERÁ TRACKEADA" | tail -20
```

**O que verificar:**
- ✅ Log `"✅ fbclid encontrado nos args"`
- ✅ Log `"✅ fbc retornado com sucesso"`
- ✅ Log `"✅ VENDA SERÁ TRACKEADA"`

**Se não há logs:**
- ❌ **PROBLEMA**: fbclid/fbc não foi capturado
- ✅ **SOLUÇÃO**: Verificar se cliente passou pelo redirect `/go/<slug>` antes de comprar

---

### **7. Verificar se Purchase foi enviado (CAPI)**

```bash
tail -5000 logs/gunicorn.log | grep -iE "Purchase via Server|meta_purchase_sent.*True|meta_event_id" | tail -20
```

**O que verificar:**
- ✅ Log `"Purchase via Server enfileirado com sucesso"`
- ✅ Log `"meta_purchase_sent marcado como True"`

**Se não há logs:**
- ❌ **PROBLEMA**: Purchase não foi enviado via CAPI
- ✅ **SOLUÇÃO**: Verificar se `send_meta_pixel_purchase_event` foi chamado

---

## 🔍 DIAGNÓSTICO AUTOMATIZADO

Execute o script:

```bash
bash diagnosticar_venda_nao_trackeada.sh
```

**O que o script verifica:**
1. Últimas vendas (última hora)
2. Logs da última venda
3. Purchase disparado
4. fbclid/fbc capturado
5. Delivery token gerado
6. Pool/pixel configurado

---

## 🚨 CAUSAS COMUNS

### **1. Cliente não acessou /delivery**

**Sintoma:**
- ✅ Venda confirmada (`status='paid'`)
- ✅ `delivery_token` gerado
- ✅ Link enviado via Telegram
- ❌ **NÃO há logs de `/delivery/`**

**Solução:**
- Cliente precisa **clicar no link** enviado via Telegram
- Purchase só é disparado quando cliente acessa `/delivery/<token>`

---

### **2. Pool não tem Pixel configurado**

**Sintoma:**
- ✅ Venda confirmada
- ✅ Cliente acessou `/delivery/`
- ❌ Pool não tem `meta_pixel_id` ou `meta_tracking_enabled = False`

**Solução:**
- Configurar Meta Pixel no pool
- Ativar `meta_tracking_enabled` e `meta_events_purchase`

---

### **3. Cliente não passou pelo redirect**

**Sintoma:**
- ✅ Venda confirmada
- ✅ Cliente acessou `/delivery/`
- ❌ **NÃO há `fbclid` ou `fbc`**

**Solução:**
- Cliente precisa passar pelo redirect `/go/<slug>` **ANTES** de comprar
- Sem `fbclid`, Meta não consegue atribuir à campanha

---

### **4. Purchase não foi enviado (CAPI falhou)**

**Sintoma:**
- ✅ Venda confirmada
- ✅ Cliente acessou `/delivery/`
- ✅ Pool tem pixel configurado
- ❌ **NÃO há logs de `Purchase via Server`**

**Solução:**
- Verificar logs de erro de CAPI
- Verificar se `meta_access_token` está correto

---

## ✅ PRÓXIMOS PASSOS

1. **Execute o diagnóstico:**
   ```bash
   bash diagnosticar_venda_nao_trackeada.sh
   ```

2. **Verifique os logs:**
   ```bash
   tail -f logs/gunicorn.log | grep -iE "Purchase|Delivery|fbclid|fbc"
   ```

3. **Verifique no Meta Event Manager:**
   - Acesse: https://business.facebook.com/events_manager2
   - Verifique se Purchase aparece (pode levar alguns minutos)

4. **Se Purchase não aparece:**
   - Verifique se cliente passou pelo redirect antes de comprar
   - Verifique se pool tem pixel configurado
   - Verifique se cliente acessou `/delivery/`

---

## 📝 COMANDO RÁPIDO

```bash
# Diagnóstico completo
bash diagnosticar_venda_nao_trackeada.sh

# Verificar última venda
psql -U postgres -d grimbots -c "
SELECT payment_id, status, TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid, 
       CASE WHEN meta_purchase_sent THEN '✅' ELSE '❌' END as purchase_sent,
       fbclid, delivery_token
FROM payments 
WHERE status = 'paid' 
ORDER BY paid_at DESC 
LIMIT 1;
"
```

