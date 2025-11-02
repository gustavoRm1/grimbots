#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica logs do Celery para eventos Meta Pixel e confirma se estão sendo processados
"""

import os
import sys
from datetime import datetime, timedelta

print("=" * 80)
print("🔍 VERIFICAÇÃO: Logs Celery Meta Pixel")
print("=" * 80)

# 1. Verificar arquivo de log do Celery
log_file = "/var/log/celery/worker1.log"
if os.path.exists(log_file):
    print(f"\n✅ Arquivo de log encontrado: {log_file}")
    
    # Ler últimas 100 linhas
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines
            
            print(f"\n📋 Últimas {len(recent_lines)} linhas do log:")
            print("-" * 80)
            
            # Filtrar linhas relacionadas a Meta
            meta_lines = [l for l in recent_lines if 'meta' in l.lower() or 'Meta Event' in l or 'Purchase' in l or 'TOKEN' in l]
            
            if meta_lines:
                print(f"\n🔍 {len(meta_lines)} linha(s) relacionada(s) a Meta:")
                for line in meta_lines[-20:]:  # Últimas 20
                    print(f"   {line.strip()}")
            else:
                print("\n⚠️ NENHUMA linha relacionada a Meta encontrada nos logs!")
                print("\n📋 Últimas 20 linhas gerais do log:")
                for line in recent_lines[-20:]:
                    print(f"   {line.strip()}")
    except Exception as e:
        print(f"❌ Erro ao ler log: {e}")
else:
    print(f"\n❌ Arquivo de log não encontrado: {log_file}")
    print("\n💡 Tentando encontrar arquivos de log do Celery...")
    
    log_dir = "/var/log/celery"
    if os.path.exists(log_dir):
        files = os.listdir(log_dir)
        print(f"   Arquivos encontrados em {log_dir}:")
        for f in files:
            print(f"     - {f}")
    else:
        print(f"   ❌ Diretório {log_dir} não existe")

# 2. Verificar logs do app.py (journalctl)
print("\n" + "=" * 80)
print("🔍 Verificando logs do app.py (journalctl) para 'Purchase enfileirado'")
print("=" * 80)

print("\n💡 Execute na VPS:")
print("   journalctl -u grimbots -n 500 --no-pager | grep -i 'Purchase enfileirado\\|Meta Pixel\\|send_meta_event'")

print("\n" + "=" * 80)

