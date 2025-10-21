#!/usr/bin/env python
"""
TESTE MANUAL: META PIXEL PURCHASE ELITE
========================================

Testa envio de evento Purchase com dados COMPLETOS:
- external_id (do fbclid)
- client_ip_address (capturado)
- client_user_agent (capturado)
- currency: BRL
- value: valor real

Autor: QI 500 Elite Team
Data: 2025-10-21
"""

import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

def test_purchase_event():
    print("=" * 80)
    print("🎯 TESTE MANUAL: META PIXEL PURCHASE ELITE")
    print("=" * 80)
    print()
    
    from app import app, db
    from models import Payment, BotUser, RedirectPool, PoolBot
    from utils.meta_pixel import MetaPixelAPI
    from utils.encryption import decrypt
    from celery_app import send_meta_event
    import time
    
    with app.app_context():
        # Buscar último pagamento PAID
        payment = Payment.query.filter_by(status='paid').order_by(Payment.paid_at.desc()).first()
        
        if not payment:
            print("❌ Nenhum pagamento encontrado com status 'paid'")
            print("   Crie um pagamento de teste primeiro")
            return
        
        print(f"📊 PAYMENT ENCONTRADO:")
        print(f"   ID: {payment.id}")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Customer: {payment.customer_name}")
        print(f"   Amount: R$ {payment.amount}")
        print(f"   Status: {payment.status}")
        print()
        
        # Buscar pool
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        if not pool_bot:
            print("❌ Bot não está associado a nenhum pool")
            return
        
        pool = pool_bot.pool
        
        if not pool.meta_tracking_enabled:
            print(f"❌ Pool '{pool.name}' não tem Meta Pixel habilitado")
            return
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            print(f"❌ Pool '{pool.name}' não tem Pixel ID ou Access Token")
            return
        
        print(f"📊 POOL ENCONTRADO:")
        print(f"   Nome: {pool.name}")
        print(f"   Pixel ID: {pool.meta_pixel_id}")
        print(f"   Purchase enabled: {pool.meta_events_purchase}")
        print()
        
        # Buscar BotUser
        bot_user = BotUser.query.filter_by(
            bot_id=payment.bot_id,
            telegram_user_id=payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else None
        ).first()
        
        print(f"📊 BOTUSER:")
        if bot_user:
            print(f"   Telegram ID: {bot_user.telegram_user_id}")
            print(f"   External ID: {bot_user.external_id or 'N/A'}")
            print(f"   IP Address: {bot_user.ip_address if hasattr(bot_user, 'ip_address') else 'N/A'}")
            print(f"   User Agent: {(bot_user.user_agent[:50] + '...') if hasattr(bot_user, 'user_agent') and bot_user.user_agent else 'N/A'}")
            print(f"   fbclid: {bot_user.fbclid or 'N/A'}")
            print(f"   utm_source: {bot_user.utm_source or 'N/A'}")
            print(f"   utm_campaign: {bot_user.utm_campaign or 'N/A'}")
        else:
            print(f"   ❌ BotUser não encontrado!")
        print()
        
        # Gerar event_id
        event_id = MetaPixelAPI._generate_event_id(
            event_type='purchase',
            unique_id=payment.payment_id
        )
        
        # Descriptografar token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            print(f"❌ Erro ao descriptografar token: {e}")
            return
        
        # Construir payload COMPLETO
        event_data = {
            'event_name': 'Purchase',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'user_data': {
                'external_id': bot_user.external_id if bot_user and bot_user.external_id else f'payment_{payment.id}',
            },
            'custom_data': {
                'currency': 'BRL',
                'value': float(payment.amount),
                'content_id': str(pool.id),
                'content_name': payment.product_name or 'Produto',
                'content_type': 'product'
            }
        }
        
        # Adicionar IP/UA se disponível (TRACKING ELITE)
        if bot_user:
            if hasattr(bot_user, 'ip_address') and bot_user.ip_address:
                event_data['user_data']['client_ip_address'] = bot_user.ip_address
            
            if hasattr(bot_user, 'user_agent') and bot_user.user_agent:
                event_data['user_data']['client_user_agent'] = bot_user.user_agent
        
        print("📊 PAYLOAD PURCHASE:")
        print("=" * 80)
        import json
        print(json.dumps(event_data, indent=2, ensure_ascii=False))
        print("=" * 80)
        print()
        
        # VALIDAÇÕES CRÍTICAS
        print("🔍 VALIDAÇÕES CRÍTICAS:")
        checks_passed = 0
        checks_total = 0
        
        # Check 1: external_id presente
        checks_total += 1
        if event_data['user_data'].get('external_id'):
            print(f"   ✅ external_id presente: {event_data['user_data']['external_id']}")
            checks_passed += 1
        else:
            print(f"   ❌ external_id AUSENTE!")
        
        # Check 2: currency
        checks_total += 1
        if event_data['custom_data'].get('currency') == 'BRL':
            print(f"   ✅ currency correto: BRL")
            checks_passed += 1
        else:
            print(f"   ❌ currency inválido ou ausente!")
        
        # Check 3: value
        checks_total += 1
        if event_data['custom_data'].get('value') and event_data['custom_data']['value'] > 0:
            print(f"   ✅ value presente: R$ {event_data['custom_data']['value']}")
            checks_passed += 1
        else:
            print(f"   ❌ value inválido ou zero!")
        
        # Check 4: event_id único
        checks_total += 1
        if event_data.get('event_id') and len(event_data['event_id']) > 10:
            print(f"   ✅ event_id único: {event_data['event_id'][:30]}...")
            checks_passed += 1
        else:
            print(f"   ❌ event_id ausente ou muito curto!")
        
        # Check 5: IP/UA (ELITE)
        checks_total += 1
        has_ip = event_data['user_data'].get('client_ip_address')
        has_ua = event_data['user_data'].get('client_user_agent')
        if has_ip and has_ua:
            print(f"   ✅ TRACKING ELITE: IP e UA presentes")
            checks_passed += 1
        elif has_ip or has_ua:
            print(f"   ⚠️  TRACKING ELITE parcial (falta {'UA' if has_ip else 'IP'})")
            checks_passed += 0.5
        else:
            print(f"   ❌ TRACKING ELITE ausente (sem IP/UA)")
        
        print()
        print(f"📊 SCORE DE QUALIDADE: {checks_passed}/{checks_total} ({checks_passed/checks_total*100:.1f}%)")
        print()
        
        # Perguntar se quer enviar
        print("❓ ENVIAR ESTE EVENTO PARA O META AGORA?")
        print("   Digite 'SIM' para enviar (teste real)")
        print("   Digite 'NAO' para apenas validar payload")
        
        resposta = input("\n>>> ").strip().upper()
        
        if resposta == 'SIM':
            print("\n🚀 ENVIANDO EVENTO PARA META...")
            
            # Enviar via Celery
            task = send_meta_event.apply_async(
                args=[
                    pool.meta_pixel_id,
                    access_token,
                    event_data,
                    pool.meta_test_event_code
                ],
                priority=1
            )
            
            print(f"✅ Evento enfileirado!")
            print(f"   Task ID: {task.id}")
            print(f"   Pixel ID: {pool.meta_pixel_id}")
            print()
            print("📊 AGUARDE 10-30 SEGUNDOS E VERIFIQUE:")
            print(f"   1. Meta Events Manager: https://business.facebook.com/events_manager2/list/pixel/{pool.meta_pixel_id}")
            print(f"   2. Logs do Celery: tail -f logs/celery.log | grep Purchase")
            print()
        else:
            print("\n⏭️  Envio cancelado. Apenas validação realizada.")
        
        print("=" * 80)
        print("✅ TESTE CONCLUÍDO")
        print("=" * 80)

if __name__ == '__main__':
    test_purchase_event()

