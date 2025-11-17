#!/usr/bin/env python3
"""
Script de Verificação Completa - Tracking de Vendas
Verifica se o sistema está trackeando vendas corretamente
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import Payment, BotUser, db
from datetime import datetime, timedelta
import redis
import json

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def verificar_tracking_vendas():
    """Verificação completa do tracking de vendas"""
    
    print("=" * 80)
    print("🔍 VERIFICAÇÃO COMPLETA - TRACKING DE VENDAS")
    print("=" * 80)
    print()
    
    with app.app_context():
        # 1. VERIFICAR PAYMENTS RECENTES
        print("📊 1. VERIFICANDO PAYMENTS RECENTES (últimas 24h)")
        print("-" * 80)
        
        recent_payments = Payment.query.filter(
            Payment.created_at >= datetime.now() - timedelta(hours=24)
        ).order_by(Payment.id.desc()).limit(20).all()
        
        print(f"   Total de payments nas últimas 24h: {len(recent_payments)}")
        
        payments_com_tracking = 0
        payments_paid = 0
        payments_paid_com_tracking = 0
        
        for payment in recent_payments:
            if payment.tracking_token:
                payments_com_tracking += 1
                if payment.status == 'paid':
                    payments_paid_com_tracking += 1
            
            if payment.status == 'paid':
                payments_paid += 1
        
        print(f"   ✅ Payments com tracking_token: {payments_com_tracking}/{len(recent_payments)}")
        print(f"   ✅ Payments pagos: {payments_paid}/{len(recent_payments)}")
        print(f"   ✅ Payments pagos COM tracking: {payments_paid_com_tracking}/{payments_paid if payments_paid > 0 else 1}")
        
        if payments_paid > 0 and payments_paid_com_tracking < payments_paid:
            print(f"   ⚠️  ATENÇÃO: {payments_paid - payments_paid_com_tracking} vendas pagas SEM tracking_token!")
        
        print()
        
        # 2. VERIFICAR TRACKING TOKENS NO REDIS
        print("📊 2. VERIFICANDO TRACKING TOKENS NO REDIS")
        print("-" * 80)
        
        try:
            tracking_keys = redis_client.keys("tracking:*")
            tracking_tokens = [k for k in tracking_keys if not k.startswith("tracking:fbclid:") and not k.startswith("tracking:chat:") and not k.startswith("tracking:last_token:")]
            
            print(f"   Total de tracking tokens no Redis: {len(tracking_tokens)}")
            
            if tracking_tokens:
                # Verificar alguns tokens
                sample_tokens = tracking_tokens[:5]
                tokens_com_dados_completos = 0
                
                for key in sample_tokens:
                    data = redis_client.get(key)
                    if data:
                        try:
                            payload = json.loads(data)
                            has_fbp = bool(payload.get('fbp'))
                            has_fbc = bool(payload.get('fbc'))
                            has_fbclid = bool(payload.get('fbclid'))
                            has_pageview_event_id = bool(payload.get('pageview_event_id'))
                            has_client_ip = bool(payload.get('client_ip'))
                            has_client_user_agent = bool(payload.get('client_user_agent'))
                            
                            if has_fbp and has_fbclid and has_pageview_event_id and has_client_ip:
                                tokens_com_dados_completos += 1
                        except:
                            pass
                
                print(f"   ✅ Tokens com dados completos (amostra): {tokens_com_dados_completos}/{len(sample_tokens)}")
            else:
                print("   ⚠️  NENHUM tracking token encontrado no Redis!")
        except Exception as e:
            print(f"   ❌ Erro ao acessar Redis: {e}")
        
        print()
        
        # 3. VERIFICAR ÚLTIMOS PAYMENTS PAGOS
        print("📊 3. VERIFICANDO ÚLTIMOS PAYMENTS PAGOS")
        print("-" * 80)
        
        paid_payments = Payment.query.filter(
            Payment.status == 'paid',
            Payment.updated_at >= datetime.now() - timedelta(hours=24)
        ).order_by(Payment.id.desc()).limit(10).all()
        
        print(f"   Total de payments pagos nas últimas 24h: {len(paid_payments)}")
        print()
        
        for payment in paid_payments:
            tracking_status = "✅" if payment.tracking_token else "❌"
            tracking_preview = payment.tracking_token[:20] + "..." if payment.tracking_token else "N/A"
            
            # Verificar se tracking data existe no Redis
            redis_status = "❌"
            if payment.tracking_token:
                try:
                    redis_data = redis_client.get(f"tracking:{payment.tracking_token}")
                    if redis_data:
                        redis_status = "✅"
                except:
                    pass
            
            print(f"   Payment {payment.id}:")
            print(f"      Status: {payment.status}")
            print(f"      Tracking Token: {tracking_status} {tracking_preview}")
            print(f"      Redis Data: {redis_status}")
            print(f"      Valor: R$ {payment.amount:.2f}")
            if hasattr(payment, 'updated_at') and payment.updated_at:
                print(f"      Atualizado: {payment.updated_at}")
            print()
        
        # 4. VERIFICAR LOGS RECENTES
        print("📊 4. COMANDOS PARA VERIFICAR LOGS")
        print("-" * 80)
        print("   Execute os seguintes comandos para verificar logs:")
        print()
        print("   # PageView events:")
        print("   tail -n 100 logs/gunicorn.log | grep 'META PAGEVIEW'")
        print()
        print("   # ViewContent events:")
        print("   tail -n 100 logs/gunicorn.log | grep 'META VIEWCONTENT'")
        print()
        print("   # Purchase events:")
        print("   tail -n 100 logs/gunicorn.log | grep 'META PURCHASE'")
        print()
        print("   # Webhooks:")
        print("   tail -n 100 logs/celery.log | grep 'WEBHOOK'")
        print()
        
        # 5. RESUMO FINAL
        print("=" * 80)
        print("📋 RESUMO FINAL")
        print("=" * 80)
        print()
        
        if payments_paid > 0:
            tracking_percentage = (payments_paid_com_tracking / payments_paid) * 100
            print(f"   ✅ Taxa de tracking: {tracking_percentage:.1f}% ({payments_paid_com_tracking}/{payments_paid})")
            
            if tracking_percentage < 90:
                print(f"   ⚠️  ATENÇÃO: Taxa de tracking abaixo de 90%!")
            else:
                print(f"   ✅ Taxa de tracking OK!")
        else:
            print("   ⚠️  Nenhuma venda paga nas últimas 24h para verificar")
        
        print()
        print("=" * 80)
        print("✅ VERIFICAÇÃO CONCLUÍDA")
        print("=" * 80)

if __name__ == "__main__":
    verificar_tracking_vendas()

