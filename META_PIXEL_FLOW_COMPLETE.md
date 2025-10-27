# 📊 FLUXO COMPLETO - META PIXEL PURCHASE

## 🎯 OBJETIVO
Garantir que o Meta Pixel Purchase seja enviado para **TODOS os gateways** após compra aprovada, **SEM duplicação**.

---

## 📍 PONTOS DE DISPARO

### 1. **WEBHOOK (Principal - app.py linha 4560)**
```python
# app.py - payment_webhook()
if status == 'paid' and was_pending:
    # ... atualizar stats ...
    send_meta_pixel_purchase_event(payment)  # ✅ LINHA 4560
```

**Gateways afetados:** Todos (Paradise, PushynPay, SyncPay, WiinPay)

**Quando:** Quando o gateway envia webhook confirmando pagamento

**Anti-duplicação:** 
- Flag `meta_purchase_sent` verifica ANTES de enviar (linha 4327)
- Se já enviado, retorna imediatamente (early return)

---

### 2. **CONSULTA ATIVA (bot_manager.py linha 2144)**
```python
# bot_manager.py - _handle_verify_payment()
if api_status and api_status.get('status') == 'paid':
    if payment.status == 'pending':
        # ... atualizar stats ...
        send_meta_pixel_purchase_event(payment)  # ✅ LINHA 2144
        db.session.commit()
```

**Gateways afetados:** PushynPay, SyncPay (NÃO Paradise)

**Quando:** Quando usuário clica "Verificar Pagamento" e pagamento foi aprovado

**Anti-duplicação:**
- Meta Pixel enviado ANTES do commit
- Flag `meta_purchase_sent` é setado no commit
- Webhook subsequente verifica flag e não duplica

---

### 3. **PARADISE CHECKER (paradise_payment_checker.py linha 121)**
```python
# paradise_payment_checker.py - check_paradise_payments()
if status == 'paid':
    # ... atualizar stats ...
    send_meta_pixel_purchase_event(payment)  # ✅ LINHA 121
```

**Gateways afetados:** Paradise apenas

**Quando:** Job cron a cada 2 minutos verifica pagamentos pendentes do Paradise

**Anti-duplicação:**
- Mismo mecanismo de flag
- Job verifica ANTES de processar

---

## 🔒 GARANTIAS DE ANTI-DUPLICAÇÃO

### 1. **Flag `meta_purchase_sent` (models.py linha 818)**
```python
meta_purchase_sent = db.Column(db.Boolean, default=False)
meta_purchase_sent_at = db.Column(db.DateTime, nullable=True)
meta_event_id = db.Column(db.String(100), nullable=True)
```

**Uso:** Verifica ANTES de enviar evento

### 2. **Verificação no `send_meta_pixel_purchase_event` (app.py linha 4327)**
```python
if payment.meta_purchase_sent:
    logger.info(f"⚠️ Purchase já enviado ao Meta, ignorando: {payment.payment_id}")
    return  # ✅ EARLY RETURN
```

### 3. **Flag Otimista (app.py linha 4417-4420)**
```python
payment.meta_purchase_sent = True
payment.meta_purchase_sent_at = datetime.now()
payment.meta_event_id = event_id
db.session.commit()  # ✅ CRÍTICO: Persistir no banco!
```

**Importante:** Flag é setado ANTES do evento ser processado pelo Celery

---

## 🎯 FLUXO POR GATEWAY

### **Paradise**
1. Webhook recebido → `payment_webhook()` → Envia Meta Pixel (linha 4560)
2. Se webhook falhar → Job cron verifica a cada 2min → Envia Meta Pixel (linha 121)
3. Consulta manual desabilitada (linha 2096)

### **PushynPay**
1. Webhook recebido → `payment_webhook()` → Envia Meta Pixel (linha 4560)
2. Se usuário clica "Verificar" → API consultada → Envia Meta Pixel (linha 2144)

### **SyncPay**
1. Webhook recebido → `payment_webhook()` → Envia Meta Pixel (linha 4560)
2. Se usuário clica "Verificar" → API consultada → Envia Meta Pixel (linha 2144)

### **WiinPay**
1. Webhook recebido → `payment_webhook()` → Envia Meta Pixel (linha 4560)
2. Se usuário clica "Verificar" → API consultada → Envia Meta Pixel (linha 2144)

---

## ✅ VALIDAÇÃO

Para testar se Meta Pixel está sendo enviado:

### 1. Verificar logs:
```bash
grep "Meta Pixel Purchase" /var/log/grimbots/*.log
```

### 2. Verificar DB:
```sql
SELECT payment_id, status, meta_purchase_sent, meta_event_id, created_at 
FROM payment 
WHERE status = 'paid' 
ORDER BY created_at DESC 
LIMIT 10;
```

### 3. Verificar Celery:
```bash
celery -A celery_app flower
# Acessar: http://localhost:5555
# Ver tasks do tipo 'send_meta_event'
```

---

## 🚨 PROBLEMAS COMUNS

### 1. **Meta Pixel não enviado**
- ✅ Verificar se pool tem `meta_tracking_enabled = TRUE`
- ✅ Verificar se pool tem `meta_events_purchase = TRUE`
- ✅ Verificar se pool tem `meta_pixel_id` e `meta_access_token`

### 2. **Meta Pixel duplicado**
- ✅ Verificar flag `meta_purchase_sent` no DB
- ✅ Verificar se há múltiplos webhooks do gateway
- ✅ Verificar se `was_pending` está correto

### 3. **Meta Pixel enviado mas não aparece no Meta**
- ✅ Verificar se `meta_test_event_code` está configurado
- ✅ Verificar se `external_id` está sendo enviado
- ✅ Verificar se `client_ip_address` está presente

---

## 📝 ARQUIVOS MODIFICADOS

1. **app.py** (linha 4560)
   - Meta Pixel no webhook

2. **bot_manager.py** (linha 2144)
   - Meta Pixel na consulta ativa
   - Removido Meta Pixel duplicado (linha 2170)

3. **paradise_payment_checker.py** (linha 121)
   - Meta Pixel no job cron

---

## 🎉 RESULTADO FINAL

✅ **Meta Pixel Purchase envia em TODOS os fluxos**
✅ **Anti-duplicação garantida via flag**
✅ **Todos os gateways cobertos**
✅ **Logs detalhados para debugging**

