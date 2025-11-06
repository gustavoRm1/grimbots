"""
🔧 ATUALIZAR VENDAS SYNCPAY ESPECÍFICAS

Este script atualiza vendas específicas do SyncPay que foram pagas
mas não foram atualizadas no sistema.

Vendas a atualizar:
1. R$ 14,90 - Ref: 9b36cc1edf44d398b898c3d414713d - ID: #3554805
2. R$ 33,80 - Ref: e7f04ccee0425ca7a01773eea2a4bf - ID: #3554763
3. R$ 33,80 - Ref: 0f57f18b674274be53ad32ff456c1f - ID: #3554430

Autor: QI 600 + QI 602
"""

from app import app, db
from models import Payment, Gateway, get_brazil_time
from gateway_factory import GatewayFactory
from datetime import timedelta
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ VENDAS CONFIRMADAS NO PAINEL SYNCPAY
VENDAS_CONFIRMADAS = [
    {
        'external_reference': '9b36cc1edf44d398b898c3d414713d',
        'syncpay_id': '3554805',
        'amount': 14.90,
        'paid_at': '2025-11-06 06:58:00'
    },
    {
        'external_reference': 'e7f04ccee0425ca7a01773eea2a4bf',
        'syncpay_id': '3554763',
        'amount': 33.80,
        'paid_at': '2025-11-06 06:58:00'
    },
    {
        'external_reference': '0f57f18b674274be53ad32ff456c1f',
        'syncpay_id': '3554430',
        'amount': 33.80,
        'paid_at': '2025-11-06 06:44:00'
    }
]

def update_syncpay_payment(payment: Payment, venda_info: dict) -> bool:
    """
    Atualiza um pagamento SyncPay específico
    
    Args:
        payment: Payment object
        venda_info: Dados da venda confirmada no painel SyncPay
    
    Returns:
        True se atualizado com sucesso, False caso contrário
    """
    try:
        logger.info(f"\n{'='*80}")
        logger.info(f"🔄 ATUALIZANDO: {payment.payment_id}")
        logger.info(f"   External Reference: {venda_info['external_reference']}")
        logger.info(f"   SyncPay ID: {venda_info['syncpay_id']}")
        logger.info(f"   Amount: R$ {venda_info['amount']:.2f}")
        logger.info(f"   Status atual: {payment.status}")
        
        # Verificar se já está pago
        if payment.status == 'paid':
            logger.warning(f"⚠️ Payment {payment.payment_id} já está marcado como paid")
            logger.warning(f"   Pulando atualização...")
            return False
        
        # Atualizar status
        payment.status = 'paid'
        
        # Atualizar gateway_transaction_id se não tiver
        if not payment.gateway_transaction_id:
            payment.gateway_transaction_id = venda_info['syncpay_id']
            logger.info(f"✅ Gateway Transaction ID atualizado: {venda_info['syncpay_id']}")
        
        # Atualizar paid_at se o campo existir
        if hasattr(payment, 'paid_at'):
            from datetime import datetime
            try:
                paid_at = datetime.strptime(venda_info['paid_at'], '%Y-%m-%d %H:%M:%S')
                payment.paid_at = paid_at
                logger.info(f"✅ Paid At atualizado: {paid_at}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao atualizar paid_at: {e}")
        
        # Commit
        db.session.commit()
        logger.info(f"✅ Status atualizado para 'paid' no banco de dados")
        
        # ✅ Enviar entregável
        logger.info(f"📦 Enviando entregável...")
        try:
            from bot_manager import BotManager
            bot_manager = BotManager()
            
            # Buscar bot
            from models import Bot
            bot = Bot.query.filter_by(id=payment.bot_id).first()
            if bot:
                # Verificar se bot está ativo
                if payment.bot_id in bot_manager.active_bots:
                    token = bot_manager.active_bots[payment.bot_id]['token']
                    chat_id = int(payment.customer_user_id) if payment.customer_user_id else None
                    
                    if chat_id:
                        try:
                            import telegram
                            bot_telegram = telegram.Bot(token=token)
                            
                            bot_config = bot_manager.active_bots[payment.bot_id].get('config', {})
                            delivery_message = bot_config.get('delivery_message', '✅ Pagamento confirmado! Seu acesso foi liberado.')
                            
                            bot_telegram.send_message(
                                chat_id=chat_id,
                                text=delivery_message,
                                parse_mode='HTML'
                            )
                            
                            logger.info(f"✅ Entregável enviado para chat {chat_id}")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao enviar entregável: {e}")
                    else:
                        logger.warning(f"⚠️ customer_user_id não encontrado: {payment.customer_user_id}")
                else:
                    logger.warning(f"⚠️ Bot {payment.bot_id} não está ativo")
            else:
                logger.warning(f"⚠️ Bot {payment.bot_id} não encontrado")
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar entregável: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # ✅ Enviar Meta Pixel Purchase Event
        logger.info(f"📊 Enviando Meta Pixel Purchase Event...")
        try:
            from app import send_meta_pixel_purchase_event
            from bot_manager import BotManager
            
            bot_manager = BotManager()
            send_meta_pixel_purchase_event(payment, bot_manager)
            logger.info(f"✅ Meta Pixel Purchase Event enviado")
        except Exception as e:
            logger.error(f"❌ Erro ao enviar Meta Pixel: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar {payment.payment_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.session.rollback()
        return False

def main():
    """Função principal"""
    with app.app_context():
        print("\n" + "=" * 80)
        print("🔧 ATUALIZAR VENDAS SYNCPAY ESPECÍFICAS")
        print("=" * 80)
        
        print(f"\n📋 Vendas a atualizar: {len(VENDAS_CONFIRMADAS)}")
        
        total_found = 0
        total_updated = 0
        total_not_found = 0
        total_errors = 0
        
        # Processar cada venda
        for i, venda_info in enumerate(VENDAS_CONFIRMADAS, 1):
            print(f"\n{'='*80}")
            print(f"🔍 Processando venda {i}/{len(VENDAS_CONFIRMADAS)}")
            print(f"{'='*80}")
            print(f"External Reference: {venda_info['external_reference']}")
            print(f"SyncPay ID: {venda_info['syncpay_id']}")
            print(f"Amount: R$ {venda_info['amount']:.2f}")
            
            # Buscar payment pelo external_reference
            # Tentar busca exata primeiro
            payment = Payment.query.filter_by(payment_id=venda_info['external_reference']).first()
            
            if not payment:
                # Tentar busca parcial (external_reference pode ser parte do payment_id)
                payments = Payment.query.filter(
                    Payment.payment_id.like(f"%{venda_info['external_reference']}%")
                ).all()
                
                if payments:
                    # Priorizar payment do SyncPay
                    syncpay_payments = [p for p in payments if p.gateway_type == 'syncpay']
                    if syncpay_payments:
                        payment = syncpay_payments[0]
                        logger.info(f"✅ Payment encontrado por busca parcial (SyncPay): {payment.payment_id}")
                    else:
                        payment = payments[0]
                        logger.info(f"⚠️ Payment encontrado por busca parcial (outro gateway): {payment.payment_id}")
            
            if not payment:
                # Tentar buscar por amount e gateway_type (última tentativa)
                logger.warning(f"⚠️ Payment não encontrado por external_reference, tentando por amount...")
                payments = Payment.query.filter(
                    Payment.gateway_type == 'syncpay',
                    Payment.status == 'pending',
                    Payment.amount == venda_info['amount']
                ).order_by(Payment.created_at.desc()).limit(5).all()
                
                if payments:
                    logger.warning(f"⚠️ Encontrados {len(payments)} pagamentos pending com mesmo amount")
                    logger.warning(f"   Usando o mais recente...")
                    payment = payments[0]
                else:
                    logger.error(f"❌ Payment NÃO encontrado para external_reference: {venda_info['external_reference']}")
                    total_not_found += 1
                    continue
            
            total_found += 1
            logger.info(f"✅ Payment encontrado: {payment.payment_id}")
            logger.info(f"   Bot ID: {payment.bot_id}")
            logger.info(f"   Amount: R$ {payment.amount:.2f}")
            logger.info(f"   Status: {payment.status}")
            logger.info(f"   Gateway Transaction ID: {payment.gateway_transaction_id or 'N/A'}")
            
            # Atualizar payment
            if update_syncpay_payment(payment, venda_info):
                total_updated += 1
            else:
                total_errors += 1
        
        # Resumo final
        print("\n" + "=" * 80)
        print("📊 RESUMO FINAL")
        print("=" * 80)
        print(f"✅ Total encontrado: {total_found}/{len(VENDAS_CONFIRMADAS)}")
        print(f"✅ Total atualizado: {total_updated}")
        print(f"❌ Total não encontrado: {total_not_found}")
        print(f"❌ Total com erro: {total_errors}")
        print("=" * 80)
        
        if total_updated > 0:
            print(f"\n✅ {total_updated} venda(s) foram atualizadas com sucesso!")
            print(f"   - Status atualizado para 'paid'")
            print(f"   - Entregáveis enviados")
            print(f"   - Meta Pixel Purchase Events enviados")
        else:
            print(f"\n⚠️ Nenhuma venda foi atualizada.")
            if total_not_found > 0:
                print(f"   {total_not_found} venda(s) não foram encontradas no banco de dados.")
                print(f"   Verifique se os external_reference estão corretos.")

if __name__ == '__main__':
    main()

