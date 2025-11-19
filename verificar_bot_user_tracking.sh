#!/bin/bash
# Script para verificar tracking via bot_user

PAYMENT_ID=9326

echo "🔍 VERIFICANDO TRACKING VIA BOT_USER"
echo ""

cd ~/grimbots && source venv/bin/activate && python -c "
from app import app, db
from models import Payment, BotUser
from utils.tracking_service import TrackingServiceV4
import json

with app.app_context():
    payment = Payment.query.get($PAYMENT_ID)
    if not payment:
        print(f'❌ Payment {PAYMENT_ID} não encontrado')
        exit(1)
    
    print(f'✅ Payment ID: {payment.id}')
    print(f'   customer_user_id: {payment.customer_user_id}')
    print(f'   bot_id: {payment.bot_id}')
    print(f'   tracking_token: {payment.tracking_token or \"❌ NONE\"}')
    print(f'   created_at: {payment.created_at}')
    print('')
    
    # Tentar recuperar via bot_user
    telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else payment.customer_user_id
    print(f'🔍 Buscando bot_user com telegram_user_id: {telegram_user_id}')
    
    bot_user = BotUser.query.filter_by(
        bot_id=payment.bot_id,
        telegram_user_id=str(telegram_user_id)
    ).first()
    
    if not bot_user:
        print(f'❌ bot_user NÃO encontrado!')
        print(f'   Isso indica que o usuário NÃO passou pelo redirect')
    else:
        print(f'✅ bot_user encontrado!')
        print(f'   bot_user.id: {bot_user.id}')
        print(f'   tracking_session_id: {bot_user.tracking_session_id or \"❌ NONE\"}')
        print(f'   created_at: {bot_user.created_at}')
        print('')
        
        if bot_user.tracking_session_id:
            print(f'🔍 Recuperando tracking_data do Redis...')
            ts = TrackingServiceV4()
            tracking_data = ts.recover_tracking_data(bot_user.tracking_session_id)
            
            if tracking_data:
                print(f'✅ tracking_data encontrado no Redis!')
                print(f'   tracking_token: {bot_user.tracking_session_id[:30]}...')
                print(f'   utm_source: {tracking_data.get(\"utm_source\") or \"❌ NONE\"}')
                print(f'   utm_campaign: {tracking_data.get(\"utm_campaign\") or \"❌ NONE\"}')
                print(f'   utm_medium: {tracking_data.get(\"utm_medium\") or \"❌ NONE\"}')
                print(f'   utm_content: {tracking_data.get(\"utm_content\") or \"❌ NONE\"}')
                print(f'   utm_term: {tracking_data.get(\"utm_term\") or \"❌ NONE\"}')
                print(f'   grim: {tracking_data.get(\"grim\") or \"❌ NONE\"}')
                print(f'   campaign_code: {tracking_data.get(\"campaign_code\") or \"❌ NONE\"}')
                print(f'   fbclid: {tracking_data.get(\"fbclid\")[:50] if tracking_data.get(\"fbclid\") else \"❌ NONE\"}...')
                print(f'   pageview_event_id: {tracking_data.get(\"pageview_event_id\") or \"❌ NONE\"}')
                print(f'   client_ip: {tracking_data.get(\"client_ip\") or \"❌ NONE\"}')
                print(f'   client_user_agent: {tracking_data.get(\"client_user_agent\")[:50] if tracking_data.get(\"client_user_agent\") else \"❌ NONE\"}...')
            else:
                print(f'❌ tracking_data NÃO encontrado no Redis para token: {bot_user.tracking_session_id[:30]}...')
                print(f'   Isso pode indicar que o token expirou ou não foi salvo')
        else:
            print(f'❌ bot_user.tracking_session_id está vazio!')
            print(f'   Isso indica que o usuário NÃO passou pelo redirect ou token não foi salvo')
    
    print('')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('🔧 PROBLEMA IDENTIFICADO:')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    if not payment.tracking_token:
        print('❌ payment.tracking_token está NONE')
        print('   SOLUÇÃO: Atualizar payment.tracking_token com bot_user.tracking_session_id')
        if bot_user and bot_user.tracking_session_id:
            print(f'   ✅ Corrigindo: payment.tracking_token = bot_user.tracking_session_id')
            payment.tracking_token = bot_user.tracking_session_id
            db.session.commit()
            print(f'   ✅ payment.tracking_token atualizado!')
" 2>/dev/null

