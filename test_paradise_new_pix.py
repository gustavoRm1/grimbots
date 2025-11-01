#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para testar criação de PIX na Paradise
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from gateway_factory import GatewayFactory

with app.app_context():
    print("=" * 80)
    print("TESTE: Criar PIX na Paradise")
    print("=" * 80)
    
    # Buscar gateway Paradise
    from models import Gateway
    gateway = Gateway.query.filter_by(gateway_type='paradise', is_active=True, is_verified=True).first()
    
    if not gateway:
        print("❌ Nenhum gateway Paradise ativo encontrado")
        sys.exit(1)
    
    creds = {
        'api_key': gateway.api_key,
        'product_hash': gateway.product_hash,
        'offer_hash': gateway.offer_hash,
        'store_id': gateway.store_id,
        'split_percentage': gateway.split_percentage or 2.0
    }
    
    # Criar gateway
    pg = GatewayFactory.create_gateway('paradise', creds)
    
    if not pg:
        print("❌ Erro ao criar gateway Paradise")
        sys.exit(1)
    
    print(f"✅ Gateway criado")
    
    # Testar PIX de R$ 19.97
    payment_id = f"TEST_1761963600_{os.urandom(4).hex()}"
    result = pg.generate_pix(
        amount=19.97,
        description="Teste PIX",
        payment_id=payment_id,
        customer_data={
            'name': 'Teste Cliente',
            'email': 'teste@teste.com',
            'phone': '11999999999',
            'document': '12345678901'
        }
    )
    
    if result:
        print(f"\n✅ PIX GERADO COM SUCESSO:")
        print(f"   Payment ID: {payment_id}")
        print(f"   Transaction ID: {result.get('transaction_id')}")
        print(f"   Transaction Hash: {result.get('transaction_hash')}")
        print(f"   PIX Code: {result.get('pix_code')[:50]}...")
    else:
        print(f"\n❌ ERRO AO GERAR PIX")
    
    print("\n" + "=" * 80)

