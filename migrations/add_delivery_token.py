#!/usr/bin/env python3
"""
Migration: Adicionar delivery_token e purchase_sent_from_delivery ao Payment
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import inspect, text

def migrate():
    """Adiciona campos delivery_token e purchase_sent_from_delivery à tabela payments"""
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('payments')]
            
            if 'delivery_token' in columns and 'purchase_sent_from_delivery' in columns:
                print("✅ Campos delivery_token e purchase_sent_from_delivery já existem na tabela payments")
                return True
            
            print("🔄 Adicionando campos delivery_token e purchase_sent_from_delivery na tabela payments...")
            
            if 'delivery_token' not in columns:
                db.session.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN delivery_token VARCHAR(64) UNIQUE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payments_delivery_token 
                    ON payments(delivery_token)
                """))
                print("✅ Campo delivery_token adicionado com sucesso!")
            
            if 'purchase_sent_from_delivery' not in columns:
                db.session.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN purchase_sent_from_delivery BOOLEAN DEFAULT FALSE
                """))
                print("✅ Campo purchase_sent_from_delivery adicionado com sucesso!")
            
            db.session.commit()
            print("✅ Migration concluída com sucesso!")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao adicionar campos: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    migrate()

