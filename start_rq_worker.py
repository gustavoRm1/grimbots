#!/usr/bin/env python
"""
Script para iniciar worker RQ (Redis Queue)
Execute: python start_rq_worker.py
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

# Criar fila
queue = Queue('tasks', connection=redis_conn)

if __name__ == '__main__':
    print("="*70)
    print(" RQ Worker - Iniciando")
    print("="*70)
    print(f" Redis: {os.environ.get('REDIS_URL', 'redis://localhost:6379/0')}")
    print(f" Queue: tasks")
    print("="*70)
    
    with Connection(redis_conn):
        worker = Worker([queue])
        worker.work()

