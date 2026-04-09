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
        # TENTATIVA 1: VIA EXPRESSA (Processamento Direto Legado) - PRIMEIRO!
        # ============================================================================
        # Esta é a via à prova de balas - processa direto sem Redis, sem burocracia
        # Buscar config direto do banco
        try:
            bot_config = bot.config or BotConfig.query.filter_by(bot_id=bot_id).first()
            config_dict = bot_config.to_dict() if bot_config else {}
        except Exception as config_error:
            db.session.rollback()
            logger.warning(f"⚠️ Erro ao buscar config (não crítico): {config_error}")
            config_dict = {}  # Continua sem config
        
        # ✅ QI 200: Enfileirar para processamento assíncrono via Worker RQ
        # GARANTIA: O Worker criará/atualizará o BotUser ANTES de processar a mensagem
        try:
            from tasks_async import task_queue, process_telegram_message_async
            
            # 🚨 DIAGNÓSTICO: Verificar se workers estão processando
            use_sync_fallback = False
            queue_length = 0
            
            if task_queue:
                try:
                    # Verificar tamanho da fila - se > 10, workers provavelmente estão parados
                    queue_length = task_queue.count
                    if queue_length > 10:
                        logger.critical(f"🚨 FILA BACKLOGADA! {queue_length} jobs pendentes. Workers provavelmente PARADOS!")
                        use_sync_fallback = True
                except Exception as qe:
                    logger.warning(f"⚠️ Não foi possível verificar tamanho da fila: {qe}")
            
            if task_queue and not use_sync_fallback:
                task_queue.enqueue(
                    process_telegram_message_async,
                    bot_id,
                    update,
                    bot.token,
                    config_dict
                )
                logger.info(f"✅ Mensagem enfileirada | Bot: {bot_id} | Queue size: {queue_length}")
                return jsonify({'status': 'queued'}), 200
            else:
                # 🚨 WORKERS PARADOS - Processar síncrono para não perder mensagens!
                if use_sync_fallback:
                    logger.critical(f"🚨 WORKERS PARADOS! Processando síncrono para não perder mensagem | Bot: {bot_id}")
                else:
                    logger.warning(f"⚠️ Fila RQ não disponível, processando síncrono | Bot: {bot_id}")
                
                from tasks_async import process_telegram_message_async
                process_telegram_message_async(bot_id, update, bot.token, config_dict)
                return jsonify({'status': 'processed_sync'}), 200
                
        except Exception as e:
            logger.error(f"❌ Erro ao enfileirar processamento: {e}", exc_info=True)
            # 🚨 ÚLTIMO RECURSO: Tentar processar síncrono mesmo com erro
            try:
                logger.critical(f"🚨 ERRO NA FILA - Tentando processar síncrono como último recurso | Bot: {bot_id}")
                from tasks_async import process_telegram_message_async
                process_telegram_message_async(bot_id, update, bot.token, {})
                return jsonify({'status': 'processed_sync_fallback'}), 200
            except Exception as sync_error:
                logger.critical(f"💀 FALHA TOTAL: Nem síncrono funcionou: {sync_error}", exc_info=True)
                return jsonify({'error': 'Processing failed'}), 500
            
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
