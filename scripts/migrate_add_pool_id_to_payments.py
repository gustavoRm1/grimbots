#!/usr/bin/env python3
"""
Migration: Adiciona coluna pool_id na tabela payments

Uso:
    python scripts/migrate_add_pool_id_to_payments.py

Seguro para rodar múltiplas vezes (idempotente).
Suporta: MySQL, SQLite, PostgreSQL
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from internal_logic.core.extensions import create_app, db
from sqlalchemy import inspect, text


def column_exists(table_name, column_name):
    """Verifica se coluna já existe na tabela (funciona em MySQL, SQLite, PostgreSQL)"""
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def run_migration():
    app = create_app()
    with app.app_context():
        engine = db.engine
        dialect = engine.dialect.name
        logger.info(f"Banco detectado: {dialect} | URL: {engine.url}")

        table = 'payments'
        column = 'pool_id'

        if column_exists(table, column):
            logger.info(f"Coluna '{column}' já existe em '{table}' — nada a fazer.")
            return

        logger.info(f"Criando coluna '{column}' em '{table}'...")

        if dialect == 'mysql':
            stmt = text(f"ALTER TABLE {table} ADD COLUMN {column} INT NULL, ADD INDEX idx_payment_pool_id ({column})")
        elif dialect == 'sqlite':
            stmt = text(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER NULL")
        elif dialect == 'postgresql':
            stmt = text(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER NULL")
        else:
            logger.error(f"Dialeto não suportado: {dialect}")
            sys.exit(1)

        with engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()

        logger.info(f"Coluna '{column}' criada com sucesso em '{table}'!")

        if column_exists(table, column):
            logger.info(f"Verificação: coluna '{column}' confirmada em '{table}'.")
        else:
            logger.error(f"Verificação: coluna '{column}' NÃO encontrada após migration!")
            sys.exit(1)


if __name__ == '__main__':
    run_migration()
