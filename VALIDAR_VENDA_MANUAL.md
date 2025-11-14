# 🔍 VALIDAÇÃO MANUAL - VENDA RECENTE

## ✅ COMANDO RÁPIDO (BUSCAR VENDAS DAS ÚLTIMAS 24H)

```bash
cd /root/grimbots
source venv/bin/activate
python scripts/validar_venda_recente.py
```

## 📋 SE NÃO ENCONTRAR VENDA, BUSCAR MANUALMENTE

### 1️⃣ Listar Todas as Vendas Recentes

```bash
cd /root/grimbots
source venv/bin/activate
python -c "
from models import Payment
from app import app
from datetime import datetime, timedelta
with app.app_context():
    payments = Payment.query.filter(
        Payment.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).order_by(Payment.created_at.desc()).limit(10).all()
    if payments:
        print(f'✅ {len(payments)} vendas nas últimas 24 horas:')
        for p in payments:
            print(f'   {p.payment_id} | {p.status} | R\$ {p.amount:.2f} | {p.created_at}')
    else:
        print('❌ Nenhuma venda nas últimas 24 horas')
"
```

### 2️⃣ Buscar Venda Específica por Payment ID

Substitua `PAYMENT_ID` pelo ID da venda:

```bash
cd /root/grimbots
source venv/bin/activate
python -c "
from models import Payment
from app import app
with app.app_context():
    payment = Payment.query.filter_by(payment_id='PAYMENT_ID').first()
    if payment:
        print(f'Payment ID: {payment.payment_id}')
        print(f'Status: {payment.status}')
        print(f'Tracking Token: {getattr(payment, \"tracking_token\", \"ausente\")}')
        print(f'Created: {payment.created_at}')
    else:
        print('Venda não encontrada')
"
```

### 3️⃣ Verificar Logs do Redirect (PageView)

Substitua `TRACKING_TOKEN` pelo token da venda:

```bash
# Buscar logs do redirect
grep -iE "\[META REDIRECT\].*TRACKING_TOKEN" logs/gunicorn.log | tail -10

# OU buscar por qualquer redirect recente
grep -iE "\[META REDIRECT\].*fbc" logs/gunicorn.log | tail -10
```

### 4️⃣ Verificar Logs do Purchase

Substitua `PAYMENT_ID` pelo ID da venda:

```bash
# Buscar logs do Purchase
grep -iE "\[META PURCHASE\].*PAYMENT_ID" logs/gunicorn.log | tail -15

# OU buscar por qualquer Purchase recente
grep -iE "\[META PURCHASE\].*fbc" logs/gunicorn.log | tail -10
```

### 5️⃣ Verificar se fbc Sintético Foi Gerado (NÃO DEVE APARECER)

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

## 🎯 VALIDAÇÃO RÁPIDA (ÚLTIMOS LOGS)

```bash
# Ver últimos redirects
tail -100 logs/gunicorn.log | grep -iE "\[META REDIRECT\]" | tail -5

# Ver últimos purchases
tail -100 logs/gunicorn.log | grep -iE "\[META PURCHASE\]" | tail -5

# Verificar se há fbc sintético (NÃO DEVE APARECER)
tail -500 logs/gunicorn.log | grep -iE "fbc.*gerado.*fbclid" | tail -3
```

