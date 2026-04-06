"""
SaaS Bot Manager - Wrapper Factory
✅ REFATORADO: Sprint 1 Final - Application Factory Pattern
"""

from dotenv import load_dotenv
load_dotenv()

from internal_logic.core.extensions import create_app, db, socketio, login_manager, csrf, limiter
app = create_app()

# Re-exports para compatibilidade legada
from internal_logic.core.models import (
    User, Bot, BotConfig, Gateway, Payment, AuditLog,
    Achievement, UserAchievement, BotUser, BotMessage,
    RedirectPool, PoolBot, RemarketingCampaign, RemarketingBlacklist,
    Commission, PushSubscription, NotificationSettings,
    get_brazil_time, Subscription
)
from internal_logic.services.payment_processor import (
    send_payment_delivery, process_payment_confirmation,
    reconcile_paradise_payments, reconcile_pushynpay_payments,
    reconcile_atomopay_payments, reconcile_aguia_payments,
    reconcile_bolt_payments, check_expired_subscriptions,
    reset_high_error_count_subscriptions, update_ranking_premium_rates,
    health_check_all_pools, check_scheduled_remarketing_campaigns,
)
from internal_logic.core.utils import strip_surrogate_chars, sanitize_payload
from bot_manager import BotManager
from utils.meta_pixel import normalize_external_id

bot_manager = app.config.get('BOT_MANAGER') or BotManager()
