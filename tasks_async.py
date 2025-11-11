"""
Tasks Assíncronas QI 200 - Redis Queue (RQ)
3 FILAS SEPARADAS para máxima performance:
1. tasks - Telegram (urgente)
2. gateway - Gateway/PIX/Reconciliadores
3. webhook - Webhooks de pagamento
"""

import os
import logging
from rq import Queue
from redis import Redis
from typing import Dict, Any, Optional
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from redis_manager import get_redis_connection

logger = logging.getLogger(__name__)

# Conectar ao Redis
try:
    # ✅ QI 500: Usar connection pool para RQ (decode_responses=False para bytes)
    # RQ serializa jobs como bytes comprimidos, não strings
    redis_conn = get_redis_connection(decode_responses=False)
    
    # ✅ QI 200: 3 FILAS SEPARADAS
    task_queue = Queue('tasks', connection=redis_conn)  # Telegram (urgente)
    gateway_queue = Queue('gateway', connection=redis_conn)  # Gateway/PIX/Reconciliadores
    webhook_queue = Queue('webhook', connection=redis_conn)  # Webhooks
    logger.info("✅ 3 Filas RQ inicializadas com connection pool: tasks, gateway, webhook")
except Exception as e:
    logger.error(f"❌ Erro ao conectar Redis para RQ: {e}")
    redis_conn = None
    task_queue = None
    gateway_queue = None
    webhook_queue = None


_AUX_TABLES_READY = False


def _ensure_aux_tables() -> None:
    """Garante que tabelas auxiliares de webhook existam (create if not)."""
    global _AUX_TABLES_READY
    if _AUX_TABLES_READY:
        return

    try:
        from app import db
        from models import WebhookEvent, WebhookPendingMatch

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
    from app import db
    from models import WebhookEvent, get_brazil_time

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
    if existing:
        existing.status = result.get('status')
        existing.transaction_id = transaction_id or existing.transaction_id
        existing.transaction_hash = transaction_hash or existing.transaction_hash
        existing.payload = raw_payload
        existing.received_at = get_brazil_time()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    else:
        event = WebhookEvent(
            gateway_type=gateway_type,
            dedup_key=dedup_key,
            transaction_id=transaction_id or None,
            transaction_hash=transaction_hash or None,
            status=result.get('status'),
            payload=raw_payload
        )
        db.session.add(event)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()


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
    from app import db
    from models import WebhookPendingMatch, get_brazil_time

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
    from app import db
    from models import WebhookPendingMatch

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
        from app import app, db
        from models import BotUser, Bot, get_brazil_time
        from bot_manager import send_meta_pixel_viewcontent_event
        import base64
        import json
        import redis
        
        with app.app_context():
            # Recarregar config do banco
            bot = db.session.get(Bot, bot_id)
            if bot and bot.config:
                config = bot.config.to_dict()
            
            user_from = message.get('from', {})
            telegram_user_id = str(user_from.get('id', ''))
            first_name = user_from.get('first_name', 'Usuário')
            username = user_from.get('username', '')
            
            # Extrair tracking do start_param
            pool_id_from_start = None
            external_id_from_start = None
            utm_data_from_start = {}
            
            if start_param:
                if start_param.startswith('t'):
                    try:
                        tracking_encoded = start_param[1:]
                        missing_padding = len(tracking_encoded) % 4
                        if missing_padding:
                            tracking_encoded += '=' * (4 - missing_padding)
                        
                        tracking_json = base64.urlsafe_b64decode(tracking_encoded).decode()
                        tracking_data = json.loads(tracking_json)
                        
                        pool_id_from_start = tracking_data.get('p')
                        external_id_from_start = tracking_data.get('e')
                        
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
                elif start_param.startswith('p') and start_param[1:].isdigit():
                    pool_id_from_start = int(start_param[1:])
                elif start_param.startswith('pool_'):
                    parts = start_param.split('_')
                    if len(parts) >= 2:
                        pool_id_from_start = int(parts[1])
                    if len(parts) >= 4:
                        external_id_from_start = '_'.join(parts[2:])
            
            # Buscar ou criar BotUser
            bot_user = BotUser.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id,
                archived=False
            ).first()
            
            if not bot_user:
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).first()
                
                if bot_user and bot_user.archived:
                    bot_user.archived = False
                    bot_user.archived_reason = None
                    bot_user.archived_at = None
            
            is_new_user = False
            if not bot_user:
                bot_user = BotUser(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id,
                    first_name=first_name,
                    username=username,
                    welcome_sent=False,
                    external_id=external_id_from_start,
                    utm_source=utm_data_from_start.get('utm_source'),
                    utm_campaign=utm_data_from_start.get('utm_campaign'),
                    campaign_code=utm_data_from_start.get('campaign_code'),
                    fbclid=utm_data_from_start.get('fbclid')
                )
                is_new_user = True
                
                # Tracking Elite - buscar do Redis
                if utm_data_from_start.get('fbclid'):
                    try:
                        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                        fbclid_value = utm_data_from_start['fbclid']
                        tracking_key = f"tracking:{fbclid_value}"
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
                            
                            bot_user.tracking_session_id = tracking_elite.get('session_id')
                            
                            if tracking_elite.get('timestamp'):
                                from datetime import datetime
                                bot_user.click_timestamp = datetime.fromisoformat(tracking_elite['timestamp'])
                            
                            grim_from_redis = tracking_elite.get('grim', '')
                            fbclid_completo_redis = tracking_elite.get('fbclid')
                            
                            if fbclid_completo_redis:
                                bot_user.fbclid = fbclid_completo_redis
                                bot_user.external_id = fbclid_completo_redis
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
                            
                            # Salvar tracking:chat:{chat_id} via TrackingService
                            try:
                                from utils.tracking_service import TrackingService
                                TrackingService.save_tracking_data(
                                    fbclid=fbclid_completo_redis or '',
                                    fbp=tracking_elite.get('fbp', ''),
                                    fbc=tracking_elite.get('fbc', ''),
                                    ip_address=tracking_elite.get('ip', ''),
                                    user_agent=tracking_elite.get('user_agent', ''),
                                    grim=grim_from_redis or '',
                                    telegram_user_id=str(chat_id),
                                    utms={
                                        'utm_source': tracking_elite.get('utm_source', ''),
                                        'utm_campaign': tracking_elite.get('utm_campaign', ''),
                                        'utm_medium': tracking_elite.get('utm_medium', ''),
                                        'utm_content': tracking_elite.get('utm_content', ''),
                                        'utm_term': tracking_elite.get('utm_term', '')
                                    }
                                )
                            except Exception as e:
                                logger.warning(f"Erro ao salvar tracking:chat:{chat_id}: {e}")
                    except Exception as e:
                        logger.error(f"Erro ao buscar tracking elite: {e}")
                
                try:
                    db.session.add(bot_user)
                    db.session.flush()
                except Exception as e:
                    db.session.rollback()
                    bot_user = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id,
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
                if utm_data_from_start.get('fbclid') and not bot_user.fbclid:
                    bot_user.fbclid = utm_data_from_start['fbclid']
                
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


def process_webhook_async(gateway_type: str, data: Dict[str, Any]):
    """
    Processa webhook de pagamento de forma assíncrona
    
    Executa:
    - Processar webhook via adapter
    - Buscar payment
    - Atualizar status
    - Processar estatísticas
    - Enviar entregável
    - Enviar Meta Pixel Purchase
    """
    try:
        from app import app, db
        from models import Payment, Gateway, Bot, get_brazil_time, Commission, WebhookEvent, WebhookPendingMatch
        from gateway_factory import GatewayFactory
        from app import bot_manager, send_payment_delivery, send_meta_pixel_purchase_event
        
        with app.app_context():
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
                from bot_manager import bot_manager
                result = bot_manager.process_payment_webhook(gateway_type, data)
            
            if result:
                # Registrar evento para auditoria (deduplicado por gateway/hash)
                try:
                    _persist_webhook_event(
                        gateway_type=gateway_type,
                        result=result,
                        raw_payload=data
                    )
                except Exception as log_error:
                    logger.warning(f"⚠️ Falha ao registrar webhook em webhook_events: {log_error}")

                gateway_transaction_id = result.get('gateway_transaction_id')
                status = result.get('status')
                
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
                    
                    if payment.status == 'paid' and status == 'paid':
                        # Webhook duplicado - tentar reenviar entregável e garantir Meta Purchase
                        try:
                            send_payment_delivery(payment, bot_manager)
                        except Exception as e:
                            logger.error(f"Erro ao reenviar entregável (duplicado): {e}")
                        if not payment.meta_purchase_sent:
                            try:
                                logger.info(f"♻️ Webhook duplicado para {payment.payment_id}, meta_purchase_sent ainda falso - reenfileirando Meta Purchase")
                                send_meta_pixel_purchase_event(payment)
                            except Exception as e:
                                logger.warning(f"Erro ao reenfileirar Meta Pixel Purchase (duplicado): {e}")
                        return {'status': 'already_processed'}
                    
                    if payment.status != 'paid':
                        payment.status = status

                    status_is_paid = (status == 'paid')
                    deve_processar_estatisticas = status_is_paid and was_pending
                    deve_enviar_entregavel = status_is_paid
                    deve_enviar_meta_purchase = status_is_paid and not payment.meta_purchase_sent

                    if deve_processar_estatisticas:
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
                            from app import GAMIFICATION_V2_ENABLED
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
                        
                    if deve_enviar_meta_purchase:
                        try:
                            send_meta_pixel_purchase_event(payment)
                        except Exception as e:
                            logger.warning(f"Erro ao enviar Meta Pixel Purchase: {e}")
                    
                    if deve_enviar_entregavel:
                        try:
                            send_payment_delivery(payment, bot_manager)
                        except Exception as e:
                            logger.error(f"Erro ao enviar entregável: {e}")
                    
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        raise
                    finally:
                        _clear_pending_match(
                            gateway_type=gateway_type,
                            transaction_id=event_id or event_tx,
                            transaction_hash=event_hash
                        )
                    logger.info(f"✅ Webhook processado: {payment.payment_id} -> {status}")
                    return {'status': 'success', 'payment_id': payment.payment_id}
                else:
                    logger.warning(f"⚠️ Payment não encontrado para webhook: {gateway_transaction_id}")
                    return {'status': 'payment_not_found'}
            else:
                logger.warning(f"⚠️ Webhook não processado: result=None")
                return {'status': 'not_processed'}
                
    except Exception as e:
        logger.error(f"❌ Erro em process_webhook_async: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


def reconcile_paradise_payments_async():
    """Reconciliador Paradise em fila async"""
    try:
        from app import reconcile_paradise_payments
        reconcile_paradise_payments()
    except Exception as e:
        logger.error(f"❌ Erro em reconcile_paradise_payments_async: {e}", exc_info=True)

def reconcile_pushynpay_payments_async():
    """Reconciliador PushynPay em fila async"""
    try:
        from app import reconcile_pushynpay_payments
        reconcile_pushynpay_payments()
    except Exception as e:
        logger.error(f"❌ Erro em reconcile_pushynpay_payments_async: {e}", exc_info=True)

def process_pending_webhooks(limit: int = 50, max_attempts: int = 12) -> int:
    """
    Reprocessa webhooks armazenados em webhook_pending_matches.

    Retorna quantidade processada com sucesso.
    """
    from app import app, db
    from models import WebhookPendingMatch, get_brazil_time

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
        from app import app, db
        from models import Bot, BotConfig, Payment, Gateway
        from gateway_factory import GatewayFactory
        from bot_manager import BotManager
        import uuid
        import time
        
        with app.app_context():
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
                    bot_manager = BotManager(None, None)
                    message = f"💰 PIX Gerado!\n\nValor: R$ {price:.2f}\n\nEscaneie o QR Code ou copie o código PIX:"
                    qr_code = pix_code
                    
                    bot_manager.send_telegram_message(
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
                        bot_manager.send_telegram_message(
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

