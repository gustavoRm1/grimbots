#!/usr/bin/env python
"""
Script de Migração: Adicionar campos de nome de exibição no ranking
Data: 2025-11-25
Descrição: Adiciona campos ranking_display_name e ranking_first_visit_handled na tabela users
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


def add_ranking_display_name_fields():
    """
    Adiciona colunas ranking_display_name e ranking_first_visit_handled na tabela users
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
            logger.info("🚀 Iniciando migração: Adicionar campos de nome de exibição no ranking")
            logger.info("=" * 60)
            
            # ✅ Detectar tipo de banco de dados
            inspector = inspect(db.engine)
            dialect_name = db.engine.dialect.name
            
            logger.info(f"📊 Tipo de banco detectado: {dialect_name}")
            
            # ✅ Verificar se as colunas já existem
            columns = [col['name'] for col in inspector.get_columns('users')]
            logger.info(f"📊 Colunas existentes na tabela users: {len(columns)}")
            
            # ✅ Adicionar ranking_display_name se não existir
            if 'ranking_display_name' not in columns:
                logger.info("➕ Adicionando coluna ranking_display_name...")
                try:
                    if dialect_name == 'postgresql':
                        db.session.execute(text("""
                            ALTER TABLE users 
                            ADD COLUMN ranking_display_name VARCHAR(50) NULL
                        """))
                    elif dialect_name == 'sqlite':
                        # SQLite não suporta ADD COLUMN IF NOT EXISTS diretamente
                        db.session.execute(text("""
                            ALTER TABLE users 
                            ADD COLUMN ranking_display_name VARCHAR(50)
                        """))
                    else:
                        # MySQL e outros
                        db.session.execute(text("""
                            ALTER TABLE users 
                            ADD COLUMN ranking_display_name VARCHAR(50) NULL
                        """))
                    db.session.commit()
                    logger.info("✅ Coluna ranking_display_name adicionada com sucesso")
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'duplicate' in error_msg or 'already exists' in error_msg or 'exists' in error_msg:
                        logger.info("⏭️  Coluna ranking_display_name já existe (ignorando erro)")
                        db.session.rollback()
                    else:
                        raise
            else:
                logger.info("⏭️  Coluna ranking_display_name já existe, pulando...")
            
            # ✅ Atualizar lista de colunas após primeira adição
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            # ✅ Adicionar ranking_first_visit_handled se não existir
            if 'ranking_first_visit_handled' not in columns:
                logger.info("➕ Adicionando coluna ranking_first_visit_handled...")
                try:
                    if dialect_name == 'postgresql':
                        db.session.execute(text("""
                            ALTER TABLE users 
                            ADD COLUMN ranking_first_visit_handled BOOLEAN DEFAULT FALSE
                        """))
                    elif dialect_name == 'sqlite':
                        # SQLite usa INTEGER para boolean (0 ou 1)
                        db.session.execute(text("""
                            ALTER TABLE users 
                            ADD COLUMN ranking_first_visit_handled INTEGER DEFAULT 0
                        """))
                    else:
                        # MySQL e outros
                        db.session.execute(text("""
                            ALTER TABLE users 
                            ADD COLUMN ranking_first_visit_handled BOOLEAN DEFAULT FALSE
                        """))
                    db.session.commit()
                    logger.info("✅ Coluna ranking_first_visit_handled adicionada com sucesso")
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'duplicate' in error_msg or 'already exists' in error_msg or 'exists' in error_msg:
                        logger.info("⏭️  Coluna ranking_first_visit_handled já existe (ignorando erro)")
                        db.session.rollback()
                    else:
                        raise
            else:
                logger.info("⏭️  Coluna ranking_first_visit_handled já existe, pulando...")
            
            # ✅ Verificar se as colunas foram criadas corretamente
            final_columns = [col['name'] for col in inspector.get_columns('users')]
            added_columns = [col for col in final_columns if col in ['ranking_display_name', 'ranking_first_visit_handled']]
            
            logger.info("=" * 60)
            logger.info("✅ Migração concluída com sucesso!")
            logger.info(f"📊 Colunas adicionadas: {added_columns}")
            logger.info(f"📊 Total de colunas na tabela users: {len(final_columns)}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na migração: {e}", exc_info=True)
            db.session.rollback()
            return False


if __name__ == '__main__':
    success = add_ranking_display_name_fields()
    sys.exit(0 if success else 1)
