"""
Bot Runner Service
==================
Serviço dedicado ao ciclo de vida dos bots Telegram.
Gerencia start, stop, polling e heartbeat de forma isolada.
"""

import logging
import threading
import time
import os
from typing import Dict, Any, Optional, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class BotRunner:
    """
    Gerencia o ciclo de vida de bots Telegram.
    Responsável por: iniciar, parar, monitorar e fazer polling de bots.
    """
    
    def __init__(
        self,
        bot_state,
        scheduler=None,
        webhook_url: Optional[str] = None,
        on_update_received: Optional[Callable] = None
    ):
        """
        Inicializa o BotRunner.
        
        Args:
            bot_state: Instância do estado do bot (RedisBrain/BotState)
            scheduler: Scheduler APScheduler opcional para jobs
            webhook_url: URL base para webhooks
            on_update_received: Callback quando update é recebido (bot_id, update)
        """
        self.bot_state = bot_state
        self.scheduler = scheduler
        self.webhook_url = webhook_url or os.environ.get('WEBHOOK_URL', '')
        self.on_update_received = on_update_received
        
        # Tracking de recursos por bot
        self.bot_threads: Dict[int, threading.Thread] = {}
        self.polling_jobs: Dict[int, str] = {}  # bot_id -> job_id
        
        # Session HTTP para chamadas Telegram
        self._telegram_session = requests.Session()
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(['GET', 'POST']),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
        self._telegram_session.mount('https://', adapter)
        
        logger.info("✅ BotRunner inicializado")
    
    def start_bot(self, bot_id: int, token: str, config: Dict[str, Any]) -> bool:
        """
        Inicia um bot Telegram - Com estado centralizado em Redis
        
        Args:
            bot_id: ID do bot no banco
            token: Token do bot
            config: Configuração do bot
            
        Returns:
            bool: True se iniciado com sucesso
        """
        # Verificar se bot já está ativo no Redis
        if self.bot_state.is_bot_active(bot_id):
            logger.warning(f"Bot {bot_id} já está ativo no Redis")
            return False
        
        # Adquirir lock de auto-start para prevenir race conditions
        if not self.bot_state.acquire_autostart_lock(bot_id, timeout=30):
            logger.warning(f"🔒 Bot {bot_id} está sendo iniciado por outro worker - aguardando")
            for _ in range(6):
                time.sleep(0.5)
                if self.bot_state.is_bot_active(bot_id):
                    logger.info(f"✅ Bot {bot_id} foi iniciado por outro worker")
                    return True
            logger.warning(f"⚠️ Timeout aguardando bot {bot_id} iniciar por outro worker")
            return False
        
        try:
            # Configurar webhook para receber mensagens do Telegram
            self._setup_webhook(token, bot_id)
            
            # Registrar bot no Redis (única fonte de verdade)
            self.bot_state.register_bot(bot_id, token, config, worker_pid=os.getpid())
            
            # Iniciar heartbeat para manter bot ativo no Redis
            self.bot_state.start_heartbeat_thread(bot_id, interval=60)
            
            # Iniciar thread de monitoramento
            thread = threading.Thread(
                target=self._bot_monitor_thread,
                args=(bot_id,),
                daemon=True
            )
            thread.start()
            self.bot_threads[bot_id] = thread
            
            logger.info(f"✅ Bot {bot_id} iniciado com webhook configurado (Redis 100%)")
            return True
            
        finally:
            # Liberar lock de auto-start
            self.bot_state.release_autostart_lock(bot_id)
    
    def stop_bot(self, bot_id: int) -> bool:
        """
        Para um bot Telegram - Remove do Redis (única fonte de verdade)
        
        Args:
            bot_id: ID do bot no banco
            
        Returns:
            bool: True se parado com sucesso
        """
        # Remover do Redis (todos os workers verão imediatamente)
        self.bot_state.unregister_bot(bot_id)
        
        # Remover job do scheduler se existir
        if bot_id in self.polling_jobs and self.scheduler:
            try:
                self.scheduler.remove_job(self.polling_jobs[bot_id])
                del self.polling_jobs[bot_id]
                logger.info(f"✅ Polling job removido para bot {bot_id}")
            except Exception as e:
                logger.error(f"Erro ao remover job: {e}")
        
        # Thread será encerrada automaticamente
        if bot_id in self.bot_threads:
            del self.bot_threads[bot_id]
        
        logger.info(f"✅ Bot {bot_id} parado e removido do Redis")
        return True
    
    def _setup_webhook(self, token: str, bot_id: int) -> bool:
        """
        Configura webhook para um bot específico.
        
        Args:
            token: Token do bot
            bot_id: ID do bot
            
        Returns:
            bool: True se configurado com sucesso
        """
        try:
            if not self.webhook_url:
                logger.warning(f"⚠️ WEBHOOK_URL não configurado, pulando configuração para bot {bot_id}")
                return False
            
            webhook_endpoint = f"{self.webhook_url}/webhook/telegram/{bot_id}"
            url = f"https://api.telegram.org/bot{token}/setWebhook"
            
            response = self._telegram_session.post(
                url,
                json={'url': webhook_endpoint},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Webhook configurado para bot {bot_id}: {webhook_endpoint}")
                return True
            else:
                logger.warning(f"⚠️ Erro ao configurar webhook bot {bot_id}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao configurar webhook: {e}")
            return False
    
    def _bot_monitor_thread(self, bot_id: int):
        """
        Thread de monitoramento de um bot (heartbeat local)
        
        Args:
            bot_id: ID do bot
        """
        logger.info(f"📊 Monitor do bot {bot_id} iniciado")
        
        error_count = 0
        max_backoff_seconds = 60
        cycle = 0
        
        while True:
            try:
                # Verificar se bot está ativo no Redis
                bot_info = self.bot_state.get_bot_data(bot_id)
                if not bot_info or bot_info.get('status') != 'running':
                    logger.info(f"📊 Monitor do bot {bot_id} encerrado (status não-running)")
                    break
                
                cycle += 1
                error_count = max(0, error_count - 1)  # Decay de erros
                
                # Heartbeat leve a cada 30 ciclos (~30 segundos)
                if cycle % 30 == 0:
                    logger.debug(f"💓 Heartbeat bot {bot_id} - ciclo {cycle}")
                
                time.sleep(1)
                
            except Exception as e:
                error_count += 1
                backoff = min(2 ** error_count, max_backoff_seconds)
                logger.error(f"❌ Erro no monitor bot {bot_id}: {e} (backoff: {backoff}s)")
                time.sleep(backoff)
    
    def _polling_cycle(self, bot_id: int, token: str):
        """
        Ciclo de polling - chamado pelo scheduler a cada segundo
        
        Args:
            bot_id: ID do bot
            token: Token do bot
        """
        try:
            # Verificar se bot está ativo no Redis
            bot_data = self.bot_state.get_bot_data(bot_id)
            if not bot_data or bot_data.get('status') != 'running':
                logger.warning(f"⚠️ Bot {bot_id} não está ativo no Redis, pulando polling")
                return
            
            # Buscar offset/poll_count do Redis (transientes)
            config = bot_data.get('config', {})
            offset = config.get('_polling_offset', 0)
            poll_count = config.get('_polling_count', 0)
            poll_count += 1
            
            # Atualizar métricas no Redis (não crítico se falhar)
            try:
                new_config = config.copy()
                new_config['_polling_offset'] = offset
                new_config['_polling_count'] = poll_count
                self.bot_state.update_bot_config(bot_id, new_config)
            except:
                pass
            
            # Log apenas a cada 30 polls (30 segundos)
            if poll_count % 30 == 0:
                logger.info(f"✅ Bot {bot_id} online e aguardando mensagens...")
            
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            response = self._telegram_session.get(
                url,
                params={'offset': offset, 'timeout': 25},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('ok'):
                    updates = data.get('result', [])
                    
                    if updates:
                        logger.info(f"\n{'='*60}")
                        logger.info(f"📨 NOVA MENSAGEM RECEBIDA! ({len(updates)} update(s))")
                        logger.info(f"{'='*60}")
                        
                        max_update_id = offset
                        for update in updates:
                            if update.get('update_id', 0) > max_update_id:
                                max_update_id = update['update_id']
                            
                            # Chamar callback para processar update
                            if self.on_update_received:
                                try:
                                    self.on_update_received(bot_id, update)
                                except Exception as e:
                                    logger.error(f"❌ Erro ao processar update: {e}")
                        
                        # Atualizar offset uma única vez após processar todos
                        if max_update_id > offset:
                            try:
                                current_config = self.bot_state.get_bot_data(bot_id)
                                if current_config:
                                    new_config = current_config.get('config', {}).copy()
                                    new_config['_polling_offset'] = max_update_id + 1
                                    self.bot_state.update_bot_config(bot_id, new_config)
                            except:
                                pass
        
        except requests.exceptions.Timeout:
            pass  # Timeout é esperado
        except Exception as e:
            logger.error(f"❌ Erro no polling bot {bot_id}: {e}")
            time.sleep(5)  # DEFESA: Evitar loop infinito de CPU
    
    def start_polling_job(self, bot_id: int, token: str, interval: int = 1) -> bool:
        """
        Inicia um job de polling para o bot via scheduler.
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            interval: Intervalo em segundos entre polls
            
        Returns:
            bool: True se job criado com sucesso
        """
        if not self.scheduler:
            logger.warning(f"⚠️ Scheduler não disponível para polling do bot {bot_id}")
            return False
        
        try:
            job_id = f'bot_polling_{bot_id}'
            self.scheduler.add_job(
                id=job_id,
                func=self._polling_cycle,
                args=[bot_id, token],
                trigger='interval',
                seconds=interval,
                replace_existing=True
            )
            self.polling_jobs[bot_id] = job_id
            logger.info(f"✅ Polling job criado para bot {bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar polling job: {e}")
            return False
    
    def stop_polling_job(self, bot_id: int) -> bool:
        """
        Para o job de polling de um bot.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            bool: True se job removido com sucesso
        """
        if bot_id not in self.polling_jobs or not self.scheduler:
            return False
        
        try:
            self.scheduler.remove_job(self.polling_jobs[bot_id])
            del self.polling_jobs[bot_id]
            logger.info(f"✅ Polling job removido para bot {bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover polling job: {e}")
            return False
    
    def is_bot_running(self, bot_id: int) -> bool:
        """
        Verifica se um bot está rodando.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            bool: True se bot está ativo
        """
        return self.bot_state.is_bot_active(bot_id)
    
    def get_bot_info(self, bot_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtém informações de um bot do estado.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            Dict com informações do bot ou None
        """
        return self.bot_state.get_bot_data(bot_id)
