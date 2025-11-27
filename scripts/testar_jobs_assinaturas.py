#!/usr/bin/env python3
"""
Script para testar os jobs de assinaturas manualmente
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from app import (
    check_expired_subscriptions,
    check_pending_subscriptions_in_groups,
    retry_failed_subscription_removals
)

def main():
    print("=" * 70)
    print("🧪 TESTE MANUAL DOS JOBS DE ASSINATURAS")
    print("=" * 70)
    print()
    
    with app.app_context():
        # Teste 1: check_expired_subscriptions
        print("🔍 Testando check_expired_subscriptions...")
        try:
            check_expired_subscriptions()
            print("✅ Sucesso!")
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        
        # Teste 2: check_pending_subscriptions_in_groups
        print("🔍 Testando check_pending_subscriptions_in_groups...")
        try:
            check_pending_subscriptions_in_groups()
            print("✅ Sucesso!")
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        
        # Teste 3: retry_failed_subscription_removals
        print("🔍 Testando retry_failed_subscription_removals...")
        try:
            retry_failed_subscription_removals()
            print("✅ Sucesso!")
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        print("=" * 70)
        print("✅ TESTES CONCLUÍDOS")
        print("=" * 70)

if __name__ == '__main__':
    main()

