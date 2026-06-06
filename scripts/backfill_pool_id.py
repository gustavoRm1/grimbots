#!/usr/bin/env python3
"""
Backfill: Preenche payment.pool_id para registros existentes

Estratégias (em ordem de prioridade):
  1. payment.tracking_token → Redis → pool_id
  2. BotUser.tracking_session_id → Redis → pool_id
  3. payment.meta_pixel_id → match em Pool que tem este bot
  4. PoolBot.query.filter_by(bot_id=payment.bot_id).first() (fallback)

Uso:
    python scripts/backfill_pool_id.py

Idempotente — pula payments que já têm pool_id.
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
from internal_logic.core.models import Payment, PoolBot, BotUser
from sqlalchemy import text


def _try_from_tracking_token(payment) -> int | None:
    """Estratégia 1: tracking_token → Redis → pool_id"""
    if not payment.tracking_token:
        return None
    try:
        from internal_logic.services.tracking_service_v4 import TrackingServiceV4
        ts = TrackingServiceV4()
        data = ts.recover_tracking_data(payment.tracking_token)
        if data:
            pool_id = data.get("pool_id")
            if pool_id:
                logger.info(f"  Pool {pool_id} via tracking_token (Redis)")
                return int(pool_id)
    except Exception as e:
        logger.warning(f"  Erro recover tracking_token: {e}")
    return None


def _try_from_botuser_session(payment) -> int | None:
    """Estratégia 2: BotUser.tracking_session_id → Redis → pool_id"""
    if not payment.customer_user_id:
        return None
    try:
        bot_user = BotUser.query.filter_by(
            bot_id=payment.bot_id,
            telegram_user_id=str(payment.customer_user_id)
        ).first()
        if bot_user and bot_user.tracking_session_id:
            from internal_logic.services.tracking_service_v4 import TrackingServiceV4
            ts = TrackingServiceV4()
            data = ts.recover_tracking_data(bot_user.tracking_session_id)
            if data:
                pool_id = data.get("pool_id")
                if pool_id:
                    logger.info(f"  Pool {pool_id} via BotUser.tracking_session_id (Redis)")
                    return int(pool_id)
    except Exception as e:
        logger.warning(f"  Erro recover BotUser session: {e}")
    return None


def _try_from_meta_pixel_id(payment) -> int | None:
    """Estratégia 3: meta_pixel_id → match Pool que tem este bot"""
    if not payment.meta_pixel_id:
        return None
    try:
        pool_bots = PoolBot.query.filter_by(bot_id=payment.bot_id).all()
        for pb in pool_bots:
            if pb.pool and pb.pool.meta_pixel_id == payment.meta_pixel_id:
                logger.info(f"  Pool {pb.pool_id} via meta_pixel_id match (payment.meta_pixel_id={payment.meta_pixel_id})")
                return pb.pool_id
    except Exception as e:
        logger.warning(f"  Erro meta_pixel_id match: {e}")
    return None


def _try_fallback(payment) -> int | None:
    """Estratégia 4: primeiro pool do bot"""
    try:
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        if pool_bot:
            logger.info(f"  Pool {pool_bot.pool_id} via fallback (primeiro pool do bot)")
            return pool_bot.pool_id
    except Exception as e:
        logger.warning(f"  Erro fallback: {e}")
    return None


def run_backfill():
    app = create_app()
    with app.app_context():
        engine = db.engine
        logger.info(f"Banco: {engine.dialect.name} | URL: {engine.url}")

        total = Payment.query.filter(Payment.pool_id.is_(None)).count()
        logger.info(f"Payments sem pool_id: {total}")

        if total == 0:
            logger.info("Nada a fazer.")
            return

        ok = 0
        fail = 0
        batch_size = 500
        offset = 0

        while offset < total:
            batch = Payment.query.filter(Payment.pool_id.is_(None)) \
                .order_by(Payment.id.desc()) \
                .offset(offset).limit(batch_size).all()
            if not batch:
                break

            for payment in batch:
                pool_id = _try_from_tracking_token(payment)
                if pool_id is None:
                    pool_id = _try_from_botuser_session(payment)
                if pool_id is None:
                    pool_id = _try_from_meta_pixel_id(payment)
                if pool_id is None:
                    pool_id = _try_fallback(payment)

                if pool_id is not None:
                    payment.pool_id = pool_id
                    ok += 1
                else:
                    fail += 1

            db.session.commit()
            logger.info(f"  Lote salvo (offset={offset}, ok={ok}, fail={fail})")
            offset += len(batch)

        logger.info("=" * 50)
        logger.info(f"Backfill concluído!")
        logger.info(f"  Atualizados: {ok}")
        logger.info(f"  Sem pool: {fail}")
        logger.info("=" * 50)


if __name__ == '__main__':
    run_backfill()
