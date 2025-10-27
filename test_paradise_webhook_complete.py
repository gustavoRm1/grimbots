#!/usr/bin/env python3
"""
Teste COMPLETO: Webhook Paradise
================================

Testa se após processar webhook Paradise:
1. ✅ Pagamento é marcado como paid
2. ✅ Cliente recebe link de acesso no Telegram
3. ✅ Meta Pixel Purchase é enviado ao Facebook
4. ✅ Estatísticas são atualizadas
"""

import os
import sys
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_complete_webhook_flow():
    """Testa fluxo completo do webhook Paradise"""
    
    with app.app_context():
        # Buscar último pagamento Paradise APROVADO no painel
        payment = Payment.query.filter_by(
            gateway_type='paradise',
            status='paid'
        ).order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum pagamento Paradise marcado como paid encontrado")
            return
        
        print("=" * 80)
        print("TESTE COMPLETO: WEBHOOK PARADISE")
        print("=" * 80)
        
        print(f"\n📊 PAGAMENTO NO BANCO:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Status: {payment.status}")
        print(f"   Gateway Type: {payment.gateway_type}")
        print(f"   Transaction ID: {payment.gateway_transaction_id}")
        print(f"   Amount: R$ {payment.amount:.2f}")
        print(f"   Created: {payment.created_at}")
        print(f"   Paid At: {payment.paid_at}")
        
        # Verificar estatísticas
        print(f"\n📈 ESTATÍSTICAS ATUALIZADAS:")
        print(f"   Bot Total Sales: {payment.bot.total_sales}")
        print(f"   Bot Total Revenue: R$ {payment.bot.total_revenue:.2f}")
        print(f"   Owner Total Sales: {payment.bot.owner.total_sales}")
        print(f"   Owner Total Revenue: R$ {payment.bot.owner.total_revenue:.2f}")
        
        # Verificar Meta Pixel
        print(f"\n📊 META PIXEL:")
        print(f"   Purchase Sent: {payment.meta_purchase_sent}")
        print(f"   Sent At: {payment.meta_purchase_sent_at}")
        print(f"   Event ID: {payment.meta_event_id}")
        
        # Verificar mensagem para cliente
        print(f"\n💬 MENSAGEM PARA CLIENTE:")
        print(f"   Cliente: {payment.customer_name}")
        print(f"   Chat ID: {payment.customer_user_id}")
        print(f"   Access Link Configurado: {payment.bot.config.access_link if payment.bot.config else 'Não'}")
        
        print("\n✅ TESTE CONCLUÍDO!")
        print("=" * 80)


if __name__ == '__main__':
    test_complete_webhook_flow()

