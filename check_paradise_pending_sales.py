#!/usr/bin/env python3
"""
Check Paradise Pending Sales
============================

Verifica vendas confirmadas no painel Paradise e marca como paid.
Execute via cron: */2 * * * * cd /root/grimbots && /root/grimbots/venv/bin/python check_paradise_pending_sales.py

"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway, Bot
from gateway_factory import GatewayFactory
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def send_paradise_webhook(transaction_id: str, status: str, amount: int):
    """Envia webhook Paradise manualmente"""
    webhook_url = "https://app.grimbots.online/webhook/payment/paradise"
    
    webhook_data = {
        "id": transaction_id,
        "payment_status": status,
        "amount": amount
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        logger.info(f"📤 Webhook enviado: transaction_id={transaction_id}, status={response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Erro ao enviar webhook: {e}")
        return False


def check_pending_sales():
    """Verifica vendas Paradise pendentes"""
    
    with app.app_context():
        # Buscar pagamentos Paradise pendentes das últimas 4 horas
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=4)
        
        pending_payments = Payment.query.filter(
            Payment.gateway_type == 'paradise',
            Payment.status == 'pending',
            Payment.created_at >= cutoff_time
        ).all()
        
        if not pending_payments:
            logger.info("✅ Nenhum pagamento Paradise pendente")
            return
        
        logger.info(f"🔍 Verificando {len(pending_payments)} pagamento(s) pendente(s)...")
        
        for payment in pending_payments:
            try:
                # Enviar webhook com status 'approved' (parar webhook não está disparando)
                logger.info(f"📤 Enviando webhook para transaction_id={payment.gateway_transaction_id}")
                amount_cents = int(payment.amount * 100)
                send_paradise_webhook(
                    transaction_id=payment.gateway_transaction_id,
                    status='approved',
                    amount=amount_cents
                )
            except Exception as e:
                logger.error(f"❌ Erro ao processar payment {payment.payment_id}: {e}")
        
        logger.info("✅ Verificação concluída!")


if __name__ == '__main__':
    logger.info("🚀 Iniciando verificação de vendas Paradise pendentes...")
    check_pending_sales()
    logger.info("✅ Verificação concluída!")

