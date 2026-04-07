"""
Webhooks Telegram Blueprint - VERSÃO HÍBRIDA (Fallback Legado)
===============================================================
Recebe webhooks de atualizações do Telegram para bots.
Implementação com Fallback para bots grandes (10k+ usuários).
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from internal_logic.core.extensions import limiter, db, csrf
from internal_logic.core.models import Bot, BotConfig

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram_webhooks', __name__)


@csrf.exempt
@telegram_bp.route('/webhook/telegram/<int:bot_id>', methods=['POST'])
@limiter.limit("1000 per minute")
def telegram_webhook(bot_id):
    """
    Webhook para receber atualizações do Telegram.
    VERSÃO HÍBRIDA: Tenta Redis primeiro, Fallback direto se falhar.
    """
    try:
        update = request.get_json()
        if not update:
            return jsonify({'error': 'No data'}), 400
        
        logger.info(f"📨 Webhook Telegram: Bot {bot_id} | Update ID: {update.get('update_id')}")
        
        # 1. Buscar bot no banco (query pura)
        bot = Bot.query.get(bot_id)
        if not bot:
            logger.warning(f"⚠️ Webhook para bot inexistente: {bot_id}")
            return jsonify({'status': 'ok'}), 200
        
        # 2. TENTATIVA 1: Processar via BotManager (com Redis/state)
        try:
            from bot_manager import BotManager
            bot_manager = BotManager(socketio=None, scheduler=None, user_id=bot.user_id)
            
            # Processar com state (pode falhar se Redis não tiver o bot)
            result = bot_manager._process_telegram_update(bot_id, bot.user_id, update)
            
            # Se chegou aqui, processou com sucesso via Redis path
            logger.info(f"✅ Bot {bot_id} processado via Redis/State")
            return jsonify({'status': 'ok'}), 200
            
        except Exception as redis_error:
            # Redis path falhou - vamos para Fallback Legado
            logger.warning(f"⚠️ Redis path falhou para bot {bot_id}: {redis_error}")
            logger.info(f"🔄 Acionando FALLBACK LEGADO para bot {bot_id}")
        
        # 3. TENTATIVA 2: FALLBACK LEGADO (Processamento Direto)
        try:
            # Fallback: Buscar config direto do banco
            bot_config = bot.config or BotConfig.query.filter_by(bot_id=bot_id).first()
            config_dict = bot_config.to_dict() if bot_config else {}
            
            # Processar via método fallback
            from bot_manager import BotManager
            bot_manager = BotManager(socketio=None, scheduler=None, user_id=bot.user_id)
            
            # Forçar processamento direto sem verificar Redis
            bot_manager._process_telegram_update_direct(
                bot_id=bot_id,
                token=bot.token,
                config=config_dict,
                update=update
            )
            
            logger.info(f"✅ Bot {bot_id} processado via FALLBACK LEGADO")
            return jsonify({'status': 'ok'}), 200
            
        except Exception as direct_error:
            logger.error(f"❌ Fallback legado também falhou para bot {bot_id}: {direct_error}")
            return jsonify({'status': 'ok'}), 200  # Retornar 200 para não retry
            
    except Exception as e:
        logger.error(f"❌ Erro crítico no webhook Telegram: {e}")
        return jsonify({'status': 'ok'}), 200  # Sempre retornar 200 para Telegram


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
