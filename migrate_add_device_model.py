"""Migração para adicionar campo device_model em bot_users e payments"""
from app import app, db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_device_model_field():
    """Adiciona campo device_model para armazenar modelo específico do dispositivo"""
    with app.app_context():
        logger.info("🚀 Iniciando migração: device_model")
        
        # 1. Adicionar em bot_users
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN device_model VARCHAR(100)
                """))
                logger.info("✅ device_model adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo device_model já existe em bot_users ou erro: {e}")
        
        # 2. Adicionar em payments
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN device_model VARCHAR(100)
                """))
                logger.info("✅ device_model adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo device_model já existe em payments ou erro: {e}")
        
        logger.info("✅ Migração concluída!")

if __name__ == '__main__':
    add_device_model_field()

