"""
Migration: Adicionar tabela push_subscriptions
Execute: python migrate_add_push_subscription.py
"""

from app import app, db
from models import PushSubscription

def migrate():
    with app.app_context():
        try:
            # Criar tabela se não existir
            db.create_all()
            print("✅ Tabela push_subscriptions criada/verificada com sucesso!")
        except Exception as e:
            print(f"❌ Erro na migration: {e}")
            raise

if __name__ == '__main__':
    migrate()

