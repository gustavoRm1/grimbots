#!/usr/bin/env python3
"""
Paradise Payment Checker - Polling Automático
==============================================

O Paradise não envia webhooks automáticos. Este script verifica
periodicamente o status dos pagamentos pendentes e atualiza o sistema.

Executar via cron a cada 1 minuto:
* * * * * cd /root/grimbots && /root/grimbots/venv/bin/python paradise_payment_checker.py >> /root/grimbots/logs/paradise_checker.log 2>&1
"""

import os
import sys
from datetime import datetime, timedelta

# Adicionar path do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Bot
from gateway_factory import GatewayFactory
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_paradise_payments():
    """
    Verifica todos os pagamentos Paradise pendentes e atualiza status
    """
    with app.app_context():
        try:
            # Buscar pagamentos Paradise pendentes dos últimos 2 horas
            # Paradise demora para processar transações na API de consulta
            cutoff_time = datetime.now() - timedelta(hours=2)
            
            pending_payments = Payment.query.filter(
                Payment.gateway_type == 'paradise',
                Payment.status == 'pending',
                Payment.created_at >= cutoff_time
            ).all()
            
            if not pending_payments:
                logger.info("✅ Nenhum pagamento Paradise pendente para verificar")
                return
            
            logger.info(f"🔍 Verificando {len(pending_payments)} pagamento(s) Paradise pendente(s)...")
            
            updated_count = 0
            
            for payment in pending_payments:
                try:
                    # Buscar credenciais do gateway
                    from models import Gateway
                    
                    gateway_config = Gateway.query.filter_by(
                        user_id=payment.bot.user_id,
                        gateway_type='paradise'
                    ).first()
                    
                    if not gateway_config:
                        logger.warning(f"⚠️ Gateway Paradise não configurado para bot {payment.bot_id}")
                        continue
                    
                    # Criar instância do gateway
                    gateway = GatewayFactory.create_gateway(
                        gateway_type='paradise',
                        credentials=gateway_config.credentials
                    )
                    
                    if not gateway:
                        logger.error(f"❌ Erro ao criar gateway Paradise para payment {payment.payment_id}")
                        continue
                    
                    # Consultar status na API com retry
                    logger.info(f"🔍 Consultando status: {payment.payment_id} | Transaction ID: {payment.gateway_transaction_id}")
                    
                    # Paradise demora para processar - tentar até 3 vezes com delay
                    api_status = None
                    for attempt in range(3):
                                   api_status = gateway.get_payment_status(
                                       payment.gateway_transaction_id,
                                       payment.gateway_transaction_hash  # ✅ Passar hash para Paradise
                                   )
                        
                        if api_status and api_status.get('status') != 'pending':
                            logger.info(f"✅ Status encontrado na tentativa {attempt + 1}")
                            break
                        
                        if attempt < 2:  # Não é a última tentativa
                            logger.info(f"⏳ Tentativa {attempt + 1} - aguardando 30 segundos...")
                            import time
                            time.sleep(30)
                    
                    if api_status and api_status.get('status') == 'paid':
                        logger.info(f"💰 Pagamento APROVADO: {payment.payment_id}")
                        
                        # Atualizar status
                        payment.status = 'paid'
                        payment.paid_at = datetime.now()
                        
                        # Atualizar estatísticas
                        payment.bot.total_sales += 1
                        payment.bot.total_revenue += payment.amount
                        payment.bot.owner.total_sales += 1
                        payment.bot.owner.total_revenue += payment.amount
                        
                        # Atualizar estatísticas do gateway
                        if gateway_config:
                            gateway_config.total_transactions += 1
                            gateway_config.successful_transactions += 1
                        
                        # DISPARAR META PIXEL PURCHASE
                        try:
                            from app import send_meta_pixel_purchase_event
                            send_meta_pixel_purchase_event(payment)
                            logger.info(f"📊 Meta Pixel Purchase disparado para {payment.payment_id}")
                        except Exception as e:
                            logger.error(f"❌ Erro ao disparar Meta Pixel: {e}")
                        
                        # NOTIFICAR CLIENTE VIA TELEGRAM
                        try:
                            from bot_manager import BotManager
                            bot_manager = BotManager()
                            
                            # Buscar token do bot
                            bot = Bot.query.get(payment.bot_id)
                            if bot and bot.token:
                                # Enviar mensagem de sucesso
                                success_message = f"""✅ <b>PAGAMENTO CONFIRMADO!</b>

Seu pagamento de <b>R$ {payment.amount:.2f}</b> foi aprovado!

🎉 Seu acesso foi liberado com sucesso!"""
                                
                                bot_manager.send_telegram_message(
                                    token=bot.token,
                                    chat_id=str(payment.customer_user_id),
                                    message=success_message
                                )
                                logger.info(f"✅ Cliente notificado: {payment.customer_user_id}")
                        except Exception as e:
                            logger.error(f"❌ Erro ao notificar cliente: {e}")
                        
                        db.session.commit()
                        updated_count += 1
                        
                    else:
                        logger.info(f"⏳ Pagamento ainda pendente: {payment.payment_id}")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao processar payment {payment.payment_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            if updated_count > 0:
                logger.info(f"✅ {updated_count} pagamento(s) atualizado(s) com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar pagamentos Paradise: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    logger.info("🚀 Iniciando verificação de pagamentos Paradise...")
    check_paradise_payments()
    logger.info("✅ Verificação concluída!")

