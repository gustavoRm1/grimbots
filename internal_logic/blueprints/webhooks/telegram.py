"""
Webhooks Telegram Blueprint
============================
Recebe webhooks de atualizações do Telegram para bots.
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from internal_logic.core.extensions import limiter, db, csrf
from internal_logic.core.models import Bot

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram_webhooks', __name__)


@csrf.exempt
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
        
        # DIAGNÓSTICO: BYPASS ORM COM SQL PURO
        from sqlalchemy import text
        from internal_logic.core.extensions import db
        
        try:
            # 1. Tenta achar na tabela principal de bots
            raw_bot = db.session.execute(
                text("SELECT id, token FROM bots WHERE id = :bot_id"),
                {"bot_id": bot_id}
            ).fetchone()
            
            if raw_bot:
                logger.info(f"DIAGNÓSTICO: RAW SQL ENCONTROU O BOT {bot_id} NA TABELA 'bots'! Token: {raw_bot[1][:5]}...")
            else:
                logger.warning(f"DIAGNÓSTICO: RAW SQL NÃO ACHOU O BOT {bot_id} NA TABELA 'bots'.")
                
                # 2. Tenta achar na tabela de pool (se existir na sua arquitetura)
                try:
                    raw_pool = db.session.execute(
                        text("SELECT id, token FROM pool_bots WHERE id = :bot_id"),
                        {"bot_id": bot_id}
                    ).fetchone()
                    if raw_pool:
                        logger.info(f"DIAGNÓSTICO: O BOT {bot_id} FOI ACHADO NA TABELA 'pool_bots' e não na 'bots'!")
                except Exception:
                    pass # Tabela pool_bots não existe, segue o jogo

        except Exception as e:
            logger.error(f"DIAGNÓSTICO: ERRO NO RAW SQL (Tabela com nome diferente?): {e}")
        
        # Buscar bot (query pura sem filtros contextuais)
        bot = Bot.query.get(bot_id)
        if not bot:
            logger.error(f"CRITICAL: Bot {bot_id} não encontrado no banco de dados")
            # NÃO retornar 404 para evitar retry policy do Telegram
            return jsonify({'status': 'error', 'message': 'Bot not found'}), 200
        
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
