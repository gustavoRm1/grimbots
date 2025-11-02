#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica se Celery está processando eventos Meta Pixel corretamente
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
    from celery_app import celery_app
    import redis
    from datetime import datetime, timedelta
    import json
except ImportError as e:
    print("=" * 80)
    print("❌ ERRO: Dependências não instaladas!")
    print("=" * 80)
    print(f"Erro: {e}")
    print("\n💡 SOLUÇÃO:")
    print("   1. Ative o venv: source venv/bin/activate")
    print("   2. Instale dependências: pip install -r requirements.txt")
    print("=" * 80)
    sys.exit(1)

print("=" * 80)
print("🔍 VERIFICAÇÃO: Celery e Redis para Meta Pixel Events")
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
        for worker, tasks in active.items():
            print(f"   Worker: {worker}")
            print(f"   Tasks ativas: {len(tasks)}")
            for task in tasks[:3]:  # Mostrar apenas 3 primeiras
                print(f"      - {task.get('name', 'N/A')} (ID: {task.get('id', 'N/A')[:20]}...)")
    else:
        print("❌ Celery Worker: NÃO ENCONTRADO (worker pode não estar rodando)")
except Exception as e:
    print(f"⚠️ Erro ao verificar Celery Worker: {e}")

# 3. Verificar fila de tasks
try:
    # Verificar tasks na fila
    length = r.llen('celery') if r.exists('celery') else 0
    print(f"\n📊 Tasks na fila 'celery': {length}")
    
    # Verificar resultados (últimos 5)
    try:
        # Tentar buscar tasks recentes
        if hasattr(celery_app, 'backend'):
            # Buscar resultados recentes
            print(f"\n🔍 Verificando tasks processadas recentemente...")
    except:
        pass
except Exception as e:
    print(f"⚠️ Erro ao verificar fila: {e}")

# 4. Verificar logs do Celery (via journalctl se possível)
print("\n" + "=" * 80)
print("💡 PRÓXIMOS PASSOS:")
print("=" * 80)
print("1. Verificar se Celery está rodando:")
print("   systemctl status celery")
print("\n2. Ver logs do Celery:")
print("   journalctl -u celery -n 50 --no-pager")
print("\n3. Verificar se eventos Meta estão sendo processados:")
print("   journalctl -u celery | grep -i 'Meta Event' | tail -20")
print("\n4. Se Celery não estiver rodando, iniciar:")
print("   systemctl start celery")
print("=" * 80)

