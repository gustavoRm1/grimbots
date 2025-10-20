#!/usr/bin/env python3
"""
Script para descobrir um pool real para testes
"""

import sys
sys.path.append('.')

from app import app, db
from models import RedirectPool

with app.app_context():
    # Buscar primeiro pool ativo
    pool = RedirectPool.query.filter_by(is_active=True).first()
    
    if pool:
        print(f"✅ Pool encontrado:")
        print(f"   Slug: {pool.slug}")
        print(f"   Nome: {pool.name}")
        print(f"   Cloaker: {'Ativo' if pool.meta_cloaker_enabled else 'Inativo'}")
        
        if pool.meta_cloaker_enabled:
            print(f"   Parâmetro: {pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
        
        print(f"\n📝 Atualize os testes com:")
        print(f"   TEST_SLUG = '{pool.slug}'")
        if pool.meta_cloaker_enabled and pool.meta_cloaker_param_value:
            print(f"   CORRECT_VALUE = '{pool.meta_cloaker_param_value}'")
    else:
        print("❌ Nenhum pool ativo encontrado")
        print("\n📋 Criar pool de teste:")
        print("   1. Ir para /admin/pools")
        print("   2. Criar novo pool com slug 'testslug'")
        print("   3. Ativar cloaker")
        print("   4. Configurar parâmetro grim=abc123xyz")

