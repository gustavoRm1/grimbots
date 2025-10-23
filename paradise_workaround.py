#!/usr/bin/env python3
"""
WORKAROUND TEMPORÁRIO - Paradise
===============================
Implementa workaround para o bug da API Paradise
"""

import sys
import os
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_factory import GatewayFactory
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def paradise_workaround():
    """Workaround temporário para o bug da API Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("WORKAROUND TEMPORÁRIO - PARADISE")
        print("=" * 80)
        
        # 1. Verificar pagamentos Paradise pendentes há mais de 1 hora
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        pending_payments = Payment.query.filter(
            Payment.gateway_type == 'paradise',
            Payment.status == 'pending',
            Payment.created_at <= cutoff_time
        ).all()
        
        print(f"\n📊 PAGAMENTOS PARADISE PENDENTES HÁ MAIS DE 1 HORA:")
        if pending_payments:
            for payment in pending_payments:
                print(f"   ⏳ {payment.payment_id} | Transaction: {payment.gateway_transaction_id} | Created: {payment.created_at}")
        else:
            print("   ❌ Nenhum pagamento pendente há mais de 1 hora")
        
        # 2. Verificar pagamentos Paradise pendentes há mais de 2 horas
        cutoff_time_2h = datetime.now() - timedelta(hours=2)
        
        old_pending_payments = Payment.query.filter(
            Payment.gateway_type == 'paradise',
            Payment.status == 'pending',
            Payment.created_at <= cutoff_time_2h
        ).all()
        
        print(f"\n📊 PAGAMENTOS PARADISE PENDENTES HÁ MAIS DE 2 HORAS:")
        if old_pending_payments:
            for payment in old_pending_payments:
                print(f"   ⏳ {payment.payment_id} | Transaction: {payment.gateway_transaction_id} | Created: {payment.created_at}")
        else:
            print("   ❌ Nenhum pagamento pendente há mais de 2 horas")
        
        # 3. WORKAROUND: Marcar pagamentos antigos como "verificar manualmente"
        if old_pending_payments:
            print(f"\n🔧 APLICANDO WORKAROUND:")
            
            for payment in old_pending_payments:
                # Atualizar status para "verificar_manual"
                payment.status = 'verificar_manual'
                payment.notes = f"Workaround Paradise - Bug API check_status.php - {datetime.now()}"
                
                print(f"   ✅ {payment.payment_id} marcado para verificação manual")
            
            db.session.commit()
            print(f"   💾 {len(old_pending_payments)} pagamentos atualizados")
        
        # 4. Verificar pagamentos Paradise aprovados recentemente
        recent_paid = Payment.query.filter(
            Payment.gateway_type == 'paradise',
            Payment.status == 'paid',
            Payment.paid_at >= datetime.now() - timedelta(hours=24)
        ).all()
        
        print(f"\n📊 PAGAMENTOS PARADISE APROVADOS NAS ÚLTIMAS 24H:")
        if recent_paid:
            for payment in recent_paid:
                print(f"   ✅ {payment.payment_id} | Transaction: {payment.gateway_transaction_id} | Paid: {payment.paid_at}")
        else:
            print("   ❌ Nenhum pagamento aprovado nas últimas 24h")
        
        # 5. Recomendações
        print(f"\n📋 RECOMENDAÇÕES:")
        print(f"   1. Contatar suporte Paradise sobre bug na API")
        print(f"   2. Verificar manualmente pagamentos marcados como 'verificar_manual'")
        print(f"   3. Considerar usar PushynPay temporariamente")
        print(f"   4. Monitorar logs para pagamentos aprovados via webhook")

if __name__ == '__main__':
    paradise_workaround()

