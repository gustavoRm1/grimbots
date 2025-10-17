#!/usr/bin/env python3
"""
Teste direto do HooPay - Debug
"""

import sys
import os
sys.path.append('/root/grimbots')

from app import app, db
from models import Gateway
from gateway_factory import GatewayFactory
import time

def test_hoopay():
    """Testa HooPay diretamente"""
    print("🧪 TESTANDO HOOAY DIRETAMENTE...")
    
    with app.app_context():
        # Buscar gateway HooPay ativo
        hoopay_gateway = Gateway.query.filter_by(
            gateway_type='hoopay',
            is_active=True,
            is_verified=True
        ).first()
        
        if not hoopay_gateway:
            print("❌ HooPay não encontrado ou não está ativo/verificado")
            return
        
        print(f"✅ HooPay encontrado: {hoopay_gateway.api_key[:16]}...")
        print(f"📊 Organization ID: {hoopay_gateway.organization_id}")
        print(f"💰 Split: {hoopay_gateway.split_percentage}%")
        
        # Testar criação do gateway
        credentials = {
            'api_key': hoopay_gateway.api_key,
            'organization_id': hoopay_gateway.organization_id,
            'split_percentage': hoopay_gateway.split_percentage or 4.0
        }
        
        print("🔧 Criando gateway...")
        gateway = GatewayFactory.create_gateway('hoopay', credentials)
        
        if not gateway:
            print("❌ Erro ao criar instância do HooPay")
            return
        
        print("✅ Gateway criado com sucesso!")
        
        # Testar verificação de credenciais
        print("🔍 Verificando credenciais...")
        is_valid = gateway.verify_credentials()
        print(f"📋 Credenciais válidas: {is_valid}")
        
        # Testar geração de PIX
        print("💰 Testando geração de PIX...")
        test_pix = gateway.generate_pix(
            amount=1.00,
            description='Teste HooPay',
            payment_id='TEST_' + str(int(time.time())),
            customer_data={
                'name': 'Teste Cliente',
                'email': 'teste@exemplo.com',
                'phone': '11999999999',
                'document': '12345678901'
            }
        )
        
        if test_pix:
            print("✅ PIX gerado com sucesso!")
            print(f"📊 Resultado: {test_pix}")
        else:
            print("❌ Falha ao gerar PIX")
        
        print("🎯 TESTE CONCLUÍDO!")

if __name__ == '__main__':
    test_hoopay()
