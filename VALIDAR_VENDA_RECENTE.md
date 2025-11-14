# 🔍 VALIDAÇÃO DA VENDA RECENTE - PATCH V4.1

## ✅ COMANDO RÁPIDO (TUDO EM UM)

Execute na VPS:

```bash
cd /root/grimbots
source venv/bin/activate
python scripts/validar_venda_recente.py
```

## 📋 VALIDAÇÃO MANUAL (PASSO A PASSO)

### 1️⃣ Buscar Venda Mais Recente

```bash
cd /root/grimbots
source venv/bin/activate
python -c "
from models import Payment
from app import app
from datetime import datetime, timedelta
with app.app_context():
    payment = Payment.query.filter(Payment.created_at >= datetime.utcnow() - timedelta(hours=2)).order_by(Payment.created_at.desc()).first()
    if payment:
        print(f'Payment ID: {payment.payment_id}')
        print(f'Status: {payment.status}')
        print(f'Tracking Token: {getattr(payment, \"tracking_token\", \"ausente\")}')
    else:
        print('Nenhuma venda nas últimas 2 horas')
"
```

### 2️⃣ Verificar Logs do Redirect (PageView)

Substitua `TRACKING_TOKEN` pelo token da venda:

```bash
# Buscar logs do redirect
grep -iE "\[META REDIRECT\].*TRACKING_TOKEN" logs/gunicorn.log | tail -10

# Verificar se fbc foi capturado como REAL
grep -iE "fbc.*ORIGEM REAL|fbc REAL" logs/gunicorn.log | tail -5
```

### 3️⃣ Verificar Logs do Purchase

Substitua `PAYMENT_ID` pelo ID da venda:

```bash
# Buscar logs do Purchase
grep -iE "\[META PURCHASE\].*PAYMENT_ID" logs/gunicorn.log | tail -15

# Verificar se fbc REAL foi usado
grep -iE "\[META PURCHASE\].*fbc REAL" logs/gunicorn.log | tail -5
```

### 4️⃣ Verificar se fbc Sintético Foi Gerado (NÃO DEVE APARECER)

```bash
# Se aparecer algo aqui, a correção NÃO funcionou
grep -iE "fbc.*gerado.*fbclid|fbc sintético|fbc gerado do fbclid" logs/gunicorn.log | tail -5
```

## ✅ O QUE DEVE APARECER NOS LOGS

### ✅ CORRETO (fbc REAL):

```
[META REDIRECT] Redirect - fbc capturado do cookie (ORIGEM REAL): fb.1.1732134409...
[META REDIRECT] Redirect - fbc REAL será salvo no Redis (origem: cookie): fb.1.1732134409...
[META PURCHASE] Purchase - fbc REAL recuperado do tracking_data (origem: cookie): fb.1.1732134409...
[META PURCHASE] Purchase - fbc REAL aplicado: fb.1.1732134409...
```

**Timestamp antigo (`1732134409`) = fbc REAL ✅**

### ❌ ERRADO (fbc sintético - NÃO DEVE APARECER):

```
[META REDIRECT] Redirect - fbc gerado do fbclid (formato oficial Meta): fb.1.1763124564...
```

**Timestamp recente (`1763124564`) = fbc sintético ❌**

### ⚠️ ACEITÁVEL (sem fbc, mas com external_id):

```
[META REDIRECT] Redirect - fbc NÃO encontrado no cookie - Meta terá atribuição reduzida (sem fbc)
[META PURCHASE] Purchase - fbc ausente ou ignorado. Match Quality será prejudicada.
[META PURCHASE] Purchase - Usando APENAS external_id (fbclid hasheado) + ip + user_agent para matching
```

## 📊 CHECKLIST DE VALIDAÇÃO

- [ ] ✅ Nenhum log de "fbc gerado do fbclid" (sintético)
- [ ] ✅ Logs mostram "fbc capturado do cookie (ORIGEM REAL)" OU "fbc ausente"
- [ ] ✅ Purchase mostra "fbc REAL aplicado" OU "fbc ausente ou ignorado"
- [ ] ✅ `external_id` sempre presente nos logs do Purchase
- [ ] ✅ `tracking_token` presente no Payment
- [ ] ✅ Purchase event enviado (se payment.status = 'paid')

## 🎯 RESULTADO ESPERADO

Se tudo estiver correto:

- ✅ Zero geração de fbc sintético
- ✅ fbc REAL capturado quando disponível
- ✅ external_id sempre presente
- ✅ Match Quality: 7/10 ou superior (verificar no Meta Event Manager)

## 🔍 VERIFICAR NO META EVENT MANAGER

1. Acesse: https://business.facebook.com/events_manager2
2. Selecione seu Pixel ID
3. Vá em "Test Events" ou "Events"
4. Procure pelo Purchase event da venda
5. Verifique:
   - Match Quality: deve ser 7/10 ou superior
   - Event ID: deve ser o mesmo do PageView (deduplicação)
   - External ID: deve estar presente
   - FBC: deve estar presente (se foi capturado)

