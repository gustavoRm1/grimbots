"""
Migration: Adicionar tracking_token ao modelo Payment
QI 500 - Engineer Sênior

Execute: python migrations/migrations_add_tracking_token.py
"""

import os
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask
from models import db
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_tracking_token():
    """
    Adiciona campo tracking_token ao modelo Payment.
    Migration idempotente (verifica existência antes de criar).
    """
    app = Flask(__name__)
    
    # Usar mesma configuração do app.py
    DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 
        f'sqlite:///{DB_PATH}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        try:
            # Verificar se coluna já existe (idempotente)
            inspector = inspect(db.engine)
            
            try:
                columns = [col['name'] for col in inspector.get_columns('payment')]
                
                if 'tracking_token' in columns:
                    logger.info("✅ Campo tracking_token já existe em Payment - migration já aplicada")
                    return True
            except Exception as e:
                logger.warning(f"⚠️ Tabela payment pode não existir ainda: {e}")
                # Continuar para criar a coluna (pode falhar se tabela não existir)
            
            # Adicionar coluna tracking_token
            logger.info("🔄 Adicionando coluna tracking_token ao Payment...")
            
            # SQL compatível com SQLite, PostgreSQL e MySQL
            try:
                db.session.execute(text("""
                    ALTER TABLE payment
                    ADD COLUMN tracking_token VARCHAR(100);
                """))
                db.session.commit()
                logger.info("✅ Campo tracking_token adicionado ao Payment")
            except Exception as e:
                error_msg = str(e).lower()
                if 'duplicate' in error_msg or 'already exists' in error_msg or 'exists' in error_msg:
                    logger.info("✅ Campo tracking_token já existe (ignorando erro)")
                    db.session.rollback()
                else:
                    raise
            
            # Criar índice (idempotente)
            try:
                logger.info("🔄 Criando índice idx_payment_tracking_token...")
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payment_tracking_token 
                    ON payment(tracking_token);
                """))
                db.session.commit()
                logger.info("✅ Índice idx_payment_tracking_token criado")
            except Exception as e:
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    logger.info("✅ Índice já existe (ignorando erro)")
                    db.session.rollback()
                else:
                    logger.warning(f"⚠️ Erro ao criar índice (pode já existir): {e}")
                    db.session.rollback()
            
            logger.info("✅ Migration concluída com sucesso")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro na migration: {e}", exc_info=True)
            return False


def rollback_tracking_token():
    """
    Rollback: Remove campo tracking_token do modelo Payment.
    Execute com cuidado - dados serão perdidos!
    """
    app = Flask(__name__)
    
    DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 
        f'sqlite:///{DB_PATH}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        try:
            logger.warning("⚠️ REMOVENDO tracking_token - dados serão perdidos!")
            
            # Remover índice
            try:
                db.session.execute(text("""
                    DROP INDEX IF EXISTS idx_payment_tracking_token;
                """))
                db.session.commit()
                logger.info("✅ Índice removido")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao remover índice: {e}")
                db.session.rollback()
            
            # Remover coluna (SQLite não suporta DROP COLUMN diretamente)
            # Para SQLite, seria necessário recriar a tabela
            # Para PostgreSQL/MySQL, usar:
            try:
                db.session.execute(text("""
                    ALTER TABLE payment DROP COLUMN tracking_token;
                """))
                db.session.commit()
                logger.info("✅ Coluna tracking_token removida")
            except Exception as e:
                error_msg = str(e).lower()
                if 'no such column' in error_msg or "doesn't exist" in error_msg:
                    logger.info("✅ Coluna não existe (já removida)")
                    db.session.rollback()
                else:
                    logger.error(f"❌ SQLite não suporta DROP COLUMN. Use ferramenta de migração ou recrie tabela.")
                    raise
            
            logger.info("✅ Rollback concluído")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro no rollback: {e}", exc_info=True)
            return False


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        logger.warning("🔄 Executando ROLLBACK...")
        success = rollback_tracking_token()
        sys.exit(0 if success else 1)
    else:
        logger.info("🔄 Executando migration...")
        success = add_tracking_token()
        sys.exit(0 if success else 1)

