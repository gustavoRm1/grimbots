#!/usr/bin/env python3
"""
Backfill: Copia device data + customer_name do BotUser para o Payment.

Uso:
    python scripts/backfill_device_payments.py

Idempotente — só preenche linhas com campos NULL.
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
from sqlalchemy import text


def run_backfill():
    app = create_app()
    with app.app_context():
        engine = db.engine
        dialect = engine.dialect.name
        logger.info(f"Banco detectado: {dialect}")

        # 1. Backfill device fields + customer_name from BotUser
        #    Match BotUser via: payment.bot_id = bot_users.bot_id AND
        #    CAST(payment.customer_user_id AS BIGINT) = bot_users.telegram_user_id
        cast_expr = "CAST(p.customer_user_id AS BIGINT)" if dialect != 'sqlite' else "CAST(p.customer_user_id AS INTEGER)"
        
        sql = f"""
        UPDATE payments p
        JOIN bot_users b ON p.bot_id = b.bot_id AND {cast_expr} = b.telegram_user_id
        SET 
            p.device_type = COALESCE(p.device_type, b.device_type),
            p.os_type = COALESCE(p.os_type, b.os_type),
            p.browser = COALESCE(p.browser, b.browser),
            p.device_model = COALESCE(p.device_model, b.device_model),
            p.customer_name = COALESCE(p.customer_name, b.first_name)
        WHERE p.device_type IS NULL
           OR p.os_type IS NULL
           OR p.browser IS NULL
           OR p.device_model IS NULL
           OR p.customer_name IS NULL
        """

        # SQLite doesn't support JOIN in UPDATE with the same syntax
        if dialect == 'sqlite':
            # Use correlated subquery approach
            sql = """
            UPDATE payments 
            SET 
                device_type = COALESCE(device_type, (
                    SELECT device_type FROM bot_users 
                    WHERE bot_users.bot_id = payments.bot_id 
                      AND CAST(payments.customer_user_id AS INTEGER) = bot_users.telegram_user_id
                    LIMIT 1
                )),
                os_type = COALESCE(os_type, (
                    SELECT os_type FROM bot_users 
                    WHERE bot_users.bot_id = payments.bot_id 
                      AND CAST(payments.customer_user_id AS INTEGER) = bot_users.telegram_user_id
                    LIMIT 1
                )),
                browser = COALESCE(browser, (
                    SELECT browser FROM bot_users 
                    WHERE bot_users.bot_id = payments.bot_id 
                      AND CAST(payments.customer_user_id AS INTEGER) = bot_users.telegram_user_id
                    LIMIT 1
                )),
                device_model = COALESCE(device_model, (
                    SELECT device_model FROM bot_users 
                    WHERE bot_users.bot_id = payments.bot_id 
                      AND CAST(payments.customer_user_id AS INTEGER) = bot_users.telegram_user_id
                    LIMIT 1
                )),
                customer_name = COALESCE(customer_name, (
                    SELECT first_name FROM bot_users 
                    WHERE bot_users.bot_id = payments.bot_id 
                      AND CAST(payments.customer_user_id AS INTEGER) = bot_users.telegram_user_id
                    LIMIT 1
                ))
            WHERE device_type IS NULL
               OR os_type IS NULL
               OR browser IS NULL
               OR device_model IS NULL
               OR customer_name IS NULL
            """
        elif dialect == 'postgresql':
            sql = f"""
            UPDATE payments p
            SET 
                device_type = COALESCE(p.device_type, b.device_type),
                os_type = COALESCE(p.os_type, b.os_type),
                browser = COALESCE(p.browser, b.browser),
                device_model = COALESCE(p.device_model, b.device_model),
                customer_name = COALESCE(p.customer_name, b.first_name)
            FROM bot_users b
            WHERE p.bot_id = b.bot_id 
              AND {cast_expr} = b.telegram_user_id
              AND (p.device_type IS NULL
                OR p.os_type IS NULL
                OR p.browser IS NULL
                OR p.device_model IS NULL
                OR p.customer_name IS NULL)
            """

        logger.info("Executando backfill de device data + customer_name...")

        with engine.connect() as conn:
            result = conn.execute(text(sql))
            conn.commit()
            logger.info(f"Linhas afetadas: {result.rowcount}")

        logger.info("Backfill concluído!")

        # 2. Verify
        with engine.connect() as conn:
            remaining = conn.execute(
                text("SELECT COUNT(*) FROM payments WHERE device_type IS NULL AND customer_user_id IS NOT NULL")
            ).scalar()
            logger.info(f"Payments restantes ainda sem device_type: {remaining}")


if __name__ == '__main__':
    run_backfill()
