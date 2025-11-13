#!/usr/bin/env python3
"""
Script para verificar se pageview_event_id está sendo salvo no Payment
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def verificar_payment():
    """Verifica um payment específico"""
    from app import app, db
    from models import Payment
    
    with app.app_context():
        # Payment do log
        payment_id = 'BOT41_1763051101_816ff624'
        
        payment = Payment.query.filter_by(payment_id=payment_id).first()
        
        if not payment:
            print(f"❌ Payment {payment_id} não encontrado")
            return
        
        print(f"\n📊 Payment: {payment.payment_id}")
        print(f"   Status: {payment.status}")
        print(f"   Tracking Token: {payment.tracking_token}")
        print(f"   pageview_event_id: {payment.pageview_event_id or 'NÃO SALVO ❌'}")
        print(f"   fbclid: {payment.fbclid[:50] if payment.fbclid else 'None'}...")
        print(f"   Meta Purchase Sent: {payment.meta_purchase_sent}")
        print(f"   Meta Event ID: {payment.meta_event_id}")
        print(f"   Criado em: {payment.created_at}")
        
        # Verificar Redis
        if payment.tracking_token:
            from utils.tracking_service import TrackingServiceV4
            tracking_service = TrackingServiceV4()
            tracking_data = tracking_service.recover_tracking_data(payment.tracking_token)
            
            if tracking_data:
                print(f"\n📦 Redis (tracking:{payment.tracking_token}):")
                print(f"   pageview_event_id: {tracking_data.get('pageview_event_id', 'NÃO ENCONTRADO ❌')}")
                print(f"   fbp: {'✅' if tracking_data.get('fbp') else '❌'}")
                print(f"   fbc: {'✅' if tracking_data.get('fbc') else '❌'}")
                print(f"   fbclid: {'✅' if tracking_data.get('fbclid') else '❌'}")
            else:
                print(f"\n❌ Redis não tem dados para token {payment.tracking_token}")
        
        # Diagnóstico
        print(f"\n🔍 DIAGNÓSTICO:")
        if not payment.pageview_event_id:
            print(f"   ❌ Payment NÃO tem pageview_event_id salvo")
            print(f"   💡 Isso significa que o payment foi criado antes da correção")
            print(f"   💡 Ou o pageview_event_id não estava disponível quando o PIX foi gerado")
        else:
            print(f"   ✅ Payment TEM pageview_event_id: {payment.pageview_event_id}")
        
        if payment.tracking_token:
            if tracking_data and tracking_data.get('pageview_event_id'):
                print(f"   ✅ Redis TEM pageview_event_id: {tracking_data.get('pageview_event_id')}")
            else:
                print(f"   ❌ Redis NÃO tem pageview_event_id (pode ter expirado)")

if __name__ == '__main__':
    verificar_payment()

