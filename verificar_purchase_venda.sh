#!/bin/bash
# ✅ Script para verificar se Purchase foi enviado corretamente após uma venda
# Uso: ./verificar_purchase_venda.sh [payment_id]

echo "🔍 Verificando Purchase Event enviado..."
echo ""

# Se payment_id foi fornecido, usar; caso contrário, buscar o último payment
if [ -z "$1" ]; then
    echo "📋 Buscando último payment do banco..."
    PAYMENT_ID=$(cd ~/grimbots && source venv/bin/activate && python -c "
from app import app, db
from models import Payment
with app.app_context():
    last_payment = Payment.query.filter_by(status='paid').order_by(Payment.created_at.desc()).first()
    if last_payment:
        print(last_payment.id)
    else:
        print('NONE')
" 2>/dev/null)
    
    if [ "$PAYMENT_ID" = "NONE" ] || [ -z "$PAYMENT_ID" ]; then
        echo "❌ Nenhum payment encontrado"
        exit 1
    fi
    
    echo "✅ Último payment encontrado: ID $PAYMENT_ID"
    echo ""
else
    PAYMENT_ID=$1
    echo "✅ Verificando payment ID: $PAYMENT_ID"
    echo ""
fi

# 1. Verificar logs do servidor (CAPI - Purchase via server-side)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📡 1. PURCHASE VIA SERVER (Conversions API - CAPI)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "META PURCHASE|Purchase.*payment.*$PAYMENT_ID|send_meta_pixel_purchase_event" | tail -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 2. UTMs E CAMPAIGN_CODE (Atribuição de Campanha)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "Purchase.*utm_source|Purchase.*utm_campaign|Purchase.*campaign_code|Purchase.*grim" | tail -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔑 3. EXTERNAL_ID E IDENTIFICADORES (Matching com PageView)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "Purchase.*external_id|Purchase.*fbclid|Purchase.*fbp|Purchase.*fbc|Purchase.*client_ip" | tail -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 4. EVENT_ID (Deduplicação PageView ↔ Purchase)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "Purchase.*event_id|Purchase.*eventID|pageview_event_id.*$PAYMENT_ID" | tail -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 5. CUSTOM_DATA (Dados completos do Purchase)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -A 5 "Purchase.*custom_data\|Meta Purchase.*custom_data" | tail -30

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 6. STATUS DO ENVIO (Sucesso/Falha)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 500 ~/grimbots/logs/gunicorn.log | grep -E "Purchase.*enviado|Purchase.*sucesso|Purchase.*erro|Purchase.*falha|meta_purchase_sent.*$PAYMENT_ID" | tail -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 7. VERIFICAÇÃO NO BANCO DE DADOS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd ~/grimbots && source venv/bin/activate && python -c "
from app import app, db
from models import Payment
with app.app_context():
    payment = Payment.query.get($PAYMENT_ID)
    if payment:
        print(f'Payment ID: {payment.id}')
        print(f'Status: {payment.status}')
        print(f'Amount: R\$ {payment.amount}')
        print(f'meta_purchase_sent: {payment.meta_purchase_sent}')
        print(f'utm_source: {payment.utm_source or \"❌ NONE\"}')
        print(f'utm_campaign: {payment.utm_campaign or \"❌ NONE\"}')
        print(f'campaign_code: {payment.campaign_code or \"❌ NONE\"}')
        print(f'fbclid: {\"✅ Presente\" if payment.fbclid else \"❌ Ausente\"}')
        print(f'tracking_token: {payment.tracking_token[:30] + \"...\" if payment.tracking_token and len(payment.tracking_token) > 30 else payment.tracking_token or \"❌ NONE\"}')
    else:
        print(f'❌ Payment ID $PAYMENT_ID não encontrado')
" 2>/dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 RESUMO: O que verificar para garantir atribuição de campanha"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Purchase via CAPI: Deve aparecer 'Purchase via Server enfileirado com sucesso'"
echo "✅ UTMs: Deve ter 'Purchase - utm_source' ou 'Purchase - campaign_code' nos logs"
echo "✅ external_id: Deve ter 'Purchase - external_id' ou 'fbclid' nos logs"
echo "✅ event_id: Deve ter 'Purchase - event_id' ou 'pageview_event_id' nos logs"
echo "✅ meta_purchase_sent: Deve estar True no banco de dados"
echo ""
echo "❌ Se algum item estiver ausente, a venda pode NÃO ser atribuída à campanha!"
echo ""

