#!/bin/bash
# Script para debug detalhado do payment 9326

PAYMENT_ID=9326

echo "🔍 DEBUG DETALHADO - PAYMENT ID: $PAYMENT_ID"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. VERIFICAR LOGS DO PURCHASE (COMPLETO)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 1000 ~/grimbots/logs/gunicorn.log | grep -i "9326\|purchase" | tail -50

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. VERIFICAR LOGS DO DELIVERY (QUANDO PÁGINA FOI RENDERIZADA)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 1000 ~/grimbots/logs/gunicorn.log | grep -i "delivery.*9326\|delivery.*payment" | tail -30

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. VERIFICAR TRACKING_TOKEN E REDIS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd ~/grimbots && source venv/bin/activate && python -c "
from app import app, db
from models import Payment
from utils.tracking_service import TrackingServiceV4
with app.app_context():
    payment = Payment.query.get($PAYMENT_ID)
    if payment:
        print(f'Payment ID: {payment.id}')
        print(f'tracking_token: {payment.tracking_token or \"❌ NONE\"}')
        print(f'customer_user_id: {payment.customer_user_id}')
        print(f'fbclid: {payment.fbclid[:50] if payment.fbclid else \"❌ NONE\"}...')
        
        # Tentar recuperar tracking_data do Redis
        if payment.tracking_token:
            ts = TrackingServiceV4()
            tracking_data = ts.recover_tracking_data(payment.tracking_token)
            if tracking_data:
                print(f'✅ tracking_data encontrado no Redis:')
                print(f'   utm_source: {tracking_data.get(\"utm_source\") or \"❌ NONE\"}')
                print(f'   utm_campaign: {tracking_data.get(\"utm_campaign\") or \"❌ NONE\"}')
                print(f'   campaign_code: {tracking_data.get(\"campaign_code\") or tracking_data.get(\"grim\") or \"❌ NONE\"}')
                print(f'   pageview_event_id: {tracking_data.get(\"pageview_event_id\") or \"❌ NONE\"}')
            else:
                print(f'❌ tracking_data NÃO encontrado no Redis para token: {payment.tracking_token}')
        
        # Tentar recuperar via bot_user
        from models import BotUser
        bot_user = BotUser.query.filter_by(
            bot_id=payment.bot_id,
            telegram_user_id=payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else payment.customer_user_id
        ).first()
        if bot_user and bot_user.tracking_session_id:
            print(f'✅ bot_user encontrado')
            print(f'   tracking_session_id: {bot_user.tracking_session_id[:30]}...')
            ts = TrackingServiceV4()
            tracking_data = ts.recover_tracking_data(bot_user.tracking_session_id)
            if tracking_data:
                print(f'✅ tracking_data encontrado via bot_user:')
                print(f'   utm_source: {tracking_data.get(\"utm_source\") or \"❌ NONE\"}')
                print(f'   utm_campaign: {tracking_data.get(\"utm_campaign\") or \"❌ NONE\"}')
                print(f'   campaign_code: {tracking_data.get(\"campaign_code\") or tracking_data.get(\"grim\") or \"❌ NONE\"}')
                print(f'   pageview_event_id: {tracking_data.get(\"pageview_event_id\") or \"❌ NONE\"}')
            else:
                print(f'❌ tracking_data NÃO encontrado no Redis para bot_user.tracking_session_id')
" 2>/dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. VERIFICAR SE PURCHASE FOI ENVIADO VIA CAPI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 1000 ~/grimbots/logs/gunicorn.log | grep -i "send_meta_pixel_purchase_event\|Purchase via Server\|meta purchase" | tail -30

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. VERIFICAR ERROS RELACIONADOS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -n 1000 ~/grimbots/logs/gunicorn.log | grep -i "erro.*9326\|error.*9326\|❌.*purchase\|❌.*9326" | tail -20

