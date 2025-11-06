#!/usr/bin/env python
"""
Script para iniciar worker RQ (Redis Queue) - QI 200
Suporta 3 filas separadas: tasks, gateway, webhook

Uso:
  python start_rq_worker.py tasks      # Worker Telegram (urgente)
  python start_rq_worker.py gateway    # Worker Gateway/PIX/Reconciliadores
  python start_rq_worker.py webhook    # Worker Webhooks
  python start_rq_worker.py            # Worker todas as filas
"""

import os
import sys

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq import Worker, Queue, Connection
from redis import Redis

# Conectar ao Redis
redis_conn = Redis.from_url(
    os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    decode_responses=True
)

# Determinar qual fila processar
queue_name = sys.argv[1] if len(sys.argv) > 1 else None

if queue_name:
    # Processar fila específica
    queue = Queue(queue_name, connection=redis_conn)
    queues = [queue]
    print(f" Queue: {queue_name}")
else:
    # Processar todas as filas
    queues = [
        Queue('tasks', connection=redis_conn),
        Queue('gateway', connection=redis_conn),
        Queue('webhook', connection=redis_conn)
    ]
    print(f" Queues: tasks, gateway, webhook")

if __name__ == '__main__':
    print("="*70)
    print(" RQ Worker QI 200 - Iniciando")
    print("="*70)
    print(f" Redis: {os.environ.get('REDIS_URL', 'redis://localhost:6379/0')}")
    print("="*70)
    
    with Connection(redis_conn):
        worker = Worker(queues)
        worker.work()

