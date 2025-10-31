#!/usr/bin/env python3
"""
🔄 REENVIAR Meta Pixel Purchase Events
Reenvia eventos Purchase que não foram enviados para Meta
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, send_meta_pixel_purchase_event
from models import Payment, PoolBot

with app.app_context():
    print("=" * 80)
    print("🔄 REENVIAR Meta Pixel Purchase Events")
    print("=" * 80)
    
    # Buscar pagamentos PAID de hoje (últimas 24h) sem Meta Purchase
    desde = datetime.now() - timedelta(hours=24)
    
    pagamentos = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= desde,
        Payment.meta_purchase_sent == False,
        Payment.gateway_type == 'pushynpay'
    ).order_by(Payment.id.desc()).all()
    
    if not pagamentos:
        print("✅ Nenhum pagamento para reenviar Meta Purchase")
        exit(0)
    
    print(f"\n📊 Encontrados {len(pagamentos)} pagamento(s) PAID sem Meta Purchase")
    print("=" * 80)
    
    enviados = 0
    erros = 0
    
    for payment in pagamentos:
        try:
            print(f"\n🔄 Processando Payment ID: {payment.id}")
            print(f"   Cliente: {payment.customer_name}")
            print(f"   Produto: {payment.product_name}")
            print(f"   Valor: R$ {payment.amount:.2f}")
            print(f"   Bot: {payment.bot.name if payment.bot else 'N/A'} (ID: {payment.bot_id})")
            
            # Verificar pool
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
            if not pool_bot:
                print(f"   ❌ Bot não está em nenhum pool - PULANDO")
                erros += 1
                continue
            
            pool = pool_bot.pool
            print(f"   Pool: {pool.name} (ID: {pool.id})")
            
            if not pool.meta_tracking_enabled:
                print(f"   ⚠️ Tracking desabilitado no pool - PULANDO")
                erros += 1
                continue
            
            if not pool.meta_events_purchase:
                print(f"   ⚠️ Evento Purchase desabilitado no pool - PULANDO")
                erros += 1
                continue
            
            if not pool.meta_pixel_id or not pool.meta_access_token:
                print(f"   ⚠️ Pixel ID ou Access Token não configurado - PULANDO")
                erros += 1
                continue
            
            # Enviar Meta Purchase
            print(f"   📤 Enviando Meta Purchase...")
            send_meta_pixel_purchase_event(payment)
            
            # Verificar se foi marcado como enviado
            db.session.refresh(payment)
            if payment.meta_purchase_sent:
                print(f"   ✅ Meta Purchase enviado com sucesso!")
                enviados += 1
            else:
                print(f"   ❌ Não foi marcado como enviado (verificar logs)")
                erros += 1
            
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            erros += 1
    
    print("\n" + "=" * 80)
    print(f"📊 RESUMO:")
    print(f"   ✅ Enviados: {enviados}")
    print(f"   ❌ Erros: {erros}")
    print(f"   📦 Total processado: {len(pagamentos)}")
    
    if enviados > 0:
        print(f"\n✅ {enviados} evento(s) Purchase reenviado(s) com sucesso!")

