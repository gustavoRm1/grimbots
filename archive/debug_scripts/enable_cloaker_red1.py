#!/usr/bin/env python3
"""
Script para ativar cloaker no pool 'red1'
"""

import sys
sys.path.append('.')

from app import app, db
from models import RedirectPool
import uuid

with app.app_context():
    # Buscar pool red1
    pool = RedirectPool.query.filter_by(slug='red1').first()
    
    if not pool:
        print("❌ Pool 'red1' não encontrado")
        sys.exit(1)
    
    # Ativar cloaker
    pool.meta_cloaker_enabled = True
    pool.meta_cloaker_param_name = 'grim'
    pool.meta_cloaker_param_value = 'abc123xyz'  # Valor para testes
    
    db.session.commit()
    
    print("✅ Cloaker ativado no pool 'red1'")
    print(f"   Slug: {pool.slug}")
    print(f"   Nome: {pool.name}")
    print(f"   Cloaker: Ativo")
    print(f"   Parâmetro: {pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
    print("")
    print("📝 URL protegida:")
    print(f"   https://app.grimbots.online/go/{pool.slug}?{pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
    print("")
    print("🧪 Execute os testes:")
    print("   python -m pytest tests/test_cloaker.py -v")

