#!/usr/bin/env python
"""
Script para iniciar worker RQ (Redis Queue) - QI 500
Suporta 4 filas: tasks, gateway, webhook, marathon
✅ Usa connection pool para maior performance
"""

import os
import sys

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rq import Worker, Queue
    from redis import Redis
    from redis_manager import get_redis_connection
except ImportError as e:
    print(f"❌ ERRO: Módulo não encontrado: {e}")
    sys.exit(1)

# Conectar ao Redis
try:
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    redis_conn = get_redis_connection(decode_responses=False)
    redis_conn.ping()
    print(f"✅ Redis connection pool inicializado")
except Exception as e:
    print(f"❌ ERRO: Não foi possível conectar ao Redis: {e}")
    sys.exit(1)

# Determinar qual fila processar
queue_name = sys.argv[1] if len(sys.argv) > 1 else None

if queue_name:
    queue = Queue(queue_name, connection=redis_conn)
    queues = [queue]
    print(f"📡 Monitorando Fila: {queue_name}")
else:
    queues = [
        Queue('tasks', connection=redis_conn),
        Queue('gateway', connection=redis_conn),
        Queue('webhook', connection=redis_conn),
        Queue('marathon', connection=redis_conn)
    ]
    print(f"📡 Monitorando Todas: tasks, gateway, webhook, marathon")

if __name__ == '__main__':
    try:
        print("="*70)
        print(" RQ Worker QI 500 - Usina de Disparos Ativa")
        print("="*70)
        worker = Worker(queues, connection=redis_conn)
        worker.work()
    except KeyboardInterrupt:
        print("\n⚠️ Worker interrompido")
        sys.exit(0)
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)