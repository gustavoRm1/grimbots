"""
Purchase Reconciler — RQ Job Core Logic
========================================
Poll payments com status='paid' e meta_purchase_sent=False,
verifica se o pool está em SERVER MODE, e envia Purchase via Meta CAPI.

SÓ processa pools em SERVER MODE (access_token presente).
Pools HTML-ONLY são ignorados — o browser Pixel no delivery.html assume.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from internal_logic.core.redis_manager import get_redis_connection
from . import is_server_mode
from .payload_builder import build_purchase_payload
from .capi_client import send_event

logger = logging.getLogger(__name__)


def _recover_tracking_data(tracking_token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Recupera dados de tracking do Redis.

    Key: tracking:{tracking_token}
    """
    if not tracking_token:
        return None
    try:
        redis_conn = get_redis_connection(decode_responses=True)
        key = f"tracking:{tracking_token}"
        raw = redis_conn.get(key)
        if raw:
            import json
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"[RECONCILER] Erro ao ler tracking_data do Redis: {e}")
    return None


def reconcile_purchases() -> int:
    """Poll payments paid sem Purchase enviado e envia via CAPI.

    Returns:
        Número de payments processados (enviados ou ignorados).
    """
    from internal_logic.core.extensions import db
    from internal_logic.core.models import Payment, BotUser, RedirectPool
    from utils.encryption import decrypt

    processed = 0

    try:
        # Busca payments paid recentes sem Purchase enviado
        payments = Payment.query.filter(
            Payment.status == 'paid',
            Payment.meta_purchase_sent == False,
            Payment.pool_id.isnot(None),
            Payment.paid_at > (datetime.utcnow() - timedelta(days=7)),
        ).all()

        if not payments:
            return 0

        logger.info(f"[RECONCILER] {len(payments)} payments pendentes de Purchase")

        for payment in payments:
            try:
                # ─── GUARD 1: ONLY SERVER MODE ────────────────
                pool = RedirectPool.query.get(payment.pool_id)
                if not is_server_mode(pool):
                    continue
                if not pool.meta_events_purchase:
                    continue

                # ─── Dados do bot_user ─────────────────────────
                bot_user = None
                if payment.bot_id and payment.customer_user_id:
                    bot_user = BotUser.query.filter_by(
                        bot_id=payment.bot_id,
                        telegram_user_id=payment.customer_user_id,
                    ).first()

                # ─── Tracking data do Redis ────────────────────
                tracking_token = (
                    getattr(payment, 'tracking_token', None)
                    or (getattr(bot_user, 'tracking_session_id', None) if bot_user else None)
                )
                tracking_data = _recover_tracking_data(tracking_token)

                # ─── Monta payload Purchase ────────────────────
                payload = build_purchase_payload(payment, bot_user, pool, tracking_data)
                if not payload:
                    logger.warning(
                        f"[RECONCILER] Payload vazio para payment {payment.id}"
                    )
                    continue

                # ─── Decrypt access_token ──────────────────────
                access_token = decrypt(pool.meta_access_token)
                if not access_token:
                    logger.error(
                        f"[RECONCILER] access_token inválido para pool {pool.id}"
                    )
                    continue

                test_code = pool.meta_test_event_code or None

                # ─── Envia via CAPI ────────────────────────────
                success = send_event(
                    pixel_id=pool.meta_pixel_id,
                    access_token=access_token,
                    event=payload,
                    test_event_code=test_code,
                )

                # ─── Marca como enviado ───────────────────────
                if success:
                    payment.meta_purchase_sent = True
                    payment.meta_event_id = f"purchase_{payment.id}"
                    payment.meta_purchase_sent_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(
                        f"[RECONCILER] ✅ Purchase enviado | payment={payment.id} "
                        f"| event_id={payment.meta_event_id}"
                    )
                else:
                    logger.warning(
                        f"[RECONCILER] ❌ Falha ao enviar Purchase | payment={payment.id}"
                    )
                    db.session.rollback()

                processed += 1

            except Exception as e:
                db.session.rollback()
                logger.error(
                    f"[RECONCILER] Erro processing payment {payment.id}: {e}",
                    exc_info=True,
                )

    except Exception as e:
        logger.error(f"[RECONCILER] Erro na query de payments: {e}", exc_info=True)

    return processed
