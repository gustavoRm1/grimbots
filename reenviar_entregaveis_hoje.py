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
    """Reenvia entregáveis para pagamentos paid das últimas 7 dias"""
    with app.app_context():
        agora = datetime.now()
        # Buscar pagamentos dos últimos 7 dias para garantir que pega tudo
        desde = agora - timedelta(days=7)
        
        # Buscar TODOS os pagamentos PAID dos últimos 7 dias (sem filtro de paid_at)
        pagamentos = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= desde
        ).order_by(Payment.id.desc()).all()
        
        if not pagamentos:
            print(f"❌ Nenhum pagamento PAID encontrado nos últimos 7 dias (desde {desde.strftime('%Y-%m-%d')})")
            return
        
        print(f"📊 Encontrados {len(pagamentos)} pagamento(s) PAID nos últimos 7 dias")
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
                
                # Verificar se tem customer_user_id válido
                if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
                    print(f"   ❌ Cliente sem customer_user_id válido ({payment.customer_user_id}) - PULANDO")
                    erros += 1
                    continue
                
                # Verificar se tem access_link configurado
                has_link = payment.bot.config and payment.bot.config.access_link
                link_status = "✅ COM link" if has_link else "⚠️ SEM link (mensagem genérica)"
                print(f"   {link_status}")
                
                # Enviar entregável e verificar retorno
                resultado = send_payment_delivery(payment, bot_manager)
                if resultado:
                    print(f"   ✅ Entregável reenviado com sucesso!")
                    enviados += 1
                else:
                    print(f"   ❌ ERRO: Não foi possível enviar entregável (ver logs acima)")
                    erros += 1
                
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

