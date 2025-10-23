#!/usr/bin/env python3
"""
DIAGNÓSTICO CRÍTICO - Paradise Payment
=====================================
Investiga por que o Paradise retorna not_found para transações que existem
"""

import sys
import os
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_factory import GatewayFactory
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def diagnose_paradise_problem():
    """Diagnostica o problema real do Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("DIAGNÓSTICO CRÍTICO - PARADISE PAYMENT")
        print("=" * 80)
        
        # 1. Verificar últimos pagamentos Paradise
        payments = Payment.query.filter_by(
            gateway_type='paradise'
        ).order_by(Payment.id.desc()).limit(5).all()
        
        if not payments:
            print("❌ Nenhum pagamento Paradise encontrado")
            return
        
        print(f"\n📊 ÚLTIMOS 5 PAGAMENTOS PARADISE:")
        for i, payment in enumerate(payments, 1):
            print(f"   {i}. ID: {payment.payment_id} | Status: {payment.status} | Transaction: {payment.gateway_transaction_id} | Amount: R$ {payment.amount:.2f}")
        
        # 2. Pegar último pagamento pendente
        pending_payment = Payment.query.filter_by(
            gateway_type='paradise',
            status='pending'
        ).order_by(Payment.id.desc()).first()
        
        if not pending_payment:
            print("\n❌ Nenhum pagamento pendente encontrado")
            return
        
        print(f"\n🔍 ANALISANDO PAGAMENTO PENDENTE:")
        print(f"   Payment ID: {pending_payment.payment_id}")
        print(f"   Transaction ID: {pending_payment.gateway_transaction_id}")
        print(f"   Amount: R$ {pending_payment.amount:.2f}")
        print(f"   Created: {pending_payment.created_at}")
        
        # 3. Buscar gateway
        bot = pending_payment.bot
        gateway = Gateway.query.filter_by(
            user_id=bot.user_id,
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("\n❌ Gateway Paradise não encontrado")
            return
        
        print(f"\n🔑 GATEWAY CONFIGURADO:")
        print(f"   API Key: {gateway.api_key[:20]}...")
        print(f"   Product Hash: {gateway.product_hash}")
        print(f"   Store ID: {gateway.store_id}")
        
        # 4. Testar consulta direta na API
        print(f"\n🔍 TESTANDO CONSULTA DIRETA NA API PARADISE:")
        
        url = f"https://multi.paradisepags.com/api/v1/check_status.php?hash={pending_payment.gateway_transaction_id}"
        headers = {
            'X-API-Key': gateway.api_key,
            'Accept': 'application/json'
        }
        
        print(f"   URL: {url}")
        print(f"   Headers: X-API-Key={gateway.api_key[:20]}...")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   JSON: {data}")
                
                if data.get('payment_status') == 'not_found':
                    print("\n🚨 PROBLEMA IDENTIFICADO:")
                    print("   Paradise retorna 'not_found' para transação que existe!")
                    print("   Isso pode indicar:")
                    print("   1. Transação ainda não foi processada pelo Paradise")
                    print("   2. Transaction ID está incorreto")
                    print("   3. API Key não tem permissão para acessar esta transação")
                    print("   4. Transação expirou")
                    
                    # 5. Verificar se transação foi criada recentemente
                    time_diff = datetime.now() - pending_payment.created_at
                    print(f"\n⏰ TEMPO DESDE CRIAÇÃO: {time_diff}")
                    
                    if time_diff.total_seconds() < 300:  # 5 minutos
                        print("   ✅ Transação criada recentemente - pode estar sendo processada")
                    else:
                        print("   ⚠️ Transação antiga - pode ter expirado")
                        
                elif data.get('payment_status') == 'paid':
                    print("\n✅ TRANSAÇÃO APROVADA!")
                    print("   O problema é que nosso sistema não está detectando!")
                    
                else:
                    print(f"\n📊 STATUS: {data.get('payment_status')}")
                    
        except Exception as e:
            print(f"   ❌ Erro na consulta: {e}")
        
        # 6. Verificar se webhook está configurado
        print(f"\n🔍 VERIFICANDO WEBHOOK:")
        webhook_url = f"https://app.grimbots.online/webhook/payment/paradise"
        print(f"   URL: {webhook_url}")
        
        # Testar webhook
        try:
            test_data = {
                "id": pending_payment.gateway_transaction_id,
                "payment_status": "paid",
                "amount": int(pending_payment.amount * 100)
            }
            
            response = requests.post(webhook_url, json=test_data, timeout=10)
            print(f"   Test Status: {response.status_code}")
            print(f"   Test Response: {response.text}")
            
        except Exception as e:
            print(f"   ❌ Erro no teste do webhook: {e}")
        
        # 7. Verificar se polling está funcionando
        print(f"\n🔍 VERIFICANDO POLLING:")
        try:
            # Verificar se arquivo de log existe
            log_file = "/root/grimbots/logs/paradise_checker.log"
            if os.path.exists(log_file):
                print(f"   ✅ Log file existe: {log_file}")
                # Ler últimas linhas
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"   Últimas 3 linhas:")
                        for line in lines[-3:]:
                            print(f"     {line.strip()}")
                    else:
                        print(f"   ⚠️ Log file vazio")
            else:
                print(f"   ❌ Log file não existe: {log_file}")
                
        except Exception as e:
            print(f"   ❌ Erro ao verificar log: {e}")

if __name__ == '__main__':
    diagnose_paradise_problem()
