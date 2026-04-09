"""
Delivery Routes
===============
Rota de entrega de produtos com injeção de variáveis para Meta Pixel Client-Side.

ARQUITETURA: Client-Side (HTML-Only)
- NÃO dispara Purchase no backend
- Apenas recupera dados e injeta no template delivery.html
- JavaScript no template dispara o Pixel e chama API de deduplicação
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from internal_logic.core.extensions import db

# Models (importar dos locais corretos no projeto)
from internal_logic.core.models import Payment, BotUser, PoolBot, RedirectPool

logger = logging.getLogger(__name__)

delivery_bp = Blueprint('delivery', __name__, url_prefix='/delivery')


@delivery_bp.route('/<token>')
def delivery_page(token):
    """
    Página de entrega do produto - INJETOR DE VARIÁVEIS META PIXEL
    
    ARQUITETURA CLIENT-SIDE (HTML-ONLY):
    - Recupera payment pelo delivery_token
    - Verifica se Pixel já foi disparado (anti-F5)
    - Recupera dados de tracking (fbp, fbc, fbclid)
    - Injeta variáveis no template para JavaScript operar
    - NÃO dispara Purchase no backend (apenas client-side via JS)
    
    Args:
        token: delivery_token único do payment
        
    Query Params:
        px: pixel_id opcional (usado no remarketing)
    """
    try:
        # ============================================================================
        # ETAPA 1: Recuperar Payment pelo delivery_token
        # ============================================================================
        payment = Payment.query.filter_by(delivery_token=token).first()
        
        if not payment:
            logger.error(f"❌ [DELIVERY] Token inválido: {token[:20]}...")
            return render_template('delivery_error.html', 
                                 error="Link de acesso inválido ou expirado."), 404
        
        # Verificar se pagamento está confirmado
        if payment.status != 'paid':
            logger.warning(f"⚠️ [DELIVERY] Pagamento não confirmado: payment_id={payment.id}, status={payment.status}")
            return render_template('delivery_error.html',
                                 error="Pagamento ainda não confirmado. Aguarde alguns instantes e tente novamente."), 200
        
        logger.info(f"✅ [DELIVERY] Página acessada: payment_id={payment.id}, token={token[:20]}...")
        
        # ============================================================================
        # ETAPA 2: Verificar se Pixel já foi disparado (Trava anti-F5)
        # ============================================================================
        purchase_already_sent = getattr(payment, 'meta_purchase_sent', False)
        
        # Gerar ou recuperar event_id único para deduplicação
        # Format: "purchase_{payment.id}" - consistente para Meta deduplicar
        event_id = getattr(payment, 'meta_event_id', None) or f"purchase_{payment.id}"
        
        # Se ainda não foi enviado, salvar o event_id no banco
        if not purchase_already_sent and not getattr(payment, 'meta_event_id', None):
            payment.meta_event_id = event_id
            db.session.commit()
            logger.info(f"✅ [DELIVERY] Event ID gerado e salvo: {event_id}")
        
        # ============================================================================
        # ETAPA 3: Buscar Pool correto (o que gerou o PageView)
        # ============================================================================
        pool_bot = None
        pool = None
        
        # Buscar pool_bot associado ao bot do payment
        if hasattr(payment, 'bot_id') and payment.bot_id:
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
            if pool_bot:
                pool = pool_bot.pool
                logger.info(f"✅ [DELIVERY] Pool encontrado: pool_id={pool.id if pool else 'N/A'}")
        
        if not pool_bot:
            logger.error(f"❌ [DELIVERY] Bot não está associado a nenhum pool: bot_id={getattr(payment, 'bot_id', None)}")
            return render_template('delivery_error.html',
                                 error="Configuração inválida"), 500
        
        # ============================================================================
        # ETAPA 4: Recuperar BotUser e dados de tracking
        # ============================================================================
        bot_user = None
        tracking_data = {}
        
        # Extrair telegram_user_id do payment.customer_user_id
        telegram_user_id = None
        if hasattr(payment, 'customer_user_id') and payment.customer_user_id:
            if payment.customer_user_id.startswith('user_'):
                telegram_user_id = payment.customer_user_id.replace('user_', '')
            else:
                telegram_user_id = str(payment.customer_user_id)
        
        # Buscar BotUser
        if telegram_user_id and hasattr(payment, 'bot_id'):
            bot_user = BotUser.query.filter_by(
                bot_id=payment.bot_id,
                telegram_user_id=str(telegram_user_id)
            ).first()
        
        # ============================================================================
        # ETAPA 5: Recuperar dados de tracking do Redis (TrackingServiceV4)
        # ============================================================================
        # PRIORIDADE 1: bot_user.tracking_session_id (token do redirect)
        if bot_user and hasattr(bot_user, 'tracking_session_id') and bot_user.tracking_session_id:
            try:
                # tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
                # if tracking_data:
                #     logger.info(f"✅ [DELIVERY] Tracking data recuperado via bot_user.tracking_session_id")
                pass  # Placeholder - implementar quando TrackingServiceV4 estiver disponível
            except Exception as e:
                logger.warning(f"⚠️ [DELIVERY] Erro ao recuperar tracking via bot_user: {e}")
        
        # PRIORIDADE 2: payment.tracking_token
        if not tracking_data and hasattr(payment, 'tracking_token') and payment.tracking_token:
            try:
                # tracking_data = tracking_service_v4.recover_tracking_data(payment.tracking_token) or {}
                # if tracking_data:
                #     logger.info(f"✅ [DELIVERY] Tracking data recuperado via payment.tracking_token")
                pass  # Placeholder
            except Exception as e:
                logger.warning(f"⚠️ [DELIVERY] Erro ao recuperar tracking via payment: {e}")
        
        # Extrair dados do tracking_data ou usar fallback do payment/bot_user
        fbp_value = tracking_data.get('fbp') if tracking_data else None
        fbc_value = tracking_data.get('fbc') if tracking_data else None
        fbclid_value = tracking_data.get('fbclid') if tracking_data else None
        
        # Fallback para dados do payment
        if not fbp_value and hasattr(payment, 'fbp'):
            fbp_value = payment.fbp
        if not fbc_value and hasattr(payment, 'fbc'):
            fbc_value = payment.fbc
        if not fbclid_value and hasattr(payment, 'fbclid'):
            fbclid_value = payment.fbclid
        
        # Fallback para dados do bot_user
        if not fbp_value and bot_user and hasattr(bot_user, 'fbp'):
            fbp_value = bot_user.fbp
        if not fbc_value and bot_user and hasattr(bot_user, 'fbc'):
            fbc_value = bot_user.fbc
        
        # ============================================================================
        # ETAPA 6: STICKY PIXEL COM REDUNDÂNCIA TRIPLA
        # ============================================================================
        pixel_id_to_use = None
        pixel_source = None
        
        # PRIORIDADE 1: Query param 'px' (usado em remarketing)
        px_from_query = request.args.get('px')
        if px_from_query:
            pixel_id_to_use = px_from_query
            pixel_source = 'query'
            logger.info(f"[PIXEL_STICKY] Pixel ID via query param: {pixel_id_to_use}")
        
        if not pixel_id_to_use:
            # Ordem de prioridade garantida (Sticky Pixel) - mesma do payment_processor
            pixel_sources = [
                getattr(payment, 'meta_pixel_id', None),      # 1. Payment (Backup do banco)
                tracking_data.get('pixel_id') if tracking_data else None,  # 2. Redis
                pool.meta_pixel_id if pool else None          # 3. Pool Original
            ]
            
            # Encontrar primeiro pixel_id válido
            pixel_id_to_use = next((p for p in pixel_sources if p), None)
            
            # Determinar origem para logging
            source_map = {
                0: 'payment',
                1: 'redis', 
                2: 'pool'
            }
            
            if pixel_id_to_use:
                source_index = pixel_sources.index(pixel_id_to_use)
                pixel_source = source_map.get(source_index, 'unknown')
                logger.info(f"[PIXEL_STICKY] Pixel encontrado: source={pixel_source}, pixel_id={pixel_id_to_use}")
            else:
                # FALLBACK DE SEGURANÇA: fbclid numérico como pixel temporário
                if fbclid_value and fbclid_value.isdigit():
                    pixel_id_to_use = fbclid_value
                    pixel_source = 'fbclid_fallback'
                    logger.warning(f"[PIXEL_STICKY] Fallback fbclid numérico: {pixel_id_to_use}")
                else:
                    logger.warning(f"[PIXEL_STICKY] Nenhum pixel encontrado - sem tracking")
        
        # Verificar se temos pixel configurado
        has_meta_pixel = bool(pixel_id_to_use)
        
        # ============================================================================
        # ETAPA 7: Preparar URL de redirecionamento
        # ============================================================================
        redirect_url = None
        
        # Tentar usar access_link personalizado do BotConfig
        if (pool_bot and pool_bot.bot and 
            hasattr(pool_bot.bot, 'config') and 
            pool_bot.bot.config and 
            hasattr(pool_bot.bot.config, 'access_link') and 
            pool_bot.bot.config.access_link):
            redirect_url = pool_bot.bot.config.access_link
            logger.info(f"✅ [DELIVERY] Usando access_link personalizado: {redirect_url}")
        
        # Fallback: link genérico do username do bot
        elif pool_bot and pool_bot.bot and hasattr(pool_bot.bot, 'username') and pool_bot.bot.username:
            redirect_url = f"https://t.me/{pool_bot.bot.username}?start=p{payment.id}"
            logger.info(f"⚠️ [DELIVERY] Usando fallback genérico: {redirect_url}")
        
        else:
            logger.error(f"❌ [DELIVERY] Nenhum redirect_url disponível para payment {payment.id}")
        
        # ============================================================================
        # ETAPA 8: Renderizar template INJETANDO variáveis para JavaScript
        # ============================================================================
        logger.info(f"✅ [DELIVERY] Renderizando template: payment_id={payment.id}, "
                   f"pixel={'✅' if has_meta_pixel else '❌'}, "
                   f"event_id={event_id[:30]}..., "
                   f"already_sent={purchase_already_sent}")
        
        return render_template('delivery.html',
            payment=payment,
            pixel_id=pixel_id_to_use,
            purchase_event_id=event_id,
            purchase_already_sent=purchase_already_sent,
            fbp=fbp_value,
            fbc=fbc_value,
            fbclid=fbclid_value,
            redirect_url=redirect_url,
            pool=pool,
            pool_bot=pool_bot,
            tracking_data=tracking_data
        )
        
    except Exception as e:
        logger.error(f"❌ [DELIVERY] Erro na página de delivery: {e}", exc_info=True)
        return render_template('delivery_error.html', error=str(e)), 500


@delivery_bp.route('/api/tracking/mark-purchase-sent', methods=['POST'])
def mark_purchase_sent():
    """
    API para marcar Purchase como enviado (anti-duplicação).
    
    Chamado pelo JavaScript do template delivery.html após disparar
    o evento Purchase client-side com sucesso.
    
    Request Body:
        {"payment_id": 123}
    
    Returns:
        {"success": true} ou {"error": "mensagem"}
    """
    try:
        data = request.get_json() or {}
        payment_id = data.get('payment_id')
        
        if not payment_id:
            return jsonify({'error': 'payment_id obrigatório'}), 400
        
        payment = Payment.query.filter_by(id=int(payment_id)).first_or_404()
        
        # DEFENSIVO: Verificar status do pagamento
        if payment.status != 'paid':
            if payment.status == 'pending':
                # Pagamento ainda pendente - retornar 202 Accepted (aguardando confirmação)
                logger.info(f"⏳ [MARK_PURCHASE] Pagamento pendente, aguardando confirmação: payment_id={payment.id}")
                return jsonify({
                    'status': 'pending',
                    'message': 'Pagamento em processamento, aguardando confirmação do gateway'
                }), 202
            else:
                # Status inválido (cancelled, refunded, etc.)
                logger.warning(f"⚠️ [MARK_PURCHASE] Status inválido para marcar Purchase: {payment.status}")
                return jsonify({'error': 'Pagamento não está confirmado'}), 400
        
        # Marcar como enviado
        if hasattr(payment, 'purchase_sent_from_delivery'):
            payment.purchase_sent_from_delivery = True
        
        if not getattr(payment, 'meta_purchase_sent', False):
            payment.meta_purchase_sent = True
            payment.meta_purchase_sent_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ [MARK_PURCHASE] Purchase marcado como enviado: payment_id={payment.id}")
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ [MARK_PURCHASE] Erro ao marcar Purchase como enviado: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
