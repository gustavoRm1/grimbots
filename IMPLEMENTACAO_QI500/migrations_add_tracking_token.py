"""
Migration: Adicionar tracking_token ao modelo Payment
Execute: python migrations_add_tracking_token.py
"""

import os
from flask import Flask
from models import db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

def add_tracking_token():
    """
    Adiciona campo tracking_token ao modelo Payment.
    """
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///grimbots.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        try:
            # Verificar se coluna já existe
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('payment')]
            
            if 'tracking_token' in columns:
                logger.info("✅ Campo tracking_token já existe em Payment")
                return
            
            # Adicionar coluna tracking_token
            db.session.execute(text("""
                ALTER TABLE payment
                ADD COLUMN tracking_token VARCHAR(100);
            """))
            db.session.commit()
            logger.info("✅ Campo tracking_token adicionado ao Payment")
            
            # Criar índice
            try:
                db.session.execute(text("""
                    CREATE INDEX idx_payment_tracking_token 
                    ON payment(tracking_token);
                """))
                db.session.commit()
                logger.info("✅ Índice idx_payment_tracking_token criado")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao criar índice (pode já existir): {e}")
                db.session.rollback()
            
            logger.info("✅ Migration concluída com sucesso")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro na migration: {e}", exc_info=True)
            raise

if __name__ == '__main__':
    add_tracking_token()

