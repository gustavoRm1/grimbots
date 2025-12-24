"""\
Migration: Adicionar payment_method ao Payment

Execute: python migrations/add_payment_method_to_payments.py
"""

import sys
from pathlib import Path
import logging

from sqlalchemy import text, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar raiz do projeto ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def add_payment_method_to_payments() -> bool:
    """Adiciona coluna payment_method na tabela payments (idempotente)."""
    from app import app, db

    with app.app_context():
        try:
            inspector = inspect(db.engine)
            table_name = 'payments'

            columns = [col['name'] for col in inspector.get_columns(table_name)]
            if 'payment_method' in columns:
                logger.info("✅ Coluna payment_method já existe - pulando")
                return True

            dialect_name = db.engine.dialect.name
            logger.info(f"🔍 Dialeto do banco: {dialect_name}")

            logger.info("🔄 Adicionando coluna payment_method...")

            if dialect_name == 'postgresql':
                db.session.execute(text(f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN payment_method VARCHAR(20)
                """))
                try:
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_payments_payment_method
                        ON payments(payment_method)
                    """))
                except Exception as e:
                    logger.warning(f"⚠️ Não foi possível criar índice (não crítico): {e}")
                db.session.commit()

            elif dialect_name == 'sqlite':
                db.session.execute(text(f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN payment_method VARCHAR(20)
                """))
                db.session.commit()

            else:
                db.session.execute(text(f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN payment_method VARCHAR(20)
                """))
                try:
                    db.session.execute(text("""
                        CREATE INDEX idx_payments_payment_method
                        ON payments(payment_method)
                    """))
                except Exception as e:
                    logger.warning(f"⚠️ Não foi possível criar índice (não crítico): {e}")
                db.session.commit()

            logger.info("✅ Coluna payment_method adicionada com sucesso")
            return True

        except Exception as e:
            logger.error(f"❌ Erro na migration payment_method: {e}", exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass
            return False


if __name__ == '__main__':
    ok = add_payment_method_to_payments()
    raise SystemExit(0 if ok else 1)
