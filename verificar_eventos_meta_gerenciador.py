#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 VERIFICAR: Quantos eventos chegaram no Gerenciador da Meta
Compara eventos enviados vs eventos que chegaram
"""

import os
import sys
from datetime import datetime, timedelta

venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
if os.path.exists(venv_path):
    activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db
    from models import Payment, PoolBot
except ImportError as e:
    print("=" * 80)
    print("❌ ERRO: Dependências não instaladas!")
    print("=" * 80)
    print(f"Erro: {e}")
    sys.exit(1)

print("=" * 80)
print("🔍 VERIFICAÇÃO: Eventos Meta Pixel no Gerenciador")
print("=" * 80)

with app.app_context():
    hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Buscar vendas de hoje
    vendas_hoje = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= hoje_inicio
    ).order_by(Payment.paid_at.desc()).all()
    
    print(f"\n📊 VENDAS HOJE (desde {hoje_inicio.strftime('%Y-%m-%d %H:%M')}):")
    print(f"   Total: {len(vendas_hoje)}")
    
    # Separar por status Meta Pixel
    com_meta = [v for v in vendas_hoje if v.meta_purchase_sent]
    sem_meta = [v for v in vendas_hoje if not v.meta_purchase_sent]
    
    print(f"\n📊 STATUS META PIXEL:")
    print(f"   ✅ Marcados como enviados: {len(com_meta)}")
    print(f"   ❌ Não enviados: {len(sem_meta)}")
    
    # Agrupar por hora
    print(f"\n📊 EVENTOS POR HORA (marcados como enviados):")
    eventos_por_hora = {}
    for v in com_meta:
        if v.meta_purchase_sent_at:
            hora = v.meta_purchase_sent_at.replace(minute=0, second=0, microsecond=0)
            if hora not in eventos_por_hora:
                eventos_por_hora[hora] = 0
            eventos_por_hora[hora] += 1
    
    # Ordenar por hora
    horas_ordenadas = sorted(eventos_por_hora.keys())
    for hora in horas_ordenadas:
        count = eventos_por_hora[hora]
        print(f"   {hora.strftime('%H:00')}: {count} evento(s)")
    
    # Últimas 10 vendas com Meta enviado
    print(f"\n📋 ÚLTIMAS 10 VENDAS COM META ENVIADO:")
    for v in com_meta[:10]:
        print(f"\n   Payment: {v.payment_id}")
        print(f"      Valor: R$ {v.amount:.2f}")
        print(f"      Pago em: {v.paid_at.strftime('%Y-%m-%d %H:%M:%S') if v.paid_at else 'N/A'}")
        print(f"      Meta enviado em: {v.meta_purchase_sent_at.strftime('%Y-%m-%d %H:%M:%S') if v.meta_purchase_sent_at else 'N/A'}")
        print(f"      Event ID: {v.meta_event_id}")
    
    print("\n" + "=" * 80)
    print("💡 COMPARAÇÃO COM GERENCIADOR:")
    print("=" * 80)
    print("\n1. Verifique no Gerenciador da Meta:")
    print("   - Quantos eventos aparecem hoje")
    print("   - Se há eventos por hora")
    print("   - Se há diferença entre enviados e recebidos")
    
    print("\n2. Se há diferença, verifique:")
    print("   - Test Event Code está configurado? (eventos de teste não aparecem)")
    print("   - Há delay na Meta? (pode levar até 30 minutos)")
    print("   - Eventos estão sendo deduplicados? (mesmo event_id)")
    
    print("\n3. Para verificar logs do envio:")
    print("   journalctl -u grimbots -n 1000 --no-pager | grep -i 'Purchase ENVIADO\|Purchase FALHOU\|Erro ao obter resultado'")
    
    print("\n" + "=" * 80)

