#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 DIAGNÓSTICO: Transações Paradise que não aparecem no painel
Verifica pagamentos com PIX gerado mas que não estão no painel Paradise
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway, Bot
from gateway_factory import GatewayFactory

with app.app_context():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO: Transações Paradise não aparecem no painel")
    print("=" * 80)
    
    # Buscar pagamentos Paradise pendentes das últimas 24h
    desde = datetime.now() - timedelta(hours=24)
    
    pagamentos = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.status == 'pending',
        Payment.created_at >= desde
    ).order_by(Payment.created_at.desc()).all()
    
    print(f"\n📊 Pagamentos Paradise PENDENTES (últimas 24h): {len(pagamentos)}")
    
    # Estatísticas gerais
    sem_hash = len([p for p in pagamentos if not p.gateway_transaction_hash])
    com_hash = len([p for p in pagamentos if p.gateway_transaction_hash])
    print(f"   ❌ SEM Hash: {sem_hash}")
    print(f"   ✅ COM Hash: {com_hash}")
    
    # Buscar todos os gateways Paradise para estatística
    todos_gateways = Gateway.query.filter_by(gateway_type='paradise').all()
    gateways_ativos = [g for g in todos_gateways if g.is_active and g.is_verified]
    print(f"\n📋 Gateways Paradise no sistema:")
    print(f"   Total: {len(todos_gateways)}")
    print(f"   Ativos e verificados: {len(gateways_ativos)}")
    
    for p in pagamentos[:10]:  # Mostrar apenas os 10 mais recentes
        print(f"\n   Payment ID: {p.id} ({p.payment_id})")
        print(f"   Bot: {p.bot.name if p.bot else 'N/A'} (ID: {p.bot_id})")
        print(f"   User ID: {p.bot.user_id if p.bot else 'N/A'}")
        print(f"   Valor: R$ {p.amount:.2f}")
        print(f"   Criado: {p.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Transaction ID: {p.gateway_transaction_id}")
        print(f"   Transaction Hash: {p.gateway_transaction_hash or '❌ None'}")
        print(f"   Tem QR Code: {'✅' if p.product_description and p.product_description.startswith('000201') else '❌'}")
        
        # Tentar consultar status na Paradise
        if p.gateway_transaction_id or p.gateway_transaction_hash:
            try:
                # ✅ CORREÇÃO: Buscar gateway como o reconciliador faz (is_active=True OU is_verified=True)
                gateway = Gateway.query.filter(
                    Gateway.user_id == p.bot.user_id,
                    Gateway.gateway_type == 'paradise',
                    Gateway.is_active == True,
                    Gateway.is_verified == True
                ).first()
                
                # Se não encontrou com is_active, tentar apenas is_verified
                if not gateway:
                    gateway = Gateway.query.filter(
                        Gateway.user_id == p.bot.user_id,
                        Gateway.gateway_type == 'paradise',
                        Gateway.is_verified == True
                    ).first()
                
                if gateway:
                    creds = {
                        'api_key': gateway.api_key,
                        'product_hash': gateway.product_hash,
                        'offer_hash': gateway.offer_hash,
                        'store_id': gateway.store_id,
                        'split_percentage': gateway.split_percentage or 2.0
                    }
                    g = GatewayFactory.create_gateway('paradise', creds)
                    
                    if g:
                        hash_or_id = p.gateway_transaction_hash or p.gateway_transaction_id
                        status = g.get_payment_status(str(hash_or_id))
                        
                        if status:
                            print(f"   Status na Paradise: {status.get('status', 'N/A')}")
                            print(f"   Transaction ID retornado: {status.get('gateway_transaction_id', 'N/A')}")
                        else:
                            print(f"   ⚠️ Não encontrado na Paradise (pode não ter sido criado)")
                else:
                    print(f"   ⚠️ Gateway não encontrado")
                    # Mostrar quais gateways existem para este usuário
                    if p.bot:
                        gateways_usuario = Gateway.query.filter_by(
                            user_id=p.bot.user_id,
                            gateway_type='paradise'
                        ).all()
                        if gateways_usuario:
                            print(f"      Gateways Paradise encontrados para user {p.bot.user_id}: {len(gateways_usuario)}")
                            for gw in gateways_usuario:
                                print(f"         - ID: {gw.id} | Ativo: {gw.is_active} | Verificado: {gw.is_verified}")
                        else:
                            print(f"      ❌ Nenhum gateway Paradise encontrado para user {p.bot.user_id}")
            except Exception as e:
                print(f"   ❌ Erro ao consultar: {e}")
    
    print("\n" + "=" * 80)
    print("💡 DICAS:")
    print("   1. Se QR Code existe mas não aparece no painel: verificar reference único")
    print("   2. Se não encontrado na Paradise: transação pode não ter sido criada")
    print("   3. Verificar logs do sistema para ver resposta completa da Paradise")
    print("\n🔧 CORREÇÃO:")
    if sem_hash > 0:
        print(f"   Execute: python3 corrigir_paradise_transaction_hash.py")
        print(f"   Isso corrigirá {sem_hash} pagamento(s) sem hash")
    print("=" * 80)

