"""
Personalização de texto do funil ({nome}, {@usuario}, {id}).
Fonte única usada por bot_manager._personalize_text E start_command_handler,
garantindo substituição em TODOS os caminhos de envio (incluindo /start).
"""
import logging, re
logger = logging.getLogger(__name__)

_PATTERN = re.compile(r"\{\s*(nome|name|sobrenome|usuario|username|id)\s*\}", re.IGNORECASE)

def personalize(text, bot_id, telegram_user_id):
    """Substitui placeholders; desconhecidas ficam intactas."""
    if not text or "{" not in text:
        return text
    try:
        from internal_logic.core.models import BotUser
        bu = None
        from flask import current_app, has_app_context
        if has_app_context():
            bu = BotUser.query.filter_by(
                bot_id=bot_id, telegram_user_id=str(telegram_user_id)
            ).first()
        first = (bu.first_name if bu and bu.first_name else "") or "Cliente"
        uname = ((bu.username if bu and bu.username else "") or "").lstrip("@")

        def _sub(m):
            k = m.group(1).lower()
            if k in ("nome", "name"):
                return first
            if k == "sobrenome":
                return ""
            if k in ("usuario", "username"):
                return "@" + uname if uname else first
            if k == "id":
                return str(telegram_user_id)
            return m.group(0)

        out = _PATTERN.sub(_sub, text)
        return out.replace("  ", " ").replace(" ,", ",")
    except Exception as e:
        logger.warning(f"Personalização falhou (texto original mantido): {e}")
        return text
