#!/usr/bin/env python
"""
Script de Limpeza Completa das Filas RQ - QI 1000
Remove todas as jobs corrompidas, registries e filas antigas

⚠️ ATENÇÃO: Este script apaga TODAS as jobs do RQ
Use apenas quando houver jobs corrompidas causando crashes

Uso:
  python clear_rq_queues.py
"""

import os
import sys
from redis import Redis

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def clear_rq_queues():
    """Limpa completamente todas as filas e registries do RQ"""
    try:
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url, decode_responses=False)
        
        # Testar conexão
        redis_conn.ping()
        print("✅ Conectado ao Redis")
        
        # Lista de chaves RQ para limpar
        keys_to_delete = []
        
        # Filas principais
        queues = ['tasks', 'gateway', 'webhook', 'default']
        for queue in queues:
            keys_to_delete.append(f'rq:queue:{queue}')
            print(f"📋 Fila encontrada: {queue}")
        
        # Registries (started, finished, deferred, failed)
        registry_types = ['started', 'finished', 'deferred', 'failed']
        for queue in queues:
            for reg_type in registry_types:
                key = f'rq:registry:{reg_type}:{queue}'
                keys_to_delete.append(key)
        
        # Registry geral de failed
        keys_to_delete.append('rq:failed')
        
        # Buscar todas as chaves RQ (backup caso tenha outras)
        all_keys = redis_conn.keys('rq:*')
        print(f"\n📊 Total de chaves RQ encontradas: {len(all_keys)}")
        
        # Adicionar todas as chaves RQ encontradas
        for key in all_keys:
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            if key not in keys_to_delete:
                keys_to_delete.append(key)
        
        # Confirmar antes de deletar
        print("\n" + "="*70)
        print("⚠️  ATENÇÃO: Este script vai apagar TODAS as jobs do RQ")
        print("="*70)
        print(f"Total de chaves a serem deletadas: {len(keys_to_delete)}")
        
        if len(sys.argv) > 1 and sys.argv[1] == '--force':
            confirm = 'y'
        else:
            confirm = input("\nDeseja continuar? (digite 'SIM' para confirmar): ")
        
        if confirm.upper() != 'SIM':
            print("❌ Operação cancelada")
            return
        
        # Deletar todas as chaves
        deleted = 0
        for key in keys_to_delete:
            try:
                if isinstance(key, str):
                    key_bytes = key.encode('utf-8')
                else:
                    key_bytes = key
                
                result = redis_conn.delete(key_bytes)
                if result:
                    deleted += 1
                    print(f"✅ Deletado: {key}")
            except Exception as e:
                print(f"⚠️ Erro ao deletar {key}: {e}")
        
        print("\n" + "="*70)
        print(f"✅ Limpeza concluída: {deleted} chaves deletadas")
        print("="*70)
        print("\n📝 Próximos passos:")
        print("1. Reinicie o Redis: systemctl restart redis")
        print("2. Pare todos os workers: pkill -f start_rq_worker.py")
        print("3. Reinicie os workers:")
        print("   python start_rq_worker.py tasks &")
        print("   python start_rq_worker.py gateway &")
        print("   python start_rq_worker.py webhook &")
        print("="*70)
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    clear_rq_queues()
