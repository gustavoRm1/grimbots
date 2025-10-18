"""
Script STANDALONE para Criar/Resetar Admin
Não depende do app.py (evita problemas de importação)
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from pathlib import Path
import secrets
import string
import sys
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente
load_dotenv()

# Inicializar Flask minimalista
app = Flask(__name__)

# Configurar SECRET_KEY
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    print("\n[ERRO] .env sem SECRET_KEY")
    print("\nGerando SECRET_KEY agora...")
    SECRET_KEY = secrets.token_hex(32)
    with open('.env', 'a', encoding='utf-8') as f:
        f.write(f"\nSECRET_KEY={SECRET_KEY}\n")
    print(f"[OK] SECRET_KEY gerada e adicionada ao .env")

app.config['SECRET_KEY'] = SECRET_KEY

# Configurar Database
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar DB
db = SQLAlchemy(app)

# Modelo User (mínimo necessário)
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)

def generate_secure_password(length=24):
    """Gera senha aleatória forte"""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*+-="
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_or_reset_admin():
    """Cria ou reseta admin"""
    with app.app_context():
        print("\n" + "=" * 70)
        print(" " * 15 + "ADMIN MANAGER - grimbots")
        print("=" * 70)
        
        # Verificar se admin existe
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            print(f"\n[OK] Admin encontrado:")
            print(f"   ID: {admin.id}")
            print(f"   Email: {admin.email}")
            print(f"   Username: {admin.username}")
            print(f"   Status Admin: {admin.is_admin}")
            
            print("\n" + "-" * 70)
            resposta = input("[?] Deseja RESETAR a senha? (s/n): ").strip().lower()
            
            if resposta != 's':
                print("\n[CANCELADO] Operacao cancelada pelo usuario")
                return
            
            nova_senha = generate_secure_password(24)
            admin.password_hash = generate_password_hash(nova_senha)
            admin.is_admin = True
            admin.is_active = True
            admin.is_verified = True
            
        else:
            print("\n[AVISO] Nenhum admin encontrado. Criando novo admin...\n")
            
            nova_senha = generate_secure_password(24)
            
            admin = User(
                email='admin@grimbots.com',
                username='admin',
                full_name='Administrador',
                is_admin=True,
                is_verified=True,
                is_active=True,
                password_hash=generate_password_hash(nova_senha)
            )
            db.session.add(admin)
        
        # Commitar alteracoes
        try:
            db.session.commit()
            print("\n[OK] Banco de dados atualizado!")
        except Exception as e:
            db.session.rollback()
            print(f"\n[ERRO] Erro ao salvar no banco: {e}")
            return
        
        # Salvar credenciais em arquivo
        try:
            with open('.admin_password', 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write(" " * 15 + "CREDENCIAIS ADMINISTRATIVAS\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"  Email:     {admin.email}\n")
                f.write(f"  Username:  {admin.username}\n")
                f.write(f"  Senha:     {nova_senha}\n\n")
                f.write("  URL Admin: http://localhost:5000/admin/dashboard\n\n")
                f.write("=" * 70 + "\n")
                f.write("IMPORTANTE:\n")
                f.write("  - Guarde este arquivo em local seguro\n")
                f.write("  - Nunca compartilhe estas credenciais\n")
                f.write("  - Altere a senha apos o primeiro login\n")
                f.write("=" * 70 + "\n")
            
            print("\n" + "=" * 70)
            print(" " * 20 + "[OK] ADMIN CONFIGURADO!")
            print("=" * 70)
            print("\nCREDENCIAIS DE ACESSO:\n")
            print(f"  Email:     {admin.email}")
            print(f"  Username:  {admin.username}")
            print(f"  Senha:     {nova_senha}")
            print(f"\n  URL:       http://localhost:5000/admin/dashboard")
            print("\n" + "=" * 70)
            print(f"Credenciais salvas em: .admin_password")
            print("=" * 70 + "\n")
            
        except Exception as e:
            print(f"\n[AVISO] Nao foi possivel salvar arquivo: {e}")
            print("\nANOTE AS CREDENCIAIS:")
            print("=" * 70)
            print(f"Email:    {admin.email}")
            print(f"Username: {admin.username}")
            print(f"Senha:    {nova_senha}")
            print("=" * 70 + "\n")

if __name__ == '__main__':
    try:
        create_or_reset_admin()
    except KeyboardInterrupt:
        print("\n\n[CANCELADO] Operacao cancelada pelo usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

