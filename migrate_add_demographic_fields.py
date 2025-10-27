"""
Migration: Adicionar Campos Demográficos
Para Analytics Avançado de Gestor de Tráfego

Autor: Senior QI 502 + QI 500
Data: 2025-10-27
"""

from models import db, BotUser, Payment
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

def add_demographic_fields():
    """Adiciona campos demográficos e de device para analytics avançado"""
    
    try:
        logger.info("🔄 Iniciando migration de campos demográficos...")
        
        # ✅ 1. ADICIONAR EM BotUser
        logger.info("📊 Adicionando campos em bot_users...")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN customer_age INTEGER
                """))
                logger.info("✅ customer_age adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_age já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN customer_city VARCHAR(100)
                """))
                logger.info("✅ customer_city adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_city já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN customer_state VARCHAR(50)
                """))
                logger.info("✅ customer_state adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_state já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN customer_country VARCHAR(50) DEFAULT 'BR'
                """))
                logger.info("✅ customer_country adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_country já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN customer_gender VARCHAR(20)
                """))
                logger.info("✅ customer_gender adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_gender já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN device_type VARCHAR(20)
                """))
                logger.info("✅ device_type adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo device_type já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN os_type VARCHAR(50)
                """))
                logger.info("✅ os_type adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo os_type já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN browser VARCHAR(50)
                """))
                logger.info("✅ browser adicionado em bot_users")
        except Exception as e:
            logger.warning(f"⚠️ Campo browser já existe ou erro: {e}")
        
        # ✅ 2. ADICIONAR EM Payment
        logger.info("📊 Adicionando campos em payments...")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN customer_age INTEGER
                """))
                logger.info("✅ customer_age adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_age já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN customer_city VARCHAR(100)
                """))
                logger.info("✅ customer_city adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_city já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN customer_state VARCHAR(50)
                """))
                logger.info("✅ customer_state adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_state já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN customer_country VARCHAR(50) DEFAULT 'BR'
                """))
                logger.info("✅ customer_country adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_country já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN customer_gender VARCHAR(20)
                """))
                logger.info("✅ customer_gender adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo customer_gender já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN device_type VARCHAR(20)
                """))
                logger.info("✅ device_type adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo device_type já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN os_type VARCHAR(50)
                """))
                logger.info("✅ os_type adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo os_type já existe ou erro: {e}")
        
        try:
            with db.engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN browser VARCHAR(50)
                """))
                logger.info("✅ browser adicionado em payments")
        except Exception as e:
            logger.warning(f"⚠️ Campo browser já existe ou erro: {e}")
        
        logger.info("✅ Migration concluída com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    from app import app
    with app.app_context():
        add_demographic_fields()

