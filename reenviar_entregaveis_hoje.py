#!/usr/bin/env python3
"""
Script para reenviar entregáveis para pagamentos PAID de hoje que não receberam
"""
import sys
import os
from datetime import datetime, timedelta

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, bot_manager, send_payment_delivery
from models import Payment, db

def reenviar_entregaveis_hoje():
    """Reenvia entregáveis para pagamentos paid das últimas 48 horas"""
    with app.app_context():
        agora = datetime.now()
        # Buscar pagamentos das últimas 48 horas para pegar vendas de ontem/today
        desde = agora - timedelta(hours=48)
        
        # Buscar todos os pagamentos PAID das últimas 48 horas
        pagamentos = Payment.query.filter(
            Payment.status == 'paid'
        ).filter(
            (Payment.paid_at >= desde) if Payment.paid_at else (Payment.created_at >= desde)
        ).order_by(Payment.id.desc()).all()
        
        if not pagamentos:
            print(f"❌ Nenhum pagamento PAID encontrado nas últimas 48 horas (desde {desde.strftime('%Y-%m-%d %H:%M')})")
            return
        
        print(f"📊 Encontrados {len(pagamentos)} pagamento(s) PAID nas últimas 48 horas")
        print("=" * 60)
        
        enviados = 0
        erros = 0
        
        for payment in pagamentos:
            try:
                print(f"\n🔄 Processando Payment ID: {payment.id}")
                print(f"   Cliente: {payment.customer_name} ({payment.customer_user_id})")
                print(f"   Produto: {payment.product_name}")
                print(f"   Valor: R$ {payment.amount:.2f}")
                print(f"   Bot: {payment.bot.name if payment.bot else 'N/A'} (ID: {payment.bot_id})")
                
                # Verificar se bot tem token
                if not payment.bot or not payment.bot.token:
                    print(f"   ❌ Bot {payment.bot_id} não tem token - PULANDO")
                    erros += 1
                    continue
                
                # Verificar se tem access_link configurado
                has_link = payment.bot.config and payment.bot.config.access_link
                link_status = "✅ COM link" if has_link else "⚠️ SEM link (mensagem genérica)"
                print(f"   {link_status}")
                
                # Enviar entregável
                send_payment_delivery(payment, bot_manager)
                
                print(f"   ✅ Entregável reenviado!")
                enviados += 1
                
            except Exception as e:
                print(f"   ❌ ERRO: {e}")
                erros += 1
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 60)
        print(f"📊 RESUMO:")
        print(f"   ✅ Enviados: {enviados}")
        print(f"   ❌ Erros: {erros}")
        print(f"   📦 Total processado: {len(pagamentos)}")
        
        if enviados > 0:
            print(f"\n✅ {enviados} entregável(s) reenviado(s) com sucesso!")

if __name__ == '__main__':
    print("🚀 Reenviando entregáveis para vendas de hoje...")
    print("=" * 60)
    reenviar_entregaveis_hoje()

