"""
Script de Inicialização do Banco de Dados
Cria todas as tabelas necessárias e dados iniciais
"""

from app import app, db
from models import User, Bot, BotConfig, Gateway, Payment
import os

def init_database():
    """Inicializa o banco de dados"""
    with app.app_context():
        print("🔧 Criando tabelas do banco de dados...")
        db.create_all()
        print("✅ Tabelas criadas com sucesso!")
        
        # Verificar se já existe usuário admin
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            print("\n🔧 Criando usuário administrador padrão...")
            admin = User(
                email='admin@botmanager.com',
                username='admin',
                full_name='Administrador',
                plan='pro',
                max_bots=999,
                is_verified=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Usuário admin criado:")
            print("   Email: admin@botmanager.com")
            print("   Senha: admin123")
            print("   ⚠️  ALTERE A SENHA APÓS O PRIMEIRO LOGIN!")
        else:
            print("\n✅ Usuário admin já existe")
        
        print("\n🎉 Banco de dados inicializado com sucesso!")
        print("\n📝 Informações:")
        print(f"   - Total de usuários: {User.query.count()}")
        print(f"   - Total de bots: {Bot.query.count()}")
        print(f"   - Total de gateways: {Gateway.query.count()}")
        print(f"   - Total de pagamentos: {Payment.query.count()}")

if __name__ == '__main__':
    print("=" * 60)
    print("Bot Manager SaaS - Inicialização do Banco de Dados")
    print("=" * 60)
    init_database()
    print("=" * 60)



