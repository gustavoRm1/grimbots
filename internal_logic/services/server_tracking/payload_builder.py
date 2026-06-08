"""
Purchase Payload Builder — Meta CAPI
====================================
Constrói o payload completo do evento Purchase conforme spec Meta:
- event_name, event_time, event_id, action_source, event_source_url
- user_data com PII normalizada/hasheada
- custom_data com value, currency, content_name, order_id
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .user_data import build_user_data

logger = logging.getLogger(__name__)


def build_purchase_payload(
    payment,
    bot_user,
    pool,
    tracking_data: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    """Constrói payload Purchase completo para Meta CAPI.

    Args:
        payment: Instância Payment (status='paid')
        bot_user: Instância BotUser (pode ser None)
        pool: Instância RedirectPool (com meta_pixel_id, meta_access_token)
        tracking_data: Dict opcional do Redis (fbp, fbc, ip, ua)

    Returns:
        Dict com payload CAPI ou None se faltarem dados obrigatórios.
    """
    if not payment:
        logger.warning("[PAYLOAD] payment é None")
        return None

    # ── EVENT TIME (UTC explícito) ──────────────────────────
    if payment.paid_at:
        if isinstance(payment.paid_at, datetime):
            paid_at = payment.paid_at
            if paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=timezone.utc)
            event_time = int(paid_at.timestamp())
        else:
            event_time = int(payment.paid_at)
    else:
        event_time = int(datetime.utcnow().timestamp())

    # ── EVENT SOURCE URL (required for website events) ──────
    event_source_url = getattr(payment, 'click_context_url', None)
    if not event_source_url and tracking_data:
        event_source_url = tracking_data.get('event_source_url')
    if not event_source_url:
        pool_slug = getattr(pool, 'slug', None)
        if pool_slug:
            event_source_url = f'https://app.grimbots.online/go/{pool_slug}'
        else:
            event_source_url = f'https://app.grimbots.online'

    # ── USER DATA ───────────────────────────────────────────
    user_data = build_user_data(payment, bot_user, tracking_data)

    # ── CUSTOM DATA ─────────────────────────────────────────
    custom_data: Dict[str, Any] = {
        'value': float(payment.amount or 0),
        'currency': 'BRL',
    }
    product_name = getattr(payment, 'product_name', None)
    if product_name:
        custom_data['content_name'] = product_name
    custom_data['content_type'] = 'product'
    custom_data['order_id'] = str(payment.id)

    # ── PAYLOAD ─────────────────────────────────────────────
    payload: Dict[str, Any] = {
        'event_name': 'Purchase',
        'event_time': event_time,
        'event_id': f"purchase_{payment.id}",
        'action_source': 'website',
        'user_data': user_data,
        'custom_data': custom_data,
    }
    if event_source_url:
        payload['event_source_url'] = event_source_url

    return payload
