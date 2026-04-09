"""
Tracking Service - Meta Pixel Functions
====================================
Serviço responsável pelo tracking de eventos do Meta Pixel.

✅ TRANSPLANTED: Funções completas do legado com PageView, ViewContent e Purchase
Adaptado para nova arquitetura com imports corretos.
"""

import time
import logging
import hashlib
import json
from datetime import datetime, timezone
from flask import request

logger = logging.getLogger(__name__)


def send_meta_pixel_pageview_event(pool, request, pageview_event_id=None, tracking_token=None):
    """
    Enfileira evento PageView para Meta Pixel (ASSÍNCRONO - MVP DIA 2)
    
    ARQUITETURA V4.0 - ASYNC (QI 540):
    - NÃO BLOQUEIA o redirect (< 5ms)
    - Enfileira evento no Celery
    - Worker processa em background
    - Retry persistente se falhar
    - ✅ RETORNA external_id e utm_data IMEDIATAMENTE
    
    CRÍTICO: Não espera resposta da Meta API
    
    Returns:
        tuple: (external_id, utm_data, pageview_context) para vincular eventos posteriores
    """
    try:
        # ✅ VERIFICAÇÃO 0: É crawler? (NÃO enviar PageView para crawlers)
        user_agent = request.headers.get('User-Agent', '')
        def is_crawler(ua: str) -> bool:
            """Detecta se o User-Agent é um crawler/bot"""
            if not ua:
                return False
            ua_lower = ua.lower()
            crawler_patterns = [
                'facebookexternalhit', 'facebot', 'telegrambot', 'whatsapp',
                'python-requests', 'curl', 'wget', 'bot', 'crawler', 'spider',
                'scraper', 'googlebot', 'bingbot', 'slurp', 'duckduckbot',
                'baiduspider', 'yandexbot', 'sogou', 'exabot', 'ia_archiver'
            ]
            return any(pattern in ua_lower for pattern in crawler_patterns)
        
        # 🔕 SERVER-SIDE PAGEVIEW DESATIVADO: manter apenas HTML (fbq) conforme política atual
        logger.info("🔕 PageView server-side desativado (HTML-only).")
        return None, {}, {}
        
        # ✅ VERIFICAÇÃO 1: Pool tem Meta Pixel configurado?
        if not pool.meta_tracking_enabled:
            return None, {}, {}
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            logger.warning(f"Pool {pool.id} tem tracking ativo mas sem pixel_id ou access_token")
            return None, {}, {}
        
        # ✅ VERIFICAÇÃO 2: Evento PageView está habilitado?
        if not pool.meta_events_pageview:
            logger.info(f"Evento PageView desabilitado para pool {pool.id}")
            return None, {}, {}
        
        # Importar helpers
        from utils.encryption import decrypt
        # FIXME: Implementar quando módulos estiverem disponíveis na nova arquitetura
        # from utils.meta_pixel import MetaPixelHelper
        # from utils.tracking_service import TrackingService, TrackingServiceV4
        # from utils.meta_pixel import process_meta_parameters, normalize_external_id, MetaPixelAPI
        # from utils.user_ip import get_user_ip, normalize_ip_to_ipv6
        
        # ✅ CORREÇÃO CRÍTICA: fbclid É o external_id para matching no Meta!
        grim_param = request.args.get('grim', '')
        fbclid_from_request = request.args.get('fbclid', '')
        
        # ✅ PRIORIDADE: fbclid como external_id (obrigatório para matching)
        external_id_raw = None
        if fbclid_from_request:
            external_id_raw = fbclid_from_request
            logger.info(f"🎯 TRACKING ELITE | Using fbclid as external_id: {external_id_raw[:30]}... (len={len(external_id_raw)})")
        elif grim_param:
            external_id_raw = grim_param
            logger.warning(f"⚠️ Sem fbclid, usando grim como external_id: {external_id_raw}")
        else:
            # FIXME: Implementar MetaPixelHelper.generate_external_id() quando disponível
            external_id_raw = None
            logger.warning(f"⚠️ Sem grim nem fbclid, external_id desabilitado na nova arquitetura")
        
        # ✅ CRÍTICO: Normalizar external_id para garantir matching consistente com Purchase/ViewContent
        # FIXME: Implementar normalize_external_id quando disponível
        external_id = external_id_raw
        
        event_id = pageview_event_id or f"pageview_{pool.id}_{int(time.time())}_{external_id_raw[:8] if external_id_raw else 'unknown'}"
        
        # Descriptografar access token
        try:
            # FIXME: Implementar decrypt quando disponível
            access_token = pool.meta_access_token  # Temporário - sem criptografia
        except Exception as e:
            logger.error(f"Erro ao processar access_token do pool {pool.id}: {e}")
            return None, {}, {}
        
        # Extrair UTM parameters
        # FIXME: Implementar MetaPixelHelper.extract_utm_params quando disponível
        utm_params = {}
        
        # ✅ SERVER-SIDE PARAMETER BUILDER: Processar cookies, request e headers
        # FIXME: Implementar process_meta_parameters quando disponível
        param_builder_result = {
            'fbp': None,
            'fbc': None,
            'client_ip_address': None,
            'ip_origin': None
        }
        
        fbp_value = param_builder_result.get('fbp')
        fbc_value = param_builder_result.get('fbc')
        fbc_origin = param_builder_result.get('fbc_origin')
        client_ip_from_builder = param_builder_result.get('client_ip_address')
        ip_origin = param_builder_result.get('ip_origin')
        
        # ✅ CAPTURAR DADOS PARA RETORNAR
        campaign_code_value = grim_param if grim_param else utm_params.get('code')
        
        utm_data = {
            'utm_source': utm_params.get('utm_source'),
            'utm_campaign': utm_params.get('utm_campaign'),
            'utm_content': utm_params.get('utm_content'),
            'utm_medium': utm_params.get('utm_medium'),
            'utm_term': utm_params.get('utm_term'),
            'fbclid': utm_params.get('fbclid'),
            'campaign_code': campaign_code_value
        }
        
        # ✅ ENFILEIRAR EVENTO (ASSÍNCRONO - NÃO BLOQUEIA!)
        # FIXME: Implementar send_meta_event quando disponível
        # Usar webhook queue existente no sistema
        try:
            from tasks_async import webhook_queue
            if webhook_queue:
                # Enfileirar diretamente com dados do evento
                webhook_queue.enqueue(
                    'send_meta_pixel_event',
                    pixel_id=pool.meta_pixel_id,
                    access_token=access_token,
                    event_data=event_data
                )
                logger.info(f"📤 Meta Pixel enfileirado via webhook queue: {event_id}")
            else:
                logger.warning(f"⚠️ Webhook queue indisponível - Meta Pixel não enfileirado")
        except ImportError:
            logger.warning(f"⚠️ Não foi possível importar webhook_queue - Meta Pixel não enfileirado")
        
        # logger.info(f"📤 PageView evento criado (sem enqueue na nova arquitetura): {event_id}")
        
        # ✅ CAPTURAR event_source_url para Purchase
        event_source_url = request.url if request.url else f'https://{request.host}/go/{pool.slug}'
        
        pageview_context = {
            'pageview_event_id': event_id,
            'fbp': fbp_value,
            'fbc': fbc_value,
            'client_ip': request.remote_addr,
            'client_user_agent': request.headers.get('User-Agent', ''),
            'event_source_url': event_source_url,
            'first_page': event_source_url,
            'tracking_token': tracking_token,
            'task_id': None
        }
        
        # ✅ RETORNAR IMEDIATAMENTE (não espera envio!)
        return external_id, utm_data, pageview_context
        
    except Exception as e:
        logger.error(f"💥 Erro ao enviar Meta PageView: {e}")
        return None, {}, {}


def send_meta_pixel_viewcontent_event(bot, bot_user, message, pool_id=None):
    """
    Envia evento ViewContent para Meta Pixel quando usuário inicia conversa com bot
    
    ARQUITETURA V3.0 (QI 540 - CORREÇÃO CRÍTICA):
    - Busca pixel do POOL ESPECÍFICO (passado via pool_id)
    - Se pool_id não fornecido, busca primeiro pool do bot (fallback)
    - Usa UTM e external_id salvos no BotUser
    - Alta disponibilidade: dados consolidados no pool
    - Tracking preciso mesmo com múltiplos bots
    
    CRÍTICO: Anti-duplicação via meta_viewcontent_sent flag
    
    Args:
        bot: Instância do Bot
        bot_user: Instância do BotUser
        message: Mensagem do Telegram
        pool_id: ID do pool específico (extraído do start param)
    """
    try:
        # ✅ VERIFICAÇÃO 1: Buscar pool associado ao bot
        # FIXME: Implementar quando modelos estiverem nova arquitetura
        pool = None  # Temporário - implementar busca real
        
        if not pool:
            logger.info(f"Bot não está associado a nenhum pool - Meta Pixel ignorado")
            return
        
        # ✅ VERIFICAÇÃO 2: Pool tem Meta Pixel configurado?
        if not pool.meta_tracking_enabled:
            return
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            logger.warning(f"Pool {pool.id} tem tracking ativo mas sem pixel_id ou access_token")
            return
        
        # ✅ VERIFICAÇÃO 3: Evento ViewContent está habilitado?
        if not pool.meta_events_viewcontent:
            logger.info(f"Evento ViewContent desabilitado para pool {pool.id}")
            return
        
        # ✅ VERIFICAÇÃO 4: Já enviou ViewContent para este usuário? (ANTI-DUPLICAÇÃO)
        if bot_user.meta_viewcontent_sent:
            logger.info(f"⚠️ ViewContent já enviado ao Meta, ignorando: BotUser {bot_user.id}")
            return
        
        logger.info(f"📊 Preparando envio Meta ViewContent: Pool {pool.id if pool else 'N/A'} | User {bot_user.telegram_user_id}")
        
        # Gerar event_id único para deduplicação
        # FIXME: Implementar MetaPixelAPI._generate_event_id quando disponível
        event_id = f"viewcontent_{pool.id if pool else 'unknown'}_{bot_user.telegram_user_id}_{int(time.time())}"
        
        # Descriptografar access token
        try:
            from utils.encryption import decrypt
            access_token = decrypt(pool.meta_access_token)  # Temporário - sem criptografia
        except Exception as e:
            logger.error(f"Erro ao processar access_token do pool {pool.id}: {e}")
            return
        
        # ✅ CRÍTICO V4.1: RECUPERAR DADOS COMPLETOS DO REDIS (MESMO DO PAGEVIEW!)
        # FIXME: Implementar TrackingServiceV4 quando disponível
        tracking_data = {}
        
        # ✅ PRIORIDADE 1: Recuperar do tracking_token (se disponível)
        if hasattr(bot_user, 'tracking_session_id') and bot_user.tracking_session_id:
            # FIXME: Implementar recover_tracking_data quando disponível
            tracking_data = {}  # Temporário
        
        # ✅ PRIORIDADE 2: Se não tem tracking_token, usar dados do BotUser (fallback)
        if not tracking_data:
            tracking_data = {
                'fbclid': getattr(bot_user, 'fbclid', None),
                'fbp': getattr(bot_user, 'fbp', None),
                'fbc': getattr(bot_user, 'fbc', None),
                'client_ip': getattr(bot_user, 'ip_address', None),
                'client_user_agent': getattr(bot_user, 'user_agent', None),
                'utm_source': getattr(bot_user, 'utm_source', None),
                'utm_campaign': getattr(bot_user, 'utm_campaign', None),
                'campaign_code': getattr(bot_user, 'campaign_code', None)
            }
            logger.info(f"✅ ViewContent - usando dados do BotUser (fallback)")
        
        # ✅ CRÍTICO: Construir user_data usando MetaPixelAPI._build_user_data() (MESMO DO PAGEVIEW!)
        # FIXME: Implementar normalize_external_id quando disponível
        external_id_raw = tracking_data.get('fbclid') or getattr(bot_user, 'fbclid', None)
        external_id_value = external_id_raw  # Temporário - sem normalização
        
        fbp_value = tracking_data.get('fbp') or getattr(bot_user, 'fbp', None)
        
        # ✅ CRÍTICO: Verificar fbc_origin para garantir que só enviamos fbc real
        fbc_value = None
        fbc_origin = tracking_data.get('fbc_origin')
        
        # ✅ PRIORIDADE 1: tracking_data com fbc (cookie OU generated_from_fbclid)
        if tracking_data.get('fbc') and fbc_origin in ('cookie', 'generated_from_fbclid'):
            fbc_value = tracking_data.get('fbc')
            logger.info(f"[META VIEWCONTENT] ViewContent - fbc recuperado do tracking_data (origem: {fbc_origin}): {fbc_value[:50]}...")
        # ✅ PRIORIDADE 2: BotUser (assumir que veio de cookie se foi salvo via process_start_async)
        elif bot_user and getattr(bot_user, 'fbc', None):
            fbc_value = bot_user.fbc
            logger.info(f"[META VIEWCONTENT] ViewContent - fbc recuperado do BotUser (assumido como real): {fbc_value[:50]}...")
        else:
            logger.warning(f"[META VIEWCONTENT] ViewContent - fbc ausente ou ignorado (origem: {fbc_origin or 'ausente'}) - Meta terá atribuição reduzida")
        
        # FIXME: Implementar MetaPixelAPI._build_user_data quando disponível
        user_data = {
            'customer_user_id': str(bot_user.telegram_user_id),
            'external_id': external_id_value,
            'email': None,
            'phone': None,
            'client_ip': tracking_data.get('client_ip') or getattr(bot_user, 'ip_address', None),
            'client_user_agent': tracking_data.get('client_user_agent') or getattr(bot_user, 'user_agent', None),
            'fbp': fbp_value,
            'fbc': fbc_value
        }
        
        # ✅ Construir custom_data (filtrar None/vazios)
        custom_data = {
            'content_type': 'product'
        }
        if pool and pool.id:
            custom_data['content_ids'] = [str(pool.id)]
        if pool and pool.name:
            custom_data['content_name'] = pool.name
        if bot and bot.id:
            custom_data['bot_id'] = bot.id
        if bot and bot.username:
            custom_data['bot_username'] = bot.username
        if tracking_data.get('utm_source') or getattr(bot_user, 'utm_source', None):
            custom_data['utm_source'] = tracking_data.get('utm_source') or getattr(bot_user, 'utm_source', None)
        if tracking_data.get('utm_campaign') or getattr(bot_user, 'utm_campaign', None):
            custom_data['utm_campaign'] = tracking_data.get('utm_campaign') or getattr(bot_user, 'utm_campaign', None)
        if tracking_data.get('campaign_code') or getattr(bot_user, 'campaign_code', None):
            custom_data['campaign_code'] = tracking_data.get('campaign_code') or getattr(bot_user, 'campaign_code', None)
        
        # ✅ CRÍTICO: event_source_url (mesmo do PageView)
        event_source_url = tracking_data.get('event_source_url') or tracking_data.get('first_page')
        if not event_source_url and pool and hasattr(pool, 'slug'):
            event_source_url = f'https://app.grimbots.online/go/{pool.slug}'
        
        # ✅ ENFILEIRAR EVENTO VIEWCONTENT (ASSÍNCRONO - MVP DIA 2)
        # Usar webhook queue existente no sistema
        try:
            from tasks_async import webhook_queue
            if webhook_queue:
                # Enfileirar diretamente com dados do evento
                webhook_queue.enqueue(
                    'send_meta_pixel_event',
                    pixel_id=pool.meta_pixel_id,
                    access_token=access_token,
                    event_data=event_data
                )
                logger.info(f"📤 ViewContent Meta Pixel enfileirado via webhook queue: {event_id}")
            else:
                logger.warning(f"⚠️ Webhook queue indisponível - ViewContent Meta Pixel não enfileirado")
        except ImportError:
            logger.warning(f"⚠️ Não foi possível importar webhook_queue - ViewContent Meta Pixel não enfileirado")
        
        # Marcar como enviado IMEDIATAMENTE (flag otimista)
        bot_user.meta_viewcontent_sent = True
        # FIXME: Implementar meta_viewcontent_sent_at quando disponível
        # bot_user.meta_viewcontent_sent_at = get_brazil_time()
        # db.session.commit()
        
        logger.info(f"📤 ViewContent preparado: Pool {pool.name if pool else 'N/A'} | "
                   f"User {bot_user.telegram_user_id} | "
                   f"Event ID: {event_id}")
    
    except Exception as e:
        logger.error(f"💥 Erro ao enviar Meta ViewContent: {e}")
        # Não impedir o funcionamento do bot se Meta falhar


def send_meta_pixel_purchase_event(payment):
    """
    Purchase server-side only (sem early-return antes do enqueue).
    
    Regras:
    - event_id: payment.pageview_event_id > payment.meta_event_id > tracking_data.pageview_event_id > evt_{tracking_token}
    - event_time: int(payment.created_at.timestamp())
    - Se pageview_sent ausente/False -> enqueue com countdown=1s; senão enqueue imediato
    - meta_event_id persistido antes do enqueue; meta_purchase_sent somente após enqueue OK
    - Não bloqueio por ausência de UTMs/IP/UA; apenas logar
    
    NOTA: Atualmente DESATIVADO - Purchase é disparado apenas no /delivery (HTML-only)
    """
    import hashlib
    import json
    from datetime import datetime, timezone
    
    # 🔕 SERVER-SIDE PURCHASE DESATIVADO: política HTML-only
    logger.info(f"🔕 [META PURCHASE] Server-side desativado (HTML-only) | payment_id={getattr(payment, 'id', None)}")
    return False
    
    # FIXME: Implementar lógica completa quando módulos de suporte estiverem nova arquitetura
    """
    # Pool/pixel (não bloquear)
    # FIXME: Implementar busca quando modelos estiverem nova arquitetura
    pool = None
    pixel_id = None
    access_token = None
    
    telegram_user_id = str(payment.customer_user_id).replace("user_", "") if payment.customer_user_id else None
    # FIXME: Implementar busca quando modelos estiverem nova arquitetura
    bot_user = None
    
    # Tracking data (prioridade: bot_user.tracking_session_id -> payment.tracking_token -> tracking:payment -> fallback payment)
    tracking_data = {}
    tracking_token_used = None
    
    # FIXME: Implementar TrackingServiceV4 quando disponível
    if bot_user and hasattr(bot_user, 'tracking_session_id') and bot_user.tracking_session_id:
        tracking_data = {}  # Temporário
        tracking_token_used = bot_user.tracking_session_id
    
    if not tracking_data:
        tracking_data = {
            "tracking_token": getattr(payment, "tracking_token", None),
            "pageview_event_id": getattr(payment, "pageview_event_id", None),
            "fbclid": getattr(payment, "fbclid", None),
            "fbp": getattr(payment, "fbp", None),
            "fbc": getattr(payment, "fbc", None),
            "client_ip": getattr(payment, "client_ip", None),
            "client_user_agent": getattr(payment, "client_user_agent", None),
            "utm_source": getattr(payment, "utm_source", None),
            "utm_campaign": getattr(payment, "utm_campaign", None),
            "campaign_code": getattr(payment, "campaign_code", None),
            "event_source_url": getattr(payment, "event_source_url", None),
            "first_page": getattr(payment, "first_page", None),
            "pageview_sent": False,
        }
        if not tracking_data.get("tracking_token") and getattr(payment, "tracking_token", None):
            tracking_data["tracking_token"] = payment.tracking_token
    
    # event_id exclusivo para Purchase (não reutilizar PageView)
    purchase_event_id = f"purchase_{payment.id}"
    
    # Persistir event_id exclusivo antes do enqueue
    if getattr(payment, "meta_event_id", None) != purchase_event_id:
        payment.meta_event_id = purchase_event_id
        # FIXME: Implementar commit quando modelos estiverem nova arquitetura
        # db.session.commit()
    
    # event_time
    event_time = int(payment.created_at.timestamp()) if getattr(payment, "created_at", None) else int(time.time())
    
    # Matching data (fallbacks, sem bloqueio)
    client_ip = (
        tracking_data.get("client_ip")
        or tracking_data.get("ip")
        or getattr(payment, "client_ip", None)
        or (bot_user.ip_address if bot_user else None)
    )
    client_user_agent = (
        tracking_data.get("client_user_agent")
        or tracking_data.get("ua")
        or getattr(payment, "client_user_agent", None)
        or (bot_user.user_agent if bot_user else None)
    )
    fbp_value = tracking_data.get("fbp") or getattr(payment, "fbp", None) or (bot_user.fbp if bot_user else None)
    fbc_value = tracking_data.get("fbc") or getattr(payment, "fbc", None) or (bot_user.fbc if bot_user else None)
    utm_source = tracking_data.get("utm_source") or getattr(payment, "utm_source", None) or (bot_user.utm_source if bot_user else None)
    campaign_code = tracking_data.get("campaign_code") or getattr(payment, "campaign_code", None) or (bot_user.campaign_code if bot_user else None)
    
    # Stable external_id para matching consistente
    stable_external_id = None
    if payment.customer_user_id:
        stable_external_id = hashlib.sha256(str(payment.customer_user_id).encode("utf-8")).hexdigest()
    elif bot_user and hasattr(bot_user, "id", None):
        stable_external_id = hashlib.sha256(str(bot_user.id).encode("utf-8")).hexdigest()
    
    # FIXME: Implementar MetaPixelAPI quando disponível
    user_data = {
        'customer_user_id': str(payment.customer_user_id) if payment.customer_user_id else None,
        'external_id': stable_external_id,
        'email': getattr(payment, "customer_email", None) or (bot_user.email if bot_user else None),
        'phone': "".join(filter(str.isdigit, str(getattr(payment, "customer_phone", None) or (bot_user.phone if bot_user else ""))))) or None,
        'client_ip': client_ip,
        'client_user_agent': client_user_agent,
        'fbp': fbp_value,
        'fbc': fbc_value
    }
    
    if not user_data.get("external_id") and stable_external_id:
        user_data["external_id"] = [stable_external_id]
    
    # event_source_url
    event_source_url = (
        tracking_data.get("event_source_url")
        or tracking_data.get("page_url")
        or tracking_data.get("first_page")
        or getattr(payment, "click_context_url", None)
    )
    if not event_source_url and pool and hasattr(pool, "slug"):
        event_source_url = f"https://app.grimbots.online/go/{pool.slug}"
    else:
        event_source_url = f"https://t.me/{payment.bot.username}"
    
    custom_data = {
        "value": float(payment.amount),
        "currency": getattr(payment, "currency", None) or "BRL",
    }
    if campaign_code:
        custom_data["campaign_code"] = campaign_code
    
    event_data = {
        "event_name": "Purchase",
        "event_time": event_time,
        "event_id": purchase_event_id,
        "action_source": "website",
        "event_source_url": event_source_url,
        "user_data": user_data,
        "custom_data": custom_data,
    }
    
    # FIXME: Implementar enqueue quando Celery estiver em nova arquitetura
    # Usar webhook queue existente no sistema
    try:
        from tasks_async import webhook_queue
        if webhook_queue:
            # Enfileirar diretamente com dados do evento
            webhook_queue.enqueue(
                'send_meta_pixel_event',
                pixel_id=pixel_id,
                access_token=access_token,
                event_data=event_data
            )
            logger.info(f"📤 Purchase Meta Pixel enfileirado via webhook queue: {purchase_event_id}")
        else:
            logger.warning(f"⚠️ Webhook queue indisponível - Purchase Meta Pixel não enfileirado")
    except ImportError:
        logger.warning(f"⚠️ Não foi possível importar webhook_queue - Purchase Meta Pixel não enfileirado")
    
    # FIXME: Implementar meta_purchase_sent quando modelos estiverem nova arquitetura
    # payment.meta_purchase_sent = True
    # payment.meta_purchase_sent_at = get_brazil_time()
    # db.session.commit()
    
    return False
"""

import logging
import json
import uuid
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class TrackingService:
    """
    📊 Serviço de Tracking Profissional (Meta CAPI)
    
    Integra com Meta Conversions API para:
    - PageView: Rastreamento de visualizações de página
    - ViewContent: Interesse no conteúdo
    - Purchase: Conversões de venda
    
    Todos os eventos são enviados de forma assíncrona via Celery/RQ.
    """
    
    # Meta CAPI Endpoint
    META_CAPI_URL = "https://graph.facebook.com/v18.0/{pixel_id}/events"
    
    def __init__(self):
        """Inicializa conexão com Redis"""
        try:
            import redis
            from internal_logic.core.extensions import limiter
            # Usar mesma conexão Redis do limiter
            redis_url = limiter.storage_uri if hasattr(limiter, 'storage_uri') else 'redis://localhost:6379/0'
            self.redis = redis.from_url(redis_url, decode_responses=True)
            logger.info(" TrackingService - Conectado ao Redis")
        except Exception as e:
            logger.error(f" TrackingService - Erro ao conectar Redis: {e}")
            self.redis = None
    
    def recover_tracking_data(self, tracking_token: str):
        """Recupera dados completos de tracking do Redis"""
        try:
            if not tracking_token:
                return None
                
            if not self.redis:
                logger.error(" TrackingService - Redis não disponível")
                return None
            
            key = f"tracking:{tracking_token}"
            data = self.redis.get(key)
            
            if data:
                tracking_data = json.loads(data)
                logger.info(f"[TRACKING_SERVICE] Dados recuperados para token {tracking_token[:8]}...")
                return tracking_data
                
            return None
            
        except Exception as e:
            logger.error(f"[TRACKING_SERVICE] Erro ao recuperar dados de tracking: {e}")
            return None
    
    @classmethod
    def fire_pageview(cls, pool, request, async_mode: bool = True) -> Optional[str]:
        """
        🔥 Dispara evento PageView para Meta Pixel/CAPI
        
        Args:
            pool: Instância de RedirectPool
            request: Objeto request do Flask
            async_mode: Se True, envia via task assíncrona
            
        Returns:
            str: event_id para tracking
        """
        try:
            if not pool.meta_tracking_enabled or not pool.meta_pixel_id:
                return None
            
            event_id = cls._generate_event_id()
            
            payload = {
                'event_name': 'PageView',
                'event_id': event_id,
                'event_time': int(datetime.now().timestamp()),
                'action_source': 'website',
                'user_data': cls._extract_user_data(request),
                'custom_data': {
                    'content_name': pool.name,
                    'content_ids': [pool.slug],
                    'content_type': 'product_group'
                }
            }
            
            if async_mode:
                cls._send_event_async(pool.meta_pixel_id, pool.meta_access_token, payload)
            else:
                cls._send_event_sync(pool.meta_pixel_id, pool.meta_access_token, payload)
            
            logger.debug(f"📊 PageView fired: {event_id} for pool {pool.id}")
            return event_id
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao disparar PageView: {e}")
            return None
    
    @classmethod
    def fire_viewcontent(cls, pool, request, bot_id: int, async_mode: bool = True) -> Optional[str]:
        """
        🔥 Dispara evento ViewContent para Meta Pixel/CAPI
        
        Args:
            pool: Instância de RedirectPool
            request: Objeto request do Flask
            bot_id: ID do bot selecionado
            async_mode: Se True, envia via task assíncrona
            
        Returns:
            str: event_id para tracking
        """
        try:
            if not pool.meta_tracking_enabled or not pool.meta_pixel_id:
                return None
            
            event_id = cls._generate_event_id()
            
            payload = {
                'event_name': 'ViewContent',
                'event_id': event_id,
                'event_time': int(datetime.now().timestamp()),
                'action_source': 'website',
                'user_data': cls._extract_user_data(request),
                'custom_data': {
                    'content_name': f"Bot {bot_id}",
                    'content_ids': [f"bot_{bot_id}"],
                    'content_type': 'product',
                    'value': 0.0,
                    'currency': 'BRL'
                }
            }
            
            if async_mode:
                cls._send_event_async(pool.meta_pixel_id, pool.meta_access_token, payload)
            else:
                cls._send_event_sync(pool.meta_pixel_id, pool.meta_access_token, payload)
            
            logger.debug(f"📊 ViewContent fired: {event_id} for bot {bot_id}")
            return event_id
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao disparar ViewContent: {e}")
            return None
    
    @classmethod
    def fire_purchase(cls, pool, request, value: float, currency: str = 'BRL', 
                      order_id: Optional[str] = None, async_mode: bool = True) -> Optional[str]:
        """
        🔥 Dispara evento Purchase para Meta Pixel/CAPI
        
        Args:
            pool: Instância de RedirectPool
            request: Objeto request do Flask
            value: Valor da compra
            currency: Moeda (default: BRL)
            order_id: ID do pedido
            async_mode: Se True, envia via task assíncrona
            
        Returns:
            str: event_id para tracking
        """
        try:
            if not pool.meta_tracking_enabled or not pool.meta_pixel_id:
                return None
            
            event_id = cls._generate_event_id()
            
            payload = {
                'event_name': 'Purchase',
                'event_id': event_id,
                'event_time': int(datetime.now().timestamp()),
                'action_source': 'website',
                'user_data': cls._extract_user_data(request),
                'custom_data': {
                    'content_name': pool.name,
                    'content_ids': [pool.slug],
                    'content_type': 'product_group',
                    'value': float(value),
                    'currency': currency,
                    'order_id': order_id or str(uuid.uuid4())[:8]
                }
            }
            
            if async_mode:
                cls._send_event_async(pool.meta_pixel_id, pool.meta_access_token, payload)
            else:
                cls._send_event_sync(pool.meta_pixel_id, pool.meta_access_token, payload)
            
            logger.info(f"💰 Purchase fired: {event_id} - R$ {value}")
            return event_id
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao disparar Purchase: {e}")
            return None
    
    @classmethod
    def _extract_user_data(cls, request) -> Dict[str, Any]:
        """Extrai dados do usuário de forma segura para CAPI"""
        user_data = {}
        
        # Client IP
        client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', '')
        if client_ip:
            # Hash SHA256 do IP (conforme requisitos do Meta CAPI)
            user_data['client_ip_address'] = cls._hash_sha256(client_ip)
        
        # User Agent
        user_agent = request.headers.get('User-Agent', '')
        if user_agent:
            user_data['client_user_agent'] = cls._hash_sha256(user_agent)
        
        # FBCLID (Facebook Click ID) - se presente
        fbclid = request.args.get('fbclid', '')
        if fbclid:
            user_data['fbc'] = f"fb.1.{int(datetime.now().timestamp())}.{fbclid}"
        
        # FBP (Browser ID) - se presente no cookie
        fbp = request.cookies.get('_fbp', '')
        if fbp:
            user_data['fbp'] = fbp
        
        return user_data
    
    @classmethod
    def _hash_sha256(cls, value: str) -> str:
        """Hash SHA256 para dados sensíveis (CAPI compliance)"""
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
    
    @classmethod
    def _generate_event_id(cls) -> str:
        """Gera ID único para deduplicação de eventos"""
        return str(uuid.uuid4())
    
    @classmethod
    def _send_event_async(cls, pixel_id: str, access_token: str, payload: Dict):
        """Envia evento de forma assíncrona via RQ/Celery"""
        try:
            from tasks_async import send_meta_capi_event
            send_meta_capi_event.delay(pixel_id, access_token, payload)
        except ImportError:
            # Fallback para envio síncrono se task não disponível
            cls._send_event_sync(pixel_id, access_token, payload)
        except Exception as e:
            logger.warning(f"⚠️ Falha ao enfileirar evento: {e}")
    
    @classmethod
    def _send_event_sync(cls, pixel_id: str, access_token: str, payload: Dict):
        """Envia evento de forma síncrona (fallback)"""
        try:
            url = cls.META_CAPI_URL.format(pixel_id=pixel_id)
            
            data = {
                'data': [payload],
                'access_token': access_token
            }
            
            # Enviar com timeout curto (não bloquear redirect)
            response = requests.post(
                url,
                json=data,
                timeout=2.0,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.debug(f"📊 Evento enviado: {payload.get('event_name')}")
            else:
                logger.warning(f"⚠️ Meta CAPI retornou {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao enviar evento: {e}")
