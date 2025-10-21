# 🔍 INVESTIGAÇÃO: META NÃO MARCA PURCHASE

**Data:** 2025-10-21  
**Status:** 🚨 URGENTE  
**Prioridade:** CRÍTICA

---

## **🎯 PROBLEMA RELATADO:**

> "Meta não está marcando vendas como Purchase."

---

## **📋 CHECKLIST DE INVESTIGAÇÃO:**

### **✅ 1. EVENTO PURCHASE ESTÁ SENDO ENVIADO?**

**Comando:**
```bash
cd ~/grimbots
python DIAGNOSTICO_META_PURCHASE.py
```

**O que verificar:**
- [ ] Vendas com `status='paid'` existem?
- [ ] Campo `meta_purchase_sent` está `TRUE`?
- [ ] Campo `meta_event_id` está populado?
- [ ] Logs do Celery mostram envio?

**Se meta_purchase_sent = FALSE:**
- ❌ Evento NÃO está sendo enviado
- **Causa:** Pool não tem `meta_events_purchase = TRUE`
- **Fix:** Habilitar no painel de pools

---

### **✅ 2. PAYLOAD ESTÁ COMPLETO?**

**Comando:**
```bash
python TEST_META_PURCHASE_ELITE.py
```

**Validar campos obrigatórios:**
- [ ] `event_name`: "Purchase" ✅
- [ ] `event_id`: UUID único ✅
- [ ] `external_id`: **CRÍTICO** - fbclid do clique original
- [ ] `currency`: "BRL" ✅
- [ ] `value`: > 0 ✅

**Se external_id estiver ausente:**
- ❌ Meta NÃO consegue associar à campanha
- **Causa:** fbclid não foi capturado/associado
- **Fix:** Implementar tracking completo

---

### **✅ 3. EXTERNAL_ID ESTÁ CORRETO?**

**Fluxo esperado:**
```
1. Usuário clica: /go/red1?testecamu01&fbclid=XYZ
   ↓
2. Redis salva: tracking:XYZ → {ip, ua, fbclid, ...}
   ↓
3. Usuário /start → Busca Redis → Associa ao BotUser
   ↓
4. BotUser tem:
   - external_id: "XYZ" ou hash do fbclid
   - fbclid: "XYZ"
   ↓
5. Purchase usa: bot_user.external_id
```

**Verificar no banco:**
```bash
sqlite3 instance/saas_bot_manager.db "
SELECT 
    bu.telegram_user_id,
    bu.external_id,
    bu.fbclid,
    p.payment_id,
    p.meta_purchase_sent,
    p.meta_event_id
FROM bot_users bu
INNER JOIN payment p ON p.bot_id = bu.bot_id 
    AND p.customer_user_id = 'user_' || bu.telegram_user_id
WHERE p.status = 'paid'
ORDER BY p.paid_at DESC
LIMIT 5;
"
```

**Se external_id = NULL:**
- ❌ Meta não consegue fazer match
- **Causa 1:** Usuário não veio de anúncio (acesso direto ao bot)
- **Causa 2:** fbclid não estava na URL
- **Causa 3:** Tracking não foi implementado corretamente

---

### **✅ 4. IP/UA ESTÃO PRESENTES? (TRACKING ELITE)**

**Verificar:**
```bash
sqlite3 instance/saas_bot_manager.db "
SELECT 
    telegram_user_id,
    external_id,
    fbclid,
    ip_address,
    SUBSTR(user_agent, 1, 50) as ua_preview
FROM bot_users 
WHERE ip_address IS NOT NULL
ORDER BY first_interaction DESC
LIMIT 5;
"
```

**Se ip_address = NULL:**
- ⚠️  TRACKING ELITE não está funcionando
- **Causa:** Migration não foi rodada ou Redis não está salvando
- **Fix:** Ver seção 7

---

### **✅ 5. TOKEN É VÁLIDO?**

**Testar token do Meta:**
```bash
# Buscar token no banco (criptografado)
sqlite3 instance/saas_bot_manager.db "SELECT id, name, meta_pixel_id FROM redirect_pools WHERE meta_tracking_enabled = 1;"

# Depois testar com script
python -c "
from app import app, db
from models import RedirectPool
from utils.encryption import decrypt
import requests

with app.app_context():
    pool = RedirectPool.query.filter_by(meta_tracking_enabled=True).first()
    if pool:
        token = decrypt(pool.meta_access_token)
        pixel_id = pool.meta_pixel_id
        
        # Testar token
        url = f'https://graph.facebook.com/v18.0/{pixel_id}?access_token={token}'
        r = requests.get(url)
        
        if r.status_code == 200:
            print('✅ Token válido')
        else:
            print(f'❌ Token inválido: {r.text}')
"
```

---

### **✅ 6. EVENTO APARECE NO EVENTS MANAGER?**

**Acesse:**
```
https://business.facebook.com/events_manager2/list/pixel/YOUR_PIXEL_ID
```

**Filtros:**
- Event Name: Purchase
- Últimas 24h

**Se NÃO aparecer:**
- ❌ Evento não chegou no Meta
- **Possíveis causas:**
  1. Token inválido/expirado
  2. Pixel ID errado
  3. Payload com erro (400/190)
  4. external_id não bate com fbclid

**Se APARECER mas não associado à campanha:**
- ❌ external_id não está correto
- **Fix:** Garantir que external_id = fbclid original

---

### **✅ 7. TRACKING ELITE FUNCIONANDO?**

**Verificar Redis:**
```bash
# Ver se há dados salvos
redis-cli KEYS "tracking:*"

# Se houver, ver conteúdo
redis-cli GET "tracking:FBCLID_AQUI"
```

**Verificar logs:**
```bash
sudo journalctl -u grimbots -n 100 | grep "TRACKING ELITE"
```

**Deve ver:**
```
🎯 TRACKING ELITE | fbclid=... | IP=... | Session=...
🎯 TRACKING ELITE | Dados associados | IP=... | Session=...
```

---

## **🔧 FIXES PRIORITÁRIOS:**

### **FIX 1: Garantir external_id = fbclid**

No redirect (`app.py`), já salvamos fbclid no Redis.

No bot_manager, quando /start, precisamos garantir que:
```python
bot_user.external_id = fbclid  # OU hash do fbclid
bot_user.fbclid = fbclid
```

**Verificar se está acontecendo:**
```bash
sudo journalctl -u grimbots | grep "external_id=" | tail -20
```

---

### **FIX 2: Habilitar Purchase Events no Pool**

```bash
sqlite3 instance/saas_bot_manager.db "
UPDATE redirect_pools 
SET meta_events_purchase = 1 
WHERE meta_tracking_enabled = 1;

SELECT name, meta_events_purchase FROM redirect_pools;
"
```

---

### **FIX 3: Forçar envio de Purchase para vendas antigas**

```python
# Script para reenviar Purchases não enviados
from app import app, db
from models import Payment
from app import send_meta_pixel_purchase_event

with app.app_context():
    # Buscar vendas paid sem meta_purchase_sent
    payments = Payment.query.filter(
        Payment.status == 'paid',
        Payment.meta_purchase_sent != True
    ).all()
    
    for payment in payments:
        try:
            send_meta_pixel_purchase_event(payment)
            print(f'✅ Purchase enviado: {payment.payment_id}')
        except Exception as e:
            print(f'❌ Erro: {e}')
```

---

## **🎯 PRÓXIMOS PASSOS:**

### **PASSO 1: Diagnóstico**
```bash
python DIAGNOSTICO_META_PURCHASE.py
```

### **PASSO 2: Teste Manual**
```bash
python TEST_META_PURCHASE_ELITE.py
```

### **PASSO 3: Verificar Events Manager**
- Acessar Meta Events Manager
- Filtrar por Purchase
- Ver se aparece

### **PASSO 4: Validar external_id**
- Pegar fbclid de uma venda
- Verificar se external_id no banco = fbclid
- Verificar se Purchase foi enviado com esse external_id

---

## **🚨 EXECUTE AGORA:**

```bash
cd ~/grimbots
python DIAGNOSTICO_META_PURCHASE.py
```

**ME MANDE A SAÍDA COMPLETA!** 🎯

