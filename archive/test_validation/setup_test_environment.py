#!/usr/bin/env python3
"""
🔧 CONFIGURAÇÃO DE POOL DE TESTE PARA CLOAKER
Cria pool de teste para demonstração
"""

import os
import sys
sys.path.append('.')

from app import app, db
from models import RedirectPool, PoolBot, Bot, User
from datetime import datetime

def create_test_pool():
    """Cria pool de teste para demonstração do cloaker"""
    
    with app.app_context():
        # 1. Buscar usuário admin
        admin_user = User.query.filter_by(email='admin@grimbots.com').first()
        if not admin_user:
            print("❌ Usuário admin não encontrado")
            return False
        
        # 2. Buscar bot de teste
        test_bot = Bot.query.filter_by(username='test_bot').first()
        if not test_bot:
            print("❌ Bot de teste não encontrado")
            return False
        
        # 3. Criar pool de teste
        test_pool = RedirectPool(
            name='Pool de Teste Cloaker',
            slug='test',
            description='Pool para demonstração do cloaker',
            user_id=admin_user.id,
            is_active=True,
            cloaker_enabled=True,
            cloaker_param_name='apx',
            cloaker_param_value='ohx9lury'
        )
        
        db.session.add(test_pool)
        db.session.flush()  # Para obter o ID
        
        # 4. Associar bot ao pool
        pool_bot = PoolBot(
            pool_id=test_pool.id,
            bot_id=test_bot.id,
            weight=100,
            priority=1,
            is_enabled=True
        )
        
        db.session.add(pool_bot)
        
        # 5. Commit
        db.session.commit()
        
        print(f"✅ Pool de teste criado: {test_pool.name}")
        print(f"🔗 Slug: {test_pool.slug}")
        print(f"🛡️ Cloaker: {'Ativado' if test_pool.cloaker_enabled else 'Desativado'}")
        print(f"🔑 Parâmetro: {test_pool.cloaker_param_name}={test_pool.cloaker_param_value}")
        
        return True

def create_test_bot():
    """Cria bot de teste se não existir"""
    
    with app.app_context():
        # Verificar se bot já existe
        existing_bot = Bot.query.filter_by(username='test_bot').first()
        if existing_bot:
            print("✅ Bot de teste já existe")
            return existing_bot
        
        # Buscar usuário admin
        admin_user = User.query.filter_by(email='admin@grimbots.com').first()
        if not admin_user:
            print("❌ Usuário admin não encontrado")
            return None
        
        # Criar bot de teste
        test_bot = Bot(
            name='Bot de Teste',
            username='test_bot',
            token='123456789:ABCdefGHIjklMNOpqrsTUVwxyz',
            user_id=admin_user.id,
            is_active=True,
            is_running=False
        )
        
        db.session.add(test_bot)
        db.session.commit()
        
        print(f"✅ Bot de teste criado: {test_bot.name}")
        return test_bot

def setup_test_environment():
    """Configura ambiente de teste completo"""
    
    print("🚀 Configurando ambiente de teste...")
    
    # 1. Criar bot de teste
    bot = create_test_bot()
    if not bot:
        return False
    
    # 2. Criar pool de teste
    success = create_test_pool()
    if not success:
        return False
    
    print("\n✅ Ambiente de teste configurado!")
    print("🔗 URL de teste: https://app.grimbots.online/go/test")
    print("🛡️ Parâmetro obrigatório: ?apx=ohx9lury")
    
    return True

if __name__ == "__main__":
    success = setup_test_environment()
    if success:
        print("\n🎯 Pronto para demonstração!")
        print("Execute: python test_cloaker_demonstration.py")
    else:
        print("\n❌ Falha na configuração")
        sys.exit(1)
