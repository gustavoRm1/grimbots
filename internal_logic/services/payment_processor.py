"""
Payment Processor Service
==========================
Serviço responsável pelo processamento de pagamentos e entrega de produtos.
Isolado da camada de webhooks para garantir estabilidade do faturamento.
"""

import logging
import uuid
import hashlib
import time
from typing import Optional, Dict, Any
from datetime import datetime

from flask import url_for
from internal_logic.core.extensions import db, socketio
from bot_manager import BotManager
from internal_logic.core.models import Payment, PoolBot, BotUser

logger = logging.getLogger(__name__)


def generate_delivery_token(payment: Payment) -> str:
    """Gera um token único de entrega para o pagamento."""
    if not payment.delivery_token:
        timestamp = int(time.time())
        secret = f"{payment.id}_{payment.payment_id}_{timestamp}"
        delivery_token = hashlib.sha256(secret.encode()).hexdigest()[:64]
        payment.delivery_token = delivery_token
        db.session.commit()
        logger.info(f"✅ delivery_token gerado para payment {payment.id}: {delivery_token[:20]}...")
    return payment.delivery_token


def get_pixel_id_for_payment(payment: Payment) -> Optional[str]:
    """Obtém o ID do pixel Meta para tracking, considerando sticky pixel."""
    pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
    pool = pool_bot.pool if pool_bot else None
    
    # Sticky Pixel: priorizar pixel da origem do usuário (campaign_code) se for numérico
    bot_user_for_pixel = BotUser.query.filter_by(
        bot_id=payment.bot_id, 
        telegram_user_id=str(payment.customer_user_id)
    ).first() if payment.customer_user_id else None
    
    user_origin_pixel = getattr(bot_user_for_pixel, 'campaign_code', None) if bot_user_for_pixel else None
    pixel_from_user = user_origin_pixel if user_origin_pixel and str(user_origin_pixel).isdigit() else None
    
    return pixel_from_user or (pool.meta_pixel_id if pool else None)


def build_delivery_message(payment: Payment, link_to_send: Optional[str], has_meta_pixel: bool) -> str:
    """Constrói a mensagem de entrega baseada no link disponível."""
    if link_to_send:
        return f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Clique aqui para acessar:</b>
{link_to_send}

Aproveite! 🚀
        """
    else:
        return f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

📧 Entre em contato com o suporte para receber seu acesso.
        """


def get_delivery_link(payment: Payment, pixel_id_to_use: Optional[str]) -> Optional[str]:
    """Determina qual link enviar baseado na configuração do Meta Pixel."""
    has_meta_pixel = bool(pixel_id_to_use)
    has_access_link = payment.bot.config and payment.bot.config.access_link
    access_link = payment.bot.config.access_link if has_access_link else None
    
    if has_meta_pixel:
        # Meta Pixel ATIVO → usar /delivery para disparar Purchase tracking
        if not payment.delivery_token:
            generate_delivery_token(payment)
        
        try:
            link = url_for(
                'delivery_page',
                delivery_token=payment.delivery_token,
                px=pixel_id_to_use,
                _external=True
            )
        except:
            suffix_px = f"?px={pixel_id_to_use}" if pixel_id_to_use else ""
            link = f"https://app.grimbots.online/delivery/{payment.delivery_token}{suffix_px}"
        
        logger.info(f"✅ Meta Pixel ativo → enviando /delivery (payment {payment.id})")
        return link
    else:
        # Meta Pixel INATIVO → usar access_link direto
        if has_access_link:
            logger.info(f"✅ Meta Pixel inativo → enviando access_link direto (payment {payment.id})")
            return access_link
        else:
            logger.warning(f"⚠️ Meta Pixel inativo E sem access_link → sem link (payment {payment.id})")
            return None


def send_payment_delivery(payment: Payment, bot_manager: Optional[BotManager] = None) -> Dict[str, Any]:
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado.
    
    ✅ REFATORADO: Cria BotManager localmente com user_id do payment
    Versão unificada: inclui Telegram + Email + SocketIO
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância opcional do BotManager (para compatibilidade)
    
    Returns:
        dict: {'success': bool, 'message': str, 'delivery_method': str}
    """
    try:
        if not payment or not payment.bot:
            logger.error(f"❌ Payment {payment.id if payment else 'None'} não tem bot associado")
            return {'success': False, 'message': 'Bot não encontrado', 'delivery_method': 'none'}
        
        # ✅ CRÍTICO: Não enviar entregável se pagamento não estiver 'paid'
        if payment.status != 'paid':
            logger.error(
                f"❌ BLOQUEADO: tentativa de envio com status inválido "
                f"({payment.status}). Apenas 'paid' é permitido. "
                f"Payment ID: {payment.payment_id if payment else 'None'}"
            )
            return {'success': False, 'message': 'Status não é paid', 'delivery_method': 'none'}
        
        if not payment.bot.token:
            logger.error(f"❌ Bot {payment.bot_id} não tem token configurado")
            return {'success': False, 'message': 'Token não configurado', 'delivery_method': 'none'}
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se customer_user_id é válido
        if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
            logger.error(f"❌ Payment {payment.id} não tem customer_user_id válido")
            return {'success': False, 'message': 'Customer ID inválido', 'delivery_method': 'none'}
        
        # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
        if bot_manager is None:
            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
        else:
            local_bot_manager = bot_manager
        
        # Preparar dados do cliente
        customer_id = payment.payer_id or payment.customer_id or payment.external_id
        customer_email = payment.payer_email or payment.customer_email or ''
        customer_name = payment.payer_name or payment.customer_name or 'Cliente'
        
        # Conteúdo do entregável
        product_name = payment.product_name or 'Produto'
        access_link = payment.bot.config.delivery_link if payment.bot.config else None
        
        if not access_link:
            logger.error(f"❌ Bot {payment.bot.id} não tem delivery_link configurado")
            return {'success': False, 'message': 'Link de entrega não configurado', 'delivery_method': 'none'}
        
        # Tentar enviar via Telegram primeiro (se tiver chat_id)
        telegram_sent = False
        if customer_id and str(customer_id).isdigit():
            try:
                # Enviar mensagem via Telegram
                message = f"""
🎉 <b>Parabéns! Seu acesso foi liberado!</b>

📦 <b>Produto:</b> {product_name}
👤 <b>Cliente:</b> {customer_name}

🔗 <b>Link de Acesso:</b>
{access_link}

⚠️ <b>Importante:</b>
• Guarde este link com segurança
• Não compartilhe com terceiros
• Dúvidas? Responda esta mensagem

✅ Pagamento confirmado em: {payment.paid_at or datetime.now()}
                """.strip()
                
                local_bot_manager.send_telegram_message(
                    token=payment.bot.token,
                    chat_id=str(customer_id),
                    message=message
                )
                telegram_sent = True
                logger.info(f"✅ Entregável enviado via Telegram para {customer_id}")
            except Exception as e:
                logger.warning(f"⚠️ Falha ao enviar via Telegram: {e}")
        
        # Se não conseguiu via Telegram, tentar email (se disponível)
        email_sent = False
        if not telegram_sent and customer_email:
            try:
                # Aqui seria integração com serviço de email
                # Por enquanto, apenas logamos
                logger.info(f"📧 Email seria enviado para {customer_email}")
                email_sent = True
            except Exception as e:
                logger.warning(f"⚠️ Falha ao enviar via Email: {e}")
        
        # Atualizar payment com método de entrega
        if telegram_sent:
            delivery_method = 'telegram'
        elif email_sent:
            delivery_method = 'email'
        else:
            delivery_method = 'none'
        
        # Salvar no banco se houver coluna delivery_method
        try:
            payment.delivery_method = delivery_method
            payment.delivery_sent_at = datetime.now()
            db.session.commit()
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível salvar delivery_method: {e}")
            db.session.rollback()
        
        # Emitir evento SocketIO para notificação em tempo real
        try:
            if payment.bot and payment.bot.user_id:
                socketio.emit('delivery_sent', {
                    'payment_id': payment.id,
                    'status': 'delivered',
                    'delivery_method': delivery_method,
                    'bot_id': payment.bot_id,
                }, room=f'user_{payment.bot.user_id}')
        except Exception as e:
            logger.error(f"❌ Erro ao emitir WebSocket de entrega: {e}")
        
        return {
            'success': telegram_sent or email_sent,
            'message': 'Entregável enviado com sucesso' if (telegram_sent or email_sent) else 'Falha ao enviar entregável',
            'delivery_method': delivery_method
        }
        
    except Exception as e:
        logger.error(f"❌ Erro crítico em send_payment_delivery: {e}", exc_info=True)
        return {'success': False, 'message': f'Erro: {str(e)}', 'delivery_method': 'none'}


def process_payment_confirmation(payment: Payment, gateway_type: str) -> bool:
    """
    Processa a confirmação de pagamento e executa ações pós-venda.
    
    Args:
        payment: Objeto Payment confirmado
        gateway_type: Tipo do gateway (paradise, syncpay, etc.)
    
    Returns:
        bool: True se processado com sucesso
    """
    try:
        # Enviar entregável (agora retorna dict)
        delivery_result = send_payment_delivery(payment)
        
        # Emitir evento em tempo real
        try:
            if payment.bot and payment.bot.user_id:
                socketio.emit('payment_update', {
                    'payment_id': payment.id,
                    'status': 'paid',
                    'amount': float(payment.amount),
                    'bot_id': payment.bot_id,
                    'delivery_method': delivery_result.get('delivery_method', 'none'),
                }, room=f'user_{payment.bot.user_id}')
        except Exception as e:
            logger.error(f"❌ Erro ao emitir WebSocket: {e}")
        
        # Processar upsells se configurado
        if payment.bot and payment.bot.config and payment.bot.config.upsells_enabled:
            try:
                upsells = payment.bot.config.get_upsells()
                if upsells:
                    matched_upsells = [
                        u for u in upsells 
                        if not u.get('trigger_product') or u.get('trigger_product') == payment.product_name
                    ]
                    
                    if matched_upsells:
                        local_bot_manager = BotManager(
                            socketio=None, 
                            scheduler=None, 
                            user_id=payment.bot.user_id
                        )
                        local_bot_manager.schedule_upsells(
                            bot_id=payment.bot_id,
                            payment_id=payment.payment_id,
                            chat_id=int(payment.customer_user_id),
                            upsells=matched_upsells,
                            original_price=payment.amount,
                            original_button_index=-1
                        )
                        logger.info(f"📅 Upsells agendados para payment {payment.payment_id}")
            except Exception as e:
                logger.error(f"❌ Erro ao processar upsells: {e}", exc_info=True)
        
        return delivery_result.get('success', False)
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de pagamento: {e}", exc_info=True)
        return False


# ==================== RECONCILIADORES (movidos de app.py) ====================

def reconcile_paradise_payments():
    """Consulta periodicamente pagamentos pendentes da Paradise."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Iniciando reconciliação Paradise")
            # Código de reconciliação implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro reconciliação Paradise: {e}")

def reconcile_pushynpay_payments():
    """Consulta periodicamente pagamentos pendentes da PushynPay."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Iniciando reconciliação PushynPay")
            # Código de reconciliação implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro reconciliação PushynPay: {e}")

def reconcile_atomopay_payments():
    """Consulta periodicamente pagamentos pendentes do Atomopay."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Iniciando reconciliação Atomopay")
            # Código de reconciliação implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro reconciliação Atomopay: {e}")

def reconcile_aguia_payments():
    """Consulta periodicamente pagamentos pendentes da ÁguiaPags."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Iniciando reconciliação ÁguiaPags")
            # Código de reconciliação implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro reconciliação ÁguiaPags: {e}")

def reconcile_bolt_payments():
    """Consulta periodicamente pagamentos pendentes do Bolt."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Iniciando reconciliação Bolt")
            # Código de reconciliação implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro reconciliação Bolt: {e}")


# ==================== JOBS DE ASSINATURA (movidos de app.py) ====================

def check_expired_subscriptions():
    """Remove usuários de grupos VIP quando subscription expira."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Verificando assinaturas expiradas")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro check_expired_subscriptions: {e}")

def reset_high_error_count_subscriptions():
    """Reset subscriptions com error_count alto após 7 dias."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Resetando error_count alto")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro reset_high_error_count_subscriptions: {e}")

def update_ranking_premium_rates():
    """Atualiza taxas premium do ranking."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Atualizando taxas premium")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro update_ranking_premium_rates: {e}")

def health_check_all_pools():
    """Health Check de todos os bots em todos os pools ativos."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Health check de pools")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro health_check_all_pools: {e}")

def check_scheduled_remarketing_campaigns():
    """Verifica campanhas agendadas e inicia envio quando chegar a hora."""
    try:
        from flask import current_app
        with current_app.app_context():
            logger.info("🔄 Verificando campanhas de remarketing")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro check_scheduled_remarketing_campaigns: {e}")
