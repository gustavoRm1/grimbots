"""
Tasks Assíncronas QI 200 - Redis Queue (RQ)
3 FILAS SEPARADAS para máxima performance:
1. tasks - Telegram (urgente)
2. gateway - Gateway/PIX/Reconciliadores
3. webhook - Webhooks de pagamento
"""

import os
import logging
import re

# 🚨 CRÍTICO: Carregar .env ANTES de qualquer import local do projeto
# Workers RQ precisam de ENCRYPTION_KEY e outras variáveis de ambiente
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Agora sim, imports locais (com acesso ao .env já carregado)
from rq import Queue
from redis import Redis
from typing import Dict, Any, Optional
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from redis_manager import get_redis_connection
from internal_logic.core.extensions import db

# 🚨 CRÍTICO: Importar app REAL do Flask (não o proxy current_app)
# Workers RQ precisam da instância real para criar app_context
from app import app

logger = logging.getLogger(__name__)

# Conectar ao Redis
try:
    # ✅ QI 500: Usar connection pool para RQ (decode_responses=False para bytes)
    # RQ serializa jobs como bytes comprimidos, não strings
    redis_conn = get_redis_connection(decode_responses=False)
    
    # ✅ QI 200: 4 FILAS SEPARADAS (incluindo marathon para remarketing massivo)
    task_queue = Queue('tasks', connection=redis_conn)  # Telegram (urgente - /start, tracking)
    marathon_queue = Queue('marathon', connection=redis_conn)  # Remarketing massivo (batch)
    gateway_queue = Queue('gateway', connection=redis_conn)  # Gateway/PIX/Reconciliadores
    webhook_queue = Queue('webhook', connection=redis_conn)  # Webhooks
    logger.info("✅ 4 Filas RQ inicializadas: tasks, marathon, gateway, webhook")
except Exception as e:
    logger.error(f"❌ Erro ao conectar Redis para RQ: {e}")
    redis_conn = None
    task_queue = None
    marathon_queue = None
    gateway_queue = None
    webhook_queue = None


_AUX_TABLES_READY = False


def _ensure_aux_tables() -> None:
    """Garante que tabelas auxiliares de webhook existam (create if not)."""
    global _AUX_TABLES_READY
    if _AUX_TABLES_READY:
        return

    try:
        from internal_logic.core.models import WebhookEvent, WebhookPendingMatch

        WebhookEvent.__table__.create(db.engine, checkfirst=True)
        WebhookPendingMatch.__table__.create(db.engine, checkfirst=True)
        _AUX_TABLES_READY = True
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível garantir tabelas auxiliares de webhook: {e}")


def _persist_webhook_event(
    gateway_type: str,
    result: Dict[str, Any],
    raw_payload: Dict[str, Any]
) -> None:
    """
    Salva ou atualiza o registro do webhook em webhook_events para auditoria.
    """
    from internal_logic.core.models import WebhookEvent, get_brazil_time

    _ensure_aux_tables()

    transaction_id = str(
        result.get('gateway_transaction_id')
        or raw_payload.get('id')
        or raw_payload.get('transaction_id')
        or ''
    ).strip()
    transaction_hash = str(
        result.get('gateway_hash')
        or raw_payload.get('hash')
        or raw_payload.get('transaction_hash')
        or ''
    ).strip()

    base_key = (transaction_hash or transaction_id or raw_payload.get('event') or '').strip()
    if base_key:
        dedup_key = f"{gateway_type}:{base_key}".lower()
    else:
        dedup_key = f"{gateway_type}:{get_brazil_time().timestamp()}"

    existing = WebhookEvent.query.filter_by(dedup_key=dedup_key).first()
    
    # ✅ CRÍTICO: Validar status antes de salvar (não sobrescrever com None)
    new_status = result.get('status')
    status_valido = new_status and new_status in ['paid', 'pending', 'failed', 'cancelled', 'refunded']
    
    if existing:
        # ✅ CRÍTICO: Só atualizar status se for válido e não None
        if status_valido:
            existing.status = new_status
            logger.debug(f"✅ [_persist_webhook_event] Atualizando status existente: {existing.status} → {new_status}")
        else:
            logger.warning(f"⚠️ [_persist_webhook_event] Status inválido ou None: {new_status}. Preservando status existente: {existing.status}")
        
        existing.transaction_id = transaction_id or existing.transaction_id
        existing.transaction_hash = transaction_hash or existing.transaction_hash
        existing.payload = raw_payload
        existing.received_at = get_brazil_time()
        
        try:
            db.session.commit()
            logger.debug(f"✅ [_persist_webhook_event] WebhookEvent atualizado: dedup_key={dedup_key}, status={existing.status}")
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"❌ [_persist_webhook_event] Erro de integridade ao atualizar: {e}")
    else:
        # ✅ CRÍTICO: Só criar se status for válido
        if not status_valido:
            logger.warning(f"⚠️ [_persist_webhook_event] Status inválido ou None: {new_status}. Não criando WebhookEvent")
            return
        
        event = WebhookEvent(
            gateway_type=gateway_type,
            dedup_key=dedup_key,
            transaction_id=transaction_id or None,
            transaction_hash=transaction_hash or None,
            status=new_status,
            payload=raw_payload
        )
        db.session.add(event)
        try:
            db.session.commit()
            logger.debug(f"✅ [_persist_webhook_event] WebhookEvent criado: dedup_key={dedup_key}, status={new_status}")
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"❌ [_persist_webhook_event] Erro de integridade ao criar: {e}")


def _enqueue_pending_match(
    gateway_type: str,
    transaction_id: Optional[str],
    transaction_hash: Optional[str],
    payload: Dict[str, Any],
    status: Optional[str] = None,
    max_pending_records: int = 1000
) -> None:
    """
    Registra payload para retry posterior quando payment ainda não existe.
    """
    from internal_logic.core.extensions import db
    from internal_logic.core.models import WebhookPendingMatch, get_brazil_time

    if not transaction_id and not transaction_hash:
        return

    key = (transaction_hash or transaction_id or '').strip()
    if not key:
        return

    _ensure_aux_tables()

    dedup_key = f"{gateway_type}:{key}".lower()

    existing = WebhookPendingMatch.query.filter_by(dedup_key=dedup_key).first()

    if existing:
        existing.payload = payload
        existing.status = status or existing.status
        existing.last_attempt_at = get_brazil_time()
        existing.attempts = existing.attempts or 0
        db.session.commit()
        return

    total_pending = WebhookPendingMatch.query.filter_by(gateway_type=gateway_type).count()
    if total_pending >= max_pending_records:
        logger.warning(f"⚠️ Limite de pending matches atingido para {gateway_type}. Ignorando novo registro.")
        return

    pending = WebhookPendingMatch(
        gateway_type=gateway_type,
        dedup_key=dedup_key,
        transaction_id=transaction_id or None,
        transaction_hash=transaction_hash or None,
        payload=payload,
        status=status or 'pending'
    )
    db.session.add(pending)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def _clear_pending_match(
    gateway_type: str,
    transaction_id: Optional[str],
    transaction_hash: Optional[str]
) -> None:
    """Remove pending match associado ao webhook processado."""
    from internal_logic.core.models import WebhookPendingMatch

    if not transaction_id and not transaction_hash:
        return

    key = (transaction_hash or transaction_id or '').strip()
    if not key:
        return

    dedup_key = f"{gateway_type}:{key}".lower()
    pending = WebhookPendingMatch.query.filter_by(dedup_key=dedup_key).first()
    if pending:
        db.session.delete(pending)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()


def process_start_async(
    user_id: int,  # ?? CORREÇÃO: user_id como primeiro parâmetro (sem wrapper)
    bot_id: int,
    token: str,
    config: Dict[str, Any],
    chat_id: int,
    message: Dict[str, Any],
    start_param: Optional[str] = None
):
    """
    Processa comando /start de forma assíncrona (tarefas pesadas)
    
    Executa:
    - Busca Redis para tracking
    - Decodificação de tracking
    - Parse de device/geolocalização
    - Salvar tracking no Redis
    - Salvar BotUser no banco
    - Enviar Meta Pixel ViewContent
    - Salvar welcome_sent no banco
    """
    try:
        from flask import current_app
        from internal_logic.core.models import BotUser, Bot, get_brazil_time
        from bot_manager import send_meta_pixel_viewcontent_event
        import base64
        import json
        import redis
        from utils.tracking_service import TrackingServiceV4

        with app.app_context():
            # Recarregar config do banco
            bot = db.session.get(Bot, bot_id)
            if bot and bot.config:
                config = bot.config.to_dict()
            
            user_from = message.get('from', {})
            telegram_user_id = str(user_from.get('id', ''))
            first_name = user_from.get('first_name', 'Usuário')
            username = user_from.get('username', '')

            tracking_service_v4 = TrackingServiceV4()
            tracking_token_from_start = None
            utm_data_from_start = {}  # ✅ CRÍTICO: Inicializar dict antes de usar
            pool_id_from_start = None
            external_id_from_start = None
            tracking_data = {}  # ✅ Garantir escopo para clique/utm
            
            if start_param:
                # ✅ NOVO FORMATO (V4): tracking_token direto (32 chars hex)
                # tracking_token é um UUID4 em hex, então tem exatamente 32 caracteres
                if len(start_param) == 32 and all(c in '0123456789abcdef' for c in start_param.lower()):
                    tracking_token_from_start = start_param
                    logger.info(f"✅ Tracking token V4 detectado no start param: {tracking_token_from_start}")
                    
                    # Recuperar dados completos do Redis
                    try:
                        tracking_data = tracking_service_v4.recover_tracking_data(tracking_token_from_start)
                        if tracking_data:
                            if tracking_data.get('fbclid'):
                                utm_data_from_start['fbclid'] = tracking_data['fbclid']
                            if tracking_data.get('utm_source'):
                                utm_data_from_start['utm_source'] = tracking_data['utm_source']
                            if tracking_data.get('utm_campaign'):
                                utm_data_from_start['utm_campaign'] = tracking_data['utm_campaign']
                            if tracking_data.get('campaign_code'):
                                utm_data_from_start['campaign_code'] = tracking_data['campaign_code']
                            if tracking_data.get('grim'):
                                utm_data_from_start['campaign_code'] = tracking_data['grim']
                            # ✅ CRÍTICO: Extrair fbp e fbc do tracking_data para salvar no BotUser
                            if tracking_data.get('fbp'):
                                utm_data_from_start['_fbp_from_tracking'] = tracking_data['fbp']
                            if tracking_data.get('fbc'):
                                utm_data_from_start['_fbc_from_tracking'] = tracking_data['fbc']
                                logger.info(f"✅ process_start_async - fbc encontrado no tracking_data: {tracking_data['fbc'][:50]}...")
                            logger.info(f"✅ Dados de tracking recuperados do Redis para token {tracking_token_from_start}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao recuperar tracking data do Redis: {e}")
                
                # ✅ COMPATIBILIDADE: Formato antigo V3 (t{base64})
                elif start_param.startswith('t'):
                    try:
                        tracking_encoded = start_param[1:]
                        missing_padding = len(tracking_encoded) % 4
                        if missing_padding:
                            tracking_encoded += '=' * (4 - missing_padding)
                        
                        tracking_json = base64.urlsafe_b64decode(tracking_encoded).decode()
                        tracking_data = json.loads(tracking_json)

                        pool_id_from_start = tracking_data.get('p')
                        external_id_from_start = tracking_data.get('e')
                        tracking_token_from_start = tracking_data.get('tt')
                        
                        if tracking_data.get('s'):
                            utm_data_from_start['utm_source'] = tracking_data['s']
                        if tracking_data.get('c'):
                            utm_data_from_start['utm_campaign'] = tracking_data['c']
                        if tracking_data.get('cc'):
                            utm_data_from_start['campaign_code'] = tracking_data['cc']
                        if tracking_data.get('f'):
                            fbclid_hash = tracking_data['f']
                            try:
                                r = get_redis_connection()
                                fbclid_completo = r.get(f'tracking_hash:{fbclid_hash}')
                                if fbclid_completo:
                                    utm_data_from_start['fbclid'] = fbclid_completo
                                else:
                                    utm_data_from_start['fbclid'] = fbclid_hash
                            except:
                                utm_data_from_start['fbclid'] = fbclid_hash
                    except Exception as e:
                        logger.warning(f"Erro ao decodificar tracking V3: {e}")
                
                # ✅ FALLBACK: Formato antigo p{pool_id}
                elif start_param.startswith('p') and start_param[1:].isdigit():
                    pool_id_from_start = int(start_param[1:])
                    logger.info(f"⚠️ Formato antigo detectado (p{pool_id_from_start}), sem tracking_token")
                
                # ✅ LEGACY: Formato pool_{id}_{external_id}
                elif start_param.startswith('pool_'):
                    parts = start_param.split('_')
                    if len(parts) >= 2:
                        pool_id_from_start = int(parts[1])
                    if len(parts) >= 4:
                        external_id_from_start = '_'.join(parts[2:])
            
            # HOTFIX: Cast obrigatório para string pois o schema exige VARCHAR
            telegram_user_id_str = str(telegram_user_id)
            bot_user = BotUser.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id_str,
                archived=False
            ).first()
            
            if not bot_user:
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id_str
                ).first()
                
                if bot_user and bot_user.archived:
                    bot_user.archived = False
                    bot_user.archived_reason = None
                    bot_user.archived_at = None
            
            is_new_user = False
            if not bot_user:
                # ✅ CORREÇÃO SÊNIOR QI 500: Garantir que fbclid seja completo (até 255 chars)
                # Isso garante que bot_user.fbclid seja exatamente igual ao fbclid salvo no Redis
                fbclid_from_start = utm_data_from_start.get('fbclid')
                if fbclid_from_start and len(fbclid_from_start) > 255:
                    fbclid_from_start = fbclid_from_start[:255]
                    logger.warning(f"⚠️ fbclid truncado para 255 chars: {fbclid_from_start[:50]}...")
                
                bot_user = BotUser(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id_str,
                    first_name=first_name,
                    username=username,
                    welcome_sent=False,
                    external_id=external_id_from_start,
                    utm_source=utm_data_from_start.get('utm_source'),
                    utm_campaign=utm_data_from_start.get('utm_campaign'),
                    campaign_code=utm_data_from_start.get('campaign_code'),
                    fbclid=fbclid_from_start,  # ✅ CORREÇÃO SÊNIOR QI 500: fbclid completo (até 255 chars)
                    tracking_session_id=tracking_token_from_start,
                    # ✅ CRÍTICO: Salvar fbp e fbc do tracking_data (recuperado via tracking_token)
                    fbp=utm_data_from_start.get('_fbp_from_tracking'),
                    fbc=utm_data_from_start.get('_fbc_from_tracking'),
                    # ✅ CONTEXTO DO CLIQUE (capturado no entry do bot para remarketing)
                    last_click_context_url=(
                        tracking_data.get('event_source_url')
                        or tracking_data.get('first_page')
                        or None
                    ),
                    last_fbclid=utm_data_from_start.get('fbclid'),
                    last_fbp=utm_data_from_start.get('_fbp_from_tracking'),
                    last_fbc=utm_data_from_start.get('_fbc_from_tracking')
                )
                logger.info(f"✅ BotUser criado com tracking_session_id: {tracking_token_from_start[:20] if tracking_token_from_start else 'N/A'}... e fbclid: {fbclid_from_start[:50] if fbclid_from_start else 'N/A'}... (len={len(fbclid_from_start) if fbclid_from_start else 0})")
                is_new_user = True
                if utm_data_from_start.get('_fbc_from_tracking'):
                    logger.info(f"✅ process_start_async - fbc salvo no BotUser (novo): {utm_data_from_start.get('_fbc_from_tracking')[:50]}...")
                
                # Tracking Elite - buscar do Redis
                # ✅ CORREÇÃO: Priorizar tracking_token se disponível (chave correta)
                tracking_json = None
                if tracking_token_from_start:
                    try:
                        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                        tracking_key = f"tracking:{tracking_token_from_start}"  # ✅ CORRETO: Chave do redirect
                        tracking_json = r.get(tracking_key)
                        logger.info(f"✅ process_start_async - Buscando tracking_elite na chave correta: {tracking_key}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao buscar tracking via tracking_token: {e}")
                        tracking_json = None
                
                # ✅ FALLBACK: Se não encontrou via tracking_token, tentar via fbclid (chave antiga)
                if not tracking_json and utm_data_from_start.get('fbclid'):
                    try:
                        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                        fbclid_value = utm_data_from_start['fbclid']
                        tracking_key = f"tracking:{fbclid_value}"  # Fallback para chave antiga
                        tracking_json = r.get(tracking_key)
                        
                        if not tracking_json and len(fbclid_value) <= 12:
                            fbclid_completo = r.get(f'tracking_hash:{fbclid_value}')
                            if fbclid_completo:
                                tracking_key = f"tracking:{fbclid_completo}"
                                tracking_json = r.get(tracking_key)
                        
                        if tracking_json:
                            tracking_elite = json.loads(tracking_json)
                            
                            bot_user.ip_address = tracking_elite.get('ip')
                            bot_user.user_agent = tracking_elite.get('user_agent')
                            
                            # Parse device e geolocalização
                            try:
                                from utils.device_parser import parse_user_agent, parse_ip_to_location
                                
                                device_info = parse_user_agent(bot_user.user_agent)
                                if hasattr(bot_user, 'device_type'):
                                    bot_user.device_type = device_info.get('device_type')
                                if hasattr(bot_user, 'os_type'):
                                    bot_user.os_type = device_info.get('os_type')
                                if hasattr(bot_user, 'browser'):
                                    bot_user.browser = device_info.get('browser')
                                if hasattr(bot_user, 'device_model'):
                                    bot_user.device_model = device_info.get('device_model')
                                
                                if bot_user.ip_address:
                                    location_info = parse_ip_to_location(bot_user.ip_address)
                                    if hasattr(bot_user, 'customer_city'):
                                        bot_user.customer_city = location_info.get('city', 'Unknown')
                                    if hasattr(bot_user, 'customer_state'):
                                        bot_user.customer_state = location_info.get('state', 'Unknown')
                                    if hasattr(bot_user, 'customer_country'):
                                        bot_user.customer_country = location_info.get('country', 'BR')
                            except Exception as e:
                                logger.warning(f"Erro ao parsear device/geolocalização: {e}")
                            
                            # ✅ CORREÇÃO SÊNIOR QI 500: Só salvar tracking_session_id de tracking_elite se não tiver tracking_token_from_start
                            # Isso garante que tracking_token_from_start (do start_param) tenha prioridade sobre tracking_elite
                            # ✅ CORREÇÃO CRÍTICA V15: Validar tracking_elite.session_id antes de salvar
                            # NUNCA salvar token gerado (com prefixo tracking_) em bot_user.tracking_session_id
                            if not tracking_token_from_start and tracking_elite.get('session_id'):
                                session_id_from_elite = tracking_elite.get('session_id')
                                # ✅ VALIDAÇÃO: session_id deve ser UUID de 32 chars (não gerado)
                                is_generated_token = session_id_from_elite.startswith('tracking_')
                                is_uuid_token = len(session_id_from_elite) == 32 and all(c in '0123456789abcdef' for c in session_id_from_elite.lower())
                                
                                if is_generated_token:
                                    logger.error(f"❌ [PROCESS_START] tracking_elite.session_id é GERADO: {session_id_from_elite[:30]}... - NÃO salvar em bot_user.tracking_session_id")
                                    logger.error(f"   Isso quebra o link entre PageView e Purchase")
                                    logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                    # ✅ NÃO salvar - manter token original do redirect (se existir)
                                elif is_uuid_token:
                                    # ✅ Token é UUID (vem do redirect) - pode salvar
                                    bot_user.tracking_session_id = session_id_from_elite
                                    logger.info(f"✅ bot_user.tracking_session_id salvo de tracking_elite: {session_id_from_elite[:20]}...")
                                else:
                                    logger.warning(f"⚠️ [PROCESS_START] tracking_elite.session_id tem formato inválido: {session_id_from_elite[:30]}... (len={len(session_id_from_elite)})")
                                    # ✅ NÃO salvar - formato inválido
                            elif tracking_token_from_start:
                                logger.info(f"✅ bot_user.tracking_session_id preservado (tracking_token_from_start tem prioridade): {tracking_token_from_start[:20]}...")
                            
                            if tracking_elite.get('timestamp'):
                                from datetime import datetime
                                bot_user.click_timestamp = datetime.fromisoformat(tracking_elite['timestamp'])
                            
                            grim_from_redis = tracking_elite.get('grim', '')
                            fbclid_completo_redis = tracking_elite.get('fbclid')
                            
                            # ✅ CRÍTICO: Salvar fbp e fbc no bot_user para uso posterior no Purchase
                            # ✅ CORREÇÃO SÊNIOR: Preservar FBP do Redis, não atualizar com cookie novo
                            if tracking_elite.get('fbp') and not bot_user.fbp:
                                bot_user.fbp = tracking_elite.get('fbp')
                                logger.info(f"✅ process_start_async - fbp salvo no bot_user: {bot_user.fbp[:30]}...")
                            elif tracking_elite.get('fbp') and bot_user.fbp:
                                logger.info(f"✅ process_start_async - fbp já existe no bot_user, preservando: {bot_user.fbp[:30]}... (não atualizando com {tracking_elite.get('fbp')[:30]}...)")
                            if tracking_elite.get('fbc') and not bot_user.fbc:
                                bot_user.fbc = tracking_elite.get('fbc')
                                logger.info(f"✅ process_start_async - fbc salvo no bot_user: {bot_user.fbc[:50]}...")
                            elif tracking_elite.get('fbc') and bot_user.fbc:
                                logger.info(f"✅ process_start_async - fbc já existe no bot_user, preservando: {bot_user.fbc[:50]}... (não atualizando com {tracking_elite.get('fbc')[:50]}...)")
                            
                            # ✅ CORREÇÃO SÊNIOR QI 500: Garantir que fbclid seja completo (até 255 chars)
                            # Isso garante que bot_user.fbclid seja exatamente igual ao fbclid salvo no Redis
                            if fbclid_completo_redis:
                                # ✅ CRÍTICO: Salvar fbclid completo sem truncar (até 255 chars)
                                bot_user.fbclid = fbclid_completo_redis[:255] if len(fbclid_completo_redis) > 255 else fbclid_completo_redis
                                bot_user.external_id = bot_user.fbclid
                                logger.info(f"✅ bot_user.fbclid salvo completo (len={len(bot_user.fbclid)}): {bot_user.fbclid[:50]}...")
                                if grim_from_redis:
                                    bot_user.campaign_code = grim_from_redis
                            elif grim_from_redis:
                                bot_user.external_id = grim_from_redis
                                bot_user.campaign_code = grim_from_redis
                            
                            # Enriquecer UTMs
                            if not bot_user.utm_source and tracking_elite.get('utm_source'):
                                bot_user.utm_source = tracking_elite['utm_source']
                            if not bot_user.utm_campaign and tracking_elite.get('utm_campaign'):
                                bot_user.utm_campaign = tracking_elite['utm_campaign']
                            if not bot_user.utm_medium:
                                bot_user.utm_medium = tracking_elite.get('utm_medium')
                            if not bot_user.utm_content:
                                bot_user.utm_content = tracking_elite.get('utm_content')
                            if not bot_user.utm_term:
                                bot_user.utm_term = tracking_elite.get('utm_term')
                            
                            # ✅ CORREÇÃO SÊNIOR QI 500: Salvar tracking:chat:{chat_id} via TrackingServiceV4 com tracking_token
                            # Isso garante que tracking:chat:{customer_user_id} tenha o tracking_token correto para _generate_pix_payment recuperar
                            try:
                                # ✅ CRÍTICO: PRIORIDADE 1 - Usar tracking_token_from_start se disponível (tem prioridade máxima)
                                # PRIORIDADE 2 - Usar tracking_token de tracking_elite.get('session_id')
                                # PRIORIDADE 3 - Usar tracking_token de bot_user.tracking_session_id
                                # PRIORIDADE 4 - Recuperar do Redis via fbclid
                                tracking_token_for_chat = None
                                
                                # ✅ PRIORIDADE 1: tracking_token_from_start (do start_param) - TEM PRIORIDADE MÁXIMA
                                if tracking_token_from_start:
                                    tracking_token_for_chat = tracking_token_from_start
                                    logger.info(f"✅ Tracking token para tracking:chat:{chat_id} (prioridade 1 - start_param): {tracking_token_for_chat[:20]}...")
                                # ✅ PRIORIDADE 2: tracking_elite.get('session_id')
                                elif tracking_elite.get('session_id'):
                                    tracking_token_for_chat = tracking_elite.get('session_id')
                                    logger.info(f"✅ Tracking token para tracking:chat:{chat_id} (prioridade 2 - tracking_elite): {tracking_token_for_chat[:20]}...")
                                # ✅ PRIORIDADE 3: bot_user.tracking_session_id
                                elif bot_user and bot_user.tracking_session_id:
                                    tracking_token_for_chat = bot_user.tracking_session_id
                                    logger.info(f"✅ Tracking token para tracking:chat:{chat_id} (prioridade 3 - bot_user): {tracking_token_for_chat[:20]}...")
                                # ✅ PRIORIDADE 4: Recuperar do Redis via fbclid
                                elif fbclid_completo_redis:
                                    try:
                                        tracking_token_from_fbclid = tracking_service_v4.redis.get(f"tracking:fbclid:{fbclid_completo_redis}")
                                        if tracking_token_from_fbclid:
                                            tracking_token_for_chat = tracking_token_from_fbclid
                                            logger.info(f"✅ Tracking token para tracking:chat:{chat_id} (prioridade 4 - fbclid): {tracking_token_for_chat[:20]}...")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Erro ao recuperar tracking_token via fbclid: {e}")
                                
                                # ✅ Se tracking_token está disponível, salvar via TrackingServiceV4.save_tracking_data()
                                # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de salvar
                                if tracking_token_for_chat:
                                    # ✅ CORREÇÃO V16: Validar tracking_token ANTES de salvar em tracking:chat
                                    is_generated_token = tracking_token_for_chat.startswith('tracking_')
                                    is_uuid_token = len(tracking_token_for_chat) == 32 and all(c in '0123456789abcdef' for c in tracking_token_for_chat.lower())
                                    
                                    if is_generated_token:
                                        logger.error(f"❌ [PROCESS_START] tracking_token_for_chat é GERADO: {tracking_token_for_chat[:30]}... - NÃO salvar em tracking:chat")
                                        logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                        # ✅ NÃO salvar token gerado
                                    elif is_uuid_token:
                                        # ✅ Token válido - pode salvar
                                        bot_id_for_tracking = bot_user.bot_id if bot_user else bot_id
                                        tracking_service_v4.save_tracking_data(
                                            tracking_token=tracking_token_for_chat,  # ✅ GARANTIR que tracking_token seja salvo
                                            bot_id=bot_id_for_tracking,
                                            customer_user_id=str(chat_id),
                                            fbclid=fbclid_completo_redis or '',
                                            fbp=tracking_elite.get('fbp', ''),
                                            fbc=tracking_elite.get('fbc', ''),
                                            utm_source=tracking_elite.get('utm_source', ''),
                                            utm_medium=tracking_elite.get('utm_medium', ''),
                                            utm_campaign=tracking_elite.get('utm_campaign', '')
                                        )
                                        logger.info(f"✅ tracking:chat:{chat_id} salvo com tracking_token: {tracking_token_for_chat[:20]}...")
                                    else:
                                        logger.warning(f"⚠️ [PROCESS_START] tracking_token_for_chat tem formato inválido: {tracking_token_for_chat[:30]}... (len={len(tracking_token_for_chat)}) - NÃO salvar")
                                else:
                                    logger.warning(f"⚠️ tracking_token não encontrado para salvar em tracking:chat:{chat_id}")
                            except Exception as e:
                                logger.warning(f"Erro ao salvar tracking:chat:{chat_id}: {e}")
                    except Exception as e:
                        logger.error(f"Erro ao buscar tracking elite: {e}")
                
                # ✅ CORREÇÃO SÊNIOR QI 500: Salvar tracking:chat:{chat_id} com tracking_token_from_start mesmo se tracking_elite não for encontrado
                # Isso garante que tracking:chat:{customer_user_id} tenha o tracking_token correto para _generate_pix_payment recuperar
                # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de salvar
                if tracking_token_from_start:
                    try:
                        # ✅ CORREÇÃO V16: Validar tracking_token_from_start ANTES de salvar em tracking:chat
                        is_generated_token = tracking_token_from_start.startswith('tracking_')
                        is_uuid_token = len(tracking_token_from_start) == 32 and all(c in '0123456789abcdef' for c in tracking_token_from_start.lower())
                        
                        if is_generated_token:
                            logger.error(f"❌ [PROCESS_START] tracking_token_from_start é GERADO: {tracking_token_from_start[:30]}... - NÃO salvar em tracking:chat")
                            logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                            # ✅ NÃO salvar token gerado
                        elif is_uuid_token:
                            # ✅ Token válido - pode salvar
                            # ✅ CRÍTICO: Recuperar dados do Redis via tracking_token_from_start
                            tracking_data_from_token = tracking_service_v4.recover_tracking_data(tracking_token_from_start) or {}
                            
                            # ✅ Se tracking_data tem dados, usar eles; senão, usar dados de utm_data_from_start
                            fbclid_for_chat = tracking_data_from_token.get('fbclid') or utm_data_from_start.get('fbclid') or ''
                            fbp_for_chat = tracking_data_from_token.get('fbp') or utm_data_from_start.get('_fbp_from_tracking') or ''
                            fbc_for_chat = tracking_data_from_token.get('fbc') or utm_data_from_start.get('_fbc_from_tracking') or ''
                            utm_source_for_chat = tracking_data_from_token.get('utm_source') or utm_data_from_start.get('utm_source') or ''
                            utm_medium_for_chat = tracking_data_from_token.get('utm_medium') or utm_data_from_start.get('utm_medium') or ''
                            utm_campaign_for_chat = tracking_data_from_token.get('utm_campaign') or utm_data_from_start.get('utm_campaign') or ''
                            
                            # ✅ Salvar tracking:chat:{chat_id} com tracking_token_from_start
                            tracking_service_v4.save_tracking_data(
                                tracking_token=tracking_token_from_start,  # ✅ GARANTIR que tracking_token seja salvo
                                bot_id=bot_id,
                                customer_user_id=str(chat_id),
                                fbclid=fbclid_for_chat,
                                fbp=fbp_for_chat,
                                fbc=fbc_for_chat,
                                utm_source=utm_source_for_chat,
                                utm_medium=utm_medium_for_chat,
                                utm_campaign=utm_campaign_for_chat
                            )
                            logger.info(f"✅ tracking:chat:{chat_id} salvo com tracking_token_from_start: {tracking_token_from_start[:20]}... | fbclid={'✅' if fbclid_for_chat else '❌'}, fbp={'✅' if fbp_for_chat else '❌'}, fbc={'✅' if fbc_for_chat else '❌'}")
                        else:
                            logger.warning(f"⚠️ [PROCESS_START] tracking_token_from_start tem formato inválido: {tracking_token_from_start[:30]}... (len={len(tracking_token_from_start)}) - NÃO salvar")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao salvar tracking:chat:{chat_id} com tracking_token_from_start: {e}")
                
                try:
                    db.session.add(bot_user)
                    db.session.flush()
                except Exception as e:
                    db.session.rollback()
                    bot_user = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id_str,
                        archived=False
                    ).first()
                    if not bot_user:
                        raise
                
                if bot:
                    bot.total_users = BotUser.query.filter_by(bot_id=bot_id, archived=False).count()
                
                db.session.commit()
                logger.info(f"✅ BotUser criado/atualizado: {first_name}")
            else:
                bot_user.last_interaction = get_brazil_time()
                
                if external_id_from_start and not bot_user.external_id:
                    bot_user.external_id = external_id_from_start
                if utm_data_from_start.get('utm_source') and not bot_user.utm_source:
                    bot_user.utm_source = utm_data_from_start['utm_source']
                if utm_data_from_start.get('utm_campaign') and not bot_user.utm_campaign:
                    bot_user.utm_campaign = utm_data_from_start['utm_campaign']
                if utm_data_from_start.get('campaign_code') and not bot_user.campaign_code:
                    bot_user.campaign_code = utm_data_from_start['campaign_code']
                # ✅ CORREÇÃO SÊNIOR QI 500: Garantir que fbclid seja completo (até 255 chars)
                # Isso garante que bot_user.fbclid seja exatamente igual ao fbclid salvo no Redis
                # ✅ CRÍTICO: SEMPRE atualizar fbclid se veio do start_param (pode ser mais recente)
                if utm_data_from_start.get('fbclid'):
                    fbclid_from_start = utm_data_from_start['fbclid']
                    # ✅ CRÍTICO: Salvar fbclid completo sem truncar (até 255 chars)
                    fbclid_to_save = fbclid_from_start[:255] if len(fbclid_from_start) > 255 else fbclid_from_start
                    if bot_user.fbclid != fbclid_to_save:
                        bot_user.fbclid = fbclid_to_save
                        logger.info(f"✅ bot_user.fbclid atualizado do start_param (len={len(bot_user.fbclid)}): {bot_user.fbclid[:50]}...")
                    elif not bot_user.fbclid:
                        bot_user.fbclid = fbclid_to_save
                        logger.info(f"✅ bot_user.fbclid salvo do start_param (len={len(bot_user.fbclid)}): {bot_user.fbclid[:50]}...")
                
                # ✅ CRÍTICO: Se bot_user já tem fbclid mas não tem tracking_session_id, tentar recuperar do Redis
                # Isso garante que mesmo se start_param não tiver token, podemos recuperar via fbclid
                if bot_user.fbclid and not bot_user.tracking_session_id:
                    try:
                        tracking_token_from_existing_fbclid = tracking_service_v4.redis.get(f"tracking:fbclid:{bot_user.fbclid}")
                        if tracking_token_from_existing_fbclid:
                            # ✅ VALIDAÇÃO: Verificar se token é válido (UUID de 32 chars, não token gerado)
                            is_generated_token = tracking_token_from_existing_fbclid.startswith('tracking_')
                            is_uuid_token = len(tracking_token_from_existing_fbclid) == 32 and all(c in '0123456789abcdef' for c in tracking_token_from_existing_fbclid.lower())
                            
                            if is_uuid_token and not is_generated_token:
                                bot_user.tracking_session_id = tracking_token_from_existing_fbclid
                                logger.info(f"✅ bot_user.tracking_session_id recuperado via fbclid existente: {tracking_token_from_existing_fbclid[:20]}...")
                                # ✅ Atualizar utm_data_from_start para usar este token nas próximas verificações
                                if not tracking_token_from_start:
                                    tracking_token_from_start = tracking_token_from_existing_fbclid
                                    logger.info(f"✅ tracking_token_from_start atualizado via fbclid existente: {tracking_token_from_start[:20]}...")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao recuperar tracking_token via fbclid existente: {e}")

                # ✅ CORREÇÃO SÊNIOR QI 500: SEMPRE salvar tracking_session_id quando tracking_token_from_start estiver disponível
                # Isso garante que _generate_pix_payment sempre encontre o tracking_token correto
                tracking_token_to_save = None
                
                # ✅ PRIORIDADE 1: tracking_token_from_start (do start_param)
                if tracking_token_from_start:
                    tracking_token_to_save = tracking_token_from_start
                    logger.info(f"✅ tracking_token_from_start encontrado (prioridade 1): {tracking_token_from_start[:20]}...")
                # ✅ PRIORIDADE 2: Recuperar do Redis via fbclid se tracking_token_from_start não existe
                elif utm_data_from_start.get('fbclid'):
                    try:
                        fbclid_from_start = utm_data_from_start.get('fbclid')
                        tracking_token_from_fbclid = tracking_service_v4.redis.get(f"tracking:fbclid:{fbclid_from_start}")
                        if tracking_token_from_fbclid:
                            tracking_token_to_save = tracking_token_from_fbclid
                            logger.info(f"✅ tracking_token recuperado do Redis via fbclid (prioridade 2): {tracking_token_from_fbclid[:20]}...")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao recuperar tracking_token via fbclid: {e}")
                # ✅ PRIORIDADE 3: Recuperar do Redis via bot_user.fbclid se bot_user já tem fbclid mas não tem tracking_session_id
                elif bot_user and bot_user.fbclid and not bot_user.tracking_session_id:
                    try:
                        tracking_token_from_bot_user_fbclid = tracking_service_v4.redis.get(f"tracking:fbclid:{bot_user.fbclid}")
                        if tracking_token_from_bot_user_fbclid:
                            tracking_token_to_save = tracking_token_from_bot_user_fbclid
                            logger.info(f"✅ tracking_token recuperado do Redis via bot_user.fbclid (prioridade 3): {tracking_token_from_bot_user_fbclid[:20]}...")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao recuperar tracking_token via bot_user.fbclid: {e}")
                
                # ✅ CRÍTICO: Salvar tracking_session_id se encontrou token válido
                if tracking_token_to_save:
                    # ✅ VALIDAÇÃO: Verificar se token é válido (UUID de 32 chars, não token gerado)
                    is_generated_token = tracking_token_to_save.startswith('tracking_')
                    is_uuid_token = len(tracking_token_to_save) == 32 and all(c in '0123456789abcdef' for c in tracking_token_to_save.lower())
                    
                    if is_generated_token:
                        logger.error(f"❌ [PROCESS_START] tracking_token_to_save é GERADO: {tracking_token_to_save[:30]}... - NÃO salvar em bot_user.tracking_session_id")
                        logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                    elif is_uuid_token:
                        # ✅ Token é válido - salvar
                        if bot_user.tracking_session_id != tracking_token_to_save:
                            bot_user.tracking_session_id = tracking_token_to_save
                            logger.info(f"✅ bot_user.tracking_session_id atualizado: {tracking_token_to_save[:20]}...")
                        else:
                            logger.info(f"✅ bot_user.tracking_session_id já está correto: {tracking_token_to_save[:20]}...")
                        
                        # ✅ CRÍTICO: Garantir que seja commitado
                        try:
                            db.session.commit()
                            logger.info(f"✅ bot_user.tracking_session_id commitado no banco")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao commitar bot_user.tracking_session_id: {e}")
                            db.session.rollback()
                    else:
                        logger.warning(f"⚠️ [PROCESS_START] tracking_token_to_save tem formato inválido: {tracking_token_to_save[:30]}... (len={len(tracking_token_to_save)})")
                else:
                    logger.warning(f"⚠️ [PROCESS_START] Nenhum tracking_token encontrado para salvar em bot_user.tracking_session_id")
                    logger.warning(f"   Isso pode quebrar o link entre PageView e Purchase se cliente passar pelo redirect mas start_param não tiver token")

                # ✅ CRÍTICO: Se fbc foi recuperado do tracking_data mas não foi salvo no BotUser, salvar agora
                # ✅ PATCH 4: Salvar fbc no BotUser se disponível (garantir persistência)
                fbc_from_tracking = utm_data_from_start.get('_fbc_from_tracking')
                if fbc_from_tracking and not bot_user.fbc:
                    bot_user.fbc = fbc_from_tracking
                    logger.info(f"[META PIXEL] process_start_async - fbc recuperado do tracking_data e salvo no bot_user: {bot_user.fbc[:50]}...")
                
                # ✅ PATCH 4: Salvar fbp no BotUser se disponível
                fbp_from_tracking = utm_data_from_start.get('_fbp_from_tracking')
                if fbp_from_tracking and not bot_user.fbp:
                    bot_user.fbp = fbp_from_tracking
                    logger.info(f"[META PIXEL] process_start_async - fbp recuperado do tracking_data e salvo no bot_user: {bot_user.fbp[:30]}...")

                if tracking_token_from_start:
                    payload = {
                        "tracking_token": tracking_token_from_start,
                        "bot_id": bot_id,
                        "customer_user_id": telegram_user_id,
                        "fbclid": bot_user.fbclid or utm_data_from_start.get('fbclid'),
                        "fbp": getattr(bot_user, 'fbp', None) or utm_data_from_start.get('_fbp_from_tracking'),  # ✅ Priorizar bot_user, fallback para tracking_data
                        "fbc": getattr(bot_user, 'fbc', None) or utm_data_from_start.get('_fbc_from_tracking'),  # ✅ Priorizar bot_user, fallback para tracking_data
                        "utm_source": bot_user.utm_source,
                        "utm_campaign": bot_user.utm_campaign,
                        "utm_medium": getattr(bot_user, 'utm_medium', None),
                        "utm_content": getattr(bot_user, 'utm_content', None),
                        "utm_term": getattr(bot_user, 'utm_term', None),
                        "grim": bot_user.campaign_code or utm_data_from_start.get('campaign_code'),
                        "last_interaction_at": get_brazil_time().isoformat(),
                    }
                    compact_payload = {k: v for k, v in payload.items() if v}
                    ok = tracking_service_v4.save_tracking_token(tracking_token_from_start, compact_payload)
                    if not ok:
                        logger.warning("Retry saving tracking_token once (start)")
                        tracking_service_v4.save_tracking_token(tracking_token_from_start, compact_payload)
                
                db.session.commit()
            
            # Enviar Meta Pixel ViewContent (apenas para novos usuários)
            if is_new_user:
                try:
                    send_meta_pixel_viewcontent_event(bot, bot_user, message, pool_id_from_start)
                except Exception as e:
                    logger.warning(f"Erro ao enviar ViewContent: {e}")
            
            # Marcar welcome_sent (será feito pelo handler síncrono após enviar mensagem)
            # Não fazer aqui para evitar race condition
            
    except Exception as e:
        logger.error(f"❌ Erro em process_start_async: {e}", exc_info=True)


def process_telegram_message_async(bot_id: int, update_data: Dict[str, Any], token: str, config: Dict[str, Any]):
    """
    Processa mensagens do Telegram em background (Worker RQ).
    
    GARANTIA CRÍTICA: Cria/atualiza o BotUser ANTES de processar qualquer mensagem.
    Isso evita perda de leads quando o worker processa o webhook.
    
    Args:
        bot_id: ID do bot no banco
        update_data: Dicionário com update do Telegram (message, callback_query, etc)
        token: Token do bot Telegram
        config: Configuração do bot (dicionário)
    """
    from datetime import datetime
    from internal_logic.core.extensions import db
    from internal_logic.core.models import BotUser, Bot
    from bot_manager import BotManager
    from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError
    
    job_id = f"{bot_id}_{datetime.utcnow().timestamp()}"
    logger.critical(f"?? [WORKER ENTRY] process_telegram_message_async iniciado | Job: {job_id} | Bot: {bot_id}")
    
    try:
        with app.app_context():
            # ============================================================================
            # BLOCO CRÍTICO: CRIAÇÃO/ATUALIZAÇÃO DO BOTUSER (RESTAURAÇÃO LEGADA)
            # ============================================================================
            utc_now = datetime.utcnow()
            
            try:
                # 1. Extração segura dos dados do update do Telegram
                message = update_data.get('message') or update_data.get('callback_query', {}).get('message')
                from_user = None
                
                if 'message' in update_data:
                    from_user = update_data['message'].get('from')
                elif 'callback_query' in update_data:
                    from_user = update_data['callback_query'].get('from')
                elif 'edited_message' in update_data:
                    from_user = update_data['edited_message'].get('from')
                
                if from_user:
                    telegram_id = from_user.get('id')
                    # ?? CORREÇÃO CRÍTICA: Cast para string para compatibilidade com VARCHAR(255)
                    telegram_id_str = str(telegram_id)
                    first_name = from_user.get('first_name', '')
                    username = from_user.get('username', '')
                    
                    logger.critical(f"?? [WORKER] Processando usuário {telegram_id_str} para bot {bot_id}")
                    
                    # 2. Busca ou Criação do BotUser
                    user = BotUser.query.filter_by(bot_id=bot_id, telegram_user_id=telegram_id_str).first()
                    
                    if not user:
                        # É UM LEAD NOVO (Vai contar no Dashboard de Hoje!)
                        user = BotUser(
                            bot_id=bot_id,
                            telegram_user_id=telegram_id_str,
                            first_name=first_name,
                            username=username,
                            first_interaction=utc_now,
                            last_interaction=utc_now,
                            archived=False
                        )
                        db.session.add(user)
                        logger.critical(f"✅ [LEAD NOVO] BotUser criado: {telegram_id} | Bot: {bot_id}")
                    else:
                        # LEAD ANTIGO VOLTANDO (Atualiza apenas o last_interaction)
                        user.first_name = first_name
                        user.username = username
                        user.last_interaction = utc_now
                        user.archived = False  # Desarquiva se ele estava inativo
                        logger.critical(f"✅ [LEAD EXISTENTE] BotUser atualizado: {telegram_id} | Bot: {bot_id}")
                    
                    # 3. Força o commit imediato ANTES de processar o funil
                    try:
                        db.session.commit()
                        logger.critical(f"💾 [COMMIT SUCCESS] BotUser persistido | Telegram: {telegram_id} | Bot: {bot_id}")
                    except OperationalError as oe:
                        db.session.rollback()
                        logger.critical(f"🚨 [OPERATIONAL ERROR] Falha de conexão DB: {oe}", exc_info=True)
                        # Tentar reconectar e salvar novamente
                        try:
                            db.session.remove()
                            db.session.add(user)
                            db.session.commit()
                            logger.critical(f"💾 [RETRY SUCCESS] BotUser persistido após reconexão")
                        except Exception as retry_error:
                            logger.critical(f"💀 [RETRY FAILED] Não foi possível salvar após reconexão: {retry_error}", exc_info=True)
                    except IntegrityError as ie:
                        db.session.rollback()
                        logger.critical(f"🚨 [INTEGRITY ERROR] Violação de constraint: {ie}", exc_info=True)
                    except SQLAlchemyError as se:
                        db.session.rollback()
                        logger.critical(f"🚨 [SQLAlchemy ERROR] Erro no banco: {se}", exc_info=True)
                    except Exception as commit_error:
                        db.session.rollback()
                        logger.critical(f"💀 [COMMIT FAILED] Erro desconhecido: {commit_error}", exc_info=True)
                    
            except Exception as e:
                db.session.rollback()
                logger.critical(f"❌ [CRÍTICO] Falha ao salvar BotUser no banco: {e}", exc_info=True)
                # Continua processando mesmo assim para não perder a mensagem
            
            # ============================================================================
            # PROCESSAMENTO DA MENSAGEM (após garantir que BotUser existe)
            # ============================================================================
            try:
                bot_manager = BotManager(socketio=None, scheduler=None)
                bot_manager._process_telegram_update(bot_id, None, update_data)
                logger.critical(f"✅ [MESSAGE PROCESSED] Job: {job_id} | Bot: {bot_id}")
            except Exception as e:
                logger.critical(f"❌ [MESSAGE FAILED] Erro no processamento: {e}", exc_info=True)
                
    except Exception as e:
        logger.critical(f"💀 [FATAL] Erro crítico no Worker Telegram: {e}", exc_info=True)
    finally:
        logger.critical(f"🏁 [WORKER EXIT] Job: {job_id} finalizado")


def process_webhook_async(user_id: int, gateway_type: str, data: Dict[str, Any]):
    """
    Processa webhook de pagamento de forma assíncrona
    
    ✅ ISOLAMENTO NAMESPACE V2: Agora recebe user_id como primeiro argumento
    
    Executa:
    - Processar webhook via adapter
    - Buscar payment
    - Atualizar status
    - Processar estatísticas
    - Enviar entregável
    - Enviar Meta Pixel Purchase
    
    Args:
        user_id: ID do usuário (OBRIGATÓRIO para namespace isolado)
        gateway_type: Tipo do gateway (bolt, paradise, etc)
        data: Dados do webhook
    """
    job_id = f"webhook_{gateway_type}_{datetime.utcnow().timestamp()}"
    logger.critical(f"🚀 [WEBHOOK WORKER ENTRY] process_webhook_async iniciado | Job: {job_id} | Gateway: {gateway_type} | User: {user_id}")
    
    try:
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Payment, Gateway, Bot, get_brazil_time, Commission, WebhookEvent, WebhookPendingMatch
        from gateway_factory import GatewayFactory
        from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError
        
        # ✅ ISOLAMENTO: Criar BotManager isolado para este usuário (se necessário)
        # Não usar bot_manager global - criar instância com user_id
        
        with app.app_context():
            logger.critical(f"🔍 [WEBHOOK WORKER] App context criado | Job: {job_id}")
            
            # ✅ ISOLAMENTO: Se user_id for 0, resolver pelo transaction_id
            if user_id == 0:
                transaction_id = data.get('_transaction_id_for_lookup')
                if transaction_id:
                    # Buscar payment para obter user_id
                    payment = Payment.query.filter_by(external_id=transaction_id).first()
                    if payment:
                        user_id = payment.user_id
                        logger.info(f"✅ User_id resolvido pelo transaction_id: {user_id}")
                    else:
                        # Buscar pelo gateway_transaction_id
                        payment = Payment.query.filter_by(gateway_transaction_id=transaction_id).first()
                        if payment:
                            user_id = payment.user_id
                            logger.info(f"✅ User_id resolvido pelo gateway_transaction_id: {user_id}")
            
            grim_payment_id = data.pop('_grim_payment_id', None)
            # Criar gateway com adapter
            dummy_credentials = {}
            if gateway_type == 'syncpay':
                dummy_credentials = {'client_id': 'dummy', 'client_secret': 'dummy'}
            elif gateway_type == 'pushynpay':
                dummy_credentials = {'api_key': 'dummy'}
            elif gateway_type == 'paradise':
                dummy_credentials = {'api_key': 'dummy', 'product_hash': 'dummy'}
            elif gateway_type == 'wiinpay':
                dummy_credentials = {'api_key': 'dummy'}
            elif gateway_type == 'atomopay':
                dummy_credentials = {'api_token': 'dummy'}
            elif gateway_type == 'umbrellapag':
                dummy_credentials = {'api_key': 'dummy'}
            elif gateway_type == 'bolt':
                dummy_credentials = {'api_key': 'dummy', 'company_id': 'dummy'}
            elif gateway_type == 'aguia':
                dummy_credentials = {'api_key': 'dummy'}
            
            gateway_instance = GatewayFactory.create_gateway(gateway_type, dummy_credentials, use_adapter=True)
            
            gateway = None
            result = None
            
            if gateway_instance:
                producer_hash = None
                if hasattr(gateway_instance, 'extract_producer_hash'):
                    producer_hash = gateway_instance.extract_producer_hash(data)
                    if producer_hash:
                        gateway = Gateway.query.filter_by(
                            gateway_type=gateway_type,
                            producer_hash=producer_hash
                        ).first()
                
                result = gateway_instance.process_webhook(data)
            else:
                # 🛑 BLINDAGEM: Não usar bot_manager global
                # Criar instância isolada do BotManager para este usuário
                from bot_manager import BotManager
                user_bot_manager = BotManager(None, None, user_id=user_id)
                result = user_bot_manager.process_payment_webhook(gateway_type, data)
            
            if result:
                gateway_transaction_id = result.get('gateway_transaction_id')
                status = result.get('status')
                
                # ✅ LOGS DETALHADOS: Webhook recebido e processado
                logger.info(f"📥 [WEBHOOK {gateway_type.upper()}] Webhook recebido e processado")
                logger.info(f"   Transaction ID: {gateway_transaction_id}")
                logger.info(f"   Status normalizado: {status}")
                logger.info(f"   Payment ID: {result.get('payment_id')}")
                logger.info(f"   Amount: R$ {result.get('amount', 0):.2f}" if result.get('amount') else "   Amount: N/A")
                
                # ✅ IDEMPOTÊNCIA MELHORADA: Verificar se webhook já foi processado (independente do status)
                from internal_logic.core.models import WebhookEvent
                from datetime import timedelta
                cinco_minutos_atras = get_brazil_time() - timedelta(minutes=5)
                
                # ✅ Verificar se webhook com mesmo transaction_id já foi processado recentemente
                webhook_recente = WebhookEvent.query.filter(
                    WebhookEvent.gateway_type == gateway_type,
                    WebhookEvent.transaction_id == gateway_transaction_id,
                    WebhookEvent.received_at >= cinco_minutos_atras
                ).order_by(WebhookEvent.received_at.desc()).first()
                
                if webhook_recente:
                    # ✅ Se status é o mesmo, é duplicado exato
                    if webhook_recente.status == status:
                        logger.info(f"♻️ [WEBHOOK {gateway_type.upper()}] Webhook duplicado detectado (mesmo status '{status}' nos últimos 5min)")
                        logger.info(f"   Transaction ID: {gateway_transaction_id}")
                        logger.info(f"   Webhook anterior recebido em: {webhook_recente.received_at}")
                        logger.info(f"   Status: {webhook_recente.status}")
                        logger.info(f"   Pulando processamento para evitar duplicação")
                        return {'status': 'duplicate_webhook', 'message': f'Webhook duplicado (status: {status})'}
                    else:
                        # ✅ Status diferente: pode ser atualização (ex: pending → paid)
                        logger.info(f"🔄 [WEBHOOK {gateway_type.upper()}] Webhook com status diferente detectado")
                        logger.info(f"   Transaction ID: {gateway_transaction_id}")
                        logger.info(f"   Status anterior: {webhook_recente.status} → Status novo: {status}")
                        logger.info(f"   Webhook anterior recebido em: {webhook_recente.received_at}")
                        logger.info(f"   Processando atualização de status...")
                
                # ✅ Registrar evento para auditoria (deduplicado por gateway/hash)
                try:
                    _persist_webhook_event(
                        gateway_type=gateway_type,
                        result=result,
                        raw_payload=data
                    )
                    logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Webhook registrado em webhook_events")
                except Exception as log_error:
                    logger.warning(f"⚠️ [WEBHOOK {gateway_type.upper()}] Falha ao registrar webhook em webhook_events: {log_error}")
                
                # Buscar payment
                payment_query = Payment.query
                if gateway:
                    payment_query = payment_query.filter_by(gateway_type=gateway_type)
                    user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
                    if user_bot_ids:
                        payment_query = payment_query.filter(Payment.bot_id.in_(user_bot_ids))
                
                # ---------------------------------------------------------
                # MATCH ROBUSTO ÁTOMO PAY — QI 500 (RESOLVE PENDING)
                # ---------------------------------------------------------
                event_id = str(gateway_transaction_id or '').strip()
                event_tx = str(data.get('transaction_id') or result.get('transaction_id') or '').strip()
                event_hash = str(result.get('gateway_hash') or data.get('transaction_hash') or data.get('hash') or '').strip()
                event_ref = str(result.get('external_reference') or data.get('reference') or '').strip()
                producer = str(result.get('producer_hash') or data.get('producer_hash') or '').strip()
                
                # ✅ EXTRAÇÃO ESPECÍFICA ÁGUIAPAGS (PAYLOAD REAL)
                if gateway_type == 'aguia':
                    data_obj = data.get('data', {})
                    event_id = str(data_obj.get('transactionId', '')).strip()
                    event_ref = str(data_obj.get('providerReference', '')).strip() 
                    status_raw = str(data_obj.get('status', '')).strip()
                    
                    # ✅ TRADUÇÃO DE STATUS ÁGUIAPAGS PARA PADRÃO DO SISTEMA
                    if status_raw == 'CAPTURED':
                        status = 'paid'
                    elif status_raw == 'PENDING':
                        status = 'pending'
                    elif status_raw.upper() in ['REFUSED', 'CANCELED', 'REFUNDED']:
                        status = 'failed' if status_raw.upper() != 'REFUNDED' else 'refunded'
                    else:
                        status = 'failed'
                    
                    logger.info(f"🔍 [ÁGUIAPAGS] Parse específico - TransactionID: {event_id}, Status: {status_raw} → {status}")
                else:
                    # ✅ FLUXO PADRÃO PARA OUTROS GATEWAYS
                    status = result.get('status')

                payment = None

                # 0) Se o reconciliador indicou explicitamente o payment_id interno, usar primeiro
                if grim_payment_id:
                    payment = Payment.query.get(int(grim_payment_id))
                    if payment:
                        logger.info("🎯 Payment encontrado via _grim_payment_id: %s", payment.payment_id)

                # 1) Construir filtros unificados (evita divergências por espaços/formatação)
                if not payment:
                    search_filters = []
                    values_seen = set()

                    def add_equal(value, column):
                        if value and value not in values_seen:
                            search_filters.append(column == value)
                            values_seen.add(value)

                    def add_like(value):
                        if value and value not in values_seen:
                            search_filters.append(Payment.payment_id.ilike(f"%{value}%"))
                            values_seen.add(value)

                    add_equal(event_id, Payment.gateway_transaction_id)
                    add_equal(event_id, Payment.gateway_transaction_hash)
                    add_equal(event_ref, Payment.gateway_transaction_id)
                    add_equal(event_ref, Payment.gateway_transaction_hash)
                    add_equal(event_ref, Payment.payment_id)

                    if event_hash:
                        search_filters.append(Payment.gateway_transaction_hash.ilike(f"%{event_hash}%"))

                    if event_ref and "_" in event_ref:
                        suffix = event_ref.split("_")[-1]
                        search_filters.append(Payment.payment_id.ilike(f"%{suffix}%"))

                    add_like(event_id)
                    add_like(event_tx)
                    add_like(event_hash)

                    if search_filters:
                        payment = (
                            payment_query
                            .filter(or_(*search_filters))
                            .order_by(Payment.created_at.desc())
                            .first()
                        )

                # 2) Fallback extra: busca incremental se ainda não achou (mantém compatibilidade)
                if not payment:
                    for candidate in filter(None, [event_id, event_tx, data.get('id')]):
                        payment = payment_query.filter_by(gateway_transaction_id=str(candidate).strip()).first()
                        if payment:
                            break

                if not payment and event_hash:
                    payment = payment_query.filter_by(gateway_transaction_hash=event_hash).first()

                if not payment and event_ref:
                    payment = payment_query.filter_by(payment_id=event_ref).first()

                if not payment and event_hash:
                    payment = payment_query.filter(Payment.payment_id.ilike(f"%{event_hash}%")).first()

                if not payment:
                    should_enqueue_pending = not data.get('_skip_pending_enqueue')
                    logger.warning(
                        "❌ Payment não encontrado | gateway=%s | event_id=%s | event_tx=%s | "
                        "event_hash=%s | event_ref=%s | producer=%s | enqueue_pending=%s | payload=%s | result=%s",
                        gateway_type,
                        event_id,
                        event_tx,
                        event_hash,
                        event_ref,
                        producer,
                        should_enqueue_pending,
                        data,
                        result,
                    )
                    if should_enqueue_pending and gateway_type == 'atomopay':
                        try:
                            _enqueue_pending_match(
                                gateway_type=gateway_type,
                                transaction_id=event_id or event_tx,
                                transaction_hash=event_hash,
                                payload=data,
                                status=status
                            )
                        except Exception as pending_error:
                            logger.error(f"❌ Falha ao registrar pending match: {pending_error}", exc_info=True)
                    return {'status': 'payment_not_found'}
                
                if payment:
                    was_pending = payment.status == 'pending'
                    status_antigo = payment.status

                    # ✅ Persistir payment_method (não altera status, não dispara tracking)
                    try:
                        method_from_webhook = result.get('payment_method')
                        if method_from_webhook and not getattr(payment, 'payment_method', None):
                            payment.payment_method = str(method_from_webhook)[:20]
                    except Exception as method_error:
                        logger.warning(f"⚠️ Erro ao salvar payment_method do webhook: {method_error}")
                    
                    # ✅ CRÍTICO: Validação anti-fraude - Rejeitar webhook 'paid' recebido muito rápido após criação
                    # Se payment foi criado há menos de 10 segundos e webhook vem como 'paid', é suspeito
                    if status == 'paid' and payment.created_at:
                        try:
                            from datetime import timedelta
                            tempo_desde_criacao = (get_brazil_time() - payment.created_at).total_seconds()
                            
                            if tempo_desde_criacao < 10:  # Menos de 10 segundos
                                logger.error(
                                    f"🚨 [WEBHOOK {gateway_type.upper()}] BLOQUEADO: Webhook 'paid' recebido muito rápido após criação!"
                                )
                                logger.error(
                                    f"   Payment ID: {payment.payment_id}"
                                )
                                logger.error(
                                    f"   Tempo desde criação: {tempo_desde_criacao:.2f} segundos"
                                )
                                logger.error(
                                    f"   Status do webhook: {status}"
                                )
                                logger.error(
                                    f"   ⚠️ Isso é SUSPEITO - UmbrellaPay não confirma pagamento em menos de 10 segundos!"
                                )
                                logger.error(
                                    f"   🔒 REJEITANDO webhook e mantendo status como 'pending'"
                                )
                                
                                # ✅ Registrar webhook rejeitado para auditoria
                                try:
                                    _persist_webhook_event(
                                        gateway_type=gateway_type,
                                        result={'status': 'pending', 'gateway_transaction_id': gateway_transaction_id},  # Forçar pending
                                        raw_payload=data
                                    )
                                except:
                                    pass
                                
                                return {
                                    'status': 'rejected_too_fast',
                                    'message': f'Webhook paid rejeitado - recebido {tempo_desde_criacao:.2f}s após criação (mínimo: 10s)'
                                }
                        except Exception as time_error:
                            logger.warning(f"⚠️ [WEBHOOK {gateway_type.upper()}] Erro ao calcular tempo desde criação: {time_error}")
                    
                    # ✅ LOGS DETALHADOS: Estado atual do payment
                    logger.info(f"🔍 [WEBHOOK {gateway_type.upper()}] Payment encontrado: {payment.payment_id}")
                    logger.info(f"   Status atual no sistema: {status_antigo}")
                    logger.info(f"   Status do webhook: {status}")
                    logger.info(f"   Era pending: {was_pending}")
                    
                    # ✅ IDEMPOTÊNCIA: Se payment já está paid e webhook também é paid, não atualizar
                    if payment.status == 'paid' and status == 'paid':
                        logger.info(f"♻️ [WEBHOOK {gateway_type.upper()}] Payment já está PAID - Webhook duplicado")
                        logger.info(f"   Tentando reenviar entregável e garantir Meta Purchase...")
                        
                        # ✅ CRÍTICO: Refresh antes de validar status
                        db.session.refresh(payment)
                        
                        # ✅ CRÍTICO: Validar status ANTES de chamar send_payment_delivery
                        if payment.status == 'paid':
                            try:
                                send_payment_delivery(payment)
                                logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Entregável reenviado")
                            except Exception as e:
                                logger.error(f"❌ [WEBHOOK {gateway_type.upper()}] Erro ao reenviar entregável (duplicado): {e}")
                        else:
                            logger.error(
                                f"❌ ERRO GRAVE: send_payment_delivery chamado com payment.status != 'paid' "
                                f"(status atual: {payment.status}, payment_id: {payment.payment_id})"
                            )
                        
                        # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                        # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                        logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
                        
                        # ✅ CORREÇÃO CRÍTICA QI 500: Processar upsells mesmo em webhook duplicado
                        # Upsells podem não ter sido agendados no primeiro webhook se houve algum erro
                        logger.info(f"🔍 [UPSELLS ASYNC WEBHOOK DUPLICADO] Verificando upsells para payment {payment.payment_id}")
                        if payment.bot.config and payment.bot.config.upsells_enabled:
                            logger.info(f"✅ [UPSELLS ASYNC WEBHOOK DUPLICADO] Upsells habilitados - agendando via RQ")
                            try:
                                # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
                                from bot_manager import BotManager
                                local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
                                
                                upsells = payment.bot.config.get_upsells()
                                if upsells:
                                    matched_upsells = []
                                    for upsell in upsells:
                                        trigger_product = upsell.get('trigger_product', '')
                                        if not trigger_product or trigger_product == payment.product_name:
                                            matched_upsells.append(upsell)
                                    
                                    if matched_upsells:
                                        logger.info(f"✅ [UPSELLS ASYNC WEBHOOK DUPLICADO] Agendando {len(matched_upsells)} upsell(s)")
                                        local_bot_manager.schedule_upsells(
                                            bot_id=payment.bot_id,
                                            payment_id=payment.payment_id,
                                            chat_id=int(payment.customer_user_id),
                                            upsells=matched_upsells,
                                            original_price=payment.amount,
                                            original_button_index=-1
                                        )
                            except Exception as upsell_error:
                                logger.error(f"❌ Erro ao processar upsells no webhook duplicado: {upsell_error}", exc_info=True)
                        
                        return {'status': 'already_processed'}
                    
                    # ✅ VALIDAÇÃO: Só atualizar se status mudou
                    if payment.status != status:
                        logger.info(f"🔄 [WEBHOOK {gateway_type.upper()}] Atualizando status: {status_antigo} → {status}")
                        payment.status = status
                    else:
                        logger.info(f"ℹ️ [WEBHOOK {gateway_type.upper()}] Status não mudou ({status}) - não atualizando")

                    status_is_paid = (status == 'paid')
                    deve_processar_estatisticas = status_is_paid and was_pending
                    deve_enviar_entregavel = status_is_paid
                    # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                    # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                    deve_enviar_meta_purchase = False  # ❌ Sempre False - Purchase apenas na página de entrega
                    
                    # ✅ CRÍTICO: Logging detalhado para diagnóstico
                    logger.info(f"🔍 [DIAGNÓSTICO] payment {payment.payment_id}: status='{status}' | deve_enviar_entregavel={deve_enviar_entregavel} | status_antigo='{status_antigo}' | was_pending={was_pending}")
                    logger.info(f"📊 [WEBHOOK {gateway_type.upper()}] Decisões de processamento:")
                    logger.info(f"   Status é paid: {status_is_paid}")
                    logger.info(f"   Deve processar estatísticas: {deve_processar_estatisticas}")
                    logger.info(f"   Deve enviar entregável: {deve_enviar_entregavel}")
                    logger.info(f"   Deve enviar Meta Purchase: {deve_enviar_meta_purchase} (sempre False - Purchase apenas na página de entrega)")

                    if deve_processar_estatisticas:
                        logger.info(f"💰 [WEBHOOK {gateway_type.upper()}] Processando estatísticas e atualizando payment...")
                        payment.paid_at = get_brazil_time()
                        payment.bot.total_sales += 1
                        payment.bot.total_revenue += payment.amount
                        payment.bot.owner.total_sales += 1
                        payment.bot.owner.total_revenue += payment.amount
                        
                        if payment.gateway_type:
                            gateway_obj = Gateway.query.filter_by(
                                user_id=payment.bot.user_id,
                                gateway_type=payment.gateway_type
                            ).first()
                            if gateway_obj:
                                gateway_obj.total_transactions += 1
                                gateway_obj.successful_transactions += 1
                        
                        # Registrar comissão
                        existing_commission = Commission.query.filter_by(payment_id=payment.id).first()
                        if not existing_commission:
                            commission_amount = payment.bot.owner.add_commission(payment.amount)
                            commission = Commission(
                                user_id=payment.bot.owner.id,
                                payment_id=payment.id,
                                bot_id=payment.bot.id,
                                sale_amount=payment.amount,
                                commission_amount=commission_amount,
                                commission_rate=payment.bot.owner.commission_percentage,
                                status='paid',
                                paid_at=get_brazil_time()
                            )
                            db.session.add(commission)
                            payment.bot.owner.total_commission_paid += commission_amount
                        
                        # Gamificação V2.0
                        try:
                            GAMIFICATION_V2_ENABLED = os.environ.get('GAMIFICATION_V2_ENABLED', 'false').lower() == 'true'
                            if GAMIFICATION_V2_ENABLED:
                                payment.bot.owner.update_streak(payment.created_at)
                                from ranking_engine_v2 import RankingEngine
                                from achievement_checker_v2 import AchievementChecker
                                
                                ranking_engine = RankingEngine()
                                ranking_engine.recalculate_user_ranking(payment.bot.owner.id)
                                
                                achievement_checker = AchievementChecker()
                                achievement_checker.check_sale_achievements(payment.bot.owner.id, payment.amount)
                        except Exception as e:
                            logger.warning(f"Erro em gamificação: {e}")
                        
                    # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                    # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                    # ✅ Não disparar Purchase quando pagamento é confirmado (via webhook async)
                    logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
                    
                    # ✅ CRÍTICO: Logging antes de verificar deve_enviar_entregavel
                    logger.info(f"🔍 [DIAGNÓSTICO] payment {payment.payment_id}: Verificando deve_enviar_entregavel={deve_enviar_entregavel} | status='{status}'")
                    if deve_enviar_entregavel:
                        # ✅ CRÍTICO: Refresh antes de validar status
                        db.session.refresh(payment)
                        logger.info(f"✅ [DIAGNÓSTICO] payment {payment.payment_id}: deve_enviar_entregavel=True - VAI ENVIAR ENTREGÁVEL")
                        
                        # ✅ CRÍTICO: Validar status ANTES de chamar send_payment_delivery
                        if payment.status == 'paid':
                            try:
                                logger.info(f"📦 [WEBHOOK {gateway_type.upper()}] Enviando entregável...")
                                send_payment_delivery(payment)
                                logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Entregável enviado com sucesso")
                            except Exception as e:
                                logger.error(f"❌ [WEBHOOK {gateway_type.upper()}] Erro ao enviar entregável: {e}", exc_info=True)
                        else:
                            logger.error(
                                f"❌ ERRO GRAVE: send_payment_delivery chamado com payment.status != 'paid' "
                                f"(status atual: {payment.status}, payment_id: {payment.payment_id})"
                            )
                    else:
                        logger.error(f"❌ [DIAGNÓSTICO] payment {payment.payment_id}: deve_enviar_entregavel=False - NÃO VAI ENVIAR ENTREGÁVEL! (status='{status}')")
                    
                    # ✅ COMMIT: Salvar todas as alterações
                    try:
                        db.session.commit()
                        logger.info(f"💾 [WEBHOOK {gateway_type.upper()}] Pagamento {payment.payment_id} atualizado para '{status}'")
                    except Exception:
                        db.session.rollback()
                        raise
                    finally:
                        _clear_pending_match(
                            gateway_type=gateway_type,
                            transaction_id=event_id or event_tx,
                            transaction_hash=event_hash
                        )
                    
                    # ✅ VALIDAÇÃO PÓS-UPDATE: Refresh e assert
                    db.session.refresh(payment)
                    if payment.status != status:
                        logger.error(f"🚨 [WEBHOOK {gateway_type.upper()}] ERRO CRÍTICO: Status não foi atualizado corretamente!")
                        logger.error(f"   Esperado: {status}, Atual: {payment.status}")
                        logger.error(f"   Payment ID: {payment.payment_id}")
                    else:
                        logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Validação pós-update: Status confirmado como '{payment.status}'")
                    
                    # ============================================================================
                    # ✅ UPSELLS AUTOMÁTICOS - APÓS COMPRA APROVADA (TASKS_ASYNC)
                    # ✅ FLAT CODE: Processamento simplificado com Guard Clauses
                    # ============================================================================
                    
                    # 🛡️ GUARD CLAUSE: Verificar condições uma única vez
                    if status != 'paid' or not payment.bot or not payment.bot.config or not payment.bot.config.upsells_enabled:
                        logger.info(f"ℹ️ [UPSELLS ASYNC] Condições não atendidas para payment {payment.payment_id} - pulando upsells")
                    else:
                        logger.info(f"✅ [UPSELLS ASYNC] Condições atendidas! Processando upsells para payment {payment.payment_id}")
                        
                        try:
                            # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados
                            from internal_logic.core.models import Payment as PaymentModel
                            payment_check = PaymentModel.query.filter_by(payment_id=payment.payment_id).first()
                            
                            # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
                            from bot_manager import BotManager
                            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
                            
                            # Obter upsells configurados
                            upsells = payment.bot.config.get_upsells()
                            if not upsells:
                                logger.info(f"ℹ️ [UPSELLS ASYNC] Lista de upsells vazia para payment {payment.payment_id}")
                            else:
                                logger.info(f"🎯 [UPSELLS ASYNC] Verificando upsells para produto: {payment.product_name}")
                                
                                # Filtrar upsells que fazem match com o produto comprado
                                matched_upsells = [
                                    upsell for upsell in upsells
                                    if not upsell.get('trigger_product') or upsell.get('trigger_product') == payment.product_name
                                ]
                                
                                if matched_upsells:
                                    logger.info(f"✅ [UPSELLS ASYNC] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")
                                    local_bot_manager.schedule_upsells(
                                        bot_id=payment.bot_id,
                                        payment_id=payment.payment_id,
                                        chat_id=int(payment.customer_user_id),
                                        upsells=matched_upsells,
                                        original_price=payment.amount,
                                        original_button_index=-1
                                    )
                                    logger.info(f"📅 [UPSELLS ASYNC] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                else:
                                    logger.info(f"ℹ️ [UPSELLS ASYNC] Nenhum upsell configurado para '{payment.product_name}'")
                                    
                        except Exception as e:
                            logger.error(f"❌ [UPSELLS ASYNC] Erro ao processar upsells para payment {payment.payment_id}: {e}", exc_info=True)
                            import traceback
                            traceback.print_exc()
                    
                    # ✅ Enviar notificação WebSocket APENAS para o dono do bot (após atualizar status para 'paid')
                    if status == 'paid' and payment and payment.bot:
                        try:
                            from internal_logic.core.extensions import socketio
                            if payment.bot.user_id:
                                socketio.emit('payment_update', {
                                    'payment_id': payment.payment_id,
                                    'status': status,
                                    'bot_id': payment.bot_id,
                                    'amount': payment.amount,
                                    'customer_name': payment.customer_name
                                }, room=f'user_{payment.bot.user_id}')
                                logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Notificação WebSocket enviada para user_{payment.bot.user_id} (payment {payment.id})")
                            else:
                                logger.warning(f"⚠️ [WEBHOOK {gateway_type.upper()}] Payment {payment.id} não tem bot.user_id - não enviando notificação WebSocket")
                        except Exception as e:
                            logger.error(f"❌ [WEBHOOK {gateway_type.upper()}] Erro ao emitir notificação WebSocket para payment {payment.id}: {e}")
                    
                    logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Webhook processado com sucesso: {payment.payment_id} -> {status}")
                    logger.info(f"🔍 [DIAGNÓSTICO] process_webhook_async - SUCESSO para payment {payment.payment_id}")
                    return {'status': 'success', 'payment_id': payment.payment_id}
                else:
                    logger.warning(f"⚠️ Payment não encontrado para webhook: {gateway_transaction_id}")
                    logger.warning(f"🔍 [DIAGNÓSTICO] process_webhook_async - Payment NÃO encontrado: gateway_transaction_id={gateway_transaction_id}")
                    return {'status': 'payment_not_found'}
            else:
                logger.critical(f"⚠️ [WEBHOOK WORKER] Webhook não processado: result=None | Job: {job_id}")
                return {'status': 'not_processed'}
                
    except OperationalError as oe:
        logger.critical(f"🚨 [WEBHOOK WORKER] OperationalError - Falha de conexão DB: {oe}", exc_info=True)
        return {'status': 'error', 'error': f'Database connection error: {str(oe)}'}
    except IntegrityError as ie:
        logger.critical(f"🚨 [WEBHOOK WORKER] IntegrityError - Violação de constraint: {ie}", exc_info=True)
        return {'status': 'error', 'error': f'Integrity error: {str(ie)}'}
    except SQLAlchemyError as se:
        logger.critical(f"🚨 [WEBHOOK WORKER] SQLAlchemyError: {se}", exc_info=True)
        return {'status': 'error', 'error': f'Database error: {str(se)}'}
    except Exception as e:
        logger.critical(f"💀 [WEBHOOK WORKER] ERRO CRÍTICO: {e}", exc_info=True)
        logger.critical(f"💀 [WEBHOOK WORKER] Exception type: {type(e).__name__}")
        logger.critical(f"💀 [WEBHOOK WORKER] Exception message: {str(e)}")
        return {'status': 'error', 'error': str(e)}
    finally:
        logger.critical(f"🏁 [WEBHOOK WORKER EXIT] Job: {job_id} finalizado")


def reconcile_paradise_payments_async():
    """Reconciliador Paradise em fila async"""
    try:
        from internal_logic.services.payment_processor import reconcile_paradise_payments
        reconcile_paradise_payments()
    except Exception as e:
        logger.error(f"❌ Erro em reconcile_paradise_payments_async: {e}", exc_info=True)

def reconcile_pushynpay_payments_async():
    """Reconciliador PushynPay em fila async"""
    try:
        from internal_logic.services.payment_processor import reconcile_pushynpay_payments
        reconcile_pushynpay_payments()
    except Exception as e:
        logger.error(f"❌ Erro em reconcile_pushynpay_payments_async: {e}", exc_info=True)

def process_pending_webhooks(limit: int = 50, max_attempts: int = 12) -> int:
    """
    Reprocessa webhooks armazenados em webhook_pending_matches.

    Retorna quantidade processada com sucesso.
    """
    from internal_logic.core.models import WebhookPendingMatch, get_brazil_time

    processed = 0

    _ensure_aux_tables()

    with app.app_context():
        pendings = (
            WebhookPendingMatch.query
            .order_by(WebhookPendingMatch.last_attempt_at.asc().nullsfirst())
            .limit(limit)
            .all()
        )

        for pending in pendings:
            try:
                payload = dict(pending.payload or {})
                payload['_skip_pending_enqueue'] = True
                pending.attempts = (pending.attempts or 0) + 1
                pending.last_attempt_at = get_brazil_time()
                db.session.commit()

                result = process_webhook_async(pending.gateway_type, payload)
                status = (result or {}).get('status')

                if status in {'success', 'already_processed'}:
                    db.session.delete(pending)
                    db.session.commit()
                    processed += 1
                elif pending.attempts >= max_attempts:
                    logger.error(
                        "❌ Pending webhook descartado após %s tentativas | gateway=%s | transaction_id=%s | hash=%s",
                        pending.attempts,
                        pending.gateway_type,
                        pending.transaction_id,
                        pending.transaction_hash
                    )
                    db.session.delete(pending)
                    db.session.commit()
            except Exception as e:
                logger.error(f"❌ Erro ao reprocessar pending webhook: {e}", exc_info=True)
                db.session.rollback()

    return processed


def generate_pix_async(
    bot_id: int,
    token: str,
    chat_id: int,
    user_info: Dict[str, Any],
    button_index: int,
    config: Dict[str, Any]
):
    """
    Gera PIX de forma assíncrona (FILA GATEWAY)
    
    Executa:
    - Validação de produto
    - Criação de offer
    - Criação de payment
    - Geração de PIX via gateway
    - Envio de mensagem com QR Code
    """
    try:
        from flask import current_app
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Bot, BotConfig, Payment, Gateway
        from gateway_factory import GatewayFactory
        from bot_manager import BotManager
        import uuid
        import time
        
        with current_app.app_context():
            bot = db.session.get(Bot, bot_id)
            if not bot:
                logger.error(f"Bot {bot_id} não encontrado")
                return
            
            # Recarregar config
            if bot.config:
                config = bot.config.to_dict()
            
            main_buttons = config.get('main_buttons', [])
            if button_index >= len(main_buttons):
                logger.error(f"Índice de botão inválido: {button_index}")
                return
            
            button = main_buttons[button_index]
            price = float(button.get('price', 0))
            product_name = button.get('text', 'Produto')
            
            # Buscar gateway
            gateway = Gateway.query.filter_by(
                user_id=bot.user_id,
                gateway_type=config.get('gateway_type', 'syncpay')
            ).first()
            
            if not gateway:
                logger.error(f"Gateway não encontrado para bot {bot_id}")
                return
            
            # Criar payment
            payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            payment = Payment(
                bot_id=bot_id,
                payment_id=payment_id,
                customer_user_id=str(chat_id),
                customer_name=user_info.get('first_name', 'Cliente'),
                product_name=product_name,
                amount=price,
                gateway_type=gateway.gateway_type,
                status='pending'
            )
            
            db.session.add(payment)
            db.session.commit()
            
            # Criar gateway instance
            credentials = gateway.get_decrypted_credentials()
            gateway_instance = GatewayFactory.create_gateway(
                gateway.gateway_type,
                credentials,
                use_adapter=True
            )
            
            if not gateway_instance:
                logger.error(f"Erro ao criar gateway instance")
                return
            
            # Gerar PIX
            pix_result = gateway_instance.create_payment(
                amount=price,
                customer={
                    'name': user_info.get('first_name', 'Cliente'),
                    'email': f"user_{chat_id}@telegram.local",
                    'phone': '11999999999',
                    'document': '00000000000'
                },
                description=product_name,
                external_reference=payment_id
            )
            
            if pix_result:
                pix_code = (
                    pix_result.get('pix_qr_code')
                    or pix_result.get('pix_code')
                    or pix_result.get('qr_code')
                    or pix_result.get('emv')
                )
            else:
                pix_code = None

            has_transaction = False
            if pix_result:
                transaction_id_value = (
                    pix_result.get('transaction_id')
                    or pix_result.get('id')
                    or pix_result.get('hash')
                    or pix_result.get('transaction_hash')
                )
                gateway_hash_value = (
                    pix_result.get('gateway_hash')
                    or pix_result.get('hash')
                    or pix_result.get('transaction_hash')
                )
                if transaction_id_value or gateway_hash_value:
                    payment.gateway_transaction_id = str(transaction_id_value or '')
                    payment.gateway_transaction_hash = str(gateway_hash_value or '')
                    has_transaction = True

            if has_transaction:
                db.session.commit()
                
                if pix_code:
                    # Enviar mensagem com QR Code
                    # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
                    from bot_manager import BotManager
                    local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.user_id)
                    
                    message = f"💰 PIX Gerado!\n\nValor: R$ {price:.2f}\n\nEscaneie o QR Code ou copie o código PIX:"
                    qr_code = pix_code
                    
                    local_bot_manager.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        buttons=[{
                            'text': '✅ Verificar Pagamento',
                            'callback_data': f'verify_{payment.id}'
                        }]
                    )
                    
                    # Enviar QR Code como imagem
                    media_url = (
                        pix_result.get('pix_qr_code_image')
                        or pix_result.get('qr_code_url')
                        or pix_result.get('qr_code_base64')
                    )
                    if media_url:
                        local_bot_manager.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="",
                            media_url=media_url,
                            media_type='photo'
                        )
                else:
                    logger.warning(f"⚠️ PIX gerado sem código disponível imediato: payment_id={payment.payment_id} (aguardando webhook).")
                
                logger.info(f"✅ PIX gerado: {payment_id}")
            else:
                logger.error(f"Erro ao gerar PIX: {pix_result}")
                
    except Exception as e:
        logger.error(f"❌ Erro em generate_pix_async: {e}", exc_info=True)


def task_process_broadcast_campaign(campaign_id: int):
    """
    ✅ Worker RQ para processar campanha de remarketing (Marathon Engine).
    
    🏗️ REFATORADO: Arquitetura Master Pre-Allocation + Marathon Engine
    - A campanha JÁ EXISTE no banco (criada pela API) - recebemos apenas o ID
    - Marathon Engine: Resiliência para 50k+ leads com:
      * FloodWait handling (obedece retry_after do Telegram)
      * Network Timeout recovery (10s backoff)
      * Macro-Batching (resfriamento a cada 800 envios)
      * Job timeout estendido para 12h
    
    Args:
        campaign_id: ID da campanha RemarketingCampaign já existente no banco
    """
    from flask import current_app
    from internal_logic.core.extensions import db
    from internal_logic.core.models import Bot, BotUser, Payment, RemarketingBlacklist, RemarketingCampaign, get_brazil_time
    from bot_manager import BotManager
    from datetime import timedelta
    from redis_manager import get_redis_connection
    import json
    import time
    import requests
    
    with current_app.app_context():
        try:
            # ✅ BUSCAR CAMPANHA EXISTENTE NO BANCO
            campaign = db.session.query(RemarketingCampaign).get(campaign_id)
            if not campaign:
                logger.error(f"🚨 [MARATHON] Campanha {campaign_id} não encontrada no banco!")
                return
            
            # Extrair todos os dados da campanha
            bot_id = campaign.bot_id
            group_id = campaign.group_id
            message_template = campaign.message or ''
            media_url = campaign.media_url
            media_type = campaign.media_type or 'video'
            audio_enabled = campaign.audio_enabled or False
            audio_url = campaign.audio_url or ''
            buttons = json.loads(campaign.buttons) if campaign.buttons else []
            days_since_last_contact = campaign.days_since_last_contact or 7
            audience_segment = campaign.target_audience or 'all_users'
            
            # ✅ CORREÇÃO: Passar audience_segment diretamente (sem mapeamento)
            # O count_eligible_leads() espera o audience_segment original do frontend
            target_audience = audience_segment
            
            # ✅ INICIALIZAR CONEXÕES
            redis_conn = get_redis_connection()
            
            # ✅ ISOLAMENTO: Buscar bot para obter user_id
            from internal_logic.core.models import Bot
            bot = Bot.query.get(bot_id)
            if not bot:
                logger.error(f"❌ [MARATHON SETUP] Bot {bot_id} não encontrado")
                return
            
            # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do bot
            from bot_manager import BotManager
            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=bot.user_id)
            contact_limit = get_brazil_time() - timedelta(days=days_since_last_contact)
            
            # ==========================================
            # 🎯 FASE DE CONTAGEM DE LEADS (Worker Setup)
            # ==========================================
            logger.info(f"🔍 [MARATHON SETUP] Contando leads elegíveis para campanha {campaign_id} | Bot: {bot_id}")
            
            # Contar leads elegíveis usando o método correto (count_eligible_leads)
            total_targets = local_bot_manager.count_eligible_leads(
                bot_id=bot_id,
                target_audience=target_audience,
                days_since_last_contact=days_since_last_contact,
                exclude_buyers=False,  # Já filtrado pelo target_audience
                audience_segment=audience_segment
            )
            
            logger.info(f"📊 [MARATHON SETUP] Campanha {campaign_id} | Leads elegíveis encontrados: {total_targets}")
            
            # Se 0 leads, finalizar imediatamente
            if total_targets == 0:
                logger.info(f"ℹ️ [MARATHON SETUP] Campanha {campaign_id}: 0 leads elegíveis, finalizando")
                campaign.status = 'completed'
                campaign.completed_at = get_brazil_time()
                campaign.total_targets = 0
                campaign.total_sent = 0
                campaign.total_failed = 0
                db.session.commit()
                return
            
            # Atualizar campanha com o total real de targets
            campaign.total_targets = total_targets
            db.session.commit()
            
            logger.info(f"✅ [MARATHON SETUP] Campanha {campaign_id} | total_targets atualizado: {total_targets}")
            
            # Taxa limit base: Telegram permite 30 mensagens/segundo
            RATE_LIMIT_MSGS_PER_SEC = 30
            rate_limit_delay = 1.0 / RATE_LIMIT_MSGS_PER_SEC
            
            # 🏃 MARATHON ENGINE: Contadores para Macro-Batching
            consecutive_sent = 0
            MACRO_BATCH_SIZE = 800
            MACRO_BATCH_COOLDOWN = 45  # segundos
            
            logger.info(f"🚀 [MARATHON ENGINE] Iniciando campanha | campaign_id={campaign_id} | bot_id={bot_id} | leads={total_targets}")
            
            # ==========================================
            # 🚀 INICIAR PROCESSAMENTO (Campanha já existe)
            # ==========================================
            
            # Buscar bot e validar
            bot = Bot.query.get(bot_id)
            if not bot:
                logger.error(f"⚠️ [MARATHON] Bot {bot_id} não encontrado")
                campaign.status = 'failed'
                campaign.completed_at = get_brazil_time()
                db.session.commit()
                return
            
            # Atualizar status para 'sending'
            campaign.status = 'sending'
            campaign.started_at = get_brazil_time()
            db.session.commit()
            
            logger.info(f"📊 [MARATHON] Processando bot {bot.name} (ID: {bot_id}) | Campaign: {campaign_id}")
            
            # ==========================================
            # 🚀 MARATHON PROCESSING LOOP
            # ==========================================
            logger.info(f"🏃 [MARATHON] Iniciando envio para {total_targets} leads | Bot: {bot.name}")
            
            # Chaves Redis
            sent_set_key = f"gb:{bot.user_id}:remarketing:sent:{campaign_id}"
            blacklist_key = f"gb:{bot.user_id}:remarketing:blacklist:{bot_id}"
            
            # Variáveis de controle
            bot_token_str = str(bot.token)
            campaign_id_int = int(campaign_id)
            batch_size = 200
            offset = 0
            sent_count = 0
            failed_count = 0
            skipped_count = 0
            bot_is_dead = False
            
            # Query de leads elegíveis
            q = db.session.query(BotUser).filter(
                BotUser.bot_id == bot_id,
                BotUser.archived == False
            )
            
            if days_since_last_contact > 0:
                q = q.filter(BotUser.last_interaction <= contact_limit)
            
            # Filtrar blacklist usando subquery (performance em escala)
            blacklist_subquery = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                bot_id=bot_id
            )
            q = q.filter(~BotUser.telegram_user_id.in_(blacklist_subquery))
            
            # Filtros de segmento (usando subqueries para performance em escala)
            if target_audience == 'all_users':
                # Todos os usuários - sem filtro adicional
                pass
            elif target_audience == 'buyers':
                # Todos que compraram (status = 'paid') - usando subquery
                buyer_subquery = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid'
                ).distinct()
                q = q.filter(BotUser.telegram_user_id.in_(buyer_subquery))
            elif target_audience == 'non_buyers':
                # Excluir compradores - usando subquery com ~in_
                buyer_subquery = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid'
                ).distinct()
                q = q.filter(~BotUser.telegram_user_id.in_(buyer_subquery))
            elif target_audience == 'abandoned_cart' or target_audience == 'pix_generated':
                # Usuários que geraram PIX mas não pagaram (status = 'pending') - subquery
                pending_subquery = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'pending'
                ).distinct()
                q = q.filter(BotUser.telegram_user_id.in_(pending_subquery))
            elif target_audience == 'downsell_buyers':
                # Todos que compraram via downsell - subquery
                downsell_subquery = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.is_downsell == True
                ).distinct()
                q = q.filter(BotUser.telegram_user_id.in_(downsell_subquery))
            elif target_audience == 'order_bump_buyers':
                # Todos que compraram com order bump - subquery
                orderbump_subquery = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.order_bump_accepted == True
                ).distinct()
                q = q.filter(BotUser.telegram_user_id.in_(orderbump_subquery))
            elif target_audience == 'upsell_buyers':
                # Todos que compraram via upsell - subquery
                upsell_subquery = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.is_upsell == True
                ).distinct()
                q = q.filter(BotUser.telegram_user_id.in_(upsell_subquery))
            elif target_audience == 'remarketing_buyers':
                # Todos que compraram via remarketing - subquery
                remarketing_subquery = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.is_remarketing == True
                ).distinct()
                q = q.filter(BotUser.telegram_user_id.in_(remarketing_subquery))
            
            # ✅ CONSISTÊNCIA DE PAGINAÇÃO: ORDER BY obrigatório
            q = q.order_by(BotUser.id)
            
            # Loop principal de envio
            processed_in_batch = 0  # ✅ CHECKPOINT INCREMENTAL: Contador de progresso
            CHECKPOINT_INTERVAL = 20  # ✅ Commit a cada 20 leads
            
            while offset < total_targets and not bot_is_dead:
                batch = q.offset(offset).limit(batch_size).all()
                if not batch:
                    break
                
                for lead in batch:
                    try:
                        # Validar chat_id
                        if not lead.telegram_user_id:
                            skipped_count += 1
                            processed_in_batch += 1
                            continue
                        
                        try:
                            chat_int = int(str(lead.telegram_user_id))
                            if chat_int == 0:
                                skipped_count += 1
                                processed_in_batch += 1
                                continue
                        except:
                            skipped_count += 1
                            processed_in_batch += 1
                            continue
                        
                        # Verificar se já enviou (Redis)
                        if redis_conn.sismember(sent_set_key, str(lead.telegram_user_id)):
                            skipped_count += 1
                            processed_in_batch += 1
                            continue
                        
                        # Verificar blacklist (Redis)
                        if redis_conn.sismember(blacklist_key, str(lead.telegram_user_id)):
                            skipped_count += 1
                            processed_in_batch += 1
                            continue
                        
                        # Verificar opt-out
                        if getattr(lead, 'opt_out', False) or getattr(lead, 'unsubscribed', False):
                            skipped_count += 1
                            processed_in_batch += 1
                            continue
                        
                        # ✅ MONTAR MENSAGEM PERSONALIZADA
                        personalized_message = message_template.replace('{nome}', lead.first_name or 'Cliente')
                        personalized_message = personalized_message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])
                        
                        # ✅ MONTAR BOTÕES
                        remarketing_buttons = []
                        if buttons:
                            for btn_idx, btn in enumerate(buttons):
                                if btn.get('price') and btn.get('description'):
                                    remarketing_buttons.append({
                                        'text': btn.get('text', 'Comprar'),
                                        'callback_data': f"rmkt_{campaign_id_int}_{btn_idx}"
                                    })
                                elif btn.get('url'):
                                    remarketing_buttons.append({
                                        'text': btn.get('text', 'Link'),
                                        'url': btn.get('url')
                                    })
                        
                        # ✅ MARATHON LOOP DE RETRY (com FloodWait e Network handling)
                        lead_sent = False
                        flood_wait_happened = False
                        floodwait_attempts = 0  # ✅ Contador de FloodWait consecutivos
                        
                        for attempt in range(3):
                            try:
                                result = local_bot_manager.send_telegram_message(
                                    token=bot_token_str,
                                    chat_id=str(lead.telegram_user_id),
                                    message=personalized_message,
                                    media_url=media_url,
                                    media_type=media_type if media_url else None,
                                    audio_url=audio_url if audio_enabled and audio_url else None,
                                    buttons=remarketing_buttons if remarketing_buttons else None
                                )
                                
                                # 🚨 VALIDAÇÃO STRICT
                                if isinstance(result, dict) and result.get('error'):
                                    error_code = result.get('error_code')
                                    
                                    # 🌊 FLOODWAIT HANDLING: Erro 429 com retry_after explícito
                                    if error_code == 429:
                                        retry_after = result.get('retry_after')
                                        floodwait_attempts += 1
                                        
                                        # ✅ QUEBRA DE CICLO: Se já tentou 3x com FloodWait, desistir do lead
                                        if floodwait_attempts >= 3:
                                            logger.error(f"❌ [FLOODWAIT] Lead {lead.telegram_user_id} esgotou 3 tentativas de FloodWait. Contabilizando falha.")
                                            break  # Sai do for attempt, lead será marcado como falha
                                        
                                        if retry_after:
                                            logger.warning(f"⏸️ [FLOODWAIT] Telegram pediu espera de {retry_after}s (tentativa {floodwait_attempts}/3)")
                                            time.sleep(retry_after)
                                            flood_wait_happened = True
                                            # NÃO contar como tentativa usada - tentar mesmo lead novamente
                                            continue
                                        else:
                                            # Fallback: retry_after não fornecido, aguardar 30s
                                            logger.warning(f"⏸️ [FLOODWAIT] 429 sem retry_after, aguardando 30s")
                                            time.sleep(30)
                                            continue
                                    
                                    # Outros erros: lançar exceção para tratamento downstream
                                    raise Exception(f"status={error_code}, desc={result.get('description', '')}")
                                
                                elif not result:
                                    raise Exception("Falha silenciosa: Função retornou False ou None")
                                
                                # ✅ SUCESSO REAL
                                sent_count += 1
                                consecutive_sent += 1
                                redis_conn.sadd(sent_set_key, str(lead.telegram_user_id))
                                lead_sent = True
                                flood_wait_happened = False
                                
                                # 🎯 MACRO-BATCHING: Resfriamento a cada 800 envios consecutivos
                                if consecutive_sent >= MACRO_BATCH_SIZE:
                                    logger.info(f"⏸️ [MACRO-BATCH] Resfriando API por {MACRO_BATCH_COOLDOWN}s após {consecutive_sent} envios")
                                    time.sleep(MACRO_BATCH_COOLDOWN)
                                    consecutive_sent = 0
                                
                                if sent_count % 100 == 0:
                                    logger.info(f"📤 [MARATHON] Bot {bot_id} | Progresso: {sent_count}/{total_targets} | Campaign: {campaign_id_int}")
                                
                                break  # Sucesso, sair do loop de retry
                                
                            except requests.exceptions.Timeout as timeout_err:
                                # 🌐 NETWORK TIMEOUT HANDLING: Aguardar 10s e tentar novamente
                                logger.warning(f"⏱️ [NETWORK TIMEOUT] Timeout na tentativa {attempt + 1}/3. Aguardando 10s...")
                                time.sleep(10)
                                if attempt == 2:
                                    logger.error(f"❌ [NETWORK TIMEOUT] Esgotadas 3 tentativas para {lead.telegram_user_id}")
                                continue
                                
                            except Exception as send_error:
                                error_str = str(send_error).lower()
                                result_from_exception = send_error  # fallback para inspeção

                                # ══════════════════════════════════════════════════════════════════
                                # TELEGRAM ERROR TAXONOMY — 3 BUCKETS ESTRITOS
                                # Fonte: Telegram Bot API — https://core.telegram.org/bots/api#making-requests
                                # ══════════════════════════════════════════════════════════════════

                                # ──────────────────────────────────────────────────────────────────
                                # BUCKET 1: USER_FATAL — O problema é o Lead
                                # Ação: blacklist + failed_count++ + break (tentativas) + continue (próximo lead)
                                # A campanha NÃO PARA.
                                # ──────────────────────────────────────────────────────────────────
                                USER_FATAL_KEYWORDS = [
                                    # 403 Forbidden — Usuário bloqueou o bot ou o bot foi removido do chat
                                    'bot was blocked by the user',
                                    'user is deactivated',                  # Conta Telegram deletada/desativada
                                    'have no rights to send a message',     # Bot sem permissão nesse chat específico
                                    'not enough rights',                    # Permissão insuficiente (chat específico)
                                    # 400 Bad Request — O destinatário/chat não existe ou é inválido
                                    'chat not found',
                                    'user not found',
                                    'chat_id is empty',
                                    'peer_id_invalid',                      # ID de peer inválido (MTProto traduzido)
                                    'input_user_deactivated',               # Variante MTProto de conta desativada
                                    'bot was kicked from the group',        # Bot expulso do grupo (problema desse chat)
                                    'bot was kicked from the supergroup',
                                    'bot is not a member',                  # Bot não é membro do canal/grupo
                                    'need administrator rights',            # Falta de admin nesse chat específico
                                    'group chat was upgraded to a supergroup',  # Chat migrou, ID antigo inválido
                                    'blocked by the user',                  # Variante curta
                                    'user blocked',                         # Variante interna
                                ]

                                is_user_fatal = any(kw in error_str for kw in USER_FATAL_KEYWORDS)

                                # ──────────────────────────────────────────────────────────────────
                                # BUCKET 3: BOT_FATAL — O problema é o Sistema/Credenciais
                                # Verificado ANTES do RETRYABLE para evitar retry infinito em token morto.
                                # Ação: bot_is_dead = True + break no loop principal.
                                # ──────────────────────────────────────────────────────────────────
                                BOT_FATAL_KEYWORDS = [
                                    # 401 Unauthorized — Token inválido, revogado ou bot deletado pelo owner
                                    'unauthorized',
                                    'token is invalid',
                                    'bot token is invalid',
                                    '401',
                                    # Bot banido globalmente pela plataforma Telegram
                                    'bot was banned',
                                    'this bot has been blocked',            # Bloqueio global (diferente de por usuário)
                                    # Webhook conflitando — indica misconfiguration sistêmica
                                    'terminated by other getupdates request',
                                ]

                                is_bot_fatal = any(kw in error_str for kw in BOT_FATAL_KEYWORDS)

                                # ──────────────────────────────────────────────────────────────────
                                # BUCKET 2: RETRYABLE — O problema é Rede/Rate Limits
                                # Ação: sleep (retry_after ou backoff) + continue no loop de tentativas.
                                # Se esgotar tentativas: failed_count++ + continue (próximo lead).
                                # A campanha NÃO PARA.
                                # ──────────────────────────────────────────────────────────────────
                                RETRYABLE_KEYWORDS = [
                                    # 429 Too Many Requests — FloodWait explícito do Telegram
                                    'too many requests',
                                    'retry_after',
                                    'flood',
                                    # 5xx — Erros do lado do servidor Telegram (instabilidade)
                                    '500',
                                    '502',
                                    '503',
                                    '504',
                                    'bad gateway',
                                    'service unavailable',
                                    'gateway timeout',
                                    'internal server error',
                                    # Erros de rede/transporte (requests library)
                                    'connection',
                                    'timeout',
                                    'timed out',
                                    'network',
                                    'remotedisconnected',
                                    'connectionreset',
                                    'connectionrefused',
                                    # 400 temporários/ambíguos que podem ser retentados
                                    'migrate_to_chat_id',               # Chat migrou — pode ser retentado com novo ID
                                    'retry',
                                ]

                                is_retryable = any(kw in error_str for kw in RETRYABLE_KEYWORDS)

                                # ══════════════════════════════════════════════════════════════════
                                # ROTEADOR DE BUCKETS — Prioridade: BOT_FATAL > USER_FATAL > RETRYABLE
                                # ══════════════════════════════════════════════════════════════════

                                if is_bot_fatal:
                                    # ── BUCKET 3: BOT_FATAL ────────────────────────────────────────
                                    logger.error(
                                        f"🚨 [BOT_FATAL] Token morto/revogado para bot_id={bot_id}. "
                                        f"Motivo: '{send_error}'. Encerrando campanha deste bot."
                                    )
                                    bot_is_dead = True
                                    db.session.query(Bot).filter(Bot.id == bot_id).update({
                                        'is_active': False,
                                        'last_error': f"[BOT_FATAL] Desativado automaticamente: {str(send_error)[:200]}"
                                    })
                                    db.session.commit()
                                    break  # ← Sai do for attempt (loop de tentativas)

                                elif is_user_fatal:
                                    # ── BUCKET 1: USER_FATAL ───────────────────────────────────────
                                    logger.info(
                                        f"🚫 [USER_FATAL] Lead {lead.telegram_user_id} inválido/bloqueado. "
                                        f"Motivo: '{send_error}'. Adicionando à blacklist."
                                    )
                                    redis_conn.sadd(blacklist_key, str(lead.telegram_user_id))
                                    lead.unsubscribed = True
                                    lead.inactive = True
                                    failed_count += 1
                                    # ✅ Removido db.session.commit() - aguarda checkpoint incremental (a cada 20 leads)
                                    break  # ← Sai do for attempt; próximo lead via continue externo

                                elif is_retryable:
                                    # ── BUCKET 2: RETRYABLE ────────────────────────────────────────
                                    # ✅ Correção SRE: Extrair retry_after via Regex (não hasattr)
                                    retry_after_secs = None
                                    match = re.search(r'retry[_\s]after[=\s]*(\d+)', error_str)
                                    if match:
                                        retry_after_secs = int(match.group(1))
                                    
                                    if retry_after_secs:
                                        sleep_time = int(retry_after_secs) + 1  # +1s de margem de segurança
                                        logger.warning(
                                            f"⏸️ [RETRYABLE/FLOODWAIT] Lead {lead.telegram_user_id}, "
                                            f"tentativa {attempt + 1}/3. "
                                            f"Telegram pediu {retry_after_secs}s. Aguardando {sleep_time}s."
                                        )
                                    else:
                                        # Exponential Backoff: 5s, 15s, 45s para tentativas 1, 2, 3
                                        sleep_time = (3 ** attempt) * 5
                                        logger.warning(
                                            f"⏸️ [RETRYABLE/BACKOFF] Lead {lead.telegram_user_id}, "
                                            f"tentativa {attempt + 1}/3. "
                                            f"Erro: '{send_error}'. Backoff: {sleep_time}s."
                                        )
                                    
                                    time.sleep(sleep_time)

                                    if attempt >= 2:  # Última tentativa (0, 1, 2)
                                        # Esgotou todas as tentativas — falha do lead, campanha continua
                                        logger.error(
                                            f"❌ [RETRYABLE_EXHAUSTED] Lead {lead.telegram_user_id} esgotou "
                                            f"3 tentativas. Contabilizando como falha."
                                        )
                                        failed_count += 1
                                        # Não adiciona à blacklist — é erro temporário, não permanente
                                    # continue implícito: o loop de `attempt` segue para a próxima tentativa

                                else:
                                    # ── BUCKET FALLBACK: UNKNOWN ────────────────────────────────────
                                    # Erro não mapeado — trata como RETRYABLE conservador para não matar campanha
                                    sleep_time = (3 ** attempt) * 5
                                    logger.warning(
                                        f"⚠️ [UNKNOWN_ERROR] Lead {lead.telegram_user_id}, "
                                        f"tentativa {attempt + 1}/3. "
                                        f"Erro não classificado: '{send_error}'. "
                                        f"Tratando como RETRYABLE. Backoff: {sleep_time}s."
                                    )
                                    time.sleep(sleep_time)

                                    if attempt >= 2:  # Última tentativa
                                        logger.error(
                                            f"❌ [UNKNOWN_EXHAUSTED] Lead {lead.telegram_user_id} esgotou tentativas "
                                            f"em erro desconhecido. Contabilizando como falha."
                                        )
                                        failed_count += 1
                        
                        # ✅ TRAVA DE SEGURANÇA SRE: Abortar lote se bot morreu
                        if bot_is_dead:
                            break  # ← Este break sai do 'for lead in batch'
                        
                        # ✅ CHECKPOINT INCREMENTAL: Atualizar dashboard a cada 20 leads
                        processed_in_batch += 1
                        if not lead_sent and not bot_is_dead:
                            failed_count += 1
                        
                        if bot_is_dead:
                            break
                        
                        # Rate limit apenas se não houve FloodWait já
                        if not flood_wait_happened:
                            time.sleep(rate_limit_delay)
                        
                        # ✅ Commit incremental a cada 20 leads ou último do batch (Stateless SQL Update)
                        if processed_in_batch >= CHECKPOINT_INTERVAL or lead == batch[-1]:
                            db.session.query(RemarketingCampaign).filter(
                                RemarketingCampaign.id == campaign_id
                            ).update({
                                'total_sent': sent_count,
                                'total_failed': failed_count
                            }, synchronize_session=False)
                            db.session.commit()
                            processed_in_batch = 0  # Reset contador
                            
                    except Exception as lead_error:
                        failed_count += 1
                        processed_in_batch += 1
                        logger.error(f"❌ [MARATHON] Erro processando lead {lead.id}: {lead_error}")
                        continue
                
                # Checkpoint a cada batch - atualizar campanha via SQL direto (Stateless)
                offset += batch_size
                
                db.session.query(RemarketingCampaign).filter(
                    RemarketingCampaign.id == campaign_id
                ).update({
                    'total_sent': sent_count,
                    'total_failed': failed_count
                }, synchronize_session=False)
                db.session.commit()
                
                # Limpeza de memória
                db.session.expunge_all()
            
            # ✅ FINALIZAR CAMPANHA (Stateless SQL Update - evita DetachedInstanceError)
            final_status = 'failed' if bot_is_dead else 'completed'
            db.session.query(RemarketingCampaign).filter(
                RemarketingCampaign.id == campaign_id
            ).update({
                'status': final_status,
                'completed_at': get_brazil_time(),
                'total_sent': sent_count,
                'total_failed': failed_count
            }, synchronize_session=False)
            db.session.commit()
            
            logger.info(f"🏁 [MARATHON ENGINE] Campaign {campaign_id} finalizada | Bot {bot_id} | Enviados: {sent_count} | Falhas: {failed_count} | Bot morto: {bot_is_dead}")
            
        except Exception as e:
            logger.error(f"❌ [MARATHON ENGINE] Erro fatal na campanha {campaign_id}: {e}", exc_info=True)
            # Tentar marcar como failed
            try:
                if 'campaign' in locals() and campaign:
                    campaign.status = 'failed'
                    campaign.completed_at = get_brazil_time()
                    db.session.commit()
            except:
                pass
            raise


# ============================================================================
# ✅ MIGRAÇÃO RQ: Jobs para Downsells e Upsells (APScheduler removido)
# ============================================================================

def send_downsell_async(
    user_id: int,  # ?? CORREÇÃO: user_id como primeiro parâmetro (sem wrapper)
    bot_id: int,
    payment_id: str,
    chat_id: int,
    downsell: dict,
    index: int,
    original_price: float,
    original_button_index: int
):
    """
    Job RQ para enviar downsell agendado
    Executado pelos workers RQ da fila 'marathon'
    """
    from internal_logic.core.models import Payment
    
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
            
            # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
            from bot_manager import BotManager
            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
            
            # Executar envio do downsell
            result = local_bot_manager._send_downsell(
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


def send_downsell_job(bot_id: int, payment_id: str, chat_id: int, downsell: dict, 
                       index: int, original_price: float, original_button_index: int):
    """
    Job RQ para enviar downsell agendado
    Executado pelos workers RQ da fila 'tasks' ou 'marathon'
    """
    from internal_logic.core.models import Payment
    
    with app.app_context():
        try:
            # ✅ ANTI-DUPLICAÇÃO: Verificar se pagamento está pago
            payment = Payment.query.filter_by(payment_id=payment_id).first()
            
            if not payment:
                logger.warning(f"⚠️ [DOWNSELL JOB] Payment {payment_id} não encontrado - ignorando")
                return False
            
            if payment.status != 'paid':
                logger.info(f"ℹ️ [DOWNSELL JOB] Payment {payment_id} status='{payment.status}' - downsell cancelado")
                return False
            
            # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
            from bot_manager import BotManager
            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
            
            # Executar envio do downsell
            result = local_bot_manager._send_downsell(
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
    from internal_logic.core.models import Payment
    
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
            
            # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
            from bot_manager import BotManager
            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
            
            # Executar envio do upsell
            result = local_bot_manager._send_upsell(
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
