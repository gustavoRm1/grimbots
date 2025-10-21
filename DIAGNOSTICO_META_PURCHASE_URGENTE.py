#!/usr/bin/env python3
"""
DIAGNÓSTICO CRÍTICO: Por que Purchase não aparece no Events Manager?

Executa análise completa do último Purchase enviado:
- Payload exato
- Response da API
- Validação de campos obrigatórios
- Match quality esperado
- Tempo desde envio
"""

from app import app, db
from models import Payment, RedirectPool, BotUser
from utils.encryption import decrypt
from datetime import datetime
import requests
import json

def diagnosticar_purchase():
    with app.app_context():
        # 1. BUSCAR ÚLTIMO PURCHASE ENVIADO
        last_purchase = Payment.query.filter(
            Payment.meta_purchase_sent == True
        ).order_by(Payment.meta_purchase_sent_at.desc()).first()
        
        if not last_purchase:
            print("❌ NENHUM PURCHASE FOI ENVIADO!")
            return
        
        print("="*80)
        print("🔍 DIAGNÓSTICO CRÍTICO - META PURCHASE")
        print("="*80)
        print()
        
        # INFORMAÇÕES DA VENDA
        print("📊 VENDA:")
        print(f"   Cliente: {last_purchase.customer_name}")
        print(f"   Valor: R$ {last_purchase.amount:.2f}")
        print(f"   Pago em: {last_purchase.paid_at}")
        print(f"   Purchase enviado em: {last_purchase.meta_purchase_sent_at}")
        print(f"   Tempo decorrido: {datetime.now() - last_purchase.meta_purchase_sent_at}")
        print(f"   Event ID: {last_purchase.meta_event_id}")
        print()
        
        # 2. BUSCAR BOT E POOL
        from models import Bot, PoolBot
        
        bot = Bot.query.get(last_purchase.bot_id)
        if not bot:
            print("❌ Bot não encontrado!")
            return
        
        pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        if not pool_bot:
            print("❌ Bot não está associado a nenhum pool!")
            return
        
        pool = pool_bot.pool
        
        print("🔧 CONFIGURAÇÃO:")
        print(f"   Bot: {bot.name} (@{bot.username})")
        print(f"   Pool: {pool.name}")
        print(f"   Pixel ID: {pool.meta_pixel_id}")
        print()
        
        # 3. BUSCAR BOTUSER PARA DADOS DE TRACKING
        bot_user = BotUser.query.filter_by(
            bot_id=bot.id,
            telegram_user_id=int(last_purchase.customer_user_id.replace('user_', '')) if last_purchase.customer_user_id and last_purchase.customer_user_id.startswith('user_') else None
        ).first()
        
        print("👤 DADOS DO USUÁRIO:")
        if bot_user:
            print(f"   External ID: {bot_user.external_id[:50] if bot_user.external_id else 'AUSENTE'}...")
            print(f"   FBCLID: {bot_user.fbclid[:50] if bot_user.fbclid else 'AUSENTE'}...")
            print(f"   IP: {bot_user.ip_address or 'AUSENTE'}")
            print(f"   User-Agent: {(bot_user.user_agent[:80] + '...') if bot_user.user_agent else 'AUSENTE'}")
        else:
            print("   ❌ BotUser não encontrado!")
        print()
        
        # 4. RECRIAR PAYLOAD EXATO
        print("📤 PAYLOAD ENVIADO AO META:")
        print("-" * 80)
        
        import time
        
        # Recriar o event_data exato
        event_data = {
            'event_name': 'Purchase',
            'event_time': int(last_purchase.paid_at.timestamp()) if last_purchase.paid_at else int(time.time()),
            'action_source': 'website',
            'event_source_url': f'https://t.me/{bot.username}',
            'user_data': {}
        }
        
        # External ID (CRÍTICO!)
        if bot_user and bot_user.external_id:
            event_data['user_data']['external_id'] = bot_user.external_id
        
        # IP e User-Agent (CRÍTICO para match quality!)
        if bot_user and bot_user.ip_address:
            event_data['user_data']['client_ip_address'] = bot_user.ip_address
        
        if bot_user and bot_user.user_agent:
            event_data['user_data']['client_user_agent'] = bot_user.user_agent
        
        # Custom Data (OBRIGATÓRIO para Purchase!)
        event_data['custom_data'] = {
            'currency': 'BRL',
            'value': float(last_purchase.amount),
            'content_type': 'product',
            'content_name': last_purchase.product_name or 'Produto Digital',
            'payment_method': last_purchase.gateway_type or 'pix'
        }
        
        # Event ID (para deduplicação)
        if last_purchase.meta_event_id:
            event_data['event_id'] = last_purchase.meta_event_id
        
        print(json.dumps(event_data, indent=2, ensure_ascii=False))
        print("-" * 80)
        print()
        
        # 5. VALIDAR CAMPOS OBRIGATÓRIOS
        print("✅ VALIDAÇÃO DE CAMPOS OBRIGATÓRIOS:")
        validations = {
            'event_name': event_data.get('event_name'),
            'event_time': event_data.get('event_time'),
            'action_source': event_data.get('action_source'),
            'external_id': event_data.get('user_data', {}).get('external_id'),
            'client_ip_address': event_data.get('user_data', {}).get('client_ip_address'),
            'client_user_agent': event_data.get('user_data', {}).get('client_user_agent'),
            'currency': event_data.get('custom_data', {}).get('currency'),
            'value': event_data.get('custom_data', {}).get('value'),
            'event_id': event_data.get('event_id')
        }
        
        missing_critical = []
        for field, value in validations.items():
            status = '✅' if value else '❌'
            print(f"   {status} {field}: {value if value else 'AUSENTE'}")
            
            # Campos críticos para match quality
            if field in ['external_id', 'client_ip_address', 'client_user_agent'] and not value:
                missing_critical.append(field)
        
        print()
        
        if missing_critical:
            print("🚨 PROBLEMA IDENTIFICADO:")
            print(f"   Campos críticos ausentes: {', '.join(missing_critical)}")
            print(f"   Isso resulta em MATCH QUALITY BAIXO!")
            print(f"   Meta pode IGNORAR o evento!")
            print()
        
        # 6. TESTAR ENVIO REAL AGORA
        print("🧪 TESTE DE ENVIO REAL:")
        print("-" * 80)
        
        try:
            access_token = decrypt(pool.meta_access_token)
            pixel_id = pool.meta_pixel_id
            
            url = f'https://graph.facebook.com/v21.0/{pixel_id}/events'
            
            payload = {
                'data': [event_data],
                'access_token': access_token
            }
            
            # Adicionar test_event_code se disponível
            if pool.meta_test_event_code:
                payload['test_event_code'] = pool.meta_test_event_code
                print(f"   🧪 MODO TESTE: {pool.meta_test_event_code}")
            
            print(f"   URL: {url}")
            print(f"   Enviando...")
            
            response = requests.post(url, json=payload, timeout=10)
            
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            print()
            
            if response.status_code == 200:
                data = response.json()
                print("   ✅ EVENTO ACEITO PELA META!")
                
                # Verificar eventos recebidos
                if 'events_received' in data:
                    print(f"   📊 Eventos recebidos: {data['events_received']}")
                
                # Verificar messages (warnings/errors)
                if 'messages' in data and data['messages']:
                    print(f"   ⚠️ Mensagens da Meta:")
                    for msg in data['messages']:
                        print(f"      - {msg}")
                
                # Verificar fbtrace_id (para suporte)
                if 'fbtrace_id' in data:
                    print(f"   🔍 FB Trace ID: {data['fbtrace_id']}")
            else:
                print("   ❌ ERRO NO ENVIO!")
                print(f"   Detalhes: {response.text}")
        
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
        
        print("-" * 80)
        print()
        
        # 7. DIAGNÓSTICO FINAL
        print("🎯 DIAGNÓSTICO FINAL:")
        print("-" * 80)
        
        if missing_critical:
            print("❌ PROBLEMA: Campos críticos ausentes no payload")
            print(f"   Campos faltando: {', '.join(missing_critical)}")
            print()
            print("📋 SOLUÇÃO:")
            print("   1. Garantir que BotUser tem external_id, IP e User-Agent")
            print("   2. Tracking Elite deve capturar esses dados no /start")
            print("   3. Reenviar evento com dados completos")
        else:
            print("✅ PAYLOAD COMPLETO - Todos os campos críticos presentes")
            print()
            print("⏳ TEMPO DE PROCESSAMENTO DO META:")
            print("   - Events Manager: 1-5 minutos (tempo real)")
            print("   - Ads Manager: 15 min - 24 horas")
            print("   - Atribuição final: até 7 dias")
            print()
            print("🔍 ONDE VERIFICAR:")
            print(f"   1. Events Manager: https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/overview")
            print(f"   2. Test Events (se usando test_event_code)")
            print(f"   3. Buscar por Event ID: {last_purchase.meta_event_id}")

if __name__ == '__main__':
    diagnosticar_purchase()

