"""
Tarefas Assíncronas para Sincronização de Webhooks Telegram (RQ)
===============================================================

Motor de sincronização "Always Online" - garante que todos os bots
estão sempre escutando seus webhooks sem bloquear o servidor principal.

Regra de negócio imutável: "TODOS OS BOTS ESTÃO SEMPRE ONLINE"
"""

import logging
import time
from typing import Optional

import telebot
from flask import current_app

from internal_logic.core.extensions import db
from internal_logic.core.models import Bot

logger = logging.getLogger(__name__)


def task_sync_single_webhook(bot_id: int) -> dict:
    """
    Sincroniza o webhook de um único bot no Telegram.
    
    Executa remove_webhook() seguido de set_webhook() para garantir
    que o bot está sempre recebendo atualizações.
    
    Args:
        bot_id: ID do bot no banco de dados
        
    Returns:
        dict: Status da operação {'success': bool, 'bot_id': int, 'message': str}
    """
    try:
        with current_app.app_context():
            # Buscar bot pelo ID
            bot = db.session.get(Bot, bot_id)
            
            if not bot:
                logger.warning(f"⚠️ Bot {bot_id} não encontrado para sincronização")
                return {
                    'success': False,
                    'bot_id': bot_id,
                    'message': 'Bot não encontrado no banco de dados'
                }
            
            if not bot.token:
                logger.warning(f"⚠️ Bot {bot_id} não tem token configurado")
                return {
                    'success': False,
                    'bot_id': bot_id,
                    'message': 'Bot sem token configurado'
                }
            
            # Construir URL do webhook
            webhook_url = f"https://app.grimbots.online/webhook/telegram/{bot.id}"
            
            try:
                # Instanciar TeleBot
                tb = telebot.TeleBot(bot.token)
                
                # Remover webhook antigo (limpeza)
                tb.remove_webhook()
                logger.debug(f"🧹 Webhook removido para bot {bot_id}")
                
                # Pequena pausa para evitar rate limit
                time.sleep(0.1)
                
                # Configurar novo webhook
                tb.set_webhook(url=webhook_url)
                logger.info(f"✅ Webhook sincronizado: Bot {bot_id} -> {webhook_url}")
                
                return {
                    'success': True,
                    'bot_id': bot_id,
                    'message': f'Webhook sincronizado: {webhook_url}',
                    'webhook_url': webhook_url
                }
                
            except telebot.apihelper.ApiTelegramException as api_error:
                # Token inválido ou erro da API Telegram
                error_msg = str(api_error)
                logger.error(f"❌ Erro API Telegram para bot {bot_id}: {error_msg}")
                
                return {
                    'success': False,
                    'bot_id': bot_id,
                    'message': f'Erro API Telegram: {error_msg}'
                }
                
    except Exception as e:
        logger.error(f"❌ Erro inesperado ao sincronizar bot {bot_id}: {e}", exc_info=True)
        return {
            'success': False,
            'bot_id': bot_id,
            'message': f'Erro interno: {str(e)}'
        }


def task_sync_all_webhooks() -> dict:
    """
    Sincroniza webhooks de TODOS os bots ativos no sistema.
    
    Regra: Todos os bots estão sempre online. Itera sobre todos
    os bots da tabela e sincroniza um por um.
    
    Returns:
        dict: Resumo da operação com contagens de sucesso/falha
    """
    try:
        with current_app.app_context():
            # Buscar TODOS os bots (regra: todos estão sempre online)
            bots = Bot.query.all()
            
            total = len(bots)
            success_count = 0
            failed_count = 0
            failed_bots = []
            
            logger.info(f"🚀 Iniciando sincronização em massa: {total} bots")
            
            for bot in bots:
                try:
                    result = task_sync_single_webhook(bot.id)
                    
                    if result['success']:
                        success_count += 1
                    else:
                        failed_count += 1
                        failed_bots.append({
                            'bot_id': bot.id,
                            'error': result['message']
                        })
                    
                    # Rate limiting: 0.1s entre cada bot para respeitar Telegram
                    time.sleep(0.1)
                    
                except Exception as bot_error:
                    failed_count += 1
                    failed_bots.append({
                        'bot_id': bot.id,
                        'error': str(bot_error)
                    })
                    logger.error(f"❌ Falha ao sincronizar bot {bot.id}: {bot_error}")
            
            summary = {
                'success': True,
                'total': total,
                'success_count': success_count,
                'failed_count': failed_count,
                'failed_bots': failed_bots,
                'message': f'Sincronização concluída: {success_count}/{total} bots OK'
            }
            
            logger.info(f"✅ Sincronização em massa concluída: {success_count}/{total} bots OK")
            return summary
            
    except Exception as e:
        logger.error(f"❌ Erro crítico na sincronização em massa: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Erro crítico: {str(e)}',
            'total': 0,
            'success_count': 0,
            'failed_count': 0
        }
