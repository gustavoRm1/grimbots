# ============================================================================
# LEGACY TRACKING LOGIC - EXTRAÇÃO DO CÓDIGO LEGADO (STAGING)
# Arquivo: _legacy_exports/legacy_tracking_logic.py
# Origem: app_legacy.py e botmanager.py
# ============================================================================
# Este arquivo contém as funções EXATAS de tracking do Meta Pixel
# NÃO MODIFICAR - Apenas para referência durante migração
# ============================================================================

import time
import logging
from flask import request

logger = logging.getLogger(__name__)


# ============================================================================
# 1. send_meta_pixel_pageview_event
# Origem: app_legacy.py (linhas ~10649-11053)
# ============================================================================

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
        from utils.meta_pixel import MetaPixelHelper
        from utils.encryption import decrypt
        from utils.tracking_service import TrackingService, TrackingServiceV4
        from utils.meta_pixel import process_meta_parameters, normalize_external_id, MetaPixelAPI
        from utils.user_ip import get_user_ip, normalize_ip_to_ipv6
        
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
            external_id_raw = MetaPixelHelper.generate_external_id()
            logger.warning(f"⚠️ Sem grim nem fbclid, usando external_id sintético: {external_id_raw}")
        
        # ✅ CRÍTICO: Normalizar external_id para garantir matching consistente com Purchase/ViewContent
        external_id = normalize_external_id(external_id_raw)
        if external_id != external_id_raw:
            logger.info(f"✅ PageView - external_id normalizado: {external_id} (original len={len(external_id_raw)})")
        else:
            logger.info(f"✅ PageView - external_id usado original: {external_id[:30]}... (len={len(external_id)})")
        
        event_id = pageview_event_id or f"pageview_{pool.id}_{int(time.time())}_{external_id[:8] if external_id else 'unknown'}"
        
        # Descriptografar access token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            logger.error(f"Erro ao descriptografar access_token do pool {pool.id}: {e}")
            return None, {}, {}
        
        # Extrair UTM parameters
        utm_params = MetaPixelHelper.extract_utm_params(request)
        
        # ✅ CRÍTICO V4.1: Recuperar tracking_data do Redis ANTES de usar
        tracking_service_v4 = TrackingServiceV4()
        
        # ✅ GARANTIR que tracking_data está SEMPRE inicializado (evita NameError)
        tracking_data = {}
        if tracking_token:
            try:
                tracking_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
                if tracking_data:
                    logger.info(f"✅ PageView - tracking_data recuperado do Redis: {len(tracking_data)} campos")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao recuperar tracking_data do Redis: {e}")
                tracking_data = {}
        
        # ✅ VALIDAÇÃO: Garantir que tracking_data está no escopo (debug)
        if 'tracking_data' not in locals():
            logger.error(f"❌ CRÍTICO: tracking_data não está no escopo local!")
            tracking_data = {}
        
        # ✅ SERVER-SIDE PARAMETER BUILDER: Processar cookies, request e headers
        param_builder_result = process_meta_parameters(
            request_cookies=dict(request.cookies),
            request_args=dict(request.args),
            request_headers=dict(request.headers),
            request_remote_addr=request.remote_addr,
            referer=request.headers.get('Referer')
        )
        
        # ✅ PRIORIDADE: Parameter Builder > tracking_data (Redis) > cookie direto
        fbp_value = param_builder_result.get('fbp')
        fbc_value = param_builder_result.get('fbc')
        fbc_origin = param_builder_result.get('fbc_origin')
        client_ip_from_builder = param_builder_result.get('client_ip_address')
        ip_origin = param_builder_result.get('ip_origin')
        
        # ✅ LOG: Mostrar origem dos parâmetros processados pelo Parameter Builder
        if fbp_value:
            logger.info(f"[META PAGEVIEW] PageView - fbp processado pelo Parameter Builder (origem: {param_builder_result.get('fbp_origin')}): {fbp_value[:30]}...")
        else:
            logger.warning(f"[META PAGEVIEW] PageView - fbp NÃO retornado pelo Parameter Builder (cookie _fbp ausente)")
        
        if fbc_value and fbc_origin != 'generated_from_fbclid':
            logger.info(f"[META PAGEVIEW] PageView - fbc processado pelo Parameter Builder (origem: {fbc_origin}): {fbc_value[:50]}...")
        elif fbc_origin == 'generated_from_fbclid':
            logger.info("[META PAGEVIEW] PageView - fbc gerado do fbclid IGNORADO (regra canônica: não regenerar)")
            fbc_value = None
            fbc_origin = None
        else:
            # ✅ DEBUG: Verificar por que fbc não foi retornado
            fbclid_in_args = request.args.get('fbclid', '').strip()
            fbc_in_cookies = request.cookies.get('_fbc', '').strip()
            logger.warning(f"[META PAGEVIEW] PageView - fbc NÃO retornado pelo Parameter Builder")
            logger.warning(f"   Cookie _fbc: {'✅ Presente' if fbc_in_cookies else '❌ Ausente'}")
            logger.warning(f"   fbclid na URL: {'✅ Presente' if fbclid_in_args else '❌ Ausente'} (len={len(fbclid_in_args)})")
            if fbclid_in_args:
                logger.warning(f"   fbclid valor: {fbclid_in_args[:50]}...")
        
        if client_ip_from_builder:
            logger.info(f"[META PAGEVIEW] PageView - client_ip processado pelo Parameter Builder (origem: {ip_origin}): {client_ip_from_builder}")
        else:
            logger.warning(f"[META PAGEVIEW] PageView - client_ip NÃO retornado pelo Parameter Builder (cookie _fbi ausente)")
        
        # ✅ FALLBACK: Se Parameter Builder não retornou valores válidos, tentar tracking_data (Redis)
        if not fbp_value and tracking_data:
            fbp_value = tracking_data.get('fbp') or None
            if fbp_value:
                logger.info(f"[META PAGEVIEW] PageView - fbp recuperado do tracking_data (Redis - fallback): {fbp_value[:30]}...")
        
        if not fbc_value and tracking_data:
            fbc_value = tracking_data.get('fbc') or None
            fbc_origin = tracking_data.get('fbc_origin')
            if fbc_value:
                logger.info(f"[META PAGEVIEW] PageView - fbc recuperado do tracking_data (Redis - fallback): {fbc_value[:50]}...")
        
        # ✅ CRÍTICO V4.1: Validar fbc_origin para garantir que só enviamos fbc real
        if fbc_value and fbc_origin == 'synthetic':
            logger.warning(f"[META PAGEVIEW] PageView - fbc IGNORADO (origem: synthetic) - Meta não atribui com fbc sintético")
            fbc_value = None
            fbc_origin = None
        
        # ✅ FALLBACK FINAL: FBP - Gerar se ainda não tiver (apenas se não for crawler)
        if not fbp_value and not is_crawler(request.headers.get('User-Agent', '')):
            fbp_value = TrackingService.generate_fbp()
            logger.info(f"[META PAGEVIEW] PageView - fbp gerado no servidor (fallback final): {fbp_value[:30]}...")
        
        # ✅ LOG FINAL: Mostrar resultado final
        if fbc_value:
            if fbc_origin == 'cookie':
                logger.info(f"[META PAGEVIEW] PageView - fbc REAL confirmado (origem: cookie): {fbc_value[:50]}...")
            elif fbc_origin == 'generated_from_fbclid':
                logger.info(f"[META PAGEVIEW] PageView - fbc gerado conforme Meta best practices (origem: generated_from_fbclid): {fbc_value[:50]}...")
            else:
                logger.info(f"[META PAGEVIEW] PageView - fbc confirmado (origem: {fbc_origin}): {fbc_value[:50]}...")
        else:
            logger.warning(f"[META PAGEVIEW] PageView - fbc ausente após processamento - Meta pode ter atribuição reduzida")
        
        # ✅ CORREÇÃO SÊNIOR QI 500: Salvar tracking no Redis SEMPRE se external_id existir (garante matching!)
        if external_id:
            try:
                ip_address_to_save = client_ip_from_builder if client_ip_from_builder else get_user_ip(request)
                
                TrackingService.save_tracking_data(
                    fbclid=external_id,
                    fbp=fbp_value,
                    fbc=fbc_value,
                    ip_address=ip_address_to_save,
                    user_agent=request.headers.get('User-Agent', ''),
                    grim=grim_param,
                    utms=utm_params
                )
                if fbp_value:
                    logger.info(f"✅ PageView - fbp do browser salvo no Redis para Purchase: {fbp_value[:30]}...")
                else:
                    logger.info(f"✅ PageView - tracking salvo no Redis (fbp ausente, será gerado pelo browser)")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao salvar tracking no Redis: {e}")
        
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
        
        # ============================================================================
        # ✅ ENFILEIRAR EVENTO (ASSÍNCRONO - NÃO BLOQUEIA!)
        # ============================================================================
        from celery_app import send_meta_event
        
        # ✅ CORREÇÃO SÊNIOR QI 500: SEMPRE usar external_id normalizado (garante matching com Purchase!)
        external_id_for_hash = external_id
        
        # ✅ CRÍTICO: Usar _build_user_data com external_id string (será hashado internamente)
        if client_ip_from_builder:
            client_ip = normalize_ip_to_ipv6(client_ip_from_builder) if client_ip_from_builder else None
        else:
            client_ip = get_user_ip(request, normalize_to_ipv6=True)
        
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=None,
            external_id=external_id_for_hash,
            email=None,
            phone=None,
            client_ip=client_ip,
            client_user_agent=request.headers.get('User-Agent', ''),
            fbp=fbp_value,
            fbc=fbc_value
        )
        
        # ✅ CRÍTICO: Garantir que external_id existe (obrigatório para Conversions API)
        if not user_data.get('external_id'):
            if external_id:
                user_data['external_id'] = [MetaPixelAPI._hash_data(external_id)]
                logger.warning(f"⚠️ PageView - external_id forçado no user_data (não deveria acontecer): {external_id} (len={len(external_id)})")
                logger.info(f"✅ PageView - MATCH GARANTIDO com Purchase (mesmo external_id normalizado)")
            elif grim_param:
                user_data['external_id'] = [MetaPixelAPI._hash_data(grim_param)]
                logger.warning(f"⚠️ PageView - external_id (grim) forçado no user_data: {grim_param[:30]}...")
            else:
                fallback_external_id = MetaPixelHelper.generate_external_id()
                user_data['external_id'] = [MetaPixelAPI._hash_data(fallback_external_id)]
                logger.error(f"❌ PageView - External ID não encontrado, usando fallback: {fallback_external_id}")
                logger.error(f"❌ PageView - Isso quebra matching com Purchase! Verifique se fbclid está sendo capturado corretamente.")
        
        # ✅ LOG CRÍTICO: Mostrar dados enviados para matching (quantidade de atributos)
        external_ids = user_data.get('external_id', [])
        attributes_count = sum([
            1 if external_ids else 0,
            1 if user_data.get('em') else 0,
            1 if user_data.get('ph') else 0,
            1 if user_data.get('client_ip_address') else 0,
            1 if user_data.get('client_user_agent') else 0,
            1 if user_data.get('fbp') else 0,
            1 if user_data.get('fbc') else 0
        ])
        
        fbp_status = '✅' if user_data.get('fbp') else '❌'
        if not user_data.get('fbp'):
            logger.error(f"❌ PageView - fbp AUSENTE (CRÍTICO para funil server-side!)")
            logger.error(f"   Isso quebra matching PageView ↔ Purchase e gera eventos órfãos")
        
        if attributes_count < 5:
            logger.warning(f"⚠️ PageView com apenas {attributes_count}/7 atributos - Match Quality pode ser baixa")
        elif attributes_count == 7:
            logger.info(f"✅ PageView com 7/7 atributos - Match Quality MÁXIMA garantida!")
        
        logger.info(f"🔍 Meta PageView - User Data: {attributes_count}/7 atributos | " +
                   f"external_id={'✅' if external_ids else '❌'} [{external_ids[0][:16] if external_ids else 'N/A'}...] | " +
                   f"fbp={fbp_status} | " +
                   f"fbc={'✅' if user_data.get('fbc') else '❌'} | " +
                   f"ip={'✅' if user_data.get('client_ip_address') else '❌'} | " +
                   f"ua={'✅' if user_data.get('client_user_agent') else '❌'}")
        
        # ✅ CRÍTICO: event_source_url deve apontar para URL do redirecionador
        event_source_url = request.url if request.url else f'https://{request.host}/go/{pool.slug}'
        
        # ✅ CORREÇÃO V4.1: Filtrar valores None/vazios do custom_data
        custom_data = {}
        if pool.id:
            custom_data['pool_id'] = pool.id
        if pool.name:
            custom_data['pool_name'] = pool.name
        if utm_data.get('utm_source'):
            custom_data['utm_source'] = utm_data['utm_source']
        if utm_data.get('utm_campaign'):
            custom_data['utm_campaign'] = utm_data['utm_campaign']
        if utm_data.get('utm_content'):
            custom_data['utm_content'] = utm_data['utm_content']
        if utm_data.get('utm_medium'):
            custom_data['utm_medium'] = utm_data['utm_medium']
        if utm_data.get('utm_term'):
            custom_data['utm_term'] = utm_data['utm_term']
        if utm_data.get('fbclid'):
            custom_data['fbclid'] = utm_data.get('fbclid')
        if utm_data.get('campaign_code'):
            custom_data['campaign_code'] = utm_data.get('campaign_code')
        
        # ✅ CORREÇÃO META: event_time = timestamp real do PageView (pageview_ts)
        pageview_ts = tracking_data.get('pageview_ts') if tracking_data else None
        event_time = pageview_ts if pageview_ts else int(time.time())

        event_data = {
            'event_name': 'PageView',
            'event_time': event_time,
            'event_id': event_id,
            'action_source': 'website',
            'event_source_url': event_source_url,
            'user_data': user_data,
            'custom_data': custom_data
        }
        
        # ✅ ENFILEIRAR (NÃO ESPERA RESPOSTA)
        task = send_meta_event.delay(
            pixel_id=pool.meta_pixel_id,
            access_token=access_token,
            event_data=event_data,
            test_code=pool.meta_test_event_code
        )
        
        logger.info(f"📤 PageView enfileirado: Pool {pool.id} | Event ID: {event_id} | Task: {task.id}")
        
        # ✅ CRÍTICO: Capturar event_source_url para Purchase
        event_source_url = request.url or f'https://app.grimbots.online/go/{pool.slug}'
        
        pageview_context = {
            'pageview_event_id': event_id,
            'fbp': fbp_value,
            'fbc': fbc_value,
            'client_ip': get_user_ip(request),
            'client_user_agent': request.headers.get('User-Agent', ''),
            'event_source_url': event_source_url,
            'first_page': event_source_url,
            'tracking_token': tracking_token,
            'task_id': task.id if task else None
        }
        
        # ✅ RETORNAR IMEDIATAMENTE (não espera envio!)
        return external_id, utm_data, pageview_context
        
    except Exception as e:
        logger.error(f"💥 Erro ao enviar Meta PageView: {e}")
        return None, {}, {}


# ============================================================================
# 2. send_meta_pixel_viewcontent_event  
# Origem: botmanager.py (linhas ~152-394)
# ============================================================================

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
        from internal_logic.core.models import PoolBot, RedirectPool
        
        # Se pool_id foi passado, buscar pool específico
        if pool_id:
            pool_bot = PoolBot.query.filter_by(bot_id=bot.id, pool_id=pool_id).first()
            if not pool_bot:
                logger.warning(f"Bot {bot.id} não está no pool {pool_id} especificado - tentando fallback")
                pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        else:
            # Fallback: buscar primeiro pool do bot
            pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        
        if not pool_bot:
            logger.info(f"Bot {bot.id} não está associado a nenhum pool - Meta Pixel ignorado")
            return
        
        pool = pool_bot.pool
        
        logger.info(f"📊 Pool selecionado para ViewContent: {pool.id} ({pool.name}) | " +
                   f"pool_id_param={pool_id} | bot_id={bot.id}")
        
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
        
        logger.info(f"📊 Preparando envio Meta ViewContent: Pool {pool.name} | User {bot_user.telegram_user_id}")
        
        # Importar Meta Pixel API
        from utils.meta_pixel import MetaPixelAPI
        from utils.encryption import decrypt
        from utils.tracking_service import TrackingServiceV4
        from internal_logic.core.extensions import db
        from internal_logic.core.models import get_brazil_time
        
        # Gerar event_id único para deduplicação
        event_id = MetaPixelAPI._generate_event_id(
            event_type='viewcontent',
            unique_id=f"{pool.id}_{bot_user.telegram_user_id}"
        )
        
        # Descriptografar access token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            logger.error(f"Erro ao descriptografar access_token do pool {pool.id}: {e}")
            return
        
        # ✅ CRÍTICO V4.1: RECUPERAR DADOS COMPLETOS DO REDIS (MESMO DO PAGEVIEW!)
        tracking_service_v4 = TrackingServiceV4()
        tracking_data = {}
        
        # ✅ PRIORIDADE 1: Recuperar do tracking_token (se disponível)
        if hasattr(bot_user, 'tracking_session_id') and bot_user.tracking_session_id:
            tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
            logger.info(f"✅ ViewContent - tracking_data recuperado do Redis: {len(tracking_data)} campos")
        
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
        from utils.meta_pixel import normalize_external_id
        
        # ✅ CORREÇÃO CRÍTICA: Normalizar external_id para garantir matching consistente com PageView/Purchase
        external_id_raw = tracking_data.get('fbclid') or getattr(bot_user, 'fbclid', None)
        external_id_value = normalize_external_id(external_id_raw) if external_id_raw else None
        if external_id_value != external_id_raw and external_id_raw:
            logger.info(f"✅ ViewContent - external_id normalizado: {external_id_value} (original len={len(external_id_raw)})")
            logger.info(f"✅ ViewContent - MATCH GARANTIDO com PageView/Purchase (mesmo algoritmo de normalização)")
        elif external_id_value:
            logger.info(f"✅ ViewContent - external_id usado original: {external_id_value[:30]}... (len={len(external_id_value)})")
        
        fbp_value = tracking_data.get('fbp') or getattr(bot_user, 'fbp', None)
        
        # ✅ CORREÇÃO CRÍTICA: Verificar fbc_origin para garantir que só enviamos fbc real (cookie)
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
        
        ip_value = tracking_data.get('client_ip') or getattr(bot_user, 'ip_address', None)
        ua_value = tracking_data.get('client_user_agent') or getattr(bot_user, 'user_agent', None)
        
        # ✅ Usar _build_user_data para garantir formato correto (hash SHA256, array external_id, etc)
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=str(bot_user.telegram_user_id),
            external_id=external_id_value,
            email=None,
            phone=None,
            client_ip=ip_value,
            client_user_agent=ua_value,
            fbp=fbp_value,
            fbc=fbc_value
        )
        
        # ✅ Construir custom_data (filtrar None/vazios)
        custom_data = {
            'content_type': 'product'
        }
        if pool.id:
            custom_data['content_ids'] = [str(pool.id)]
        if pool.name:
            custom_data['content_name'] = pool.name
        if bot.id:
            custom_data['bot_id'] = bot.id
        if bot.username:
            custom_data['bot_username'] = bot.username
        if tracking_data.get('utm_source') or getattr(bot_user, 'utm_source', None):
            custom_data['utm_source'] = tracking_data.get('utm_source') or getattr(bot_user, 'utm_source', None)
        if tracking_data.get('utm_campaign') or getattr(bot_user, 'utm_campaign', None):
            custom_data['utm_campaign'] = tracking_data.get('utm_campaign') or getattr(bot_user, 'utm_campaign', None)
        if tracking_data.get('campaign_code') or getattr(bot_user, 'campaign_code', None):
            custom_data['campaign_code'] = tracking_data.get('campaign_code') or getattr(bot_user, 'campaign_code', None)
        
        # ✅ CRÍTICO: event_source_url (mesmo do PageView)
        event_source_url = tracking_data.get('event_source_url') or tracking_data.get('first_page')
        if not event_source_url and pool.slug:
            event_source_url = f'https://app.grimbots.online/go/{pool.slug}'
        
        # ============================================================================
        # ✅ ENFILEIRAR EVENTO VIEWCONTENT (ASSÍNCRONO - MVP DIA 2)
        # ============================================================================
        from celery_app import send_meta_event
        
        event_data = {
            'event_name': 'ViewContent',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'event_source_url': event_source_url,
            'user_data': user_data,
            'custom_data': custom_data
        }
        
        # ✅ LOG: Verificar dados enviados
        external_ids = user_data.get('external_id', [])
        attributes_count = sum([
            1 if external_ids else 0,
            1 if user_data.get('em') else 0,
            1 if user_data.get('ph') else 0,
            1 if user_data.get('client_ip_address') else 0,
            1 if user_data.get('client_user_agent') else 0,
            1 if user_data.get('fbp') else 0,
            1 if user_data.get('fbc') else 0
        ])
        logger.info(f"[META VIEWCONTENT] ViewContent - User Data: {attributes_count}/7 atributos | " +
                   f"external_id={'✅' if external_ids else '❌'} | " +
                   f"fbp={'✅' if user_data.get('fbp') else '❌'} | " +
                   f"fbc={'✅' if user_data.get('fbc') else '❌'} | " +
                   f"ip={'✅' if user_data.get('client_ip_address') else '❌'} | " +
                   f"ua={'✅' if user_data.get('client_user_agent') else '❌'}")
        
        # ✅ ENFILEIRAR COM PRIORIDADE MÉDIA
        task = send_meta_event.apply_async(
            args=[
                pool.meta_pixel_id,
                access_token,
                event_data,
                pool.meta_test_event_code
            ],
            priority=5  # Média prioridade
        )
        
        # Marcar como enviado IMEDIATAMENTE (flag otimista)
        bot_user.meta_viewcontent_sent = True
        bot_user.meta_viewcontent_sent_at = get_brazil_time()
        
        # Commit da flag
        db.session.commit()
        
        logger.info(f"📤 ViewContent enfileirado: Pool {pool.name} | " +
                   f"User {bot_user.telegram_user_id} | " +
                   f"Event ID: {event_id} | " +
                   f"Task: {task.id} | " +
                   f"UTM: {bot_user.utm_source}/{bot_user.utm_campaign}")
    
    except Exception as e:
        logger.error(f"💥 Erro ao enviar Meta ViewContent: {e}")
        # Não impedir o funcionamento do bot se Meta falhar


# ============================================================================
# 3. send_meta_pixel_purchase_event
# Origem: app.py (linhas ~12200-12430)
# ============================================================================

def send_meta_pixel_purchase_event(payment):
    """
    Purchase server-side only (sem early-return antes do enqueue).
    
    Regras:
    - event_id: payment.pageview_event_id > payment.meta_event_id > tracking_data.pageview_event_id > evt_{tracking_token}
    - event_time: int(payment.created_at.timestamp())
    - Se pageview_sent ausente/False -> enqueue com countdown=1s; senão enqueue imediato
    - meta_event_id persistido antes do enqueue; meta_purchase_sent somente após enqueue OK
    - Não bloquear por ausência de UTMs/IP/UA; apenas logar
    
    NOTA: Atualmente DESATIVADO - Purchase é disparado apenas no /delivery (HTML-only)
    """
    import hashlib
    import json
    from internal_logic.core.models import PoolBot, get_brazil_time
    from utils.tracking_service import TrackingServiceV4
    from utils.meta_pixel import MetaPixelAPI
    from utils.encryption import decrypt
    from celery_app import send_meta_event
    from internal_logic.core.extensions import db
    from internal_logic.core.models import BotUser
    
    # 🔕 SERVER-SIDE PURCHASE DESATIVADO: política HTML-only
    logger.info(f"🔕 [META PURCHASE] Server-side desativado (HTML-only) | payment_id={getattr(payment, 'id', None)}")
    return False

    # Pool/pixel (não bloquear)
    pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
    pool = pool_bot.pool if pool_bot else None
    pixel_id = pool.meta_pixel_id if pool and pool.meta_pixel_id else None
    access_token = None
    if pool and pool.meta_access_token:
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            logger.warning(f"[META PURCHASE] Falha ao descriptografar access_token: {e}")

    telegram_user_id = str(payment.customer_user_id).replace("user_", "") if payment.customer_user_id else None
    bot_user = BotUser.query.filter_by(bot_id=payment.bot_id, telegram_user_id=str(telegram_user_id)).first() if telegram_user_id else None

    # Tracking data (prioridade: bot_user.tracking_session_id -> payment.tracking_token -> tracking:payment -> fallback payment)
    tracking_data = {}
    tracking_token_used = None
    tsv4 = TrackingServiceV4()
    if bot_user and bot_user.tracking_session_id:
        try:
            tracking_data = tsv4.recover_tracking_data(bot_user.tracking_session_id) or {}
            tracking_token_used = bot_user.tracking_session_id
        except Exception as e:
            logger.warning(f"[META PURCHASE] Erro recover tracking via bot_user.tracking_session_id: {e}")
    if not tracking_data and getattr(payment, "tracking_token", None):
        try:
            tracking_data = tsv4.recover_tracking_data(payment.tracking_token) or {}
            tracking_token_used = payment.tracking_token
        except Exception as e:
            logger.warning(f"[META PURCHASE] Erro recover tracking via payment.tracking_token: {e}")
    if not tracking_data:
        try:
            raw = tsv4.redis.get(f"tracking:payment:{payment.payment_id}")
            if raw:
                tracking_data = json.loads(raw)
        except Exception as e:
            logger.warning(f"[META PURCHASE] Erro recover tracking:payment:{payment.payment_id}: {e}")
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
        db.session.commit()

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

    stable_external_id = None
    if payment.customer_user_id:
        stable_external_id = hashlib.sha256(str(payment.customer_user_id).encode("utf-8")).hexdigest()
    elif bot_user and getattr(bot_user, "id", None):
        stable_external_id = hashlib.sha256(str(bot_user.id).encode("utf-8")).hexdigest()

    user_data = MetaPixelAPI._build_user_data(
        customer_user_id=str(payment.customer_user_id) if payment.customer_user_id else None,
        external_id=stable_external_id,
        email=getattr(payment, "customer_email", None) or (bot_user.email if bot_user else None),
        phone=("".join(filter(str.isdigit, str(getattr(payment, "customer_phone", None) or (bot_user.phone if bot_user else ""))))) or None,
        client_ip=client_ip,
        client_user_agent=client_user_agent,
        fbp=fbp_value,
        fbc=fbc_value,
    )
    if not user_data.get("external_id") and stable_external_id:
        user_data["external_id"] = [MetaPixelAPI._hash_data(stable_external_id)]
    # fbclid não entra em external_id; permanece apenas em fbc/fbp.

    event_source_url = (
        tracking_data.get("event_source_url")
        or tracking_data.get("page_url")
        or tracking_data.get("first_page")
        or getattr(payment, "click_context_url", None)
    )
    if not event_source_url:
        if pool and getattr(pool, "slug", None):
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

    enqueued = False
    try:
        if pixel_id and access_token:
            kwargs = {
                "pixel_id": pixel_id,
                "access_token": access_token,
                "event_data": event_data,
                "test_code": getattr(pool, "meta_test_event_code", None) if pool else None,
            }
            task = send_meta_event.delay(**kwargs)
            logger.info(f"[META PURCHASE] Enfileirado | event_id={purchase_event_id} | task={task.id}")
            enqueued = True
        else:
            logger.warning(f"[META PURCHASE] Pixel/AccessToken ausente - não foi possível enfileirar | event_id={purchase_event_id}")

        if enqueued:
            payment.meta_purchase_sent = True
            payment.meta_purchase_sent_at = get_brazil_time()
            db.session.commit()
        return enqueued
    except Exception as e:
        logger.error(f"[META PURCHASE] Erro ao enfileirar Purchase: {e}", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        return False
