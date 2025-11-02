#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testa se Celery está recebendo e processando tasks Meta Pixel
"""

import os
import sys

venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
if os.path.exists(venv_path):
    activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from celery_app import celery_app, send_meta_event
    import redis
    import time
except ImportError as e:
    print("=" * 80)
    print("❌ ERRO: Dependências não instaladas!")
    print("=" * 80)
    print(f"Erro: {e}")
    sys.exit(1)

print("=" * 80)
print("🧪 TESTE: Celery Meta Pixel Event")
print("=" * 80)

# 1. Verificar Redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.ping()
    print("✅ Redis: ONLINE")
except Exception as e:
    print(f"❌ Redis: OFFLINE - {e}")
    sys.exit(1)

# 2. Verificar Celery Worker
try:
    inspect = celery_app.control.inspect()
    active = inspect.active()
    if active:
        print("✅ Celery Worker: ATIVO")
    else:
        print("❌ Celery Worker: NÃO ENCONTRADO")
        sys.exit(1)
except Exception as e:
    print(f"❌ Erro ao verificar Celery: {e}")
    sys.exit(1)

# 3. ENFILEIRAR TASK DE TESTE
print("\n📤 Enfileirando task de teste...")
try:
    test_event_data = {
        'event_name': 'Purchase',
        'event_time': int(time.time()),
        'event_id': f'test_{int(time.time())}',
        'action_source': 'website',
        'user_data': {
            'external_id': 'test_user_123'
        },
        'custom_data': {
            'currency': 'BRL',
            'value': 10.00
        }
    }
    
    # Usar pixel_id e access_token de teste (vai falhar na Meta, mas testa se Celery processa)
    task = send_meta_event.apply_async(
        args=[
            'TEST_PIXEL_ID',
            'TEST_ACCESS_TOKEN',
            test_event_data,
            None
        ],
        priority=1
    )
    
    print(f"✅ Task enfileirada: {task.id}")
    print(f"   Status: {task.state}")
    
    # Aguardar alguns segundos
    print("\n⏳ Aguardando 5 segundos para processamento...")
    time.sleep(5)
    
    # Verificar status da task
    result = task.get(timeout=10)
    print(f"\n📊 Resultado da task:")
    print(f"   Status final: {task.state}")
    if hasattr(task, 'result'):
        print(f"   Result: {task.result}")
    if hasattr(task, 'traceback') and task.traceback:
        print(f"   Traceback: {task.traceback[:500]}")
    
except Exception as e:
    print(f"❌ Erro ao testar task: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("💡 VERIFICAÇÕES:")
print("=" * 80)
print("1. Se task ficou em 'PENDING' = Celery não está recebendo tasks")
print("2. Se task ficou em 'FAILURE' = Celery processou mas falhou (ver traceback)")
print("3. Se task ficou em 'SUCCESS' = Celery processou com sucesso")
print("4. Ver logs completos: journalctl -u celery -n 200 --no-pager")
print("=" * 80)

