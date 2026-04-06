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
from typing import Optional

from flask import url_for
from internal_logic.core.extensions import db, socketio
from bot_manager import BotManager
from models import Payment, PoolBot, BotUser

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


def send_payment_delivery(payment: Payment, bot_manager: Optional[BotManager] = None) -> bool:
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado.
    
    ✅ REFATORADO: Cria BotManager localmente com user_id do payment
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância opcional do BotManager (para compatibilidade)
    
    Returns:
        bool: True se enviado com sucesso, False se houve erro
    """
    try:
        if not payment or not payment.bot:
            logger.warning(f"⚠️ Payment ou bot inválido para envio de entregável: payment={payment}")
            return False
        
        # ✅ CRÍTICO: Não enviar entregável se pagamento não estiver 'paid'
        if payment.status != 'paid':
            logger.error(
                f"❌ BLOQUEADO: tentativa de envio com status inválido "
                f"({payment.status}). Apenas 'paid' é permitido. "
                f"Payment ID: {payment.payment_id if payment else 'None'}"
            )
            return False
        
        if not payment.bot.token:
            logger.error(f"❌ Bot {payment.bot_id} não tem token configurado")
            return False
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se customer_user_id é válido
        if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
            logger.error(f"❌ Payment {payment.id} não tem customer_user_id válido")
            return False
        
        # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
        if bot_manager is None:
            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
        else:
            local_bot_manager = bot_manager
        
        # Buscar pixel ID
        pixel_id_to_use = get_pixel_id_for_payment(payment)
        has_meta_pixel = bool(pixel_id_to_use)
        
        # Determinar link de entrega
        link_to_send = get_delivery_link(payment, pixel_id_to_use)
        
        # Construir mensagem
        access_message = build_delivery_message(payment, link_to_send, has_meta_pixel)
        
        # Enviar mensagem
        local_bot_manager.send_telegram_message(
            token=payment.bot.token,
            chat_id=str(payment.customer_user_id),
            message=access_message.strip()
        )
        
        logger.info(
            f"✅ Entregável enviado para {payment.customer_name} "
            f"(payment_id: {payment.id}, bot_id: {payment.bot_id})"
        )
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar entregável: {e}", exc_info=True)
        return False


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
        # Enviar entregável
        result = send_payment_delivery(payment)
        
        # Emitir evento em tempo real
        try:
            if payment.bot and payment.bot.user_id:
                socketio.emit('payment_update', {
                    'payment_id': payment.id,
                    'status': 'paid',
                    'amount': float(payment.amount),
                    'bot_id': payment.bot_id,
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
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de pagamento: {e}", exc_info=True)
        return False
