"""
Migration: Adicionar tabela notification_settings
Execute: python migrate_add_notification_settings.py
"""

from app import app, db
from models import NotificationSettings

def migrate():
    with app.app_context():
        try:
            # Criar tabela se não existir
            db.create_all()
            print("✅ Tabela notification_settings criada/verificada com sucesso!")
            
            # Criar settings padrão para usuários existentes
            from models import User
            users = User.query.all()
            created_count = 0
            for user in users:
                existing = NotificationSettings.query.filter_by(user_id=user.id).first()
                if not existing:
                    settings = NotificationSettings(
                        user_id=user.id,
                        notify_approved_sales=True,
                        notify_pending_sales=False
                    )
                    db.session.add(settings)
                    created_count += 1
            db.session.commit()
            print(f"✅ {created_count} configurações padrão criadas para usuários existentes!")
            
        except Exception as e:
            print(f"❌ Erro na migration: {e}")
            raise

if __name__ == '__main__':
    migrate()

