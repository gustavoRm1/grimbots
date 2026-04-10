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
    PÁGINA DE ENTREGA COM PURCHASE TRACKING
    
    Fluxo:
    1. Lead passa pelo cloaker -> PageView disparado -> tracking_token salvo no Redis
    2. Lead compra -> webhook confirma -> delivery_token gerado -> link enviado
    3. Lead acessa esta página -> Purchase disparado com matching perfeito
    4. Redireciona para link final configurado pelo usuário
    
    MATCHING 100%:
    - Usa mesmo event_id do PageView (deduplicação perfeita)
    - Usa cookies frescos do browser (_fbp, _fbc)
    - Usa tracking_data do Redis (fbclid, IP, UA)
    - Matching garantido mesmo se cookies expirarem
    """
    try:
        # Imports adaptados para arquitetura atual
        from internal_logic.core.models import Payment, PoolBot, BotUser, Gateway
        from internal_logic.services.tracking_service import TrackingService
        from internal_logic.core.models import get_brazil_time
        from gateway_factory import GatewayFactory
        import time
        from datetime import datetime
        
        # VALIDAÇÃO: Buscar payment pelo delivery_token (NÃO filtrar status aqui)
        # A rota deve tratar status pendente de forma controlada e nunca disparar Purchase.
        payment = Payment.query.filter_by(
            delivery_token=token
        ).first()
        if not payment:
            logger.error(f" Delivery token inválido ou expirado: {token}")
            return render_template('delivery_error.html', error='Link de entrega inválido ou expirado.'), 404

        # DEFENSIVO: Se status != paid, consultar gateway em tempo real.
        # Só prosseguir para Purchase/entrega se o gateway retornar explicitamente 'paid'.
        if payment.status != 'paid':
            try:
                if not payment.bot or not payment.gateway_type:
                    return render_template('delivery_error.html', error='Pagamento ainda não confirmado. Aguarde alguns instantes e tente novamente.'), 200

                gateway_row = Gateway.query.filter_by(
                    user_id=payment.bot.user_id,
                    gateway_type=payment.gateway_type,
                    is_active=True,
                    is_verified=True
                ).first()

                if not gateway_row:
                    return render_template('delivery_error.html', error='Pagamento ainda não confirmado. Aguarde alguns instantes e tente novamente.'), 200

                gateway_type = (payment.gateway_type or '').strip().lower()
                credentials = {}

                if gateway_type == 'syncpay':
                    credentials = {
                        'client_id': gateway_row.client_id,
                        'client_secret': gateway_row.client_secret,
                    }
                elif gateway_type == 'paradise':
                    credentials = {
                        'api_key': gateway_row.api_key,
                        'product_hash': gateway_row.product_hash,
                        'offer_hash': gateway_row.offer_hash,
                        'store_id': gateway_row.store_id,
                        'split_percentage': gateway_row.split_percentage or 2.0,
                    }
                elif gateway_type == 'atomopay':
                    credentials = {
                        'api_token': gateway_row.api_key,
                        'product_hash': gateway_row.product_hash,
                    }
                elif gateway_type == 'umbrellapag':
                    credentials = {
                        'api_key': gateway_row.api_key,
                        'product_hash': gateway_row.product_hash,
                    }
                elif gateway_type == 'wiinpay':
                    credentials = {
                        'api_key': gateway_row.api_key,
                        'split_user_id': gateway_row.split_user_id,
                    }
                elif gateway_type == 'babylon':
                    credentials = {
                        'api_key': gateway_row.api_key,
                        'company_id': gateway_row.client_id,
                    }
                elif gateway_type == 'bolt':
                    credentials = {
                        'api_key': gateway_row.api_key,
                        'company_id': gateway_row.client_id,
                    }
                elif gateway_type == 'aguia':
                    credentials = {
                        'api_key': gateway_row.api_key,
                        # ÁguiaPags não usa webhook_secret (webhook stateless)
                    }
                else:
                    # pushynpay/orionpay e demais baseados em api_key
                    credentials = {
                        'api_key': gateway_row.api_key,
                    }

                payment_gateway = GatewayFactory.create_gateway(
                    gateway_type=gateway_type,
                    credentials=credentials,
                    use_adapter=True
                )

                if not payment_gateway:
                    return render_template('delivery_error.html', error='Pagamento ainda não confirmado. Aguarde alguns instantes e tente novamente.'), 200

                # Identificador de consulta por gateway (Paradise prioriza hash)
                tx_identifier = payment.gateway_transaction_id
                if gateway_type == 'paradise':
                    tx_identifier = payment.gateway_transaction_hash or payment.gateway_transaction_id

                if not tx_identifier:
                    return render_template('delivery_error.html', error='Pagamento ainda não confirmado. Aguarde alguns instantes e tente novamente.'), 200

                api_status = payment_gateway.get_payment_status(str(tx_identifier))
                api_normalized_status = (api_status or {}).get('status')

                if api_normalized_status == 'paid':
                    payment.status = 'paid'
                    if not payment.paid_at:
                        payment.paid_at = get_brazil_time()
                    db.session.commit()
                    db.session.refresh(payment)
                else:
                    return render_template('delivery_error.html', error='Pagamento ainda não confirmado. Aguarde alguns instantes e tente novamente.'), 200
            except Exception as verify_error:
                logger.error(f" [DELIVERY] Erro ao verificar status em tempo real: {verify_error}", exc_info=True)
                return render_template('delivery_error.html', error='Pagamento ainda não confirmado. Aguarde alguns instantes e tente novamente.'), 200
        
        # Buscar pool CORRETO (o que gerou o PageView, não o primeiro)
        # Prioridade: 1) pool_id do tracking_data, 2) primeiro pool do bot
        pool_id_from_tracking = None
        pool_bot = None
        
        # RECUPERAR tracking_data primeiro (para identificar pool correto)
        tracking_service = TrackingService()
        telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else payment.customer_user_id
        bot_user = BotUser.query.filter_by(
            bot_id=payment.bot_id,
            telegram_user_id=str(telegram_user_id)
        ).first()
        
        if bot_user and bot_user.tracking_session_id:
            temp_tracking_data = tracking_service.recover_tracking_data(bot_user.tracking_session_id) or {}
            pool_id_from_tracking = temp_tracking_data.get('pool_id')
        
        # Buscar pool CORRETO
        if pool_id_from_tracking:
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id, pool_id=pool_id_from_tracking).first()
            if pool_bot:
                logger.info(f" Delivery - Pool correto encontrado via tracking_data: pool_id={pool_id_from_tracking}")
        
        # Fallback: primeiro pool do bot
        if not pool_bot:
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
            if pool_bot:
                logger.warning(f" Delivery - Usando primeiro pool do bot (pool_id não encontrado no tracking_data): pool_id={pool_bot.pool_id}")
        
        if not pool_bot:
            logger.error(f" Payment {payment.id}: Bot não está associado a nenhum pool")
            return render_template('delivery_error.html', error="Configuração inválida"), 500
        
        pool = pool_bot.pool
        # Inicialização defensiva para evitar UnboundLocalError em caminhos de retorno antecipado
        redirect_url = None
        # LINK DE ACESSO: sempre definir antes de qualquer retorno, mesmo sem pixel
        if pool_bot and pool_bot.bot and pool_bot.bot.config and pool_bot.bot.config.access_link:
            redirect_url = pool_bot.bot.config.access_link
            logger.info(f" Delivery - Usando access_link personalizado: {redirect_url}")
        elif pool_bot and pool_bot.bot and pool_bot.bot.username:
            redirect_url = f"https://t.me/{pool_bot.bot.username}?start=p{payment.id}"
            logger.info(f" Delivery - Usando fallback genérico (access_link não configurado): {redirect_url}")
        else:
            logger.error(f" Delivery - Nenhum redirect_url disponível para payment {payment.id}")

        # ✅ CLEAN ARCHITECTURE: 'Fio Invisível' - extrair tracking do BotUser
        # A tabela Payment é 100% financeira - tracking vem do perfil do usuário
        
        # A. Buscar dados de marketing do BotUser
        pixel_id = getattr(bot_user, 'campaign_code', None) if bot_user else None
        fbp = getattr(bot_user, 'fbp', None) if bot_user else None
        fbc = getattr(bot_user, 'fbc', None) if bot_user else None
        fbclid = getattr(bot_user, 'fbclid', None) if bot_user else None
        
        # B. Fallback Inteligente: se BotUser não tiver campaign_code, buscar do Pool/Bot
        if not pixel_id:
            pixel_id = pool.meta_pixel_id if pool else None
            logger.info(f"[FILO_INVISIVEL] Pixel fallback do Pool: {pixel_id}")
        else:
            logger.info(f"[FILO_INVISIVEL] Pixel do BotUser: {pixel_id}")
        
        # C. Validação de pixel_id
        has_meta_pixel = bool(pixel_id)
        if not has_meta_pixel:
            logger.warning("[FILO_INVISIVEL] pixel_id ausente - Purchase não será disparado")
        
        # D. Validação de FBC sintético (se houver tracking_data para verificar)
        fbc_origin = None
        if bot_user and bot_user.tracking_session_id:
            temp_tracking_data = tracking_service.recover_tracking_data(bot_user.tracking_session_id) or {}
            fbc_origin = temp_tracking_data.get('fbc_origin')
            if fbc and fbc_origin == 'synthetic':
                fbc = None  # Ignorar FBC sintético
                logger.warning("[FILO_INVISIVEL] fbc IGNORADO (origem: synthetic)")
        
        # E. Valores finais para template
        fbclid_to_use = fbclid or ''
        fbp_value = fbp or ''
        fbc_value = fbc or ''
        external_id = fbclid
        
        # CRÍTICO: Validar fbc_origin (ignorar fbc sintético)
        if fbc_value and fbc_origin == 'synthetic':
            fbc_value = None  # Meta não atribui com fbc sintético
            logger.warning(f"[META DELIVERY] Delivery - fbc IGNORADO (origem: synthetic) - Meta não atribui com fbc sintético")
        
        # LOG CRÍTICO: Verificar dados recuperados
        logger.info(f"[META DELIVERY] Delivery - Dados recuperados: fbclid={' ' if external_id else ' '}, fbp={' ' if fbp_value else ' '}, fbc={' ' if fbc_value else ' '}, fbc_origin={fbc_origin or 'ausente'}")
        
        # Sanitizar valores para JavaScript
        def sanitize_js_value(value):
            if not value:
                return ''
            import re
            value = str(value).replace("'", "\\'").replace('"', '\\"').replace('\n', '').replace('\r', '')
            value = re.sub(r'[^a-zA-Z0-9_.-]', '', value)
            return value[:255]
        
        # CORREÇÃO CRÍTICA: Normalizar external_id para garantir matching
        # Se external_id existir, normalizar (MD5 se > 80 chars, ou original se <= 80)
        # Isso garante que browser e server usem EXATAMENTE o mesmo formato
        external_id_normalized = None
        if external_id:
            try:
                # Implementar normalização local se não existir util
                if len(str(external_id)) > 80:
                    import hashlib
                    external_id_normalized = hashlib.sha256(str(external_id).encode()).hexdigest()
                else:
                    external_id_normalized = str(external_id)
            except Exception as e:
                logger.warning(f"Erro ao normalizar external_id: {e}")
                external_id_normalized = str(external_id)

        # event_id para Purchase: usar ID exclusivo do pagamento (dedup client/server)
        purchase_event_id = f"purchase_{payment.id}"
        payment.meta_event_id = purchase_event_id
        db.session.commit()
        db.session.refresh(payment)

        # ✅ CLEAN ARCHITECTURE: Injetar dados do BotUser no template
        # Sem dependência do Payment para tracking
        
        # Normalizar external_id para JavaScript
        external_id_normalized = None
        if external_id:
            try:
                if len(str(external_id)) > 80:
                    import hashlib
                    external_id_normalized = hashlib.sha256(str(external_id).encode()).hexdigest()
                else:
                    external_id_normalized = str(external_id)
            except Exception as e:
                logger.warning(f"Erro ao normalizar external_id: {e}")
                external_id_normalized = str(external_id)
        
        # Configuração do pixel para template
        pixel_config = {
            'pixel_id': pixel_id if has_meta_pixel else None,  # Do BotUser
            'event_id': purchase_event_id,  # Deduplicação
            'external_id': external_id_normalized,
            'fbp': fbp_value,  # Do BotUser
            'fbc': fbc_value,  # Do BotUser
            'value': float(payment.amount),
            'currency': 'BRL',
            'content_id': str(pool.id) if pool else str(payment.bot_id),
            'content_name': payment.product_name or payment.bot.name,
        }

        # CRÍTICO: DEDUPLICAÇÃO - Garantir que Purchase NÃO seja enviado duplicado
        purchase_already_sent = payment.meta_purchase_sent
        
        # CRÍTICO: Renderizar template PRIMEIRO para permitir client-side disparar Purchase
        # Meta deduplica automaticamente usando eventID, então não bloqueamos client-side mesmo se server-side já foi enviado
        # CORREÇÃO: NÃO marcar meta_purchase_sent ANTES de renderizar - isso bloqueava client-side!
        logger.info(f" Delivery - Renderizando página para payment {payment.id} | Pixel: {' ' if has_meta_pixel else ' '} | event_id: {pixel_config['event_id'][:30]}... | meta_purchase_sent: {payment.meta_purchase_sent}")
        
        # CORREÇÃO CRÍTICA: Buscar access_link personalizado do BotConfig (não do Bot)
        # Prioridade: 1) bot.config.access_link (configurado no painel), 2) fallback para username
        redirect_url = None
        
        # Tentar usar access_link personalizado primeiro (está em BotConfig, não em Bot)
        if pool_bot and pool_bot.bot and pool_bot.bot.config and pool_bot.bot.config.access_link:
            redirect_url = pool_bot.bot.config.access_link
            logger.info(f" Delivery - Usando access_link personalizado: {redirect_url}")
        # Fallback: link genérico do username do bot
        elif pool_bot and pool_bot.bot and pool_bot.bot.username:
            redirect_url = f"https://t.me/{pool_bot.bot.username}?start=p{payment.id}"
            logger.info(f" Delivery - Usando fallback genérico (access_link não configurado): {redirect_url}")
        else:
            logger.error(f" Delivery - Nenhum redirect_url disponível para payment {payment.id}")
        
        # LOG: pixel_id veio exclusivamente da query (funil). Nenhuma inferência.
        logger.info(f" Delivery - pixel_id via query param px: {' ' if pixel_id else ' '}")
        
        # ✅ CLEAN ARCHITECTURE: Injetar variáveis do BotUser no template
        response = render_template('delivery.html',
            payment=payment,
            pixel_id=pixel_id,  # Do BotUser
            redirect_url=redirect_url,
            pageview_event_id=getattr(payment, 'pageview_event_id', None),
            purchase_event_id=purchase_event_id,
            fbclid=fbclid_to_use,  # Do BotUser
            fbc=fbc_value,  # Do BotUser
            fbp=fbp_value,  # Do BotUser
            fbc_origin=fbc_origin  # Para validação no template
        )
        
        # DEPOIS de renderizar template, enfileirar Purchase via Server (Conversions API)
        # Isso garante que Purchase seja enviado mesmo se client-side falhar
        # Meta deduplica automaticamente usando eventID/event_id
        # SERVER-SIDE PURCHASE DESATIVADO: política HTML-only
        if has_meta_pixel and not purchase_already_sent:
            logger.info(f" [META DELIVERY] Purchase server-side desativado (HTML-only) | payment {payment.id} | event_id {pixel_config.get('event_id')}")

        return response
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        import logging
        logging.getLogger(__name__).error(f"ERRO DELIVERY: {error_trace}")
        return f"<div style='padding:20px; font-family:monospace; color:red;'><h2>🚨 ERRO FATAL DE DEBUG:</h2><pre>{error_trace}</pre></div>", 500


@delivery_bp.route('/api/tracking/mark-purchase-sent', methods=['POST'])
def mark_purchase_sent():
    """
    V4.1: API para marcar Purchase como enviado (anti-duplicação)
    
    Chamado via fetch() pelo delivery.html após disparar evento Purchase.
    Impede que o mesmo Pixel de compra dispare duas vezes se o cliente atualizar a página.
    """
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        event_id = data.get('event_id')
        
        if not payment_id:
            return jsonify({'error': 'payment_id obrigatório'}), 400
        
        # Buscar payment
        from internal_logic.core.models import Payment
        payment = Payment.query.filter_by(id=int(payment_id)).first_or_404()
        
        # V4.1: Defensivo - só marcar se pagamento estiver confirmado
        if payment.status != 'paid':
            logger.warning(f"⚠️ V4.1 - Tentativa de marcar Purchase para pagamento não confirmado: {payment_id}")
            return jsonify({'error': 'Pagamento não confirmado'}), 400
        
        # V4.1: Marcar como enviado
        payment.meta_purchase_sent = True
        if event_id:
            payment.meta_event_id = event_id
        
        db.session.commit()
        
        logger.info(f"✅ V4.1 - Purchase marcado como enviado: payment_id={payment_id}, event_id={event_id}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ V4.1 - Erro ao marcar Purchase: {e}")
        return jsonify({'error': str(e)}), 500
