#!/usr/bin/env python
"""
Script para limpar filas RQ antigas (corrige UnicodeDecodeError)
Execute: python clear_rq_queues.py
"""

import os
import sys

try:
    from redis import Redis
except ImportError:
    print("❌ Redis não instalado. Execute: pip install redis")
    sys.exit(1)

# Conectar ao Redis (sem decode para poder limpar tudo)
try:
    redis_conn = Redis.from_url(
        os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        decode_responses=False  # Sem decode para limpar
    )
    redis_conn.ping()
except Exception as e:
    print(f"❌ Erro ao conectar Redis: {e}")
    sys.exit(1)

print("="*70)
print(" Limpando Filas RQ Antigas")
print("="*70)

# Limpar filas
queues_to_clear = ['tasks', 'gateway', 'webhook']

for queue_name in queues_to_clear:
    try:
        # Limpar jobs da fila
        queue_key = f'rq:queue:{queue_name}'
        deleted = redis_conn.delete(queue_key)
        print(f"✅ Fila '{queue_name}': {deleted} chave(s) removida(s)")
        
        # Limpar jobs failed
        failed_key = f'rq:queue:{queue_name}:failed'
        deleted_failed = redis_conn.delete(failed_key)
        if deleted_failed:
            print(f"✅ Jobs failed de '{queue_name}': removidos")
        
        # Limpar jobs started
        started_key = f'rq:queue:{queue_name}:started'
        deleted_started = redis_conn.delete(started_key)
        if deleted_started:
            print(f"✅ Jobs started de '{queue_name}': removidos")
            
    except Exception as e:
        print(f"⚠️ Erro ao limpar fila '{queue_name}': {e}")

# Limpar todos os jobs RQ (mais agressivo)
try:
    # Buscar todas as chaves RQ
    all_rq_keys = redis_conn.keys('rq:*')
    if all_rq_keys:
        deleted_all = redis_conn.delete(*all_rq_keys)
        print(f"✅ Total de {deleted_all} chaves RQ removidas")
    else:
        print("✅ Nenhuma chave RQ encontrada")
except Exception as e:
    print(f"⚠️ Erro ao limpar todas as chaves: {e}")

print("="*70)
print(" Limpeza concluída!")
print("="*70)
print("Agora reinicie os workers:")
print("  sudo systemctl restart rq-worker-tasks")
print("  sudo systemctl restart rq-worker-gateway")
print("  sudo systemctl restart rq-worker-webhook")

