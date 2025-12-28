"""
🚀 CELERY APP - MVP Meta Pixel Async (VPS - SEM DOCKER)

SETUP:
- Redis: localhost:6379
- SQLite: instance/saas_bot_manager.db  
- Workers: systemd

USAR:
celery -A celery_app worker --loglevel=info

Implementado por: QI 540
"""

import os
from celery import Celery

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Broker e Backend
BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
BACKEND_URL = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Criar app
celery_app = Celery('grimbots')

# Configuração simples
celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=BACKEND_URL,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_default_retry_delay=60,
    task_max_retries=10,
    result_expires=3600,
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _validate_meta_token(access_token: str) -> bool:
    """
    Valida token de acesso do Meta usando endpoint debug_token
    
    ✅ PRODUCTION-READY:
    - Usa endpoint oficial de debug
    - Validação robusta
    - Timeout configurado
    """
    try:
        import requests
        
        # Usar endpoint oficial de debug do Meta
        url = f"https://graph.facebook.com/v18.0/debug_token"
        
        params = {
            'input_token': access_token,
            'access_token': access_token
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            token_data = data.get('data', {})
            
            # Verificar se token é válido
            is_valid = token_data.get('is_valid', False)
            expires_at = token_data.get('expires_at', 0)
            
            # Verificar se não expirou
            import time
            if expires_at > 0 and expires_at < time.time():
                return False
            
            return is_valid
        else:
            return False
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao validar token Meta: {e}")
        return False

def _send_token_alert(pixel_id: str, message: str):
    """
    Envia alerta automático para token inválido
    
    ✅ PRODUCTION-READY:
    - Log estruturado com severidade CRITICAL
    - Informações completas para debug
    - Timestamp preciso
    """
    import logging
    import time
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    
    # ✅ LOG CRÍTICO PARA ALERTA
    from models import get_brazil_time
    logger.critical(f"ALERT | Token Invalid | Pixel: {pixel_id} | " +
                   f"Message: {message} | " +
                   f"Timestamp: {get_brazil_time().isoformat()}")
    
    # ✅ FUTURO: Integrar com sistema de alertas (Slack, Discord, etc)
    # Por enquanto, apenas log crítico que pode ser monitorado

# ============================================================================
# TASKS
# ============================================================================

def _validate_event_data(event_data):
    """Valida event_data antes de enviar para Meta"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Campos obrigatórios
    required_fields = ['event_name', 'event_time', 'event_id', 'action_source']
    missing = [f for f in required_fields if not event_data.get(f)]
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {missing}")
    
    # Validar user_data
    user_data = event_data.get('user_data', {})
    if not isinstance(user_data, dict):
        raise ValueError("user_data deve ser dict")
    
    # Validar custom_data (deve ser dict, não None)
    custom_data = event_data.get('custom_data')
    if custom_data is not None and not isinstance(custom_data, dict):
        raise ValueError("custom_data deve ser dict ou None")
    
    # Se custom_data é None, converter para {}
    if custom_data is None:
        event_data['custom_data'] = {}
        logger.warning(f"⚠️ custom_data era None, convertido para {{}}")
    
    # Validar event_source_url (opcional mas recomendado)
    if not event_data.get('event_source_url'):
        logger.warning(f"⚠️ event_source_url ausente - Meta recomenda incluir")
    
    return True

@celery_app.task(bind=True, max_retries=10)
def send_meta_event(self, pixel_id, access_token, event_data, test_code=None):
    """
    Envia evento para Meta Conversions API
    
    ✅ PRODUCTION-READY (QI 540):
    - Valida token ANTES do envio
    - Falha task para erros 4xx (token inválido)
    - Retry apenas para erros 5xx
    - Logging estruturado com severidade real
    """
    import requests
    import time
    import logging
    import json
    
    logger = logging.getLogger(__name__)
    
    # ✅ VALIDAÇÃO DE EVENT_DATA ANTES DE ENVIAR
    try:
        _validate_event_data(event_data)
    except ValueError as e:
        logger.error(f"❌ Event data inválido: {e}")
        logger.error(f"   Event: {event_data.get('event_name')} | ID: {event_data.get('event_id')}")
        raise Exception(f"Event data inválido: {e}")
    
    # ✅ VALIDAÇÃO DE TOKEN ANTES DO ENVIO
    try:
        token_valid = _validate_meta_token(access_token)
        if not token_valid:
            error_msg = f"🚨 TOKEN INVÁLIDO: Meta API rejeitou token antes do envio"
            logger.error(error_msg)
            
            # ✅ ALERTA AUTOMÁTICO PARA TOKEN INVÁLIDO
            _send_token_alert(pixel_id, "Token inválido detectado")
            
            raise Exception("Token de acesso inválido ou expirado")
    except Exception as e:
        logger.error(f"🚨 ERRO NA VALIDAÇÃO DO TOKEN: {e}")
        
        # ✅ ALERTA AUTOMÁTICO PARA ERRO DE VALIDAÇÃO
        _send_token_alert(pixel_id, f"Erro na validação: {str(e)[:100]}")
        
        raise Exception(f"Falha na validação do token: {e}")
    
    url = f'https://graph.facebook.com/v18.0/{pixel_id}/events'
    
    payload = {
        'data': [event_data],
        'access_token': access_token
    }
    
    if test_code:
        payload['test_event_code'] = test_code
    
    try:
        start = time.time()
        
        # ✅ LOG CRÍTICO: Mostrar payload completo ANTES de enviar (AUDITORIA)
        # Formatar para fácil leitura
        payload_formatted = json.dumps(payload, indent=2, ensure_ascii=False)
        logger.info(f"📤 META PAYLOAD COMPLETO ({event_data.get('event_name')}):\n{payload_formatted}")
        
        # ✅ LOG CRÍTICO: Mostrar user_data separadamente para análise
        user_data = event_data.get('user_data', {})
        user_data_formatted = json.dumps(user_data, indent=2, ensure_ascii=False)
        logger.info(f"👤 USER_DATA ({event_data.get('event_name')}):\n{user_data_formatted}")
        
        response = requests.post(url, json=payload, timeout=10)
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            result = response.json()
            events_received = result.get('events_received', 0)
            # ✅ LOGGING ESTRUTURADO - SUCESSO (HTTP)
            logger.info(f"SUCCESS | Meta Event | {event_data.get('event_name')} | " +
                       f"ID: {event_data.get('event_id')} | " +
                       f"Pixel: {pixel_id} | " +
                       f"Latency: {latency}ms | " +
                       f"EventsReceived: {events_received}")
            
            # ✅ LOG CRÍTICO: Mostrar resposta completa (AUDITORIA)
            response_formatted = json.dumps(result, indent=2, ensure_ascii=False)
            logger.info(f"📥 META RESPONSE ({event_data.get('event_name')}):\n{response_formatted}")

            # ✅ REGRA META: Só considerar sucesso real se events_received >= 1
            if events_received and events_received >= 1:
                try:
                    if event_data.get('event_name') == 'Purchase':
                        from models import db, Payment, get_brazil_time
                        event_id_val = event_data.get('event_id')
                        if event_id_val:
                            payment = Payment.query.filter_by(meta_event_id=event_id_val).first()
                            if payment and not payment.meta_purchase_sent:
                                payment.meta_purchase_sent = True
                                payment.meta_purchase_sent_at = get_brazil_time()
                                db.session.commit()
                                logger.info(f"✅ META PURCHASE CONFIRMADO | payment_id={payment.id} | event_id={event_id_val} | meta_purchase_sent=True")
                except Exception as mark_err:
                    # Não falhar task se marcação falhar; apenas logar
                    logger.error(f"⚠️ Falha ao marcar meta_purchase_sent após SUCCESS: {mark_err}", exc_info=True)
                
                return result
            else:
                # events_received == 0: pedir retry para não marcar como enviado
                logger.warning(f"RETRY | Meta Event | {event_data.get('event_name')} | events_received=0 | event_id={event_data.get('event_id')}")
                raise self.retry(countdown=2 ** self.request.retries)
        
        elif response.status_code >= 500:
            # ✅ RETRY APENAS PARA ERROS 5xx (servidor)
            # ✅ LOGGING ESTRUTURADO - RETRY
            logger.warning(f"RETRY | Meta Event | {event_data.get('event_name')} | " +
                          f"Status: {response.status_code} | " +
                          f"Attempt: {self.request.retries + 1}/10 | " +
                          f"Pixel: {pixel_id}")
            raise self.retry(countdown=2 ** self.request.retries)
        
        elif response.status_code == 429:
            # Rate limit - retry com backoff maior
            # ✅ LOGGING ESTRUTURADO - RATE LIMIT
            logger.warning(f"RATE_LIMIT | Meta Event | {event_data.get('event_name')} | " +
                          f"Attempt: {self.request.retries + 1}/10 | " +
                          f"Pixel: {pixel_id}")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Backoff maior para rate limit
        
        else:
            # Erro permanente - FALHAR A TASK
            # ✅ LOGGING ESTRUTURADO - ERRO PERMANENTE
            logger.error(f"FAILED | Meta Event | {event_data.get('event_name')} | " +
                        f"Status: {response.status_code} | " +
                        f"Pixel: {pixel_id} | " +
                        f"Error: {response.text[:200]}")
            
            # ✅ FALHAR A TASK PARA ERROS 4xx (token inválido, etc)
            if response.status_code >= 400 and response.status_code < 500:
                raise Exception(f"Meta API Error {response.status_code}: {response.text}")
            
            # Para outros erros, retornar erro mas não falhar
            return {'error': response.text, 'status_code': response.status_code}
    
    except requests.exceptions.Timeout:
        # ✅ LOGGING ESTRUTURADO - TIMEOUT
        logger.warning(f"TIMEOUT | Meta Event | {event_data.get('event_name')} | " +
                      f"Attempt: {self.request.retries + 1}/10 | " +
                      f"Pixel: {pixel_id}")
        raise self.retry(countdown=2 ** self.request.retries)
    
    except Exception as e:
        # ✅ LOGGING ESTRUTURADO - EXCEÇÃO
        logger.error(f"EXCEPTION | Meta Event | {event_data.get('event_name')} | " +
                   f"Pixel: {pixel_id} | " +
                   f"Error: {str(e)[:200]}")
        raise self.retry(countdown=2 ** self.request.retries)


@celery_app.task
def reconcile_meta_purchases(days: int = 7, limit: int = 200):
    """
    Reconciliador de purchases não marcados (backfill CAPI).
    Seleciona pagamentos pagos nos últimos N dias com meta_purchase_sent=False
    e reenfileira o Purchase com o MESMO event_id (Meta deduplica).
    """
    import logging
    from datetime import datetime, timedelta, timezone
    from models import db, Payment
    from app import app, send_meta_pixel_purchase_event

    logger = logging.getLogger(__name__)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with app.app_context():
        payments = (
            Payment.query.filter(
                Payment.status == 'paid',
                Payment.meta_purchase_sent == False,  # noqa: E712
                Payment.paid_at >= cutoff
            )
            .order_by(Payment.paid_at.desc())
            .limit(limit)
            .all()
        )

        if not payments:
            logger.info(f"🔁 Reconcile: nenhum payment pendente (window={days}d).")
            return {'processed': 0, 'enqueued': 0}

        enqueued = 0
        for p in payments:
            try:
                logger.info(f"🔁 Reconcile enfileirando Purchase | payment_id={p.id} | event_id={p.meta_event_id or 'will_generate'}")
                ok = send_meta_pixel_purchase_event(p)
                if ok:
                    enqueued += 1
            except Exception as e:
                logger.error(f"❌ Reconcile falhou para payment_id={p.id}: {e}", exc_info=True)
                db.session.rollback()

        logger.info(f"🔁 Reconcile finalizado | processed={len(payments)} | enqueued={enqueued}")
        return {'processed': len(payments), 'enqueued': enqueued}


@celery_app.task
def check_health():
    """Health check do sistema"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        logger.info("✅ Health check OK")
        return {'status': 'ok'}
    except Exception as e:
        logger.error(f"❌ Health check falhou: {e}")
        return {'status': 'error', 'error': str(e)}
