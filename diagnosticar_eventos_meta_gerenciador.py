#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 DIAGNÓSTICO COMPLETO: Eventos Meta Pixel no Gerenciador
Verifica quantos eventos foram enviados vs quantos chegaram
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
    from models import Payment, PoolBot, RedirectPool
except ImportError as e:
    print("=" * 80)
    print("❌ ERRO: Dependências não instaladas!")
    print("=" * 80)
    print(f"Erro: {e}")
    sys.exit(1)

print("=" * 80)
print("🔍 DIAGNÓSTICO: Eventos Meta Pixel no Gerenciador")
print("=" * 80)

with app.app_context():
    hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Buscar vendas de hoje
    vendas_hoje = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= hoje_inicio
    ).order_by(Payment.paid_at.desc()).all()
    
    print(f"\n📊 RESUMO HOJE (desde {hoje_inicio.strftime('%Y-%m-%d %H:%M')}):")
    print(f"   Total de vendas PAID: {len(vendas_hoje)}")
    
    com_meta = [v for v in vendas_hoje if v.meta_purchase_sent]
    sem_meta = [v for v in vendas_hoje if not v.meta_purchase_sent]
    
    print(f"   ✅ Com Meta enviado: {len(com_meta)}")
    print(f"   ❌ Sem Meta enviado: {len(sem_meta)}")
    
    # Verificar Test Event Code
    pool = RedirectPool.query.filter_by(
        is_active=True,
        meta_tracking_enabled=True,
        meta_events_purchase=True
    ).first()
    
    if pool:
        print(f"\n🔍 CONFIGURAÇÃO DO POOL '{pool.name}':")
        print(f"   Pixel ID: {pool.meta_pixel_id}")
        print(f"   Test Event Code: {'✅ Configurado' if pool.meta_test_event_code else '❌ NÃO configurado'}")
        if pool.meta_test_event_code:
            print(f"      Código: {pool.meta_test_event_code}")
            print(f"      ⚠️ ATENÇÃO: Com Test Event Code, eventos NÃO aparecem no Gerenciador!")
            print(f"      Eventos de teste só aparecem no 'Test Events' do Gerenciador")
    
    # Agrupar por hora
    print(f"\n📊 EVENTOS POR HORA (marcados como enviados):")
    eventos_por_hora = {}
    for v in com_meta:
        if v.meta_purchase_sent_at:
            hora = v.meta_purchase_sent_at.replace(minute=0, second=0, microsecond=0)
            hora_str = hora.strftime('%H:00')
            if hora_str not in eventos_por_hora:
                eventos_por_hora[hora_str] = 0
            eventos_por_hora[hora_str] += 1
    
    # Ordenar por hora
    horas_ordenadas = sorted(eventos_por_hora.keys())
    if horas_ordenadas:
        for hora in horas_ordenadas:
            count = eventos_por_hora[hora]
            print(f"   {hora}: {count} evento(s)")
    else:
        print("   Nenhum evento com timestamp de envio encontrado")
    
    print("\n" + "=" * 80)
    print("🔍 ANÁLISE:")
    print("=" * 80)
    
    if pool and pool.meta_test_event_code:
        print("\n⚠️ PROBLEMA IDENTIFICADO: Test Event Code está configurado!")
        print("   Eventos com Test Event Code NÃO aparecem no Gerenciador normal.")
        print("   Eles só aparecem em 'Test Events' no Gerenciador.")
        print("\n💡 SOLUÇÃO:")
        print("   1. Remova o Test Event Code do pool se quiser eventos em produção")
        print("   2. OU verifique em 'Test Events' no Gerenciador")
        print("   3. Test Event Code é apenas para desenvolvimento/testes")
    else:
        print("\n✅ Test Event Code NÃO está configurado (eventos devem aparecer no Gerenciador)")
        print("\n💡 Se eventos não estão aparecendo:")
        print("   1. Verifique delay da Meta (pode levar até 30 minutos)")
        print("   2. Verifique logs: journalctl -u grimbots | grep 'Purchase ENVIADO'")
        print("   3. Verifique se há erros: journalctl -u grimbots | grep 'Purchase FALHOU'")
        print("   4. Execute: python3 testar_meta_pixel_direto.py")
    
    # Verificar últimas vendas
    print(f"\n📋 ÚLTIMAS 5 VENDAS COM META ENVIADO:")
    for v in com_meta[:5]:
        print(f"\n   Payment: {v.payment_id}")
        print(f"      Valor: R$ {v.amount:.2f}")
        print(f"      Meta enviado em: {v.meta_purchase_sent_at.strftime('%Y-%m-%d %H:%M:%S') if v.meta_purchase_sent_at else 'N/A'}")
        print(f"      Event ID: {v.meta_event_id}")
    
    print("\n" + "=" * 80)

