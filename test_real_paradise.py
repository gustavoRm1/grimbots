#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TESTE REAL - PARADISE API V30
Teste com credenciais REAIS do usuário
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gateway_paradise import ParadisePaymentGateway
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_real_credentials():
    """Teste com credenciais REAIS do usuário"""
    
    print("TESTE REAL - PARADISE API V30")
    print("Credenciais REAIS do usuário")
    print("=" * 50)
    
    # CREDENCIAIS REAIS DO USUÁRIO (não de teste!)
    real_credentials = {
        'api_key': 'SUA_API_KEY_REAL_AQUI',  # ← USUÁRIO DEVE COLOCAR AQUI
        'product_hash': 'SEU_PRODUCT_HASH_REAL',  # ← USUÁRIO DEVE COLOCAR AQUI
        'store_id': 'SEU_STORE_ID_REAL',  # ← USUÁRIO DEVE COLOCAR AQUI
        'split_percentage': 2.0
    }
    
    print("\n⚠️  IMPORTANTE:")
    print("Substitua as credenciais acima pelas SUAS credenciais reais!")
    print("As credenciais de teste não funcionam em produção.")
    
    print("\n📋 COMO OBTER SUAS CREDENCIAIS:")
    print("1. Acesse sua conta Paradise")
    print("2. Crie um produto → Product Hash")
    print("3. Configure sua API Key")
    print("4. Configure seu Store ID")
    
    # Teste com credenciais reais
    try:
        gateway = ParadisePaymentGateway(real_credentials)
        
        if gateway.verify_credentials():
            print("\n✅ Credenciais válidas!")
            
            # Teste de PIX
            result = gateway.generate_pix(19.97, "Teste Real", 999, {
                'name': 'João Silva',
                'email': 'joao@teste.com',
                'phone': '11999999999',
                'document': '12345678901'
            })
            
            if result:
                print("✅ PIX gerado com sucesso!")
                print(f"Transaction ID: {result.get('transaction_id')}")
            else:
                print("❌ Falha na geração do PIX")
        else:
            print("❌ Credenciais inválidas!")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == '__main__':
    test_real_credentials()
