#!/usr/bin/env python3
"""
Script de diagnóstico para verificar por que Purchase não está sendo enviado

Executar na VPS:
python3 diagnostico_purchase_eventos.py
"""

import os
import sys
from datetime import datetime, timedelta

# Adicionar diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Payment, PoolBot, RedirectPool, db
from utils.encryption import decrypt

def main():
    with app.app_context():
        print("=" * 80)
        print("🔍 DIAGNÓSTICO: Por que Purchase não está sendo enviado?")
        print("=" * 80)
        print()
        
        # 1. Verificar Pools configurados
        print("📊 1. POOLS COM META PIXEL CONFIGURADO:")
        print("-" * 80)
        pools = RedirectPool.query.filter(
            RedirectPool.meta_tracking_enabled == True
        ).all()
        
        if not pools:
            print("❌ NENHUM POOL COM meta_tracking_enabled = True!")
            return
        
        for pool in pools:
            has_token = pool.meta_access_token is not None
            token_preview = "SIM" if has_token else "NÃO"
            
            print(f"\nPool ID: {pool.id} | Nome: {pool.name}")
            print(f"  ✅ meta_tracking_enabled: {pool.meta_tracking_enabled}")
            print(f"  {'✅' if pool.meta_pixel_id else '❌'} meta_pixel_id: {pool.meta_pixel_id}")
            print(f"  {'✅' if has_token else '❌'} meta_access_token: {token_preview}")
            print(f"  {'✅' if pool.meta_events_pageview else '❌'} meta_events_pageview: {pool.meta_events_pageview}")
            print(f"  {'✅' if pool.meta_events_viewcontent else '❌'} meta_events_viewcontent: {pool.meta_events_viewcontent}")
            print(f"  {'✅' if pool.meta_events_purchase else '❌'} meta_events_purchase: {pool.meta_events_purchase} ← CRÍTICO!")
            
            if not pool.meta_events_purchase:
                print(f"  ⚠️ PROBLEMA: meta_events_purchase = FALSE - Purchase NÃO será enviado!")
        
        print()
        print("=" * 80)
        
        # 2. Verificar Payments recentes
        print("\n📊 2. PAYMENTS RECENTES (últimas 24h):")
        print("-" * 80)
        since = datetime.utcnow() - timedelta(hours=24)
        payments = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= since
        ).order_by(Payment.created_at.desc()).limit(10).all()
        
        if not payments:
            print("❌ NENHUM PAYMENT PAGO NAS ÚLTIMAS 24H!")
            return
        
        print(f"\nTotal de payments pagos: {len(payments)}")
        
        for payment in payments:
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
            pool = pool_bot.pool if pool_bot else None
            
            print(f"\nPayment ID: {payment.id} | {payment.payment_id}")
            print(f"  Valor: R$ {payment.amount:.2f}")
            print(f"  Status: {payment.status}")
            print(f"  Delivery Token: {'✅' if payment.delivery_token else '❌'} {payment.delivery_token[:20] + '...' if payment.delivery_token else 'NONE'}")
            print(f"  meta_purchase_sent: {payment.meta_purchase_sent}")
            print(f"  meta_event_id: {payment.meta_event_id or 'NONE'}")
            
            if pool:
                print(f"  Pool: {pool.name} (ID: {pool.id})")
                print(f"    meta_tracking_enabled: {pool.meta_tracking_enabled}")
                print(f"    meta_events_purchase: {pool.meta_events_purchase} ← CRÍTICO!")
                print(f"    meta_pixel_id: {pool.meta_pixel_id}")
                
                if not pool.meta_events_purchase:
                    print(f"    ⚠️ PROBLEMA: meta_events_purchase = FALSE!")
            else:
                print(f"  ❌ PROBLEMA: Bot não está associado a nenhum pool!")
        
        print()
        print("=" * 80)
        
        # 3. Estatísticas
        print("\n📊 3. ESTATÍSTICAS:")
        print("-" * 80)
        
        total_paid = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= since
        ).count()
        
        with_delivery = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= since,
            Payment.delivery_token.isnot(None)
        ).count()
        
        purchase_sent = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= since,
            Payment.meta_purchase_sent == True
        ).count()
        
        purchase_sent_with_event_id = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= since,
            Payment.meta_purchase_sent == True,
            Payment.meta_event_id.isnot(None)
        ).count()
        
        print(f"Total pagos (24h): {total_paid}")
        print(f"Com delivery_token: {with_delivery} ({with_delivery/total_paid*100:.1f}%)")
        print(f"meta_purchase_sent = True: {purchase_sent} ({purchase_sent/total_paid*100:.1f}%)")
        print(f"meta_purchase_sent = True E meta_event_id: {purchase_sent_with_event_id} ({purchase_sent_with_event_id/total_paid*100:.1f}%)")
        
        print()
        print("=" * 80)
        print("✅ DIAGNÓSTICO CONCLUÍDO")
        print("=" * 80)

if __name__ == '__main__':
    main()

