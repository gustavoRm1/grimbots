"""
Diagnóstico de Erro 500
Verifica o que está causando o erro no sistema
"""

import sys
import traceback
from app import app

with app.app_context():
    try:
        # Verificar se campos existem
        from sqlalchemy import inspect
        from models import Payment, BotUser
        
        inspector = inspect(Payment.__table__)
        payment_columns = [col.name for col in inspector.columns]
        
        print("\n📊 COLUNAS EM payments:")
        print("\n".join(payment_columns))
        
        # Verificar campos demográficos
        demographic_fields = [
            'customer_age', 'customer_city', 'customer_state', 
            'customer_country', 'customer_gender',
            'device_type', 'os_type', 'browser'
        ]
        
        print("\n🔍 VERIFICAÇÃO DE CAMPOS DEMOGRÁFICOS:")
        for field in demographic_fields:
            if field in payment_columns:
                print(f"✅ {field} existe")
            else:
                print(f"❌ {field} NÃO existe")
        
        # Testar query simples
        print("\n📊 TESTANDO QUERY SIMPLES:")
        payments = Payment.query.limit(5).all()
        print(f"✅ Query funcionou: {len(payments)} pagamentos encontrados")
        
        # Testar access aos campos
        print("\n🔍 TESTANDO ACESSO AOS CAMPOS:")
        for payment in payments[:2]:
            print(f"Payment ID: {payment.id}")
            try:
                print(f"  customer_age: {payment.customer_age}")
            except Exception as e:
                print(f"  ❌ Erro ao acessar customer_age: {e}")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        traceback.print_exc()
        sys.exit(1)

