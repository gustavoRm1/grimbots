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
    """Reenvia entregáveis para pagamentos paid de hoje"""
    with app.app_context():
        hoje = datetime.now().date()
        
        # Buscar todos os pagamentos PAID de hoje
        pagamentos = Payment.query.filter(
            Payment.status == 'paid',
            db.func.date(Payment.paid_at) == hoje if Payment.paid_at else db.func.date(Payment.created_at) == hoje
        ).all()
        
        if not pagamentos:
            print(f"❌ Nenhum pagamento PAID encontrado para hoje ({hoje})")
            return
        
        print(f"📊 Encontrados {len(pagamentos)} pagamento(s) PAID de hoje")
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

