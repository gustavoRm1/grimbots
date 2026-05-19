#!/bin/bash
# Script para verificar se bot_user tem fbclid e tentar recuperar tracking_token

PAYMENT_ID=9326

echo "🔍 VERIFICANDO BOT_USER.FBCLID - PAYMENT ID: $PAYMENT_ID"
echo ""

cd ~/grimbots && source venv/bin/activate && python -c "
from app import app, db
from models import Payment, BotUser
from utils.tracking_service import TrackingServiceV4

with app.app_context():
    payment = Payment.query.get($PAYMENT_ID)
    if not payment:
        print(f'❌ Payment $PAYMENT_ID não encontrado')
        exit(1)
    
    print(f'✅ Payment ID: {payment.id}')
    print(f'   payment.fbclid: {payment.fbclid[:50] if payment.fbclid else \"❌ NONE\"}...')
    print('')
    
    # Buscar bot_user
    telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else payment.customer_user_id
    bot_user = BotUser.query.filter_by(
        bot_id=payment.bot_id,
        telegram_user_id=str(telegram_user_id)
    ).first()
    
    if not bot_user:
        print(f'❌ bot_user NÃO encontrado!')
        exit(1)
    
    print(f'✅ bot_user encontrado!')
    print(f'   bot_user.id: {bot_user.id}')
    print(f'   bot_user.fbclid: {bot_user.fbclid[:50] if bot_user.fbclid else \"❌ NONE\"}...')
    print(f'   bot_user.tracking_session_id: {bot_user.tracking_session_id or \"❌ NONE\"}')
    print('')
    
    # Tentar recuperar tracking_token via bot_user.fbclid
    if bot_user.fbclid:
        print(f'🔍 Tentando recuperar tracking_token via bot_user.fbclid...')
        ts = TrackingServiceV4()
        try:
            tracking_token_key = f'tracking:fbclid:{bot_user.fbclid}'
            recovered_token = ts.redis.get(tracking_token_key)
            
            if recovered_token:
                print(f'✅ tracking_token encontrado via bot_user.fbclid: {recovered_token[:30]}...')
                print('')
                
                # Recuperar tracking_data
                tracking_data = ts.recover_tracking_data(recovered_token)
                if tracking_data:
                    print(f'✅ tracking_data encontrado!')
                    print(f'   utm_source: {tracking_data.get(\"utm_source\") or \"❌ NONE\"}')
                    print(f'   utm_campaign: {tracking_data.get(\"utm_campaign\") or \"❌ NONE\"}')
                    print(f'   campaign_code: {tracking_data.get(\"campaign_code\") or tracking_data.get(\"grim\") or \"❌ NONE\"}')
                    print(f'   pageview_event_id: {tracking_data.get(\"pageview_event_id\") or \"❌ NONE\"}')
                    print('')
                    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
                    print('🔧 CORRIGINDO: Atualizando bot_user e payment...')
                    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
                    
                    # Atualizar bot_user.tracking_session_id
                    if not bot_user.tracking_session_id:
                        bot_user.tracking_session_id = recovered_token
                        print(f'✅ bot_user.tracking_session_id atualizado!')
                    
                    # Atualizar payment
                    if not payment.tracking_token:
                        payment.tracking_token = recovered_token
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
                    
                    db.session.commit()
                    print(f'✅ payment.tracking_token atualizado: {payment.tracking_token[:30]}...')
                    print(f'✅ UTMs atualizados!')
                else:
                    print(f'❌ tracking_data NÃO encontrado no Redis para token: {recovered_token[:30]}...')
            else:
                print(f'❌ tracking_token NÃO encontrado no Redis via bot_user.fbclid')
                print(f'   Isso indica que o usuário NÃO passou pelo redirect ou token expirou')
        except Exception as e:
            print(f'❌ Erro ao recuperar via bot_user.fbclid: {e}')
            import traceback
            traceback.print_exc()
    else:
        print(f'❌ bot_user.fbclid está vazio - não é possível recuperar tracking_token')
        print(f'   Isso indica que o usuário NÃO passou pelo redirect')
    
    print('')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('📊 STATUS FINAL:')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    db.session.refresh(payment)
    db.session.refresh(bot_user)
    print(f'payment.tracking_token: {payment.tracking_token or \"❌ NONE\"}')
    print(f'payment.utm_source: {payment.utm_source or \"❌ NONE\"}')
    print(f'payment.utm_campaign: {payment.utm_campaign or \"❌ NONE\"}')
    print(f'payment.campaign_code: {payment.campaign_code or \"❌ NONE\"}')
    print(f'bot_user.tracking_session_id: {bot_user.tracking_session_id or \"❌ NONE\"}')
" 2>/dev/null

echo ""
echo "✅ Script executado!"

