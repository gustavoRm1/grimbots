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
# TASKS
# ============================================================================

@celery_app.task(bind=True, max_retries=10)
def send_meta_event(self, pixel_id, access_token, event_data, test_code=None):
    """
    Envia evento para Meta Conversions API
    
    Retry automático com backoff exponencial
    """
    import requests
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    
    url = f'https://graph.facebook.com/v18.0/{pixel_id}/events'
    
    payload = {
        'data': [event_data],
        'access_token': access_token
    }
    
    if test_code:
        payload['test_event_code'] = test_code
    
    try:
        start = time.time()
        
        response = requests.post(url, json=payload, timeout=10)
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Evento enviado: {event_data.get('event_name')} | " +
                       f"ID: {event_data.get('event_id')} | " +
                       f"Latência: {latency}ms")
            return result
        
        elif response.status_code in [429, 500, 502, 503, 504]:
            # Erro temporário - retry
            logger.warning(f"⚠️ Erro {response.status_code}, retry {self.request.retries + 1}/10")
            raise self.retry(countdown=2 ** self.request.retries)
        
        else:
            # Erro permanente - não retry
            logger.error(f"❌ Erro {response.status_code}: {response.text}")
            return {'error': response.text, 'status_code': response.status_code}
    
    except requests.exceptions.Timeout:
        logger.warning(f"⏰ Timeout, retry {self.request.retries + 1}/10")
        raise self.retry(countdown=2 ** self.request.retries)
    
    except Exception as e:
        logger.error(f"💥 Erro: {e}")
        raise self.retry(countdown=2 ** self.request.retries)


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
