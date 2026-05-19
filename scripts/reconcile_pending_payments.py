#!/usr/bin/env python3
"""
Script de Reconciliação de Pagamentos Pendentes
================================================
Consulta o gateway para verificar o status real de todos os pagamentos pendentes.
Se o gateway confirmar que está pago, atualiza o status no banco e dispara a entrega.

Uso:
    python scripts/reconcile_pending_payments.py [--dry-run] [--limit 50] [--gateway syncpay]
"""

import os
import sys
import logging
from datetime import datetime

# Carregar .env
from dotenv import load_dotenv
load_dotenv()

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from internal_logic.core.extensions import db
from internal_logic.core.models import Payment, Gateway, Bot, get_brazil_time
from gateways import GatewayFactory
from internal_logic.services.payment_processor import process_payment_confirmation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def reconcile_pending_payments(dry_run=False, limit=50, gateway_filter=None):
    """
    Reconcilia pagamentos pendentes consultando o gateway real.
    
    Args:
        dry_run: Se True, apenas loga o que faria sem atualizar o banco
        limit: Número máximo de pagamentos para processar por execução
        gateway_filter: Filtrar por tipo de gateway (ex: 'syncpay', 'paradise')
    """
    with app.app_context():
        # Buscar pagamentos pendentes
        query = Payment.query.filter_by(status='pending')
        
        if gateway_filter:
            query = query.filter_by(gateway_type=gateway_filter)
        
        # Ordenar por mais recente primeiro
        pending = query.order_by(Payment.created_at.desc()).limit(limit).all()
        
        if not pending:
            logger.info("✅ Nenhum pagamento pendente encontrado.")
            return
        
        logger.info(f"🔍 Encontrados {len(pending)} pagamento(s) pendente(s) para reconciliação")
        
        # Agrupar por gateway_type para reusar instâncias
        gateways_cache = {}
        updated_count = 0
        failed_count = 0
        still_pending_count = 0
        
        for payment in pending:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"📋 Payment ID: {payment.id} | payment_id: {payment.payment_id}")
                logger.info(f"   Gateway: {payment.gateway_type} | Amount: R$ {payment.amount:.2f}")
                logger.info(f"   Created: {payment.created_at} | Customer: {payment.customer_name}")
                
                # Obter gateway real do dono do bot
                if not payment.bot:
                    logger.warning(f"⚠️ Payment {payment.id} sem bot associado. Pulando.")
                    failed_count += 1
                    continue
                
                user_id = payment.bot.user_id
                
                # Buscar gateway configurado do usuário
                gateway_config = Gateway.query.filter_by(
                    user_id=user_id,
                    gateway_type=payment.gateway_type,
                    is_active=True
                ).first()
                
                if not gateway_config:
                    logger.warning(f"⚠️ Gateway {payment.gateway_type} não configurado para user {user_id}. Pulando.")
                    failed_count += 1
                    continue
                
                # Criar instância do gateway com credenciais reais
                if payment.gateway_type not in gateways_cache:
                    creds = gateway_config.get_credentials()  # Descriptografa as credenciais
                    gateway_instance = GatewayFactory.create_gateway(
                        payment.gateway_type, creds, use_adapter=True
                    )
                    if not gateway_instance:
                        logger.error(f"❌ Falha ao criar gateway {payment.gateway_type}")
                        failed_count += 1
                        continue
                    gateways_cache[payment.gateway_type] = gateway_instance
                
                gateway_instance = gateways_cache[payment.gateway_type]
                
                # Consultar status real no gateway
                if not payment.gateway_transaction_id:
                    logger.warning(f"⚠️ Payment {payment.id} sem gateway_transaction_id. Tentando por payment_id...")
                    # Tentar consultar por payment_id (nosso UUID)
                    status_result = None
                else:
                    logger.info(f"   Consultando status no gateway: {payment.gateway_transaction_id}")
                    status_result = gateway_instance.get_payment_status(payment.gateway_transaction_id)
                
                if not status_result:
                    logger.warning(f"⚠️ Não foi possível consultar status no gateway para payment {payment.id}")
                    still_pending_count += 1
                    continue
                
                gateway_status = str(status_result.get('status', '')).lower()
                logger.info(f"   Status no gateway: {gateway_status}")
                
                # Se está pago no gateway, atualizar no banco
                if gateway_status in ['paid', 'approved', 'confirmed', 'completed']:
                    if dry_run:
                        logger.info(f"🔵 [DRY RUN] Atualizaria payment {payment.id} para 'paid'")
                        updated_count += 1
                        continue
                    
                    # Atualizar status
                    payment.status = 'paid'
                    payment.paid_at = get_brazil_time()
                    db.session.add(payment)
                    db.session.commit()
                    
                    logger.info(f"✅ Payment {payment.id} atualizado para PAID!")
                    
                    # Disparar entrega, stats, websocket
                    try:
                        process_payment_confirmation(payment, payment.gateway_type)
                        logger.info(f"✅ Entrega processada para payment {payment.id}")
                    except Exception as delivery_err:
                        logger.error(f"⚠️ Erro na entrega: {delivery_err}")
                    
                    updated_count += 1
                else:
                    logger.info(f"ℹ️ Payment {payment.id} ainda está '{gateway_status}' no gateway. Mantendo pending.")
                    still_pending_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Erro ao reconciliar payment {payment.id}: {e}", exc_info=True)
                db.session.rollback()
                failed_count += 1
        
        # Resumo
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 RESUMO DA RECONCILIAÇÃO:")
        logger.info(f"   Total processados: {len(pending)}")
        logger.info(f"   ✅ Atualizados para PAID: {updated_count}")
        logger.info(f"   ⏳ Ainda pendentes: {still_pending_count}")
        logger.info(f"   ❌ Falhas: {failed_count}")
        logger.info(f"{'='*60}")
        
        if dry_run and updated_count > 0:
            logger.info(f"\n⚠️ DRY RUN — Nenhum pagamento foi atualizado. Remova --dry-run para aplicar.")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Reconcilia pagamentos pendentes com o gateway')
    parser.add_argument('--dry-run', action='store_true', help='Apenas simula sem atualizar o banco')
    parser.add_argument('--limit', type=int, default=50, help='Limite de pagamentos por execução')
    parser.add_argument('--gateway', type=str, default=None, help='Filtrar por tipo de gateway')
    
    args = parser.parse_args()
    
    logger.info(f"🚀 Iniciando reconciliação de pagamentos pendentes...")
    logger.info(f"   Dry run: {args.dry_run}")
    logger.info(f"   Limit: {args.limit}")
    logger.info(f"   Gateway filter: {args.gateway or 'todos'}")
    
    reconcile_pending_payments(
        dry_run=args.dry_run,
        limit=args.limit,
        gateway_filter=args.gateway
    )
