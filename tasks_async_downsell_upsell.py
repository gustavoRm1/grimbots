

# ============================================================================
# ✅ MIGRAÇÃO RQ: Jobs para Downsells e Upsells (APScheduler removido)
# ============================================================================

def send_downsell_job(bot_id: int, payment_id: str, chat_id: int, downsell: dict, 
                       index: int, original_price: float, original_button_index: int):
    """
    Job RQ para enviar downsell agendado
    Executado pelos workers RQ da fila 'tasks' ou 'marathon'
    """
    from app import app, db
    from models import Payment
    
    with app.app_context():
        try:
            # ✅ ANTI-DUPLICAÇÃO: Verificar se pagamento ainda está pendente
            payment = Payment.query.filter_by(payment_id=payment_id).first()
            
            if not payment:
                logger.warning(f"⚠️ [DOWNSELL JOB] Payment {payment_id} não encontrado - ignorando")
                return False
            
            if payment.status != 'pending':
                logger.info(f"ℹ️ [DOWNSELL JOB] Payment {payment_id} status='{payment.status}' - downsell cancelado")
                return False
            
            # ✅ BotManager disponível via import
            from app import bot_manager
            
            # Executar envio do downsell
            result = bot_manager._send_downsell(
                bot_id=bot_id,
                payment_id=payment_id,
                chat_id=chat_id,
                downsell=downsell,
                index=index,
                original_price=original_price,
                original_button_index=original_button_index
            )
            
            logger.info(f"✅ [DOWNSELL JOB] Downsell {index+1} enviado para payment {payment_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ [DOWNSELL JOB] Erro ao enviar downsell: {e}", exc_info=True)
            return False


def send_upsell_job(bot_id: int, payment_id: str, chat_id: int, upsell: dict,
                     index: int, original_price: float, original_button_index: int):
    """
    Job RQ para enviar upsell agendado
    Executado pelos workers RQ da fila 'tasks' ou 'marathon'
    """
    from app import app, db
    from models import Payment
    
    with app.app_context():
        try:
            # ✅ ANTI-DUPLICAÇÃO: Verificar se pagamento está pago
            payment = Payment.query.filter_by(payment_id=payment_id).first()
            
            if not payment:
                logger.warning(f"⚠️ [UPSELL JOB] Payment {payment_id} não encontrado - ignorando")
                return False
            
            if payment.status != 'paid':
                logger.info(f"ℹ️ [UPSELL JOB] Payment {payment_id} status='{payment.status}' - upsell cancelado")
                return False
            
            # ✅ BotManager disponível via import
            from app import bot_manager
            
            # Executar envio do upsell
            result = bot_manager._send_upsell(
                bot_id=bot_id,
                payment_id=payment_id,
                chat_id=chat_id,
                upsell=upsell,
                index=index,
                original_price=original_price,
                original_button_index=original_button_index
            )
            
            logger.info(f"✅ [UPSELL JOB] Upsell {index+1} enviado para payment {payment_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ [UPSELL JOB] Erro ao enviar upsell: {e}", exc_info=True)
            return False
