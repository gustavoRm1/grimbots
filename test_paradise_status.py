#!/usr/bin/env python3
"""
Script de teste para debugar a API Paradise check_status
Execute na VPS: python test_paradise_status.py
"""

import sys
import os

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_factory import GatewayFactory
import logging

# Configura logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_paradise_status():
    """Testa a verificação de status do Paradise com o último pagamento"""
    
    with app.app_context():
        # Pegar último pagamento Paradise
        payment = Payment.query.filter_by(gateway_type='paradise').order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum pagamento Paradise encontrado no banco")
            return
        
        print("=" * 80)
        print("TESTE DE VERIFICAÇÃO DE STATUS - PARADISE")
        print("=" * 80)
        
        print(f"\n📊 PAGAMENTO NO BANCO:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Status LOCAL: {payment.status}")
        print(f"   Gateway Type: {payment.gateway_type}")
        print(f"   Transaction ID: {payment.gateway_transaction_id}")
        print(f"   Amount: R$ {payment.amount:.2f}")
        print(f"   Created: {payment.created_at}")
        
        # Buscar gateway
        bot = payment.bot
        gateway = Gateway.query.filter_by(
            user_id=bot.user_id,
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("\n❌ Gateway Paradise não encontrado ou não verificado")
            return
        
        print(f"\n🔑 GATEWAY CONFIGURADO:")
        print(f"   Verificado: {gateway.is_verified}")
        print(f"   API Key: {gateway.api_key[:20]}...")
        print(f"   Product Hash: {gateway.product_hash}")
        print(f"   Offer Hash: {gateway.offer_hash}")
        print(f"   Store ID: {gateway.store_id}")
        
        # Criar instância do gateway
        credentials = {
            'api_key': gateway.api_key,
            'product_hash': gateway.product_hash,
            'offer_hash': gateway.offer_hash,
            'store_id': gateway.store_id,
            'split_percentage': gateway.split_percentage or 4.0
        }
        
        print(f"\n🔧 CRIANDO GATEWAY...")
        pg = GatewayFactory.create_gateway('paradise', credentials)
        
        if not pg:
            print("❌ Não foi possível criar instância do gateway")
            return
        
        print("✅ Gateway criado com sucesso")
        
        # Testar consulta de status
        print(f"\n🔍 CONSULTANDO STATUS NA API PARADISE...")
        print(f"   Transaction ID: {payment.gateway_transaction_id}")
        print(f"   URL: {pg.check_status_url}")
        print(f"   Param: hash={payment.gateway_transaction_id}")
        
        result = pg.get_payment_status(payment.gateway_transaction_id)
        
        print(f"\n📋 RESULTADO DA CONSULTA:")
        if result:
            print("   ✅ API retornou dados:")
            print(f"      Transaction ID: {result.get('gateway_transaction_id')}")
            print(f"      Status: {result.get('status')}")
            print(f"      Amount: R$ {result.get('amount', 0):.2f}")
        else:
            print("   ❌ API não retornou dados (None)")
        
        print("\n" + "=" * 80)
        print("TESTE FINALIZADO")
        print("=" * 80)
        
        # Instruções
        print("\n💡 PRÓXIMOS PASSOS:")
        print("   1. Verifique os logs acima para ver o que o Paradise retornou")
        print("   2. Procure por '🔍 Paradise API - Response Body (raw)'")
        print("   3. Procure por '🔍 Paradise API - Data JSON'")
        print("   4. Se o pagamento foi aprovado no Paradise mas aparece 'pending' aqui,")
        print("      o problema está no mapeamento de campos da API")

if __name__ == '__main__':
    test_paradise_status()

