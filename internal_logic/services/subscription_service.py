"""
Subscription Service
====================
Gerenciamento de assinaturas: ativacao, entrada em grupo VIP.
Extraido do BotManager (Fase 7).
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def activate_subscription(subscription_id: int) -> bool:
    from flask import current_app
    from internal_logic.core.extensions import db
    from internal_logic.core.models import Subscription
    from dateutil.relativedelta import relativedelta
    from sqlalchemy import select

    try:
        with current_app.app_context():
            subscription = db.session.execute(
                select(Subscription)
                .where(Subscription.id == subscription_id)
                .where(Subscription.status == 'pending')
                .with_for_update()
            ).scalar_one_or_none()

            if not subscription:
                logger.debug(f"Subscription {subscription_id} nao encontrada ou ja ativada")
                return False

            if subscription.status != 'pending':
                logger.warning(
                    f"Subscription {subscription_id} nao esta em status 'pending' "
                    f"(status atual: {subscription.status}) - abortando ativacao"
                )
                return False

            if subscription.started_at is not None:
                logger.warning(
                    f"Subscription {subscription_id} ja possui started_at definido "
                    f"({subscription.started_at}) - subscription ja foi ativada anteriormente"
                )
                return False

            now_utc = datetime.now(timezone.utc)

            duration_type = subscription.duration_type
            duration_value = subscription.duration_value

            if duration_type == 'hours':
                expires_at = now_utc + relativedelta(hours=duration_value)
            elif duration_type == 'days':
                expires_at = now_utc + relativedelta(days=duration_value)
            elif duration_type == 'weeks':
                expires_at = now_utc + relativedelta(weeks=duration_value)
            elif duration_type == 'months':
                expires_at = now_utc + relativedelta(months=duration_value)
            else:
                logger.error(f"Duration type invalido: {duration_type}")
                subscription.status = 'error'
                subscription.last_error = f"Duration type invalido: {duration_type}"
                db.session.commit()
                return False

            subscription.status = 'active'
            subscription.started_at = now_utc
            subscription.expires_at = expires_at

            db.session.commit()

            logger.info(f"Subscription {subscription_id} ativada | Expira em: {expires_at} UTC ({duration_value} {duration_type})")
            return True

    except Exception as e:
        logger.error(f"Erro ao ativar subscription {subscription_id}: {e}", exc_info=True)
        db.session.rollback()
        return False


def handle_new_chat_member(bot_id: int, chat_id: int, telegram_user_id: str, activate_func=None):
    from flask import current_app
    from internal_logic.core.extensions import db
    from internal_logic.core.models import Subscription
    from utils.subscriptions import normalize_vip_chat_id

    try:
        with current_app.app_context():
            pending_subscriptions = Subscription.query.filter(
                Subscription.bot_id == bot_id,
                Subscription.telegram_user_id == telegram_user_id,
                Subscription.vip_chat_id == normalize_vip_chat_id(str(chat_id)),
                Subscription.status == 'pending'
            ).all()

            if not pending_subscriptions:
                logger.debug(f"Nenhuma subscription pendente para user {telegram_user_id} no grupo {chat_id}")
                return

            logger.info(f"Usuario {telegram_user_id} entrou no grupo VIP {chat_id} | {len(pending_subscriptions)} subscription(s) pendente(s)")

            act = activate_func or activate_subscription
            for subscription in pending_subscriptions:
                try:
                    success = act(subscription.id)
                    if success:
                        logger.info(f"Subscription {subscription.id} ativada quando usuario entrou no grupo")
                    else:
                        logger.warning(f"Falha ao ativar subscription {subscription.id}")
                except Exception as e:
                    logger.error(f"Erro ao ativar subscription {subscription.id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Erro ao processar new_chat_member: {e}", exc_info=True)
