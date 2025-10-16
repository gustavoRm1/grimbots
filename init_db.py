"""
Script de Inicialização do Banco de Dados
Cria todas as tabelas necessárias e dados iniciais
"""

from app import app, db
from models import User, Bot, BotConfig, Gateway, Payment
import os
import secrets
import string

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
            
            # ============================================================================
            # CORREÇÃO #3: SENHA ADMIN SEGURA E ALEATÓRIA
            # ============================================================================
            def generate_secure_password(length=24):
                """Gera senha aleatória forte com letras, números e símbolos"""
                alphabet = string.ascii_letters + string.digits + "!@#$%&*+-="
                return ''.join(secrets.choice(alphabet) for _ in range(length))
            
            admin_password = generate_secure_password(24)
            
            admin = User(
                email='admin@botmanager.com',
                username='admin',
                full_name='Administrador',
                is_admin=True,
                is_verified=True,
                is_active=True
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            
            # ✅ SALVAR SENHA EM ARQUIVO SEGURO (gitignore)
            credentials_file = '.admin_password'
            with open(credentials_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("CREDENCIAIS ADMINISTRATIVAS - grimbots\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Email:    admin@botmanager.com\n")
                f.write(f"Username: admin\n")
                f.write(f"Senha:    {admin_password}\n\n")
                f.write("⚠️  GUARDE ESTE ARQUIVO EM LOCAL SEGURO\n")
                f.write("⚠️  NUNCA COMPARTILHE ESTAS CREDENCIAIS\n")
                f.write("⚠️  ALTERE A SENHA APÓS O PRIMEIRO LOGIN\n")
                f.write("=" * 60 + "\n")
            
            print("✅ Usuário admin criado:")
            print("   Email:    admin@botmanager.com")
            print("   Username: admin")
            print(f"   Senha:    {admin_password}")
            print(f"\n🔒 Credenciais salvas em: {credentials_file}")
            print("   ⚠️  GUARDE ESTE ARQUIVO EM LOCAL SEGURO!")
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



