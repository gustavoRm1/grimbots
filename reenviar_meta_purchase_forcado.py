#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 REENVIAR Meta Pixel Purchase Events (FORÇADO)
Reenvia eventos Purchase mesmo se já estiverem marcados como enviados
Útil para corrigir vendas que foram marcadas como enviadas mas não chegaram na Meta
"""

import os
import sys
from datetime import datetime, timedelta

venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
if os.path.exists(venv_path):
    activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, send_meta_pixel_purchase_event
from models import Payment, PoolBot

with app.app_context():
    print("=" * 80)
    print("🔄 REENVIAR Meta Pixel Purchase Events (FORÇADO)")
    print("=" * 80)
    print("\n⚠️  Este script reenvia eventos mesmo se já estiverem marcados como enviados")
    print("    Use apenas para corrigir vendas que não chegaram na Meta\n")
    
    # Buscar pagamentos PAID de hoje que estão marcados como enviados
    hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    pagamentos = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= hoje_inicio,
        Payment.meta_purchase_sent == True  # ✅ BUSCAR OS QUE ESTÃO MARCADOS COMO ENVIADOS
    ).order_by(Payment.paid_at.desc()).all()
    
    if not pagamentos:
        print("✅ Nenhum pagamento marcado como enviado encontrado para reenvio")
        exit(0)
    
    print(f"\n📊 Encontrados {len(pagamentos)} pagamento(s) marcado(s) como enviado(s)")
    print("=" * 80)
    
    enviados = 0
    erros = 0
    pulados = 0
    
    for payment in pagamentos:
        try:
            print(f"\n🔄 Processando Payment ID: {payment.id} ({payment.payment_id})")
            print(f"   Valor: R$ {payment.amount:.2f}")
            print(f"   Pago em: {payment.paid_at.strftime('%Y-%m-%d %H:%M:%S') if payment.paid_at else 'N/A'}")
            print(f"   Bot: {payment.bot.name if payment.bot else 'N/A'} (ID: {payment.bot_id})")
            
            # Verificar pool
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
            if not pool_bot:
                print(f"   ❌ Bot não está em nenhum pool - PULANDO")
                pulados += 1
                continue
            
            pool = pool_bot.pool
            print(f"   Pool: {pool.name} (ID: {pool.id})")
            
            if not pool.meta_tracking_enabled:
                print(f"   ⚠️ Tracking desabilitado no pool - PULANDO")
                pulados += 1
                continue
            
            if not pool.meta_events_purchase:
                print(f"   ⚠️ Evento Purchase desabilitado no pool - PULANDO")
                pulados += 1
                continue
            
            if not pool.meta_pixel_id or not pool.meta_access_token:
                print(f"   ⚠️ Pixel ID ou Access Token não configurado - PULANDO")
                pulados += 1
                continue
            
            # ✅ RESETAR FLAG antes de reenviar (para forçar reenvio)
            payment.meta_purchase_sent = False
            payment.meta_purchase_sent_at = None
            payment.meta_event_id = None
            db.session.commit()
            
            # Enviar Meta Purchase
            print(f"   📤 Reenviando Meta Purchase...")
            send_meta_pixel_purchase_event(payment)
            
            # Verificar se foi marcado como enviado
            db.session.refresh(payment)
            if payment.meta_purchase_sent:
                print(f"   ✅ Meta Purchase reenviado com sucesso!")
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
    print(f"   ✅ Reenviados: {enviados}")
    print(f"   ❌ Erros: {erros}")
    print(f"   ⏭️  Pulados: {pulados}")
    print(f"   📦 Total processado: {len(pagamentos)}")
    
    if enviados > 0:
        print(f"\n✅ {enviados} evento(s) Purchase reenviado(s) com sucesso!")
        print("\n💡 IMPORTANTE: Verifique nos logs se os eventos foram realmente enviados para a Meta")
        print("   Execute: journalctl -u grimbots -n 200 --no-pager | grep -i 'Purchase ENVIADO\|Purchase FALHOU'")
    
    print("=" * 80)

