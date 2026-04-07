"""
Webhook Syncer - Sincronização Nativa de Webhooks Telegram
===========================================================

Motor autossuficiente de sincronização de webhooks usando apenas
requests (biblioteca nativa). Sem dependências externas como telebot.

Arquitetura Self-Healing: Roda em thread separada no boot do servidor
para não bloquear o Gunicorn. Garante que todos os bots ativos estejam
sempre conectados aos webhooks do Telegram.

Regra de negócio: "TODOS OS BOTS ESTÃO SEMPRE ONLINE"
"""

import requests
import time
import logging
import threading
from flask import current_app

logger = logging.getLogger(__name__)

# Configurações
BASE_WEBHOOK_URL = "https://app.grimbots.online/webhook/telegram/"
TELEGRAM_API_BASE = "https://api.telegram.org/bot"
RATE_LIMIT_SECONDS = 0.1  # 100ms entre requisições para respeitar rate limit do Telegram
REQUEST_TIMEOUT = 5  # segundos


def _sync_single_bot_webhook(bot) -> bool:
    """
    Sincroniza o webhook de um único bot usando requests nativo.
    
    Args:
        bot: Instância do modelo Bot
        
    Returns:
        bool: True se sincronizado com sucesso, False caso contrário
    """
    if not bot or not bot.token:
        logger.warning(f"⚠️ Bot {bot.id if bot else 'unknown'} não tem token configurado")
        return False
    
    webhook_url = f"{BASE_WEBHOOK_URL}{bot.id}"
    api_url = f"{TELEGRAM_API_BASE}{bot.token}/setWebhook"
    
    try:
        payload = {
            "url": webhook_url,
            "drop_pending_updates": False,  # 🔥 CRÍTICO: NÃO PERDER LEADS
            "max_connections": 100,  # Alta concorrência para bots grandes (10k+ usuários)
            "allowed_updates": ["message", "callback_query", "edited_message"]  # Apenas o necessário
        }
        
        response = requests.post(
            api_url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                logger.info(f"✅ Bot {bot.id} sincronizado: {webhook_url}")
                return True
            else:
                error_desc = data.get('description', 'Unknown error')
                logger.error(f"❌ API Telegram rejeitou Bot {bot.id}: {error_desc}")
                return False
        else:
            logger.error(f"❌ HTTP {response.status_code} ao sincronizar Bot {bot.id}: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout ao sincronizar Bot {bot.id} (>{REQUEST_TIMEOUT}s)")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"🔌 Erro de conexão ao sincronizar Bot {bot.id}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro inesperado ao sincronizar Bot {bot.id}: {e}")
        return False


def _sync_webhooks_task(app):
    """
    Tarefa de sincronização que roda em background.
    
    NÃO bloqueia o boot do servidor Gunicorn.
    Itera sobre todos os bots ativos e sincroniza seus webhooks.
    
    Args:
        app: Instância da aplicação Flask (passada via _get_current_object())
    """
    with app.app_context():
        from internal_logic.core.models import Bot
        from internal_logic.core.extensions import db
        
        try:
            # Buscar todos os bots ativos (regra: todos estão sempre online)
            active_bots = Bot.query.filter_by(is_active=True).all()
            total_bots = len(active_bots)
            
            if total_bots == 0:
                logger.info("ℹ️ Nenhum bot ativo encontrado para sincronização")
                return
            
            logger.info(f"🔄 Iniciando Auto-Sincronização de {total_bots} bots no Telegram...")
            logger.info(f"   URL Base: {BASE_WEBHOOK_URL}")
            logger.info(f"   Rate Limit: {RATE_LIMIT_SECONDS}s entre requisições")
            
            success_count = 0
            failed_count = 0
            failed_bots = []
            
            for bot in active_bots:
                try:
                    if _sync_single_bot_webhook(bot):
                        success_count += 1
                    else:
                        failed_count += 1
                        failed_bots.append(bot.id)
                    
                    # Rate limiting: não bombardear a API do Telegram
                    time.sleep(RATE_LIMIT_SECONDS)
                    
                except Exception as bot_error:
                    failed_count += 1
                    failed_bots.append(bot.id)
                    logger.error(f"❌ Exceção ao processar Bot {bot.id}: {bot_error}")
                    continue  # Não deixar um bot quebrar o processamento dos outros
            
            # Resumo final
            logger.info("=" * 60)
            logger.info(f"🚀 Sincronização Concluída!")
            logger.info(f"   Total: {total_bots} bots")
            logger.info(f"   ✅ Sucesso: {success_count}")
            logger.info(f"   ❌ Falhas: {failed_count}")
            if failed_bots:
                logger.info(f"   Bots com falha: {failed_bots}")
            logger.info("=" * 60)
            
        except Exception as global_e:
            logger.critical(f"💥 Erro fatal na thread de sincronização: {global_e}", exc_info=True)


def start_webhook_sync_thread(app):
    """
    Inicia a sincronização de webhooks em uma thread separada (Self-Healing).
    
    Esta função é chamada no boot do servidor Flask/Gunicorn.
    A thread é daemon (não bloqueia o shutdown do servidor).
    
    Args:
        app: Instância da aplicação Flask
        
    Uso:
        # Em extensions.py ou app.py, após db.init_app(app):
        from internal_logic.services.webhook_syncer import start_webhook_sync_thread
        start_webhook_sync_thread(app)
    """
    try:
        # Usar _get_current_object() para garantir que a thread tenha acesso ao app
        app_obj = app._get_current_object() if hasattr(app, '_get_current_object') else app
        
        thread = threading.Thread(
            target=_sync_webhooks_task,
            args=(app_obj,),
            name="WebhookSyncThread",
            daemon=True  # 🔥 CRÍTICO: Thread daemon não bloqueia shutdown do servidor
        )
        
        thread.start()
        logger.info("🧵 Thread de sincronização de webhooks iniciada (Self-Healing mode)")
        
    except Exception as e:
        logger.error(f"❌ Falha ao iniciar thread de sincronização: {e}")


def sync_webhook_for_bot(bot_id: int) -> dict:
    """
    Sincroniza webhook para um bot específico (uso manual/debug).
    
    Args:
        bot_id: ID do bot no banco de dados
        
    Returns:
        dict: {'success': bool, 'message': str, 'bot_id': int}
    """
    try:
        from internal_logic.core.models import Bot
        
        bot = Bot.query.get(bot_id)
        if not bot:
            return {'success': False, 'message': 'Bot não encontrado', 'bot_id': bot_id}
        
        if not bot.is_active:
            return {'success': False, 'message': 'Bot não está ativo', 'bot_id': bot_id}
        
        success = _sync_single_bot_webhook(bot)
        
        return {
            'success': success,
            'message': 'Sincronizado com sucesso' if success else 'Falha na sincronização',
            'bot_id': bot_id
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar bot {bot_id}: {e}")
        return {'success': False, 'message': str(e), 'bot_id': bot_id}
