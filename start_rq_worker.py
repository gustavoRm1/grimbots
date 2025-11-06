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

try:
    from rq import Worker, Queue
    from redis import Redis
except ImportError as e:
    print(f"❌ ERRO: Módulo não encontrado: {e}")
    print("Instale com: pip install rq redis")
    sys.exit(1)

# Conectar ao Redis
try:
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    # ✅ QI 200: decode_responses=True para evitar problemas de encoding
    redis_conn = Redis.from_url(redis_url, decode_responses=True, encoding='utf-8', encoding_errors='ignore')
    # Testar conexão
    redis_conn.ping()
except Exception as e:
    print(f"❌ ERRO: Não foi possível conectar ao Redis: {e}")
    print(f"Redis URL: {redis_url}")
    print("Verifique se Redis está rodando: redis-cli ping")
    sys.exit(1)

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
    try:
        print("="*70)
        print(" RQ Worker QI 200 - Iniciando")
        print("="*70)
        print(f" Redis: {os.environ.get('REDIS_URL', 'redis://localhost:6379/0')}")
        print("="*70)
        
        # ✅ QI 200: Worker recebe conexão diretamente (sem Connection context manager)
        worker = Worker(queues, connection=redis_conn)
        worker.work()
    except KeyboardInterrupt:
        print("\n⚠️ Worker interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

