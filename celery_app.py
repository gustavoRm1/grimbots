"""
🚀 CELERY APP - MVP Meta Pixel Async
Sistema de envio assíncrono de eventos para Meta Pixel

FEATURES:
- Envio não-bloqueante
- Retry persistente com backoff exponencial
- Rate limiting distribuído
- Deduplicação
- Batching inteligente
- Dead Letter Queue

Implementado por: QI 540
"""

import os
from celery import Celery
from kombu import Exchange, Queue

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Criar app Celery
celery_app = Celery('grimbots_meta_pixel')

# Configuração
celery_app.conf.update(
    # Broker e Backend
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,
    
    # Serialização
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='America/Sao_Paulo',
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,  # Garante retry se worker morrer
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Processa um por vez (garante ordem)
    task_time_limit=300,  # 5 minutos max por task
    task_soft_time_limit=240,  # 4 minutos soft limit
    
    # Retry
    task_default_retry_delay=60,  # 1 minuto entre retries
    task_max_retries=10,
    
    # Result
    result_expires=3600,  # Resultados expiram em 1h
    
    # Monitoramento
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Rotas
    task_routes={
        'celery_app.send_meta_event': {
            'queue': 'meta_events',
            'routing_key': 'meta.event'
        },
        'celery_app.send_meta_batch': {
            'queue': 'meta_batches',
            'routing_key': 'meta.batch'
        },
        'celery_app.process_dlq': {
            'queue': 'meta_dlq',
            'routing_key': 'meta.dlq'
        }
    },
    
    # Queues com prioridades
    task_queues=(
        Queue('meta_events', Exchange('meta'), routing_key='meta.event', priority=5),
        Queue('meta_batches', Exchange('meta'), routing_key='meta.batch', priority=3),
        Queue('meta_dlq', Exchange('meta'), routing_key='meta.dlq', priority=1),
    ),
    
    # Beat schedule (jobs periódicos)
    beat_schedule={
        'aggregate-metrics-every-5-min': {
            'task': 'celery_app.aggregate_metrics',
            'schedule': 300.0,  # 5 minutos
        },
        'cleanup-old-logs-daily': {
            'task': 'celery_app.cleanup_old_logs',
            'schedule': 86400.0,  # 24 horas
        },
        'check-health-every-minute': {
            'task': 'celery_app.check_system_health',
            'schedule': 60.0,  # 1 minuto
        }
    },
)

# ============================================================================
# IMPORTS DE TASKS
# ============================================================================

# Importar tasks para registro
from tasks.meta_sender import send_meta_event, send_meta_batch, process_dlq
from tasks.metrics import aggregate_metrics, cleanup_old_logs
from tasks.health import check_system_health

# Registrar tasks
celery_app.tasks.register(send_meta_event)
celery_app.tasks.register(send_meta_batch)
celery_app.tasks.register(process_dlq)
celery_app.tasks.register(aggregate_metrics)
celery_app.tasks.register(cleanup_old_logs)
celery_app.tasks.register(check_system_health)

# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    'celery_app',
    'send_meta_event',
    'send_meta_batch',
    'process_dlq',
    'aggregate_metrics',
    'cleanup_old_logs',
    'check_system_health'
]

