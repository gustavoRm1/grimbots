"""
Webhooks Telegram Blueprint - VERSÃO INVERSA (Via Expressa Primeiro)
===============================================================
Recebe webhooks de atualizações do Telegram para bots.
Implementação: Tenta Via Expressa (direta) primeiro, Redis apenas se necessário.
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
    VERSÃO INVERSA: Via Expressa (direta) primeiro, Redis como fallback opcional.
    """
    # 🔥 CRÍTICO: Limpar qualquer transação pendente de requisições anteriores
    try:
        db.session.rollback()
    except Exception:
        pass
    
    try:
        update = request.get_json()
        if not update:
            return jsonify({'error': 'No data'}), 400
        
        logger.info(f"📨 Webhook Telegram: Bot {bot_id} | Update ID: {update.get('update_id')}")
        
        # 1. Buscar bot no banco
        try:
            bot = Bot.query.get(bot_id)
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"❌ Erro DB ao buscar bot {bot_id}: {db_error}")
            return jsonify({'status': 'ok'}), 200
        
        if not bot:
            logger.warning(f"⚠️ Webhook para bot inexistente: {bot_id}")
            return jsonify({'status': 'ok'}), 200
        
        # ============================================================================
        # 🔥 TENTATIVA 1: VIA EXPRESSA (Processamento Direto Legado) - PRIMEIRO!
        # ============================================================================
        # Esta é a via à prova de balas - processa direto sem Redis, sem burocracia
        try:
            # Buscar config direto do banco
            try:
                bot_config = bot.config or BotConfig.query.filter_by(bot_id=bot_id).first()
                config_dict = bot_config.to_dict() if bot_config else {}
            except Exception as config_error:
                db.session.rollback()
                logger.warning(f"⚠️ Erro ao buscar config (não crítico): {config_error}")
                config_dict = {}  # Continua sem config
            
            # Processar via método direto (Via Expressa)
            from bot_manager import BotManager
            bot_manager = BotManager(socketio=None, scheduler=None)
            
            bot_manager._process_telegram_update_direct(
                bot_id=bot_id,
                token=bot.token,
                config=config_dict,
                update=update
            )
            
            logger.info(f"✅ Bot {bot_id} processado via VIA EXPRESSA (direto)")
            return jsonify({'status': 'ok'}), 200
            
        except Exception as direct_error:
            logger.error(f"⚠️ Via Expressa falhou para bot {bot_id}: {direct_error}")
            logger.info(f"🔄 Acionando fallback Redis para bot {bot_id}")
        
        # ============================================================================
        # TENTATIVA 2: VIA BUROCRÁTICA (Redis/State) - Fallback opcional
        # ============================================================================
        try:
            from bot_manager import BotManager
            bot_manager = BotManager(socketio=None, scheduler=None)
            
            result = bot_manager._process_telegram_update(bot_id, None, update)
            
            logger.info(f"✅ Bot {bot_id} processado via Redis/State (fallback)")
            return jsonify({'status': 'ok'}), 200
            
        except Exception as redis_error:
            logger.error(f"❌ Via Burocrática também falhou para bot {bot_id}: {redis_error}")
            # Limpa transação antes de retornar
            try:
                db.session.rollback()
            except Exception:
                pass
            return jsonify({'status': 'ok'}), 200  # Retornar 200 para não retry
            
    except Exception as e:
        logger.error(f"❌ Erro crítico no webhook Telegram: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
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
