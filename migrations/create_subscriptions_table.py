#!/usr/bin/env python
"""
Script de Migração: Criar tabela subscriptions
Data: 2025-01-25
Descrição: Cria tabela subscriptions para sistema de assinaturas VIP
"""

import os
import sys
from pathlib import Path
from flask import Flask
from dotenv import load_dotenv

# Adicionar diretório raiz ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Carregar variáveis de ambiente
load_dotenv()

from models import db
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_subscriptions_table():
    """
    Cria tabela subscriptions com todos os campos e indexes necessários
    """
    app = Flask(__name__)
    
    # Configurar database URL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        # Fallback para SQLite
        DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f'sqlite:///{DB_PATH}'
    
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        try:
            logger.info("=" * 60)
            logger.info("🚀 Iniciando migração: Criar tabela subscriptions")
            logger.info("=" * 60)
            
            # ✅ Detectar tipo de banco de dados
            inspector = inspect(db.engine)
            dialect_name = db.engine.dialect.name
            
            logger.info(f"📊 Tipo de banco detectado: {dialect_name}")
            
            # ✅ Verificar se tabela já existe
            tables = inspector.get_table_names()
            
            if 'subscriptions' in tables:
                logger.info("⏭️  Tabela subscriptions já existe, pulando criação...")
                return True
            
            logger.info("➕ Criando tabela subscriptions...")
            
            if dialect_name == 'postgresql':
                # PostgreSQL
                db.session.execute(text("""
                    CREATE TABLE subscriptions (
                        id SERIAL PRIMARY KEY,
                        payment_id INTEGER NOT NULL UNIQUE,
                        bot_id INTEGER NOT NULL,
                        telegram_user_id VARCHAR(255) NOT NULL,
                        customer_name VARCHAR(255),
                        duration_type VARCHAR(20) NOT NULL,
                        duration_value INTEGER NOT NULL,
                        vip_chat_id VARCHAR(100) NOT NULL,
                        vip_group_link VARCHAR(500),
                        started_at TIMESTAMP WITH TIME ZONE,
                        expires_at TIMESTAMP WITH TIME ZONE,
                        removed_at TIMESTAMP WITH TIME ZONE,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        removed_by VARCHAR(50) DEFAULT 'system',
                        error_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        
                        CONSTRAINT fk_subscription_payment FOREIGN KEY (payment_id) 
                            REFERENCES payments(id) ON DELETE CASCADE,
                        CONSTRAINT fk_subscription_bot FOREIGN KEY (bot_id) 
                            REFERENCES bots(id)
                    )
                """))
                
                # Indexes PostgreSQL
                indexes = [
                    ("idx_subscription_status_expires", "status, expires_at"),
                    ("idx_subscription_vip_chat", "vip_chat_id, status"),
                    ("idx_subscription_telegram_user", "telegram_user_id"),
                    ("idx_subscription_bot_id", "bot_id"),
                    ("idx_subscription_created_at", "created_at"),
                    ("idx_subscription_payment_id", "payment_id")
                ]
                
                for idx_name, idx_cols in indexes:
                    try:
                        db.session.execute(text(f"""
                            CREATE INDEX {idx_name} ON subscriptions({idx_cols})
                        """))
                        logger.info(f"✅ Index {idx_name} criado")
                    except Exception as e:
                        error_msg = str(e).lower()
                        if 'already exists' in error_msg or 'duplicate' in error_msg:
                            logger.info(f"⏭️  Index {idx_name} já existe")
                        else:
                            raise
                
            elif dialect_name == 'sqlite':
                # SQLite
                db.session.execute(text("""
                    CREATE TABLE subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payment_id INTEGER NOT NULL UNIQUE,
                        bot_id INTEGER NOT NULL,
                        telegram_user_id VARCHAR(255) NOT NULL,
                        customer_name VARCHAR(255),
                        duration_type VARCHAR(20) NOT NULL,
                        duration_value INTEGER NOT NULL,
                        vip_chat_id VARCHAR(100) NOT NULL,
                        vip_group_link VARCHAR(500),
                        started_at TIMESTAMP,
                        expires_at TIMESTAMP,
                        removed_at TIMESTAMP,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        removed_by VARCHAR(50) DEFAULT 'system',
                        error_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
                        FOREIGN KEY (bot_id) REFERENCES bots(id)
                    )
                """))
                
                # Indexes SQLite
                indexes = [
                    ("idx_subscription_status_expires", "status, expires_at"),
                    ("idx_subscription_vip_chat", "vip_chat_id, status"),
                    ("idx_subscription_telegram_user", "telegram_user_id"),
                    ("idx_subscription_bot_id", "bot_id"),
                    ("idx_subscription_created_at", "created_at"),
                    ("idx_subscription_payment_id", "payment_id")
                ]
                
                for idx_name, idx_cols in indexes:
                    try:
                        db.session.execute(text(f"""
                            CREATE INDEX {idx_name} ON subscriptions({idx_cols})
                        """))
                        logger.info(f"✅ Index {idx_name} criado")
                    except Exception as e:
                        error_msg = str(e).lower()
                        if 'already exists' in error_msg or 'duplicate' in error_msg:
                            logger.info(f"⏭️  Index {idx_name} já existe")
                        else:
                            raise
                
            else:  # MySQL e outros
                # MySQL
                db.session.execute(text("""
                    CREATE TABLE subscriptions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        payment_id INT NOT NULL UNIQUE,
                        bot_id INT NOT NULL,
                        telegram_user_id VARCHAR(255) NOT NULL,
                        customer_name VARCHAR(255),
                        duration_type VARCHAR(20) NOT NULL,
                        duration_value INT NOT NULL,
                        vip_chat_id VARCHAR(100) NOT NULL,
                        vip_group_link VARCHAR(500),
                        started_at TIMESTAMP NULL,
                        expires_at TIMESTAMP NULL,
                        removed_at TIMESTAMP NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'pending',
                        removed_by VARCHAR(50) DEFAULT 'system',
                        error_count INT DEFAULT 0,
                        last_error TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
                        FOREIGN KEY (bot_id) REFERENCES bots(id),
                        INDEX idx_subscription_status_expires (status, expires_at),
                        INDEX idx_subscription_vip_chat (vip_chat_id, status),
                        INDEX idx_subscription_telegram_user (telegram_user_id),
                        INDEX idx_subscription_bot_id (bot_id),
                        INDEX idx_subscription_created_at (created_at),
                        INDEX idx_subscription_payment_id (payment_id)
                    )
                """))
            
            db.session.commit()
            logger.info("✅ Tabela subscriptions criada com sucesso")
            
            # ✅ Verificar estrutura criada
            final_tables = inspector.get_table_names()
            if 'subscriptions' in final_tables:
                columns = [col['name'] for col in inspector.get_columns('subscriptions')]
                logger.info(f"📊 Total de colunas na tabela subscriptions: {len(columns)}")
                logger.info(f"📊 Colunas: {', '.join(columns)}")
            
            logger.info("=" * 60)
            logger.info("✅ Migração concluída com sucesso!")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'already exists' in error_msg or 'duplicate' in error_msg:
                logger.info("⏭️  Tabela subscriptions já existe (ignorando erro)")
                db.session.rollback()
                return True
            else:
                logger.error(f"❌ Erro na migração: {e}", exc_info=True)
                db.session.rollback()
                return False


if __name__ == '__main__':
    success = create_subscriptions_table()
    sys.exit(0 if success else 1)


