"""
Migration: Adicionar customer_email, customer_phone, customer_document ao Payment

Execute: python migrations/add_customer_email_phone_document.py
"""

import os
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_customer_fields():
    """
    Adiciona campos customer_email, customer_phone, customer_document ao Payment.
    Migration idempotente (verifica existência antes de criar).
    """
    # Carregar configuração do app
    from app import app, db
    
    with app.app_context():
        try:
            # Verificar se colunas já existem (idempotente)
            inspector = inspect(db.engine)
            table_name = 'payments'
            
            try:
                columns = [col['name'] for col in inspector.get_columns(table_name)]
                logger.info(f"🔍 Colunas existentes na tabela {table_name}: {len(columns)}")
                
                # Campos para adicionar (com sintaxe específica por banco)
                dialect_name = db.engine.dialect.name
                logger.info(f"🔍 Dialeto do banco: {dialect_name}")
                
                fields_to_add = [
                    ('customer_email', 'VARCHAR(255)'),
                    ('customer_phone', 'VARCHAR(50)'),
                    ('customer_document', 'VARCHAR(50)')
                ]
                
                added_count = 0
                for field_name, field_type in fields_to_add:
                    if field_name in columns:
                        logger.info(f"✅ Campo {field_name} já existe - pulando")
                    else:
                        logger.info(f"🔄 Adicionando coluna {field_name}...")
                        try:
                            # PostgreSQL: usar IF NOT EXISTS (PostgreSQL 9.5+)
                            if dialect_name == 'postgresql':
                                # Verificar se PostgreSQL suporta IF NOT EXISTS
                                try:
                                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {field_name} {field_type}"))
                                except Exception:
                                    # Fallback: verificar manualmente antes de adicionar
                                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {field_name} {field_type}"))
                            elif dialect_name == 'sqlite':
                                db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {field_name} {field_type}"))
                            else:
                                # MySQL
                                db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {field_name} {field_type}"))
                            
                            db.session.commit()
                            logger.info(f"✅ Campo {field_name} adicionado com sucesso")
                            added_count += 1
                        except Exception as e:
                            db.session.rollback()
                            error_str = str(e).lower()
                            if 'already exists' in error_str or 'duplicate' in error_str or 'column' in error_str and 'already' in error_str:
                                logger.info(f"⚠️ Campo {field_name} já existe (ignorando erro)")
                            else:
                                logger.error(f"❌ Erro ao adicionar {field_name}: {e}")
                                # Tentar verificar novamente se foi adicionado
                                try:
                                    columns_after = [col['name'] for col in inspector.get_columns(table_name)]
                                    if field_name in columns_after:
                                        logger.info(f"✅ Campo {field_name} foi adicionado (verificação pós-erro)")
                                        added_count += 1
                                    else:
                                        raise
                                except:
                                    raise
                
                if added_count > 0:
                    logger.info(f"✅ Migration concluída: {added_count} campo(s) adicionado(s)")
                else:
                    logger.info("✅ Migration já aplicada - todos os campos já existem")
                
                # ✅ VALIDAÇÃO FINAL: Verificar se todos os campos foram adicionados
                columns_final = [col['name'] for col in inspector.get_columns(table_name)]
                missing_fields = [f for f, _ in fields_to_add if f not in columns_final]
                if missing_fields:
                    logger.error(f"❌ Campos não adicionados: {missing_fields}")
                    return False
                else:
                    logger.info("✅ Validação final: Todos os campos estão presentes")
                    return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao verificar/adicionar colunas: {e}", exc_info=True)
                db.session.rollback()
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro crítico na migration: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔄 MIGRATION: Adicionar customer_email, customer_phone, customer_document")
    logger.info("=" * 80)
    
    success = add_customer_fields()
    
    if success:
        logger.info("=" * 80)
        logger.info("✅ MIGRATION CONCLUÍDA COM SUCESSO!")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("=" * 80)
        logger.error("❌ MIGRATION FALHOU!")
        logger.error("=" * 80)
        sys.exit(1)

