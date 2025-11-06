"""
Migration: Adicionar campos QI 200
- webhook_token no Payment
- gateway_id no Payment
- tracking_token no Payment e BotUser
- webhook_secret no Gateway
- priority e weight no Gateway

Execute: python migrations_add_qi200_fields.py
"""

import sys
import os
from pathlib import Path

# Adicionar diretório raiz ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app, db
from models import Payment, Gateway, BotUser
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Executa migration para adicionar campos QI 200"""
    
    with app.app_context():
        try:
            logger.info("🚀 Iniciando migration QI 200...")
            
            # 1. Adicionar webhook_token no Payment
            logger.info("1. Adicionando webhook_token no Payment...")
            try:
                db.session.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN webhook_token VARCHAR(100) UNIQUE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payments_webhook_token 
                    ON payments(webhook_token)
                """))
                logger.info("✅ webhook_token adicionado")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info("⚠️ webhook_token já existe, pulando...")
                else:
                    raise
            
            # 2. Adicionar gateway_id no Payment
            logger.info("2. Adicionando gateway_id no Payment...")
            try:
                db.session.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN gateway_id INTEGER
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payments_gateway_id 
                    ON payments(gateway_id)
                """))
                
                # Popular gateway_id em Payments existentes
                logger.info("   Populando gateway_id em Payments existentes...")
                db.session.execute(text("""
                    UPDATE payments
                    SET gateway_id = (
                        SELECT g.id
                        FROM gateways g
                        WHERE g.user_id = (
                            SELECT b.user_id
                            FROM bots b
                            WHERE b.id = payments.bot_id
                        )
                        AND g.gateway_type = payments.gateway_type
                        AND g.is_active = 1
                        LIMIT 1
                    )
                    WHERE gateway_id IS NULL
                """))
                
                logger.info("✅ gateway_id adicionado e populado")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info("⚠️ gateway_id já existe, pulando...")
                else:
                    raise
            
            # 3. Adicionar tracking_token no Payment
            logger.info("3. Adicionando tracking_token no Payment...")
            try:
                db.session.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN tracking_token VARCHAR(100)
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payments_tracking_token 
                    ON payments(tracking_token)
                """))
                logger.info("✅ tracking_token adicionado no Payment")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info("⚠️ tracking_token já existe no Payment, pulando...")
                else:
                    raise
            
            # 4. Adicionar tracking_token no BotUser
            logger.info("4. Adicionando tracking_token no BotUser...")
            try:
                db.session.execute(text("""
                    ALTER TABLE bot_users 
                    ADD COLUMN tracking_token VARCHAR(100) UNIQUE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_bot_users_tracking_token 
                    ON bot_users(tracking_token)
                """))
                logger.info("✅ tracking_token adicionado no BotUser")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info("⚠️ tracking_token já existe no BotUser, pulando...")
                else:
                    raise
            
            # 5. Adicionar webhook_secret no Gateway
            logger.info("5. Adicionando webhook_secret no Gateway...")
            try:
                db.session.execute(text("""
                    ALTER TABLE gateways 
                    ADD COLUMN webhook_secret VARCHAR(100) UNIQUE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_gateways_webhook_secret 
                    ON gateways(webhook_secret)
                """))
                
                # Gerar webhook_secret para Gateways existentes
                logger.info("   Gerando webhook_secret para Gateways existentes...")
                import uuid
                gateways = Gateway.query.all()
                for gateway in gateways:
                    if not gateway.webhook_secret:
                        gateway.webhook_secret = str(uuid.uuid4())
                        db.session.add(gateway)
                
                logger.info("✅ webhook_secret adicionado e gerado")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info("⚠️ webhook_secret já existe, pulando...")
                else:
                    raise
            
            # 6. Adicionar priority e weight no Gateway
            logger.info("6. Adicionando priority e weight no Gateway...")
            try:
                db.session.execute(text("""
                    ALTER TABLE gateways 
                    ADD COLUMN priority INTEGER DEFAULT 0
                """))
                db.session.execute(text("""
                    ALTER TABLE gateways 
                    ADD COLUMN weight INTEGER DEFAULT 1
                """))
                logger.info("✅ priority e weight adicionados")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info("⚠️ priority/weight já existem, pulando...")
                else:
                    raise
            
            db.session.commit()
            logger.info("✅ Migration QI 200 concluída com sucesso!")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro na migration: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == '__main__':
    run_migration()

