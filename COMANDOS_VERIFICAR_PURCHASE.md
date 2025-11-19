# 📋 COMANDOS PARA VERIFICAR PURCHASE APÓS VENDA

## ✅ COMANDO RÁPIDO (RECOMENDADO):

```bash
# Dar permissão de execução
chmod +x verificar_purchase_venda.sh

# Executar script
./verificar_purchase_venda.sh
```

## 🔄 ALTERNATIVA (sem permissão):

```bash
# Executar direto com bash
bash verificar_purchase_venda.sh
```

## 📊 COMANDOS MANUAIS (se preferir):

```bash
# 1. Verificar Purchase via CAPI (server-side)
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "META PURCHASE|Purchase.*enviado|Purchase.*sucesso" | tail -20

# 2. Verificar UTMs e campaign_code
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "Purchase.*utm_source|Purchase.*utm_campaign|Purchase.*campaign_code" | tail -20

# 3. Verificar external_id (fbclid) para matching
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "Purchase.*external_id|Purchase.*fbclid" | tail -20

# 4. Verificar event_id (deduplicação)
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "Purchase.*event_id|pageview_event_id" | tail -20

# 5. Verificar status no banco (última venda)
cd ~/grimbots && source venv/bin/activate && python -c "
from app import app, db
from models import Payment
with app.app_context():
    payment = Payment.query.filter_by(status='paid').order_by(Payment.created_at.desc()).first()
    if payment:
        print(f'Payment ID: {payment.id}')
        print(f'meta_purchase_sent: {payment.meta_purchase_sent}')
        print(f'utm_source: {payment.utm_source or \"❌ NONE\"}')
        print(f'utm_campaign: {payment.utm_campaign or \"❌ NONE\"}')
        print(f'campaign_code: {payment.campaign_code or \"❌ NONE\"}')
        print(f'fbclid: {\"✅ Presente\" if payment.fbclid else \"❌ Ausente\"}')
"
```

## 🎯 O QUE VERIFICAR:

1. ✅ **Purchase via CAPI**: Deve aparecer "Purchase via Server enfileirado com sucesso"
2. ✅ **UTMs**: Deve ter `utm_source` ou `campaign_code` nos logs
3. ✅ **external_id**: Deve ter `fbclid` nos logs
4. ✅ **event_id**: Deve ter `pageview_event_id` nos logs
5. ✅ **meta_purchase_sent**: Deve estar `True` no banco

**❌ Se algum item estiver ausente, a venda pode NÃO ser atribuída à campanha!**

