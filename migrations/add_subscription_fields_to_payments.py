#!/usr/bin/env python
"""
Script de Migração: Adicionar campos de subscription ao Payment
Data: 2025-01-25
Descrição: Adiciona campos button_index, button_config e has_subscription na tabela payments
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

from internal_logic.core.models import db
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_subscription_fields_to_payments():
    """
    Adiciona colunas button_index, button_config e has_subscription na tabela payments
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
            logger.info("🚀 Iniciando migração: Adicionar campos de subscription no Payment")
            logger.info("=" * 60)
            
            # ✅ Detectar tipo de banco de dados
            inspector = inspect(db.engine)
            dialect_name = db.engine.dialect.name
            
            logger.info(f"📊 Tipo de banco detectado: {dialect_name}")
            
            # ✅ Verificar se as colunas já existem
            columns = [col['name'] for col in inspector.get_columns('payments')]
            logger.info(f"📊 Colunas existentes na tabela payments: {len(columns)}")
            
            # ✅ Adicionar button_index se não existir
            if 'button_index' not in columns:
                logger.info("➕ Adicionando coluna button_index...")
                try:
                    db.session.execute(text("""
                        ALTER TABLE payments 
                        ADD COLUMN button_index INTEGER NULL
                    """))
                    db.session.commit()
                    logger.info("✅ Coluna button_index adicionada com sucesso")
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'duplicate' in error_msg or 'already exists' in error_msg or 'exists' in error_msg:
                        logger.info("⏭️  Coluna button_index já existe (ignorando erro)")
                        db.session.rollback()
                    else:
                        raise
            else:
                logger.info("⏭️  Coluna button_index já existe, pulando...")
            
            # ✅ Atualizar lista de colunas após primeira adição
            columns = [col['name'] for col in inspector.get_columns('payments')]
            
            # ✅ Adicionar button_config se não existir
            if 'button_config' not in columns:
                logger.info("➕ Adicionando coluna button_config...")
                try:
                    db.session.execute(text("""
                        ALTER TABLE payments 
                        ADD COLUMN button_config TEXT NULL
                    """))
                    db.session.commit()
                    logger.info("✅ Coluna button_config adicionada com sucesso")
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'duplicate' in error_msg or 'already exists' in error_msg or 'exists' in error_msg:
                        logger.info("⏭️  Coluna button_config já existe (ignorando erro)")
                        db.session.rollback()
                    else:
                        raise
            else:
                logger.info("⏭️  Coluna button_config já existe, pulando...")
            
            # ✅ Atualizar lista de colunas após segunda adição
            columns = [col['name'] for col in inspector.get_columns('payments')]
            
            # ✅ Adicionar has_subscription se não existir
            if 'has_subscription' not in columns:
                logger.info("➕ Adicionando coluna has_subscription...")
                try:
                    if dialect_name == 'postgresql':
                        db.session.execute(text("""
                            ALTER TABLE payments 
                            ADD COLUMN has_subscription BOOLEAN DEFAULT FALSE NOT NULL
                        """))
                    elif dialect_name == 'sqlite':
                        # SQLite usa INTEGER para boolean (0 ou 1)
                        db.session.execute(text("""
                            ALTER TABLE payments 
                            ADD COLUMN has_subscription INTEGER DEFAULT 0 NOT NULL
                        """))
                    else:  # MySQL e outros
                        db.session.execute(text("""
                            ALTER TABLE payments 
                            ADD COLUMN has_subscription BOOLEAN DEFAULT FALSE NOT NULL
                        """))
                    db.session.commit()
                    logger.info("✅ Coluna has_subscription adicionada com sucesso")
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'duplicate' in error_msg or 'already exists' in error_msg or 'exists' in error_msg:
                        logger.info("⏭️  Coluna has_subscription já existe (ignorando erro)")
                        db.session.rollback()
                    else:
                        raise
            else:
                logger.info("⏭️  Coluna has_subscription já existe, pulando...")
            
            # ✅ Criar index parcial (apenas PostgreSQL)
            if dialect_name == 'postgresql':
                try:
                    # Verificar se index já existe
                    existing_indexes = [idx['name'] for idx in inspector.get_indexes('payments')]
                    
                    if 'idx_payment_has_subscription' not in existing_indexes:
                        logger.info("➕ Criando index idx_payment_has_subscription...")
                        db.session.execute(text("""
                            CREATE INDEX idx_payment_has_subscription 
                            ON payments(bot_id, customer_user_id, status) 
                            WHERE has_subscription = true
                        """))
                        db.session.commit()
                        logger.info("✅ Index idx_payment_has_subscription criado com sucesso")
                    else:
                        logger.info("⏭️  Index idx_payment_has_subscription já existe, pulando...")
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'duplicate' in error_msg or 'already exists' in error_msg or 'exists' in error_msg:
                        logger.info("⏭️  Index já existe (ignorando erro)")
                        db.session.rollback()
                    else:
                        logger.warning(f"⚠️  Erro ao criar index (pode não ser crítico): {e}")
                        db.session.rollback()
            
            # ✅ Verificar se as colunas foram criadas corretamente
            final_columns = [col['name'] for col in inspector.get_columns('payments')]
            added_columns = [col for col in final_columns if col in ['button_index', 'button_config', 'has_subscription']]
            
            logger.info("=" * 60)
            logger.info("✅ Migração concluída com sucesso!")
            logger.info(f"📊 Colunas adicionadas: {added_columns}")
            logger.info(f"📊 Total de colunas na tabela payments: {len(final_columns)}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na migração: {e}", exc_info=True)
            db.session.rollback()
            return False


if __name__ == '__main__':
    success = add_subscription_fields_to_payments()
    sys.exit(0 if success else 1)


