"""
Webhooks Telegram Blueprint
============================
Recebe webhooks de atualizações do Telegram para bots.
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from internal_logic.core.extensions import limiter, db
from models import Bot

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram_webhooks', __name__)


@telegram_bp.route('/webhook/telegram/<int:bot_id>', methods=['POST'])
@limiter.limit("1000 per minute")
def telegram_webhook(bot_id):
    """
    Webhook para receber atualizações do Telegram.
    Processa mensagens e comandos do bot.
    """
    try:
        update = request.get_json()
        if not update:
            return jsonify({'error': 'No data'}), 400
        
        logger.info(f"📨 Webhook Telegram: Bot {bot_id} | Update ID: {update.get('update_id')}")
        
        # Buscar bot
        bot = Bot.query.get(bot_id)
        if not bot:
            logger.warning(f"⚠️ Bot {bot_id} não encontrado")
            return jsonify({'error': 'Bot not found'}), 404
        
        # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do bot
        from bot_manager import BotManager
        bot_manager = BotManager(socketio=None, scheduler=None, user_id=bot.user_id)
        
        # Processar update
        try:
            bot_manager._process_telegram_update(bot_id, bot.user_id, update)
            return jsonify({'status': 'ok'}), 200
        except Exception as e:
            logger.error(f"❌ Erro ao processar update: {e}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        logger.error(f"❌ Erro no webhook Telegram: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/bots/<int:bot_id>/webhook-info', methods=['GET'])
def get_bot_webhook_info(bot_id):
    """Retorna getWebhookInfo do Telegram para diagnóstico."""
    try:
        bot = Bot.query.get(bot_id)
        if not bot:
            return jsonify({'error': 'Bot not found'}), 404
        
        from bot_manager import BotManager
        bot_manager = BotManager(socketio=None, scheduler=None, user_id=bot.user_id)
        
        info = bot_manager.get_webhook_info(bot.token)
        expected_url = f"https://app.grimbots.online/webhook/telegram/{bot_id}"
        
        return jsonify({
            'webhook_info': info,
            'expected_url': expected_url,
            'match': info.get('url') == expected_url
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter webhook info: {e}")
        return jsonify({'error': str(e)}), 500
