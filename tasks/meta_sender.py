"""
Meta Pixel Sender - Task Assíncrona
Envia eventos para Meta Conversions API em background

Implementado por: QI 540
"""

import os
import time
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Importar celery_app (será definido depois)
celery_app = None

def get_celery_app():
    """Lazy import para evitar circular dependency"""
    global celery_app
    if celery_app is None:
        from celery_app import celery_app as app
        celery_app = app
    return celery_app

# ============================================================================
# TASK DE ENVIO
# ============================================================================

def send_meta_event_task(pixel_id, access_token, event_data, test_code=None):
    """
    Envia evento para Meta Conversions API
    
    Args:
        pixel_id: ID do pixel Meta
        access_token: Token de acesso
        event_data: Dados do evento (dict)
        test_code: Código de teste (opcional)
    
    Returns:
        Response da Meta API
    """
    url = f'https://graph.facebook.com/v18.0/{pixel_id}/events'
    
    payload = {
        'data': [event_data],
        'access_token': access_token
    }
    
    if test_code:
        payload['test_event_code'] = test_code
    
    try:
        start_time = time.time()
        
        response = requests.post(
            url,
            json=payload,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        latency = int((time.time() - start_time) * 1000)  # ms
        
        if response.status_code == 200:
            result = response.json()
            
            logger.info(
                f"✅ Meta Pixel evento enviado: " +
                f"event_name={event_data.get('event_name')}, " +
                f"event_id={event_data.get('event_id')}, " +
                f"events_received={result.get('events_received', 0)}, " +
                f"latency={latency}ms, " +
                f"fbtrace_id={result.get('fbtrace_id')}"
            )
            
            return {
                'success': True,
                'events_received': result.get('events_received', 0),
                'fbtrace_id': result.get('fbtrace_id'),
                'latency_ms': latency
            }
        
        else:
            logger.error(
                f"❌ Meta Pixel erro {response.status_code}: " +
                f"event_id={event_data.get('event_id')}, " +
                f"response={response.text}"
            )
            
            # Retry se for erro 5xx ou 429
            if response.status_code >= 500 or response.status_code == 429:
                raise Exception(f"Meta API error {response.status_code}")
            
            # Erro 4xx = problema no payload, não retry
            return {
                'success': False,
                'error': response.text,
                'status_code': response.status_code
            }
    
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Timeout ao enviar evento: {event_data.get('event_id')}")
        raise  # Retry
    
    except requests.exceptions.RequestException as e:
        logger.error(f"💥 Erro de rede ao enviar evento: {e}")
        raise  # Retry
    
    except Exception as e:
        logger.error(f"💥 Erro inesperado: {e}")
        raise  # Retry

