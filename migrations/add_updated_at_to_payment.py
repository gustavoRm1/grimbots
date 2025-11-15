"""
Migration: Adicionar updated_at ao Payment

Execute: python migrations/add_updated_at_to_payment.py
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


def add_updated_at_to_payment():
    """
    Adiciona campo updated_at ao Payment.
    Migration idempotente (verifica existência antes de criar).
    """
    # Carregar configuração do app
    from app import app, db
    
    with app.app_context():
        try:
            # Verificar se coluna já existe (idempotente)
            inspector = inspect(db.engine)
            table_name = 'payments'
            
            try:
                columns = [col['name'] for col in inspector.get_columns(table_name)]
                logger.info(f"🔍 Colunas existentes na tabela {table_name}: {len(columns)}")
                
                # Campo para adicionar
                field_name = 'updated_at'
                field_type = 'TIMESTAMP'
                
                dialect_name = db.engine.dialect.name
                logger.info(f"🔍 Dialeto do banco: {dialect_name}")
                
                if field_name in columns:
                    logger.info(f"✅ Campo {field_name} já existe - pulando")
                    return True
                else:
                    logger.info(f"🔄 Adicionando coluna {field_name}...")
                    try:
                        # PostgreSQL: adicionar coluna com DEFAULT
                        if dialect_name == 'postgresql':
                            # Adicionar coluna
                            db.session.execute(text(f"""
                                ALTER TABLE {table_name} 
                                ADD COLUMN {field_name} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            """))
                            logger.info(f"✅ Coluna {field_name} adicionada")
                            
                            # ✅ Criar função para atualizar updated_at (CREATE OR REPLACE é idempotente)
                            try:
                                db.session.execute(text("""
                                    CREATE OR REPLACE FUNCTION update_updated_at_column()
                                    RETURNS TRIGGER AS $$
                                    BEGIN
                                        NEW.updated_at = CURRENT_TIMESTAMP;
                                        RETURN NEW;
                                    END;
                                    $$ language 'plpgsql';
                                """))
                                logger.info(f"✅ Função update_updated_at_column criada/atualizada")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao criar função (não crítico): {e}")
                            
                            # ✅ Criar trigger para atualizar updated_at (DROP IF EXISTS é idempotente)
                            try:
                                db.session.execute(text(f"""
                                    DROP TRIGGER IF EXISTS update_payments_updated_at ON {table_name};
                                    CREATE TRIGGER update_payments_updated_at
                                    BEFORE UPDATE ON {table_name}
                                    FOR EACH ROW
                                    EXECUTE FUNCTION update_updated_at_column();
                                """))
                                logger.info(f"✅ Trigger update_payments_updated_at criado")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao criar trigger (não crítico): {e}")
                            
                            # ✅ COMMIT único após todas as operações
                            db.session.commit()
                        elif dialect_name == 'sqlite':
                            # SQLite não suporta ON UPDATE, usar DEFAULT
                            db.session.execute(text(f"""
                                ALTER TABLE {table_name} 
                                ADD COLUMN {field_name} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            """))
                            db.session.commit()
                        else:
                            # MySQL: suporta ON UPDATE
                            db.session.execute(text(f"""
                                ALTER TABLE {table_name} 
                                ADD COLUMN {field_name} TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
                                ON UPDATE CURRENT_TIMESTAMP
                            """))
                            db.session.commit()
                        
                        logger.info(f"✅ Campo {field_name} adicionado com sucesso")
                        
                        # ✅ VALIDAÇÃO: Verificar se campo foi adicionado
                        columns_after = [col['name'] for col in inspector.get_columns(table_name)]
                        if field_name in columns_after:
                            logger.info(f"✅ Validação: Campo {field_name} está presente")
                            return True
                        else:
                            logger.error(f"❌ Validação: Campo {field_name} não encontrado")
                            return False
                            
                    except Exception as e:
                        db.session.rollback()
                        error_str = str(e).lower()
                        if 'already exists' in error_str or 'duplicate' in error_str or 'column' in error_str and 'already' in error_str:
                            logger.info(f"⚠️ Campo {field_name} já existe (ignorando erro)")
                            return True
                        else:
                            logger.error(f"❌ Erro ao adicionar {field_name}: {e}")
                            raise
                
            except Exception as e:
                logger.error(f"❌ Erro ao verificar/adicionar coluna: {e}", exc_info=True)
                db.session.rollback()
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro crítico na migration: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔄 MIGRATION: Adicionar updated_at ao Payment")
    logger.info("=" * 80)
    
    success = add_updated_at_to_payment()
    
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

