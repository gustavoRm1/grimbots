#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TESTE DE PRODUCAO - PARADISE API V30
Execute na VPS para validar a integração
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gateway_paradise import ParadisePaymentGateway
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_production():
    """Teste completo em produção"""
    
    print("TESTE DE PRODUCAO - PARADISE API V30")
    print("=" * 50)
    
    # 1. Verificar variáveis de ambiente
    print("\n1. VERIFICANDO VARIAVEIS DE AMBIENTE:")
    print("-" * 40)
    
    api_key = os.getenv('PARADISE_API_KEY')
    product_hash = os.getenv('PARADISE_PRODUCT_HASH')
    store_id = os.getenv('PARADISE_STORE_ID')
    webhook_url = os.getenv('WEBHOOK_URL')
    
    print(f"API Key: {'OK' if api_key else 'FALTANDO'}")
    print(f"Product Hash: {'OK' if product_hash else 'FALTANDO'}")
    print(f"Store ID: {'OK' if store_id else 'FALTANDO'}")
    print(f"Webhook URL: {webhook_url or 'FALTANDO'}")
    
    if not all([api_key, product_hash, store_id, webhook_url]):
        print("\nERRO: Variáveis de ambiente incompletas!")
        return False
    
    # 2. Inicializar gateway
    print("\n2. INICIALIZANDO GATEWAY:")
    print("-" * 30)
    
    credentials = {
        'api_key': api_key,
        'product_hash': product_hash,
        'store_id': store_id,
        'split_percentage': float(os.getenv('PARADISE_SPLIT_PERCENTAGE', '2.0'))
    }
    
    try:
        gateway = ParadisePaymentGateway(credentials)
        print("Gateway inicializado com sucesso!")
    except Exception as e:
        print(f"ERRO na inicialização: {e}")
        return False
    
    # 3. Verificar credenciais
    print("\n3. VERIFICANDO CREDENCIAIS:")
    print("-" * 30)
    
    if gateway.verify_credentials():
        print("Credenciais válidas!")
    else:
        print("ERRO: Credenciais inválidas!")
        return False
    
    # 4. Testar URL dinâmica
    print("\n4. TESTANDO URL DINAMICA:")
    print("-" * 25)
    
    checkout_url = gateway._get_dynamic_checkout_url(123)
    print(f"Checkout URL: {checkout_url}")
    
    if webhook_url not in checkout_url:
        print("ERRO: URL não está usando WEBHOOK_URL!")
        return False
    
    # 5. Teste de PIX (simulado)
    print("\n5. TESTE DE GERACAO DE PIX:")
    print("-" * 30)
    
    customer_data = {
        'name': 'Teste VPS',
        'email': 'teste@vps.com',
        'phone': '11999999999',
        'document': '12345678901'
    }
    
    result = gateway.generate_pix(19.97, "Teste VPS", 999, customer_data)
    
    if result:
        print("PIX gerado com sucesso!")
        print(f"Transaction ID: {result.get('transaction_id')}")
        print(f"PIX Code: {result.get('pix_code', 'N/A')[:50]}...")
    else:
        print("ERRO: Falha na geração do PIX!")
        return False
    
    print("\n6. RESUMO:")
    print("-" * 10)
    print("Variáveis de ambiente: OK")
    print("Inicialização: OK")
    print("Credenciais: OK")
    print("URL dinâmica: OK")
    print("Geração de PIX: OK")
    
    print("\nSISTEMA PARADISE API V30: FUNCIONANDO EM PRODUCAO!")
    return True

if __name__ == '__main__':
    success = test_production()
    if not success:
        sys.exit(1)
