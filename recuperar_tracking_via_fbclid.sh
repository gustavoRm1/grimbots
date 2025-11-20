#!/bin/bash
# Script para recuperar tracking via fbclid e corrigir payment 9326

PAYMENT_ID=9326

echo "🔍 RECUPERANDO TRACKING VIA FBCLID - PAYMENT ID: $PAYMENT_ID"
echo ""

cd ~/grimbots && source venv/bin/activate && python -c "
from app import app, db
from models import Payment, BotUser
from utils.tracking_service import TrackingServiceV4
import json

with app.app_context():
    payment = Payment.query.get($PAYMENT_ID)
    if not payment:
        print(f'❌ Payment $PAYMENT_ID não encontrado')
        exit(1)
    
    print(f'✅ Payment ID: {payment.id}')
    print(f'   fbclid: {payment.fbclid[:50] if payment.fbclid else \"❌ NONE\"}...')
    print('')
    
    # ✅ TENTAR RECUPERAR VIA fbclid
    if payment.fbclid:
        print(f'🔍 Tentando recuperar tracking_token via fbclid...')
        ts = TrackingServiceV4()
        try:
            # Buscar tracking_token no Redis via fbclid
            tracking_token_key = f'tracking:fbclid:{payment.fbclid}'
            recovered_token = ts.redis.get(tracking_token_key)
            
            if recovered_token:
                print(f'✅ tracking_token encontrado via fbclid: {recovered_token[:30]}...')
                print('')
                
                # Recuperar tracking_data completo
                tracking_data = ts.recover_tracking_data(recovered_token)
                if tracking_data:
                    print(f'✅ tracking_data encontrado no Redis!')
                    print(f'   tracking_token: {recovered_token[:30]}...')
                    print(f'   utm_source: {tracking_data.get(\"utm_source\") or \"❌ NONE\"}')
                    print(f'   utm_campaign: {tracking_data.get(\"utm_campaign\") or \"❌ NONE\"}')
                    print(f'   utm_medium: {tracking_data.get(\"utm_medium\") or \"❌ NONE\"}')
                    print(f'   grim: {tracking_data.get(\"grim\") or \"❌ NONE\"}')
                    print(f'   campaign_code: {tracking_data.get(\"campaign_code\") or \"❌ NONE\"}')
                    print(f'   pageview_event_id: {tracking_data.get(\"pageview_event_id\") or \"❌ NONE\"}')
                    print('')
                    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
                    print('🔧 CORRIGINDO: Atualizando payment e bot_user...')
                    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
                    
                    # Atualizar payment.tracking_token
                    if not payment.tracking_token:
                        payment.tracking_token = recovered_token
                    
                    # Atualizar UTMs
                    if tracking_data.get('utm_source'):
                        payment.utm_source = tracking_data.get('utm_source')
                    if tracking_data.get('utm_campaign'):
                        payment.utm_campaign = tracking_data.get('utm_campaign')
                    if tracking_data.get('utm_medium'):
                        payment.utm_medium = tracking_data.get('utm_medium')
                    if tracking_data.get('campaign_code') or tracking_data.get('grim'):
                        payment.campaign_code = tracking_data.get('campaign_code') or tracking_data.get('grim')
                    if tracking_data.get('pageview_event_id'):
                        payment.pageview_event_id = tracking_data.get('pageview_event_id')
                    
                    # Atualizar bot_user.tracking_session_id
                    telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else payment.customer_user_id
                    bot_user = BotUser.query.filter_by(
                        bot_id=payment.bot_id,
                        telegram_user_id=str(telegram_user_id)
                    ).first()
                    
                    if bot_user and not bot_user.tracking_session_id:
                        bot_user.tracking_session_id = recovered_token
                        print(f'✅ bot_user.tracking_session_id atualizado!')
                    
                    db.session.commit()
                    print(f'✅ payment.tracking_token atualizado: {payment.tracking_token[:30]}...')
                    print(f'✅ UTMs atualizados: utm_source={payment.utm_source}, utm_campaign={payment.utm_campaign}, campaign_code={payment.campaign_code}')
                    print(f'✅ pageview_event_id atualizado: {payment.pageview_event_id}')
                else:
                    print(f'❌ tracking_data NÃO encontrado no Redis para token: {recovered_token[:30]}...')
                    print(f'   Token pode ter expirado')
            else:
                print(f'❌ tracking_token NÃO encontrado no Redis via fbclid')
                print(f'   Isso indica que o usuário NÃO passou pelo redirect ou token expirou')
        except Exception as e:
            print(f'❌ Erro ao recuperar via fbclid: {e}')
            import traceback
            traceback.print_exc()
    else:
        print(f'❌ payment.fbclid está vazio - não é possível recuperar tracking_token')
    
    print('')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('📊 STATUS FINAL:')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    db.session.refresh(payment)
    print(f'payment.tracking_token: {payment.tracking_token or \"❌ NONE\"}')
    print(f'payment.utm_source: {payment.utm_source or \"❌ NONE\"}')
    print(f'payment.utm_campaign: {payment.utm_campaign or \"❌ NONE\"}')
    print(f'payment.campaign_code: {payment.campaign_code or \"❌ NONE\"}')
    print(f'payment.pageview_event_id: {payment.pageview_event_id or \"❌ NONE\"}')
    
    # Verificar bot_user
    telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else payment.customer_user_id
    bot_user = BotUser.query.filter_by(
        bot_id=payment.bot_id,
        telegram_user_id=str(telegram_user_id)
    ).first()
    if bot_user:
        print(f'bot_user.tracking_session_id: {bot_user.tracking_session_id or \"❌ NONE\"}')
" 2>/dev/null

echo ""
echo "✅ Script executado!"

