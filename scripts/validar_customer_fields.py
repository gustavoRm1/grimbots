"""
Script de Validação: Verificar se customer_email, customer_phone, customer_document foram adicionados

Execute: python scripts/validar_customer_fields.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app, db
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validar_customer_fields():
    """Valida se os campos customer_email, customer_phone, customer_document existem"""
    with app.app_context():
        try:
            logger.info("=" * 80)
            logger.info("🔍 VALIDAÇÃO: Verificando campos customer_email, customer_phone, customer_document")
            logger.info("=" * 80)
            
            # Método 1: Via SQLAlchemy Inspector
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('payments')]
            
            fields_esperados = ['customer_email', 'customer_phone', 'customer_document']
            fields_encontrados = [f for f in fields_esperados if f in columns]
            fields_faltando = [f for f in fields_esperados if f not in columns]
            
            logger.info(f"📊 Método 1 (Inspector):")
            logger.info(f"   Total de colunas na tabela: {len(columns)}")
            logger.info(f"   Campos encontrados: {fields_encontrados}")
            logger.info(f"   Campos faltando: {fields_faltando}")
            
            # Método 2: Via SQL direto (mais confiável)
            logger.info(f"\n📊 Método 2 (SQL direto):")
            try:
                result = db.session.execute(text("""
                    SELECT column_name, data_type, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = 'payments'
                    AND column_name IN ('customer_email', 'customer_phone', 'customer_document')
                    ORDER BY column_name
                """))
                
                sql_results = list(result)
                logger.info(f"   Colunas encontradas via SQL: {len(sql_results)}")
                
                for row in sql_results:
                    col_name, data_type, max_length = row
                    logger.info(f"   ✅ {col_name}: {data_type}({max_length})")
                
                sql_columns = [row[0] for row in sql_results]
                sql_faltando = [f for f in fields_esperados if f not in sql_columns]
                
                if sql_faltando:
                    logger.error(f"   ❌ Campos faltando via SQL: {sql_faltando}")
                else:
                    logger.info(f"   ✅ Todos os campos estão presentes via SQL")
                
            except Exception as e:
                logger.error(f"   ❌ Erro ao verificar via SQL: {e}", exc_info=True)
                sql_columns = []
                sql_faltando = fields_esperados
            
            # Resultado final
            logger.info("\n" + "=" * 80)
            if len(sql_columns) == 3 or len(fields_encontrados) == 3:
                logger.info("✅ VALIDAÇÃO: Todos os campos estão presentes!")
                logger.info("=" * 80)
                return True
            else:
                logger.error("❌ VALIDAÇÃO: Alguns campos estão faltando!")
                logger.error(f"   Inspector: {len(fields_encontrados)}/3")
                logger.error(f"   SQL: {len(sql_columns)}/3")
                logger.info("=" * 80)
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro crítico na validação: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    success = validar_customer_fields()
    sys.exit(0 if success else 1)

