# ============================================================================
# LEGACY FULFILLMENT LOGIC - EXTRAÇÃO DO CÓDIGO LEGADO (STAGING)
# Arquivo: _legacy_exports/legacy_fulfillment_logic.py
# Origem: app.py (linhas ~215-381)
# ============================================================================
# Este arquivo contém a função EXATA de envio de entregável (send_payment_delivery)
# NÃO MODIFICAR - Apenas para referência durante migração
# ============================================================================

import hashlib
import time
import uuid
import logging

logger = logging.getLogger(__name__)


def send_payment_delivery(payment, bot_manager=None, socketio=None):
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado
    
    ✅ REFATORADO: Cria BotManager localmente com user_id do payment
    
    EXTRACTED FROM: app.py linhas 215-381
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância opcional do BotManager (para compatibilidade)
        socketio: Instância opcional do SocketIO
    
    Returns:
        bool: True se enviado com sucesso, False se houve erro
    """
    try:
        if not payment or not payment.bot:
            logger.warning(f"⚠️ Payment ou bot inválido para envio de entregável: payment={payment}")
            return False
        
        # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
        from bot_manager import BotManager
        local_bot_manager = BotManager(socketio=socketio, scheduler=None, user_id=payment.bot.user_id)
        
        # ✅ CRÍTICO: Não enviar entregável se pagamento não estiver 'paid'
        allowed_status = ['paid']
        if payment.status not in allowed_status:
            logger.error(
                f"❌ BLOQUEADO: tentativa de envio de acesso com status inválido "
                f"({payment.status}). Apenas 'paid' é permitido. Payment ID: {payment.payment_id if payment else 'None'}"
            )
            logger.error(
                f"❌ ERRO GRAVE: send_payment_delivery chamado com payment.status != 'paid' "
                f"(status atual: {payment.status}, payment_id: {payment.payment_id if payment else 'None'})"
            )
            return False
        
        if not payment.bot.token:
            logger.error(f"❌ Bot {payment.bot_id} não tem token configurado - não é possível enviar entregável")
            return False
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se customer_user_id é válido
        if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
            logger.error(f"❌ Payment {payment.id} não tem customer_user_id válido ({payment.customer_user_id}) - não é possível enviar")
            return False
        
        # ✅ GERAR delivery_token se não existir (único por payment)
        if not payment.delivery_token:
            # Gerar token único: hash de payment_id + timestamp + secret
            timestamp = int(time.time())
            secret = f"{payment.id}_{payment.payment_id}_{timestamp}"
            delivery_token = hashlib.sha256(secret.encode()).hexdigest()[:64]
            
            payment.delivery_token = delivery_token
            from internal_logic.core.extensions import db
            db.session.commit()
            logger.info(f"✅ delivery_token gerado para payment {payment.id}: {delivery_token[:20]}...")
        
        # ✅ Buscar pool para verificar Meta Pixel
        from models import PoolBot, BotUser
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        pool = pool_bot.pool if pool_bot else None

        # ✅ Sticky Pixel: priorizar pixel da origem do usuário (campaign_code) se for numérico
        bot_user_for_pixel = BotUser.query.filter_by(
            bot_id=payment.bot_id, 
            telegram_user_id=str(payment.customer_user_id)
        ).first() if payment.customer_user_id else None
        
        user_origin_pixel = getattr(bot_user_for_pixel, 'campaign_code', None) if bot_user_for_pixel else None
        pixel_from_user = user_origin_pixel if user_origin_pixel and str(user_origin_pixel).isdigit() else None
        pixel_id_to_use = pixel_from_user or (pool.meta_pixel_id if pool else None)

        has_meta_pixel = bool(pool and pool.meta_tracking_enabled and pixel_id_to_use)
        
        # Verificar se bot tem config e access_link (link final configurado pelo usuário)
        has_access_link = payment.bot.config and payment.bot.config.access_link
        access_link = payment.bot.config.access_link if has_access_link else None
        
        # ✅ DECISÃO CRÍTICA: Qual link enviar baseado em Meta Pixel?
        # Se Meta Pixel ATIVO → usar /delivery para disparar Purchase tracking
        # Se Meta Pixel INATIVO → usar access_link direto (sem passar por /delivery)
        link_to_send = None
        
        if has_meta_pixel:
            # ✅ Meta Pixel ATIVO → usar /delivery para disparar Purchase tracking
            # Gerar delivery_token se não existir (necessário para /delivery)
            if not payment.delivery_token:
                timestamp = int(time.time())
                secret = f"{payment.id}_{payment.payment_id}_{timestamp}"
                delivery_token = hashlib.sha256(secret.encode()).hexdigest()[:64]
                payment.delivery_token = delivery_token
                from internal_logic.core.extensions import db
                db.session.commit()
                logger.info(f"✅ delivery_token gerado para Meta Pixel tracking: {delivery_token[:20]}...")
            
            # Gerar URL de delivery
            from flask import url_for
            try:
                # Transportar pixel_id do redirect junto na URL de delivery (HTML-only)
                link_to_send = url_for(
                    'delivery_page',
                    delivery_token=payment.delivery_token,
                    px=pixel_id_to_use,
                    _external=True
                )
            except:
                suffix_px = f"?px={pixel_id_to_use}" if pixel_id_to_use else ""
                link_to_send = f"https://app.grimbots.online/delivery/{payment.delivery_token}{suffix_px}"
            
            logger.info(f"✅ Meta Pixel ativo → enviando /delivery para disparar Purchase tracking (payment {payment.id})")
        else:
            # ✅ Meta Pixel INATIVO → usar access_link direto (sem passar por /delivery)
            if has_access_link:
                link_to_send = access_link
                logger.info(f"✅ Meta Pixel inativo → enviando access_link direto: {access_link[:50]}... (payment {payment.id})")
            else:
                # Sem Meta Pixel E sem access_link → sem link (mensagem genérica)
                link_to_send = None
                logger.warning(f"⚠️ Meta Pixel inativo E sem access_link → enviando mensagem genérica (payment {payment.id})")
        
        # ✅ Montar mensagem baseada no link disponível
        if link_to_send:
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Clique aqui para acessar:</b>
{link_to_send}

Aproveite! 🚀
            """
            logger.info(f"✅ Link de acesso enviado para payment {payment.id} (Meta Pixel: {'✅' if has_meta_pixel else '❌'})")
        else:
            # Mensagem genérica sem link (bot não configurou access_link e não tem Meta Pixel)
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

📧 Entre em contato com o suporte para receber seu acesso.
            """
            logger.warning(f"⚠️ Bot {payment.bot_id} não tem access_link configurado e Meta Pixel inativo - enviando mensagem genérica")
        
        # Enviar via bot manager local e capturar exceção se falhar
        try:
            local_bot_manager.send_telegram_message(
                token=payment.bot.token,
                chat_id=str(payment.customer_user_id),
                message=access_message.strip()
            )
            logger.info(f"✅ Entregável enviado para {payment.customer_name} (payment_id: {payment.id}, bot_id: {payment.bot_id}, delivery_token: {payment.delivery_token[:20]}...)")
            return True
        except Exception as send_error:
            # Erro ao enviar mensagem (bot bloqueado, chat_id inválido, etc)
            logger.error(f"❌ Erro ao enviar mensagem Telegram para payment {payment.id}: {send_error}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar entregável para payment {payment.id if payment else 'None'}: {e}", exc_info=True)
        return False


# ============================================================================
# FUNÇÃO LEGADA: Geração de PIX (para referência)
# ============================================================================

def _generate_pix_payment_legacy(bot_id, amount, description, customer_name, 
                                  customer_username, customer_user_id, **kwargs):
    """
    EXTRACTED FROM: botmanager.py (para referência da lógica de geração de PIX)
    
    Lógica legada de geração de PIX com:
    - Lock distribuído Redis
    - Gateway Factory
    - Tracking data recovery
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # ✅ CRÍTICO: Inicializar variáveis de lock NA PRIMEIRA LINHA
    lock_key = None
    lock_acquired = False
    redis_conn = None
    
    try:
        # Tentar adquirir lock distribuído
        from redis_manager import get_redis_connection
        redis_conn = get_redis_connection()
        if redis_conn:
            lock_key = f"lock:pix:{bot_id}:{customer_user_id}"
            lock_acquired = bool(redis_conn.set(lock_key, "1", nx=True, ex=10))
            if not lock_acquired:
                logger.warning(f"⚠️ Lock PIX ativo para bot_id={bot_id}, user={customer_user_id} - aguardando liberação")
                return None
        else:
            logger.warning("⚠️ Redis indisponível para lock PIX - seguindo sem lock (risco de duplicidade)")
    except Exception as lock_error:
        logger.warning(f"⚠️ Erro ao adquirir lock PIX: {lock_error} - seguindo mesmo assim (risco de duplicidade)")
    
    try:
        # ... (resto da lógica de geração de PIX)
        from models import Bot, Gateway, Payment
        from gateway_factory import GatewayFactory
        from internal_logic.core.extensions import db
        from internal_logic.core.models import get_brazil_time
        
        bot = Bot.query.get(bot_id)
        if not bot:
            return None
        
        # Buscar gateway ativo
        gateway = Gateway.query.filter_by(user_id=bot.user_id, is_active=True).first()
        if not gateway:
            return None
        
        # Preparar credenciais
        credentials = {
            'api_key': gateway.api_key,
            'client_secret': gateway.client_secret,
            'client_id': gateway.client_id,
            'product_hash': gateway.product_hash,
            'split_user_id': gateway.split_user_id
        }
        
        # Criar gateway via factory
        payment_gateway = GatewayFactory.create_gateway(
            gateway_type=gateway.gateway_type,
            credentials=credentials
        )
        
        if not payment_gateway:
            return None
        
        # Preparar customer_data
        customer_data = {
            'name': customer_name,
            'email': f"{customer_username}@telegram.user",
            'document': kwargs.get('cpf', ''),
            'phone': kwargs.get('phone', '')
        }
        
        # Gerar payment_id único
        import hashlib
        import uuid
        payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Chamar gateway
        pix_result = payment_gateway.generate_pix(
            amount=amount,
            description=description,
            payment_id=payment_id,
            customer_data=customer_data
        )
        
        # Criar registro de payment no banco
        if pix_result and pix_result.get('success'):
            payment = Payment(
                bot_id=bot_id,
                payment_id=payment_id,
                amount=amount,
                product_name=description,
                customer_user_id=customer_user_id,
                customer_name=customer_name,
                customer_username=customer_username,
                gateway_type=gateway.gateway_type,
                gateway_transaction_id=pix_result.get('transaction_id'),
                gateway_transaction_hash=pix_result.get('transaction_hash'),
                pix_code=pix_result.get('pix_code'),
                pix_qr_code=pix_result.get('qr_code'),
                status='pending',
                expires_at=get_brazil_time() + __import__('datetime').timedelta(minutes=30)
            )
            db.session.add(payment)
            db.session.commit()
            
            return {
                'payment': payment,
                'pix_code': pix_result.get('pix_code'),
                'qr_code': pix_result.get('qr_code')
            }
        
        return None
        
    finally:
        # ✅ Liberar lock
        try:
            if lock_acquired and lock_key and redis_conn:
                redis_conn.delete(lock_key)
        except Exception as unlock_error:
            logger.warning(f"⚠️ Erro ao liberar lock PIX: {unlock_error}")
