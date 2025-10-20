#!/usr/bin/env python3
"""
Script para criar pool de teste com cloaker ativo
"""

import sys
sys.path.append('.')

from app import app, db
from models import RedirectPool, PoolBot, Bot, User

with app.app_context():
    # Buscar usuário admin
    admin = User.query.filter_by(email='admin@grimbots.com').first()
    if not admin:
        admin = User.query.first()
    
    if not admin:
        print("❌ Nenhum usuário encontrado")
        sys.exit(1)
    
    # Verificar se pool testslug já existe
    existing_pool = RedirectPool.query.filter_by(slug='testslug').first()
    if existing_pool:
        print("⚠️ Pool 'testslug' já existe, atualizando...")
        pool = existing_pool
    else:
        print("📝 Criando novo pool 'testslug'...")
        pool = RedirectPool(
            user_id=admin.id,
            name='Pool de Testes QA',
            slug='testslug',
            description='Pool para testes automatizados do cloaker',
            is_active=True,
            distribution_strategy='round_robin'
        )
        db.session.add(pool)
        db.session.flush()
    
    # Ativar cloaker
    pool.meta_cloaker_enabled = True
    pool.meta_cloaker_param_name = 'grim'
    pool.meta_cloaker_param_value = 'abc123xyz'
    
    # Associar um bot ao pool
    bot = Bot.query.filter_by(is_active=True).first()
    if bot and not pool.pool_bots.first():
        pool_bot = PoolBot(
            pool_id=pool.id,
            bot_id=bot.id,
            weight=100,
            priority=1,
            is_enabled=True,
            status='online'
        )
        db.session.add(pool_bot)
        print(f"✅ Bot associado: @{bot.username}")
    
    db.session.commit()
    
    print("")
    print("=" * 60)
    print("✅ POOL DE TESTE CRIADO COM SUCESSO")
    print("=" * 60)
    print(f"   Slug: {pool.slug}")
    print(f"   Nome: {pool.name}")
    print(f"   Cloaker: Ativo")
    print(f"   Parâmetro: {pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
    print("")
    print("📝 URL protegida:")
    print(f"   https://app.grimbots.online/go/{pool.slug}?{pool.meta_cloaker_param_name}={pool.meta_cloaker_param_value}")
    print("")
    print("📋 Configuração dos testes:")
    print(f"   TEST_SLUG = '{pool.slug}'")
    print(f"   CORRECT_VALUE = '{pool.meta_cloaker_param_value}'")
    print("")
    print("🧪 Execute os testes:")
    print("   python -m pytest tests/test_cloaker.py -v")
    print("=" * 60)

