"""
Bot Manager - Gerenciador de Bots do Telegram
Responsável por validar tokens, iniciar/parar bots e processar webhooks
"""

import requests
import threading
import time
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import hashlib
import hmac

logger = logging.getLogger(__name__)

# Configurar logging para este módulo
logger.setLevel(logging.INFO)

def send_meta_pixel_viewcontent_event(bot, bot_user, message, pool_id=None):
    """
    Envia evento ViewContent para Meta Pixel quando usuário inicia conversa com bot
    
    ARQUITETURA V3.0 (QI 540 - CORREÇÃO CRÍTICA):
    - Busca pixel do POOL ESPECÍFICO (passado via pool_id)
    - Se pool_id não fornecido, busca primeiro pool do bot (fallback)
    - Usa UTM e external_id salvos no BotUser
    - Alta disponibilidade: dados consolidados no pool
    - Tracking preciso mesmo com múltiplos bots
    
    CRÍTICO: Anti-duplicação via meta_viewcontent_sent flag
    
    Args:
        bot: Instância do Bot
        bot_user: Instância do BotUser
        message: Mensagem do Telegram
        pool_id: ID do pool específico (extraído do start param)
    """
    try:
        # ✅ VERIFICAÇÃO 1: Buscar pool associado ao bot
        from models import PoolBot, RedirectPool
        
        # Se pool_id foi passado, buscar pool específico
        if pool_id:
            pool_bot = PoolBot.query.filter_by(bot_id=bot.id, pool_id=pool_id).first()
            if not pool_bot:
                logger.warning(f"Bot {bot.id} não está no pool {pool_id} especificado - tentando fallback")
                pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        else:
            # Fallback: buscar primeiro pool do bot
            pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        
        if not pool_bot:
            logger.info(f"Bot {bot.id} não está associado a nenhum pool - Meta Pixel ignorado")
            return
        
        pool = pool_bot.pool
        
        logger.info(f"📊 Pool selecionado para ViewContent: {pool.id} ({pool.name}) | " +
                   f"pool_id_param={pool_id} | bot_id={bot.id}")
        
        # ✅ VERIFICAÇÃO 2: Pool tem Meta Pixel configurado?
        if not pool.meta_tracking_enabled:
            return
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            logger.warning(f"Pool {pool.id} tem tracking ativo mas sem pixel_id ou access_token")
            return
        
        # ✅ VERIFICAÇÃO 3: Evento ViewContent está habilitado?
        if not pool.meta_events_viewcontent:
            logger.info(f"Evento ViewContent desabilitado para pool {pool.id}")
            return
        
        # ✅ VERIFICAÇÃO 4: Já enviou ViewContent para este usuário? (ANTI-DUPLICAÇÃO)
        if bot_user.meta_viewcontent_sent:
            logger.info(f"⚠️ ViewContent já enviado ao Meta, ignorando: BotUser {bot_user.id}")
            return
        
        logger.info(f"📊 Preparando envio Meta ViewContent: Pool {pool.name} | User {bot_user.telegram_user_id}")
        
        # Importar Meta Pixel API
        from utils.meta_pixel import MetaPixelAPI
        from utils.encryption import decrypt
        
        # Gerar event_id único para deduplicação
        event_id = MetaPixelAPI._generate_event_id(
            event_type='viewcontent',
            unique_id=f"{pool.id}_{bot_user.telegram_user_id}"
        )
        
        # Descriptografar access token
        try:
            access_token = decrypt(pool.meta_access_token)
        except Exception as e:
            logger.error(f"Erro ao descriptografar access_token do pool {pool.id}: {e}")
            return
        
        # ✅ USAR UTM E EXTERNAL_ID SALVOS NO BOTUSER (QI 540 - FIX CRÍTICO)
        # Dados foram salvos quando usuário acessou /go/<slug>
        # ✅ Agora eventos ViewContent e Purchase têm origem correta!
        
        # ============================================================================
        # ✅ ENFILEIRAR EVENTO VIEWCONTENT (ASSÍNCRONO - MVP DIA 2)
        # ============================================================================
        from celery_app import send_meta_event
        import time
        
        event_data = {
            'event_name': 'ViewContent',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'user_data': {
                'external_id': bot_user.external_id or f'user_{bot_user.telegram_user_id}',
                # 🎯 TRACKING ELITE: Usar IP/UA capturados no redirect
                'client_ip_address': bot_user.ip_address if hasattr(bot_user, 'ip_address') and bot_user.ip_address else None,
                'client_user_agent': bot_user.user_agent if hasattr(bot_user, 'user_agent') and bot_user.user_agent else None
            },
            'custom_data': {
                'content_id': str(pool.id),
                'content_name': pool.name,
                'bot_id': bot.id,
                'bot_username': bot.username,
                'utm_source': bot_user.utm_source,
                'utm_campaign': bot_user.utm_campaign,
                'campaign_code': bot_user.campaign_code
            }
        }
        
        # ✅ ENFILEIRAR COM PRIORIDADE MÉDIA
        task = send_meta_event.apply_async(
            args=[
                pool.meta_pixel_id,
                access_token,
                event_data,
                pool.meta_test_event_code
            ],
            priority=5  # Média prioridade
        )
        
        # Marcar como enviado IMEDIATAMENTE (flag otimista)
        bot_user.meta_viewcontent_sent = True
        bot_user.meta_viewcontent_sent_at = datetime.now()
        
        # Commit da flag
        from app import db
        db.session.commit()
        
        logger.info(f"📤 ViewContent enfileirado: Pool {pool.name} | " +
                   f"User {bot_user.telegram_user_id} | " +
                   f"Event ID: {event_id} | " +
                   f"Task: {task.id} | " +
                   f"UTM: {bot_user.utm_source}/{bot_user.utm_campaign}")
    
    except Exception as e:
        logger.error(f"💥 Erro ao enviar Meta ViewContent: {e}")
        # Não impedir o funcionamento do bot se Meta falhar

# Configuração de Split Payment da Plataforma
import os
PLATFORM_SPLIT_USER_ID = os.environ.get('PLATFORM_SPLIT_USER_ID', '')  # Client ID para receber comissões (SyncPay)
PLATFORM_SPLIT_PERCENTAGE = 2  # 2% PADRÃO PARA TODOS OS GATEWAYS

# Configuração de Split Payment para PushynPay (LEGADO - não mais usado)
# ⚠️ SPLIT DESABILITADO - Account ID fornecido não existe no PushynPay
PUSHYN_SPLIT_ACCOUNT_ID = os.environ.get('PUSHYN_SPLIT_ACCOUNT_ID', None)
PUSHYN_SPLIT_PERCENTAGE = 2  # 2% (quando habilitado)

# Importar Gateway Factory (Arquitetura Enterprise)
from gateway_factory import GatewayFactory


class BotManager:
    """Gerenciador de bots Telegram"""
    
    def __init__(self, socketio, scheduler=None):
        self.socketio = socketio
        self.scheduler = scheduler
        self.active_bots: Dict[int, Dict[str, Any]] = {}
        self.bot_threads: Dict[int, threading.Thread] = {}
        self.polling_jobs: Dict[int, str] = {}  # bot_id -> job_id
        
        # ✅ THREAD SAFETY: Lock para acesso concorrente
        self._bots_lock = threading.RLock()  # RLock permite re-entrada na mesma thread
        
        # ✅ CACHE DE RATE LIMITING (em memória)
        self.rate_limit_cache = {}  # {user_key: timestamp}
        
        # ✅ SESSÕES DE MÚLTIPLOS ORDER BUMPS
        self.order_bump_sessions = {}  # {user_key: session_data}
        
        # ✅ LIMPEZA AUTOMÁTICA DO CACHE (a cada 5 minutos)
        def cleanup_cache():
            while True:
                time.sleep(300)  # 5 minutos
                now = datetime.now()
                expired_keys = []
                for user_key, timestamp in self.rate_limit_cache.items():
                    if (now - timestamp).total_seconds() > 300:  # 5 minutos
                        expired_keys.append(user_key)
                
                for key in expired_keys:
                    del self.rate_limit_cache[key]
                
                if expired_keys:
                    logger.info(f"🧹 Rate limiting cache limpo: {len(expired_keys)} entradas removidas")
        
        cleanup_thread = threading.Thread(target=cleanup_cache, daemon=True)
        cleanup_thread.start()
        
        logger.info("BotManager inicializado")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Valida token do Telegram usando getMe
        
        Args:
            token: Token do bot
            
        Returns:
            Dict com 'bot_info' e 'error_type' (None se OK)
            Exemplo: {'bot_info': {...}, 'error_type': None}
                   ou {'bot_info': None, 'error_type': 'banned'}
            
        Raises:
            Exception: Se token for inválido (com error_type no exception)
        """
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if not data.get('ok'):
                error_description = data.get('description', 'Token inválido').lower()
                error_code = data.get('error_code')
                
                # ✅ DETECÇÃO DE BANIMENTO
                if error_code == 401 or 'unauthorized' in error_description:
                    # Verificar se é banimento ou token inválido
                    if any(keyword in error_description for keyword in ['revoked', 'blocked', 'banned', 'deactivated']):
                        error = Exception('Bot foi banido ou token foi revogado')
                        error.error_type = 'banned'
                        raise error
                    else:
                        error = Exception('Token inválido ou expirado')
                        error.error_type = 'invalid_token'
                        raise error
                else:
                    error = Exception(data.get('description', 'Token inválido'))
                    error.error_type = 'unknown'
                    raise error
            
            bot_info = data.get('result', {})
            logger.info(f"Token validado: @{bot_info.get('username')}")
            
            return {
                'bot_info': bot_info,
                'error_type': None
            }
            
        except requests.exceptions.Timeout:
            error = Exception('Timeout ao conectar com API do Telegram')
            error.error_type = 'connection_error'
            raise error
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao validar token: {e}")
            error = Exception(f"Erro de conexão com API do Telegram: {str(e)}")
            error.error_type = 'connection_error'
            raise error
        except Exception as e:
            # Se já tem error_type, preservar
            if not hasattr(e, 'error_type'):
                e.error_type = 'unknown'
            logger.error(f"Erro ao validar token: {e} (tipo: {getattr(e, 'error_type', 'unknown')})")
            raise
    
    def start_bot(self, bot_id: int, token: str, config: Dict[str, Any]):
        """
        Inicia um bot Telegram
        
        Args:
            bot_id: ID do bot no banco
            token: Token do bot
            config: Configuração do bot
        """
        with self._bots_lock:  # ✅ THREAD SAFE
            if bot_id in self.active_bots:
                logger.warning(f"Bot {bot_id} já está ativo")
                return
            
            # Configurar webhook para receber mensagens do Telegram
            self._setup_webhook(token, bot_id)
            
            # ✅ CORREÇÃO: Armazenar bot ativo com LOCK
            with self._bots_lock:
                self.active_bots[bot_id] = {
                    'token': token,
                    'config': config,
                    'started_at': datetime.now(),
                    'status': 'running'
                }
        
        # Iniciar thread de monitoramento
        thread = threading.Thread(
            target=self._bot_monitor_thread,
            args=(bot_id,),
            daemon=True
        )
        thread.start()
        self.bot_threads[bot_id] = thread
        
        logger.info(f"Bot {bot_id} iniciado com webhook configurado")
    
    def stop_bot(self, bot_id: int):
        """
        Para um bot Telegram
        
        Args:
            bot_id: ID do bot no banco
        """
        with self._bots_lock:  # ✅ THREAD SAFE
            if bot_id not in self.active_bots:
                logger.warning(f"Bot {bot_id} não está ativo")
                return
            
            # Marcar como parado
            self.active_bots[bot_id]['status'] = 'stopped'
        
        # Remover job do scheduler se existir (fora do lock)
        if bot_id in self.polling_jobs and self.scheduler:
            try:
                self.scheduler.remove_job(self.polling_jobs[bot_id])
                del self.polling_jobs[bot_id]
                logger.info(f"✅ Polling job removido para bot {bot_id}")
            except Exception as e:
                logger.error(f"Erro ao remover job: {e}")
        
        # Remover da lista de ativos
        with self._bots_lock:  # ✅ THREAD SAFE
            if bot_id in self.active_bots:
                del self.active_bots[bot_id]
        
        # Thread será encerrada automaticamente
        if bot_id in self.bot_threads:
            del self.bot_threads[bot_id]
        
        logger.info(f"Bot {bot_id} parado")
    
    def update_bot_config(self, bot_id: int, config: Dict[str, Any]):
        """
        Atualiza configuração de um bot em tempo real
        
        Args:
            bot_id: ID do bot
            config: Nova configuração
        """
        # ✅ CORREÇÃO: Atualizar config com LOCK
        with self._bots_lock:
            if bot_id in self.active_bots:
                self.active_bots[bot_id]['config'] = config
                logger.info(f"🔧 Configuração do bot {bot_id} atualizada")
                logger.info(f"🔍 DEBUG Config - downsells_enabled: {config.get('downsells_enabled', False)}")
                logger.info(f"🔍 DEBUG Config - downsells: {config.get('downsells', [])}")
            else:
                logger.warning(f"⚠️ Bot {bot_id} não está ativo para atualizar configuração")
    
    def _bot_monitor_thread(self, bot_id: int):
        """
        Thread de monitoramento de um bot (simulação de atividade)
        
        Args:
            bot_id: ID do bot
        """
        logger.info(f"Monitor do bot {bot_id} iniciado")

        # Watchdog com retry/backoff: nunca encerrar por exceções transitórias
        error_count = 0
        max_backoff_seconds = 60
        cycle = 0
        
        while True:
            with self._bots_lock:
                if bot_id not in self.active_bots or self.active_bots[bot_id]['status'] != 'running':
                    logger.info(f"Monitor do bot {bot_id} encerrado (status não-running ou removido)")
                    break

            try:
                # Heartbeat (mantém conexões em tempo real e sinaliza vivacidade)
                self.socketio.emit('bot_heartbeat', {
                    'bot_id': bot_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'online'
                }, room=f'bot_{bot_id}')

                # Registrar heartbeat compartilhado (Redis) para ambientes multi-worker
                try:
                    import redis, time as _t
                    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                    r.setex(f'bot_heartbeat:{bot_id}', 180, int(_t.time()))
                except Exception:
                    # Não interromper o monitor se Redis indisponível
                    pass

                # Reset de erros após sucesso
                error_count = 0

                # Intervalo padrão de monitoramento
                time.sleep(30)

                # Auto-verificação periódica do webhook (a cada ~5 min)
                cycle += 1
                if cycle % 10 == 0:
                    try:
                        with self._bots_lock:
                            token = self.active_bots.get(bot_id, {}).get('token')
                        if token:
                            import os, requests as _rq
                            expected_base = os.environ.get('WEBHOOK_URL', '')
                            if expected_base:
                                expected_url = f"{expected_base}/webhook/telegram/{bot_id}"
                                info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
                                resp = _rq.get(info_url, timeout=10)
                                if resp.status_code == 200:
                                    info = resp.json().get('result', {})
                                    configured = info.get('url')
                                    last_error = info.get('last_error_message')
                                    if configured != expected_url or last_error:
                                        logger.warning(f"🔁 Auto-fix webhook bot {bot_id}: cfg='{configured}', expected='{expected_url}', last_error='{last_error}'")
                                        self._setup_webhook(token, bot_id)
                                        # Se persistir 502, ativar failover polling (deleteWebhook + polling)
                                        if last_error and '502 Bad Gateway' in str(last_error):
                                            try:
                                                del_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
                                                _rq.post(del_url, timeout=10)
                                            except Exception:
                                                pass
                                            if self.scheduler:
                                                job_id = f'bot_polling_{bot_id}'
                                                self.scheduler.add_job(
                                                    id=job_id,
                                                    func=self._polling_cycle,
                                                    args=[bot_id, token],
                                                    trigger='interval',
                                                    seconds=1,
                                                    max_instances=1,
                                                    replace_existing=True
                                                )
                                                self.polling_jobs[bot_id] = job_id
                                            else:
                                                threading.Thread(target=self._polling_mode, args=(bot_id, token), daemon=True).start()
                                else:
                                    logger.warning(f"⚠️ getWebhookInfo {resp.status_code}: {resp.text}")
                    except Exception as ie:
                        logger.debug(f"Webhook auto-check falhou: {ie}")

            except Exception as e:
                error_count += 1
                backoff = min(2 ** min(error_count, 5), max_backoff_seconds)
                logger.error(f"Erro no monitor do bot {bot_id} (tentativa {error_count}): {e}. Backoff {backoff}s")
                time.sleep(backoff)
                # Continua tentando até que o status seja alterado para não-running
    
    def _setup_webhook(self, token: str, bot_id: int):
        """
        Configura webhook do Telegram
        
        Args:
            token: Token do bot
            bot_id: ID do bot
        """
        try:
            # Para desenvolvimento local, usar ngrok ou similar
            # Para produção, usar domínio real com HTTPS
            
            # IMPORTANTE: Configure WEBHOOK_URL nas variáveis de ambiente
            import os
            webhook_base = os.environ.get('WEBHOOK_URL', '')
            
            if webhook_base:
                # Configurar webhook real
                webhook_url = f"{webhook_base}/webhook/telegram/{bot_id}"
                url = f"https://api.telegram.org/bot{token}/setWebhook"
                response = requests.post(url, json={'url': webhook_url}, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"Webhook configurado: {webhook_url}")
                    # Verificar estado do webhook imediatamente
                    try:
                        info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
                        info_resp = requests.get(info_url, timeout=10)
                        if info_resp.status_code == 200:
                            info = info_resp.json()
                            url_cfg = (info.get('result') or {}).get('url')
                            last_error_date = (info.get('result') or {}).get('last_error_date')
                            last_error_message = (info.get('result') or {}).get('last_error_message')
                            pending = (info.get('result') or {}).get('pending_update_count')
                            if url_cfg != webhook_url:
                                logger.warning(f"⚠️ Webhook não corresponde (cfg='{url_cfg}') ao esperado ('{webhook_url}')")
                            if last_error_message:
                                logger.error(f"❌ getWebhookInfo: last_error='{last_error_message}' date={last_error_date}")
                            if isinstance(pending, int) and pending > 100:
                                logger.warning(f"⚠️ pending_update_count alto: {pending}")

                            # Failover automático para polling se o webhook estiver retornando 502
                            if last_error_message and '502 Bad Gateway' in str(last_error_message):
                                try:
                                    # Remover webhook e habilitar polling para não perder vendas
                                    del_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
                                    del_resp = requests.post(del_url, timeout=10)
                                    logger.warning(f"🔁 Failover para polling (deleteWebhook status={del_resp.status_code}) para bot {bot_id}")
                                except Exception as de:
                                    logger.warning(f"⚠️ Falha ao deletar webhook para failover: {de}")
                                
                                # Ativar polling job/thread
                                if self.scheduler:
                                    job_id = f'bot_polling_{bot_id}'
                                    self.scheduler.add_job(
                                        id=job_id,
                                        func=self._polling_cycle,
                                        args=[bot_id, token],
                                        trigger='interval',
                                        seconds=1,
                                        max_instances=1,
                                        replace_existing=True
                                    )
                                    self.polling_jobs[bot_id] = job_id
                                    logger.info(f"✅ Polling job (failover) criado: {job_id}")
                                else:
                                    polling_thread = threading.Thread(
                                        target=self._polling_mode,
                                        args=(bot_id, token),
                                        daemon=True
                                    )
                                    polling_thread.start()
                                    logger.info(f"✅ Polling thread (failover) iniciada para bot {bot_id}")
                        else:
                            logger.warning(f"⚠️ Falha ao consultar getWebhookInfo: {info_resp.status_code} {info_resp.text}")
                    except Exception as ie:
                        logger.warning(f"⚠️ Erro ao verificar getWebhookInfo: {ie}")
                else:
                    logger.error(f"Erro ao configurar webhook: {response.text}")
            else:
                # Modo polling para desenvolvimento local
                logger.warning(f"WEBHOOK_URL não configurado. Bot {bot_id} em modo polling.")
                
                if self.scheduler:
                    # Usar APScheduler (melhor que threads)
                    job_id = f'bot_polling_{bot_id}'
                    self.scheduler.add_job(
                        id=job_id,
                        func=self._polling_cycle,
                        args=[bot_id, token],
                        trigger='interval',
                        seconds=1,
                        max_instances=1,
                        replace_existing=True
                    )
                    self.polling_jobs[bot_id] = job_id
                    logger.info(f"✅ Polling job criado: {job_id}")
                else:
                    # Fallback para thread manual
                    polling_thread = threading.Thread(
                        target=self._polling_mode,
                        args=(bot_id, token),
                        daemon=True
                    )
                    polling_thread.start()
                    logger.info(f"✅ Polling thread iniciada para bot {bot_id}")
                
        except Exception as e:
            logger.error(f"Erro ao configurar webhook: {e}")
    
    def _polling_cycle(self, bot_id: int, token: str):
        """
        Ciclo de polling - chamado pelo scheduler a cada segundo
        
        Args:
            bot_id: ID do bot
            token: Token do bot
        """
        # ✅ CORREÇÃO: Verificar com LOCK
        with self._bots_lock:
            if bot_id not in self.active_bots or self.active_bots[bot_id]['status'] != 'running':
                # Bot não está mais ativo, remover job
                if bot_id in self.polling_jobs:
                    try:
                        self.scheduler.remove_job(self.polling_jobs[bot_id])
                        del self.polling_jobs[bot_id]
                        logger.info(f"🛑 Polling job removido para bot {bot_id}")
                    except:
                        pass
                return
        
        try:
            # ✅ CORREÇÃO: Acessar active_bots com LOCK
            with self._bots_lock:
                # Inicializar offset se não existir
                if 'offset' not in self.active_bots[bot_id]:
                    self.active_bots[bot_id]['offset'] = 0
                    self.active_bots[bot_id]['poll_count'] = 0
                
                self.active_bots[bot_id]['poll_count'] += 1
                poll_count = self.active_bots[bot_id]['poll_count']
                offset = self.active_bots[bot_id]['offset']
            
            # Log apenas a cada 30 polls (30 segundos)
            if poll_count % 30 == 0:
                logger.info(f"✅ Bot {bot_id} online e aguardando mensagens...")
            
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            response = requests.get(url, params={'offset': offset, 'timeout': 0}, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('ok'):
                    updates = data.get('result', [])
                    
                    if updates:
                        logger.info(f"\n{'='*60}")
                        logger.info(f"📨 NOVA MENSAGEM RECEBIDA! ({len(updates)} update(s))")
                        logger.info(f"{'='*60}")
                        
                        for update in updates:
                            # ✅ CORREÇÃO: Atualizar offset com LOCK
                            with self._bots_lock:
                                self.active_bots[bot_id]['offset'] = update['update_id'] + 1
                            self._process_telegram_update(bot_id, update)
        
        except requests.exceptions.Timeout:
            pass  # Timeout é esperado
        except Exception as e:
            logger.error(f"❌ Erro no polling bot {bot_id}: {e}")
    
    def _polling_mode(self, bot_id: int, token: str):
        """
        Modo polling para receber atualizações (desenvolvimento local)
        
        Args:
            bot_id: ID do bot
            token: Token do bot
        """
        logger.info(f"🔄 Iniciando polling para bot {bot_id}")
        offset = 0
        poll_count = 0
        
        # ✅ CORREÇÃO: Loop com verificação thread-safe
        while True:
            with self._bots_lock:
                if bot_id not in self.active_bots or self.active_bots[bot_id]['status'] != 'running':
                    break
            try:
                poll_count += 1
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                
                # Log a cada 5 polls para mostrar que está funcionando
                if poll_count % 5 == 0:
                    logger.info(f"📡 Bot {bot_id} polling ativo (ciclo {poll_count}) - Thread: {threading.current_thread().name}")
                
                response = requests.get(url, params={'offset': offset, 'timeout': 30}, timeout=35)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok'):
                        updates = data.get('result', [])
                        
                        if updates:
                            logger.info(f"📨 Bot {bot_id} recebeu {len(updates)} update(s)")
                            
                            for update in updates:
                                offset = update['update_id'] + 1
                                logger.info(f"🔍 Processando update {update['update_id']}")
                                # Processar update
                                self._process_telegram_update(bot_id, update)
                    else:
                        logger.error(f"❌ Resposta não OK do Telegram: {data}")
                else:
                    logger.error(f"❌ Status code {response.status_code}: {response.text}")
                
                time.sleep(1)
                
            except requests.exceptions.Timeout:
                # Timeout é normal, continuar polling
                logger.debug(f"⏱️ Timeout no polling bot {bot_id} (normal)")
                continue
            except Exception as e:
                logger.error(f"❌ Erro no polling do bot {bot_id}: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
        
        logger.info(f"🛑 Polling do bot {bot_id} encerrado")
    
    def _process_telegram_update(self, bot_id: int, update: Dict[str, Any]):
        """
        Processa update recebido do Telegram
        
        Args:
            bot_id: ID do bot
            update: Dados do update
        """
        try:
            if bot_id not in self.active_bots:
                logger.warning(f"⚠️ Bot {bot_id} não está mais ativo, ignorando update")
                return
            
            # ✅ CORREÇÃO: Acessar com LOCK
            with self._bots_lock:
                if bot_id not in self.active_bots:
                    return
                bot_info = self.active_bots[bot_id].copy()  # Copy para não segurar lock
            
            token = bot_info['token']
            config = bot_info['config']
            
            # Processar mensagem
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                user = message.get('from', {})
                telegram_user_id = str(user.get('id', ''))
                
                logger.info(f"💬 De: {user.get('first_name', 'Usuário')} | Mensagem: '{text}'")
                
                # ✅ CHAT: Salvar mensagem recebida no banco (SEMPRE, independente do comando)
                if text and text.strip():  # Apenas mensagens de texto não vazias
                    try:
                        from app import app, db
                        from models import BotUser, BotMessage
                        import json
                        from datetime import datetime, timedelta
                        
                        with app.app_context():
                            # Buscar ou criar bot_user
                            bot_user = BotUser.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id,
                                archived=False
                            ).first()
                            
                            # Se não existe, criar (será atualizado depois no /start se necessário)
                            if not bot_user:
                                bot_user = BotUser(
                                    bot_id=bot_id,
                                    telegram_user_id=telegram_user_id,
                                    first_name=user.get('first_name', 'Usuário'),
                                    username=user.get('username', ''),
                                    archived=False
                                )
                                db.session.add(bot_user)
                                db.session.flush()  # Obter ID sem commit
                            
                            # ✅ CRÍTICO: Gerar message_id único se não existir
                            telegram_msg_id = message.get('message_id')
                            if not telegram_msg_id:
                                # Se não tem message_id, gerar um baseado no timestamp + texto
                                import hashlib
                                unique_id = f"{telegram_user_id}_{datetime.now().timestamp()}_{text[:20]}"
                                telegram_msg_id = hashlib.md5(unique_id.encode()).hexdigest()[:16]
                                logger.warning(f"⚠️ Mensagem sem message_id do Telegram, gerando ID único: {telegram_msg_id}")
                            
                            telegram_msg_id_str = str(telegram_msg_id)
                            
                            # ✅ CRÍTICO: Verificar se mensagem já foi salva (evitar duplicação)
                            # Verificar por message_id E por texto + timestamp (fallback)
                            existing_message = BotMessage.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id,
                                message_id=telegram_msg_id_str,
                                direction='incoming'
                            ).first()
                            
                            # Fallback: verificar por texto similar nos últimos 5 segundos
                            if not existing_message:
                                recent_window = datetime.now() - timedelta(seconds=5)
                                similar_message = BotMessage.query.filter(
                                    BotMessage.bot_id == bot_id,
                                    BotMessage.telegram_user_id == telegram_user_id,
                                    BotMessage.message_text == text,
                                    BotMessage.direction == 'incoming',
                                    BotMessage.created_at >= recent_window
                                ).first()
                                
                                if similar_message:
                                    existing_message = similar_message
                                    logger.debug(f"⚠️ Mensagem similar encontrada nos últimos 5s, pulando duplicação")
                            
                            if not existing_message:
                                # Salvar mensagem recebida (SEMPRE, mesmo que seja /start)
                                bot_message = BotMessage(
                                    bot_id=bot_id,
                                    bot_user_id=bot_user.id,
                                    telegram_user_id=telegram_user_id,
                                    message_id=telegram_msg_id_str,
                                    message_text=text,
                                    message_type='text',
                                    direction='incoming',
                                    is_read=False,  # Será marcada como lida quando visualizada no chat
                                    raw_data=json.dumps(message)  # Salvar dados completos para debug
                                )
                                db.session.add(bot_message)
                                
                                # Atualizar last_interaction
                                bot_user.last_interaction = datetime.now()
                                
                                db.session.commit()
                                logger.info(f"✅ Mensagem recebida salva no banco: '{text[:50]}...' (message_id: {telegram_msg_id_str})")
                            else:
                                logger.debug(f"⚠️ Mensagem já existe no banco, pulando: {telegram_msg_id_str}")
                    except Exception as e:
                        logger.error(f"❌ Erro ao salvar mensagem recebida: {e}", exc_info=True)
                        # Não interromper o fluxo se falhar ao salvar
                
                # Comando /start (com ou sem parâmetros deep linking)
                # Exemplos: "/start", "/start acesso", "/start promo123"
                if text.startswith('/start'):
                    # Extrair parâmetro do deep link (se houver)
                    start_param = None
                    if len(text) > 6 and text[6] == ' ':  # "/start " tem 7 caracteres
                        start_param = text[7:].strip()  # Tudo após "/start "
                    
                    if start_param:
                        logger.info(f"⭐ COMANDO /START com parâmetro: '{start_param}' - Enviando mensagem de boas-vindas...")
                    else:
                        logger.info(f"⭐ COMANDO /START - Enviando mensagem de boas-vindas...")
                    
                    self._handle_start_command(bot_id, token, config, chat_id, message, start_param)
                
                # ✅ SOLUÇÃO HÍBRIDA: Mensagens de texto também reiniciam o funil
                # Mas com proteções para evitar spam e problemas de tracking
                elif text and text.strip():  # Mensagem de texto não vazia
                    logger.info(f"💬 MENSAGEM DE TEXTO: '{text}' - Reiniciando funil...")
                    self._handle_text_message(bot_id, token, config, chat_id, message)
            
            # Processar callback (botões)
            elif 'callback_query' in update:
                callback = update['callback_query']
                logger.info(f"🔘 BOTÃO CLICADO: {callback.get('data')}")
                self._handle_callback_query(bot_id, token, config, callback)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar update do bot {bot_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_text_message(self, bot_id: int, token: str, config: Dict[str, Any], 
                            chat_id: int, message: Dict[str, Any]):
        """
        Processa mensagens de texto (não comandos)
        
        ✅ CORREÇÃO CRÍTICA QI 600+:
        - Verifica se há conversa ativa (mensagens do bot nos últimos 30 min)
        - Se houver conversa ativa, NÃO reinicia funil (apenas salva mensagem)
        - Se NÃO houver conversa ativa, reinicia funil (usuário retornando)
        
        PROTEÇÕES IMPLEMENTADAS:
        - Verificação de conversa ativa (30 minutos)
        - Rate limiting (máximo 1 mensagem por minuto para reiniciar funil)
        - Não envia Meta Pixel ViewContent (evita duplicação)
        """
        try:
            from app import app, db
            from models import BotUser, Bot, BotMessage
            from datetime import datetime, timedelta
            
            with app.app_context():
                # Buscar usuário
                user_from = message.get('from', {})
                telegram_user_id = str(user_from.get('id', ''))
                first_name = user_from.get('first_name', 'Usuário')
                
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).first()
                
                if not bot_user:
                    # Usuário não existe - tratar como /start
                    logger.info(f"👤 Usuário não encontrado, tratando como /start")
                    self._handle_start_command(bot_id, token, config, chat_id, message, None)
                    return
                
                now = datetime.now()
                
                # ✅ VERIFICAÇÃO CRÍTICA QI 600+: Há conversa ativa?
                # Estratégia robusta: verificar última mensagem do bot + last_interaction
                conversation_window = now - timedelta(minutes=30)
                
                # 1. Verificar última mensagem do bot enviada
                last_bot_message = BotMessage.query.filter(
                    BotMessage.bot_id == bot_id,
                    BotMessage.telegram_user_id == telegram_user_id,
                    BotMessage.direction == 'outgoing'
                ).order_by(BotMessage.created_at.desc()).first()
                
                # 2. Verificar se bot_user teve interação recente (fallback se mensagens não salvas ainda)
                recent_interaction = bot_user.last_interaction and (now - bot_user.last_interaction).total_seconds() < 1800  # 30 minutos
                
                # 3. Verificar se última mensagem do bot foi recente (dentro da janela)
                recent_bot_message = last_bot_message and (now - last_bot_message.created_at).total_seconds() < 1800
                
                # ✅ CONVERSA ATIVA: Se bot enviou mensagem recente OU teve interação recente
                has_active_conversation = recent_bot_message or (recent_interaction and bot_user.welcome_sent)
                
                if has_active_conversation:
                    # ✅ CONVERSA ATIVA: Apenas salvar mensagem, NÃO reiniciar funil
                    logger.info(f"💬 Mensagem recebida em conversa ativa: '{message.get('text', '')[:50]}...' (última msg bot: {last_bot_message.created_at.strftime('%H:%M:%S') if last_bot_message else 'N/A'}, interação recente: {recent_interaction})")
                    
                    # Atualizar última interação
                    bot_user.last_interaction = now
                    db.session.commit()
                    
                    # Mensagem já foi salva em _process_telegram_update antes desta função ser chamada
                    # Não fazer mais nada - apenas deixar a mensagem salva
                    return
                
                # ✅ SEM CONVERSA ATIVA: Usuário retornando após muito tempo
                # Verificar rate limiting para evitar spam de reinicialização
                user_key = f"{bot_id}_{telegram_user_id}"
                
                if user_key in self.rate_limit_cache:
                    last_time = self.rate_limit_cache[user_key]
                    time_diff = (now - last_time).total_seconds()
                    if time_diff < 300:  # 5 minutos entre reinicializações
                        logger.info(f"⏱️ Rate limiting: Usuário {first_name} tentou reiniciar funil muito recente ({time_diff:.1f}s atrás)")
                        # Apenas atualizar interação, não reiniciar funil
                        bot_user.last_interaction = now
                        db.session.commit()
                        return
                
                # ✅ REINICIAR FUNIL: Usuário retornou após muito tempo sem conversa
                logger.info(f"💬 Reiniciando funil para usuário retornado: {first_name} (sem conversa ativa há 30+ min)")
                
                # Atualizar cache de rate limiting
                self.rate_limit_cache[user_key] = now
                
                # Atualizar última interação no banco
                bot_user.last_interaction = now
                db.session.commit()
                
                # Enviar mensagem de boas-vindas (sem Meta Pixel)
                self._send_welcome_message_only(bot_id, token, config, chat_id, message)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem de texto: {e}")
            import traceback
            traceback.print_exc()
    
    def _send_welcome_message_only(self, bot_id: int, token: str, config: Dict[str, Any], 
                                  chat_id: int, message: Dict[str, Any]):
        """
        Envia apenas a mensagem de boas-vindas (sem Meta Pixel)
        Usado para mensagens de texto que reiniciam o funil
        """
        try:
            from app import app, db
            from models import BotUser
            from datetime import datetime
            
            with app.app_context():
                # Buscar usuário para atualizar welcome_sent
                user_from = message.get('from', {})
                telegram_user_id = str(user_from.get('id', ''))
                
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).first()
                
                # Preparar mensagem de boas-vindas
                welcome_message = config.get('welcome_message', 'Olá! Bem-vindo!')
                welcome_media_url = config.get('welcome_media_url')
                welcome_media_type = config.get('welcome_media_type', 'video')
                welcome_audio_enabled = config.get('welcome_audio_enabled', False)
                welcome_audio_url = config.get('welcome_audio_url', '')
                main_buttons = config.get('main_buttons', [])
                redirect_buttons = config.get('redirect_buttons', [])
                
                # Preparar botões
                buttons = []
                for index, btn in enumerate(main_buttons):
                    if btn.get('text') and btn.get('price'):
                        buttons.append({
                            'text': btn['text'],
                            'callback_data': f"buy_{index}"
                        })
                
                for btn in redirect_buttons:
                    if btn.get('text') and btn.get('url'):
                        buttons.append({
                            'text': btn['text'],
                            'url': btn['url']
                        })
                
                # Verificar mídia válida
                valid_media = False
                if welcome_media_url and '/c/' not in welcome_media_url and welcome_media_url.startswith('http'):
                    valid_media = True
                
                # Enviar mensagem
                if valid_media:
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=welcome_message,
                        media_url=welcome_media_url,
                        media_type=welcome_media_type,
                        buttons=buttons
                    )
                    if not result:
                        result = self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=welcome_message,
                            media_url=None,
                            media_type=None,
                            buttons=buttons
                        )
                else:
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=welcome_message,
                        media_url=None,
                        media_type=None,
                        buttons=buttons
                    )
                
                if result:
                    logger.info(f"✅ Mensagem de texto reiniciou funil com {len(buttons)} botão(ões)")
                    
                    # Marcar como enviado (sem afetar Meta Pixel)
                    if bot_user:
                        bot_user.welcome_sent = True
                        bot_user.welcome_sent_at = datetime.now()
                        db.session.commit()
                    
                    # Enviar áudio se habilitado
                    if welcome_audio_enabled and welcome_audio_url:
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="",
                            media_url=welcome_audio_url,
                            media_type='audio',
                            buttons=None
                        )
                else:
                    logger.error(f"❌ Falha ao enviar mensagem de boas-vindas")
                    
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de boas-vindas: {e}")
    
    def _handle_start_command(self, bot_id: int, token: str, config: Dict[str, Any], 
                             chat_id: int, message: Dict[str, Any], start_param: str = None):
        """
        Processa comando /start (com ou sem parâmetros de deep linking)
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot (será recarregada do banco)
            chat_id: ID do chat
            message: Dados da mensagem
            start_param: Parâmetro do deep link (ex: "acesso", "promo123", None se não houver)
        """
        try:
            # ✅ CORREÇÃO CRÍTICA: Buscar config atualizada do BANCO (não da memória)
            from app import app, db
            from models import BotUser, Bot
            from datetime import datetime  # Import explícito no escopo da função
            
            with app.app_context():
                bot = db.session.get(Bot, bot_id)
                if bot and bot.config:
                    config = bot.config.to_dict()  # Usar config do banco
                    logger.info(f"🔄 Config recarregada do banco para /start")
                else:
                    logger.warning(f"⚠️ Bot {bot_id} sem config no banco, usando padrão")
                    config = config or {}  # Fallback para config da memória
                
                # Aproveitando o app_context, registrar/atualizar usuário
                user_from = message.get('from', {})
                telegram_user_id = str(user_from.get('id', ''))
                first_name = user_from.get('first_name', 'Usuário')
                username = user_from.get('username', '')
                
                # Verificar se usuário já existe
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).first()
                
                # ============================================================================
                # ✅ EXTRAIR TRACKING DATA DO START PARAM (QI 540 - FIX CRÍTICO)
                # ============================================================================
                # Formato V3: t{base64_json} → decodifica para {p: pool_id, e: external_id, s: utm_source, c: utm_campaign, ...}
                # ============================================================================
                pool_id_from_start = None
                external_id_from_start = None
                utm_data_from_start = {}
                
                if start_param:
                    # Formato V3 com tracking completo: t{base64}
                    if start_param.startswith('t'):
                        try:
                            import base64
                            import json
                            
                            # Decodificar base64
                            tracking_encoded = start_param[1:]  # Remove 't' inicial
                            
                            # Adicionar padding se necessário
                            missing_padding = len(tracking_encoded) % 4
                            if missing_padding:
                                tracking_encoded += '=' * (4 - missing_padding)
                            
                            tracking_json = base64.urlsafe_b64decode(tracking_encoded).decode()
                            tracking_data = json.loads(tracking_json)
                            
                            # Extrair dados
                            pool_id_from_start = tracking_data.get('p')
                            external_id_from_start = tracking_data.get('e')
                            
                            # Extrair UTMs
                            if tracking_data.get('s'):
                                utm_data_from_start['utm_source'] = tracking_data['s']
                            if tracking_data.get('c'):
                                utm_data_from_start['utm_campaign'] = tracking_data['c']
                            if tracking_data.get('cc'):
                                utm_data_from_start['campaign_code'] = tracking_data['cc']
                            if tracking_data.get('f'):
                                # 🎯 TRACKING ELITE: 'f' é um HASH, buscar fbclid completo no Redis
                                fbclid_hash = tracking_data['f']
                                try:
                                    import redis
                                    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                                    fbclid_completo = r.get(f'tracking_hash:{fbclid_hash}')
                                    if fbclid_completo:
                                        utm_data_from_start['fbclid'] = fbclid_completo
                                        logger.info(f"🔑 HASH {fbclid_hash} → fbclid completo recuperado")
                                    else:
                                        # Fallback: usar hash como fbclid
                                        utm_data_from_start['fbclid'] = fbclid_hash
                                        logger.warning(f"⚠️ fbclid completo não encontrado, usando hash")
                                except:
                                    utm_data_from_start['fbclid'] = fbclid_hash
                            
                            logger.info(f"🔗 Tracking decodificado (V3): pool_id={pool_id_from_start}, " +
                                       f"external_id={external_id_from_start}, utm_source={utm_data_from_start.get('utm_source')}")
                        
                        except Exception as e:
                            logger.error(f"Erro ao decodificar tracking V3: {e}")
                    
                    # Formato fallback simples: p{pool_id}
                    elif start_param.startswith('p') and start_param[1:].isdigit():
                        try:
                            pool_id_from_start = int(start_param[1:])
                            logger.info(f"🔗 Tracking fallback: pool_id={pool_id_from_start}")
                        except Exception as e:
                            logger.error(f"Erro ao extrair pool_id do fallback: {e}")
                    
                    # Formato legado: pool_{pool_id}_{external_id}
                    elif start_param.startswith('pool_'):
                        try:
                            parts = start_param.split('_')
                            if len(parts) >= 2:
                                pool_id_from_start = int(parts[1])
                            if len(parts) >= 4:
                                external_id_from_start = '_'.join(parts[2:])
                            logger.info(f"🔗 Tracking legado: pool_id={pool_id_from_start}, external_id={external_id_from_start}")
                        except Exception as e:
                            logger.error(f"Erro ao extrair tracking legado: {e}")
                
                # ============================================================================
                # ✅ LÓGICA INTELIGENTE DE RECUPERAÇÃO AUTOMÁTICA
                # ============================================================================
                should_send_welcome = False  # Flag para controlar envio
                is_new_user = False
                
                if not bot_user:
                    # Novo usuário - criar registro
                    bot_user = BotUser(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id,
                        first_name=first_name,
                        username=username,
                        welcome_sent=False,  # Ainda não enviou
                        external_id=external_id_from_start,  # ✅ Salvar external_id
                        # ✅ SALVAR UTMs DO TRACKING (QI 540 - FIX CRÍTICO)
                        utm_source=utm_data_from_start.get('utm_source'),
                        utm_campaign=utm_data_from_start.get('utm_campaign'),
                        campaign_code=utm_data_from_start.get('campaign_code'),
                        fbclid=utm_data_from_start.get('fbclid')
                    )
                    
                    # ============================================================================
                    # 🎯 TRACKING ELITE: BUSCAR DADOS DO REDIS E ASSOCIAR
                    # ============================================================================
                    if utm_data_from_start.get('fbclid'):
                        try:
                            import redis
                            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                            
                            # fbclid pode ser hash ou completo, tentar ambos
                            fbclid_value = utm_data_from_start['fbclid']
                            tracking_key = f"tracking:{fbclid_value}"
                            tracking_json = r.get(tracking_key)
                            
                            # Se não encontrou, pode ser que fbclid seja um hash, buscar o completo
                            if not tracking_json and len(fbclid_value) <= 12:
                                # É um hash, buscar fbclid completo
                                fbclid_completo = r.get(f'tracking_hash:{fbclid_value}')
                                if fbclid_completo:
                                    tracking_key = f"tracking:{fbclid_completo}"
                                    tracking_json = r.get(tracking_key)
                                    logger.info(f"🔑 Usado hash {fbclid_value} para encontrar tracking completo")
                            
                            if tracking_json:
                                tracking_elite = json.loads(tracking_json)
                                
                                # Associar dados capturados no redirect
                                bot_user.ip_address = tracking_elite.get('ip')
                                bot_user.user_agent = tracking_elite.get('user_agent')
                                
                                # ✅ NOVO: PARSER DE DEVICE INFO E GEOLOCALIZAÇÃO
                                try:
                                    from utils.device_parser import parse_user_agent, parse_ip_to_location
                                    
                                    # Parse device (mobile/desktop, iOS/Android, etc)
                                    device_info = parse_user_agent(bot_user.user_agent)
                                    
                                    # Salvar device info com getattr seguro
                                    if hasattr(bot_user, 'device_type'):
                                        bot_user.device_type = device_info.get('device_type')
                                    if hasattr(bot_user, 'os_type'):
                                        bot_user.os_type = device_info.get('os_type')
                                    if hasattr(bot_user, 'browser'):
                                        bot_user.browser = device_info.get('browser')
                                    if hasattr(bot_user, 'device_model'):
                                        bot_user.device_model = device_info.get('device_model')
                                    
                                    logger.info(f"📱 Device parseado: {device_info}")
                                    
                                    # Parse geolocalização pelo IP
                                    if bot_user.ip_address:
                                        location_info = parse_ip_to_location(bot_user.ip_address)
                                        
                                        if hasattr(bot_user, 'customer_city'):
                                            bot_user.customer_city = location_info.get('city', 'Unknown')
                                        if hasattr(bot_user, 'customer_state'):
                                            bot_user.customer_state = location_info.get('state', 'Unknown')
                                        if hasattr(bot_user, 'customer_country'):
                                            bot_user.customer_country = location_info.get('country', 'BR')
                                        
                                        logger.info(f"🌍 Geolocalização parseada: {location_info}")
                                    
                                except Exception as e:
                                    logger.warning(f"⚠️ Erro ao parsear device/geolocalização: {e}")
                                bot_user.tracking_session_id = tracking_elite.get('session_id')
                                
                                # Parse timestamp
                                if tracking_elite.get('timestamp'):
                                    bot_user.click_timestamp = datetime.fromisoformat(tracking_elite['timestamp'])
                                
                                # ✅ CORREÇÃO CRÍTICA QI 600+: fbclid como external_id (matching Meta)
                                # grim como campaign_code (atribuição de campanha)
                                # O Meta Pixel usa fbclid hashado para matching entre PageView e Purchase
                                grim_from_redis = tracking_elite.get('grim', '')
                                fbclid_completo_redis = tracking_elite.get('fbclid')
                                
                                if fbclid_completo_redis:
                                    # ✅ PRIORIDADE MÁXIMA: fbclid como external_id (matching Meta)
                                    bot_user.fbclid = fbclid_completo_redis
                                    bot_user.external_id = fbclid_completo_redis  # Para matching com Meta
                                    logger.info(f"🎯 external_id = fbclid (matching Meta): {fbclid_completo_redis[:30]}...")
                                    
                                    # Salvar grim como campaign_code (atribuição de campanha)
                                    if grim_from_redis:
                                        bot_user.campaign_code = grim_from_redis
                                        logger.info(f"🎯 campaign_code = grim (campanha): {grim_from_redis}")
                                elif grim_from_redis:
                                    # Fallback: se só tiver grim (sem fbclid), usar grim como external_id
                                    # Mas isso reduz matching quality - melhor quando tem fbclid
                                    bot_user.external_id = grim_from_redis
                                    bot_user.campaign_code = grim_from_redis
                                    logger.warning(f"⚠️ Sem fbclid, usando grim como external_id: {grim_from_redis}")
                                
                                # Enriquecer UTMs com dados do Redis (podem ter sido perdidos no start_param)
                                if not bot_user.utm_source and tracking_elite.get('utm_source'):
                                    bot_user.utm_source = tracking_elite['utm_source']
                                if not bot_user.utm_campaign and tracking_elite.get('utm_campaign'):
                                    bot_user.utm_campaign = tracking_elite['utm_campaign']
                                if not bot_user.utm_medium:
                                    bot_user.utm_medium = tracking_elite.get('utm_medium')
                                if not bot_user.utm_content:
                                    bot_user.utm_content = tracking_elite.get('utm_content')
                                if not bot_user.utm_term:
                                    bot_user.utm_term = tracking_elite.get('utm_term')
                                
                                logger.info(f"🎯 TRACKING ELITE | Dados associados | " +
                                           f"IP={bot_user.ip_address} | " +
                                           f"Session={bot_user.tracking_session_id[:8] if bot_user.tracking_session_id else 'N/A'}...")
                                
                                # Deletar do Redis após usar (não deixar lixo)
                                r.delete(tracking_key)
                            else:
                                logger.warning(f"⚠️ TRACKING ELITE | fbclid={utm_data_from_start['fbclid'][:20]}... não encontrado no Redis (expirou?)")
                        except Exception as e:
                            logger.error(f"❌ TRACKING ELITE | Erro ao buscar Redis: {e}")
                            # Não quebrar o fluxo se Redis falhar
                    
                    logger.info(f"👤 Novo usuário criado: {first_name} | " +
                               f"external_id={external_id_from_start} | " +
                               f"utm_source={utm_data_from_start.get('utm_source')} | " +
                               f"utm_campaign={utm_data_from_start.get('utm_campaign')}")
                    
                    db.session.add(bot_user)
                    
                    # Atualizar contador do bot (bot já foi carregado acima)
                    # ✅ Contar apenas usuários ativos (não arquivados)
                    if bot:
                        bot.total_users = BotUser.query.filter_by(bot_id=bot_id, archived=False).count()
                    
                    db.session.commit()
                    logger.info(f"👤 Novo usuário registrado: {first_name} (@{username})")
                    should_send_welcome = True
                    is_new_user = True
                    
                    # ============================================================================
                    # ✅ META PIXEL: VIEWCONTENT TRACKING (NOVO USUÁRIO)
                    # ============================================================================
                    try:
                        send_meta_pixel_viewcontent_event(bot, bot_user, message, pool_id_from_start)
                    except Exception as e:
                        logger.error(f"Erro ao enviar ViewContent para Meta Pixel: {e}")
                        # Não impedir o funcionamento do bot se Meta falhar
                else:
                    # Usuário já existe - ATUALIZAR tracking data se vier no start_param
                    bot_user.last_interaction = datetime.now()
                    
                    # ✅ CRÍTICO: Atualizar external_id se vier no start_param (pode ter mudado de campanha)
                    if external_id_from_start and not bot_user.external_id:
                        bot_user.external_id = external_id_from_start
                        logger.info(f"✅ external_id atualizado do start_param: {external_id_from_start}")
                    
                    # ✅ CRÍTICO: Atualizar UTMs se vierem no start_param
                    if utm_data_from_start.get('utm_source') and not bot_user.utm_source:
                        bot_user.utm_source = utm_data_from_start['utm_source']
                    if utm_data_from_start.get('utm_campaign') and not bot_user.utm_campaign:
                        bot_user.utm_campaign = utm_data_from_start['utm_campaign']
                    if utm_data_from_start.get('campaign_code') and not bot_user.campaign_code:
                        bot_user.campaign_code = utm_data_from_start['campaign_code']
                    if utm_data_from_start.get('fbclid') and not bot_user.fbclid:
                        bot_user.fbclid = utm_data_from_start['fbclid']
                    
                    # ✅ CRÍTICO: Buscar grim do Redis se não tiver external_id ainda
                    if not bot_user.external_id and utm_data_from_start.get('fbclid'):
                        try:
                            import redis
                            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                            
                            # Tentar buscar tracking_elite pelo fbclid
                            fbclid_value = utm_data_from_start['fbclid']
                            tracking_key = f"tracking_elite:{fbclid_value}"
                            tracking_data = r.hgetall(tracking_key)
                            
                            if tracking_data and tracking_data.get('grim'):
                                bot_user.external_id = tracking_data.get('grim')
                                logger.info(f"✅ external_id recuperado do Redis (usuário existente): {bot_user.external_id}")
                            
                            # Se não encontrou, tentar buscar por hash
                            if not bot_user.external_id and len(fbclid_value) <= 12:
                                fbclid_completo = r.get(f'tracking_hash:{fbclid_value}')
                                if fbclid_completo:
                                    tracking_key = f"tracking_elite:{fbclid_completo}"
                                    tracking_data = r.hgetall(tracking_key)
                                    if tracking_data and tracking_data.get('grim'):
                                        bot_user.external_id = tracking_data.get('grim')
                                        bot_user.fbclid = fbclid_completo
                                        logger.info(f"✅ external_id recuperado do Redis (via hash): {bot_user.external_id}")
                        except Exception as redis_error:
                            logger.warning(f"⚠️ Erro ao buscar Redis para usuário existente: {redis_error}")
                    
                    # ✅ CORREÇÃO: Sempre enviar boas-vindas quando /start for digitado
                    logger.info(f"👤 Usuário retornou: {first_name} (@{username}) - external_id={bot_user.external_id or 'N/A'}")
                    should_send_welcome = True
                    
                    db.session.commit()
            
            # ============================================================================
            # ✅ ENVIAR MENSAGEM DE BOAS-VINDAS (apenas se necessário)
            # ============================================================================
            if should_send_welcome:
                welcome_message = config.get('welcome_message', 'Olá! Bem-vindo!')
                welcome_media_url = config.get('welcome_media_url')
                welcome_media_type = config.get('welcome_media_type', 'video')
                welcome_audio_enabled = config.get('welcome_audio_enabled', False)
                welcome_audio_url = config.get('welcome_audio_url', '')
                main_buttons = config.get('main_buttons', [])
                redirect_buttons = config.get('redirect_buttons', [])
                
                # Preparar botões de venda (incluir índice para identificar qual botão tem order bump)
                buttons = []
                for index, btn in enumerate(main_buttons):
                    if btn.get('text') and btn.get('price'):
                        buttons.append({
                            'text': btn['text'],
                            'callback_data': f"buy_{index}"  # ✅ CORREÇÃO: Usar apenas o índice (max 10 bytes)
                        })
                
                # Adicionar botões de redirecionamento (com URL)
                for btn in redirect_buttons:
                    if btn.get('text') and btn.get('url'):
                        buttons.append({
                            'text': btn['text'],
                            'url': btn['url']  # Botão com URL abre direto no navegador
                        })
                
                # Verificar se URL de mídia é válida (não pode ser canal privado)
                valid_media = False
                if welcome_media_url:
                    # URLs de canais privados começam com /c/ - não funcionam
                    if '/c/' not in welcome_media_url and welcome_media_url.startswith('http'):
                        valid_media = True
                    else:
                        logger.info(f"⚠️ Mídia de canal privado detectada - enviando só texto")
                
                if valid_media:
                    # Tentar com mídia
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=welcome_message,
                        media_url=welcome_media_url,
                        media_type=welcome_media_type,
                        buttons=buttons
                    )
                    if not result:
                        logger.warning(f"⚠️ Falha com mídia. Enviando só texto...")
                        result = self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=welcome_message,
                            media_url=None,
                            media_type=None,
                            buttons=buttons
                        )
                else:
                    # Enviar direto sem mídia (mais rápido e confiável)
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=welcome_message,
                        media_url=None,
                        media_type=None,
                        buttons=buttons
                    )
                
                if result:
                    logger.info(f"✅ Mensagem /start enviada com {len(buttons)} botão(ões)")
                    
                    # ✅ MARCAR COMO ENVIADO NO BANCO
                    with app.app_context():
                        try:
                            bot_user_update = BotUser.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id
                            ).first()
                            if bot_user_update:
                                bot_user_update.welcome_sent = True
                                bot_user_update.welcome_sent_at = datetime.now()
                                db.session.commit()
                                logger.info(f"✅ Marcado como welcome_sent=True")
                        except Exception as e:
                            logger.error(f"Erro ao marcar welcome_sent: {e}")
                    
                    # ✅ Enviar áudio adicional se habilitado
                    if welcome_audio_enabled and welcome_audio_url:
                        logger.info(f"🎤 Enviando áudio complementar...")
                        audio_result = self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="",  # Sem caption
                            media_url=welcome_audio_url,
                            media_type='audio',
                            buttons=None  # Sem botões no áudio
                        )
                        if audio_result:
                            logger.info(f"✅ Áudio complementar enviado")
                        else:
                            logger.warning(f"⚠️ Falha ao enviar áudio complementar")
                else:
                    logger.error(f"❌ Falha ao enviar mensagem")
            else:
                logger.info(f"⏭️ Mensagem de boas-vindas já foi enviada antes, pulando...")
            
            # Emitir evento via WebSocket
            self.socketio.emit('bot_interaction', {
                'bot_id': bot_id,
                'type': 'start',
                'chat_id': chat_id,
                'user': message.get('from', {}).get('first_name', 'Usuário')
            })
            
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar /start: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_callback_query(self, bot_id: int, token: str, config: Dict[str, Any], 
                               callback: Dict[str, Any]):
        """
        Processa clique em botão e GERA PIX
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot
            callback: Dados do callback
        """
        try:
            callback_data = callback.get('data', '')
            chat_id = callback['message']['chat']['id']
            user_info = callback.get('from', {})
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🔘 CLIQUE NO BOTÃO: {callback_data}")
            logger.info(f"👤 Cliente: {user_info.get('first_name')}")
            logger.info(f"{'='*60}")
            
            callback_id = callback['id']
            url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
            
            # Botão de VERIFICAR PAGAMENTO
            if callback_data.startswith('verify_'):
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔍 Verificando pagamento...'
                }, timeout=3)
                payment_id = callback_data.replace('verify_', '')
                logger.info(f"🔍 Verificando pagamento: {payment_id}")
                
                self._handle_verify_payment(bot_id, token, chat_id, payment_id, user_info)
            
            # ✅ NOVO: Botão de REMARKETING (formato simplificado)
            elif callback_data.startswith('rmkt_'):
                # Formato: rmkt_CAMPAIGN_ID_BUTTON_INDEX
                parts = callback_data.replace('rmkt_', '').split('_')
                campaign_id = int(parts[0])
                btn_idx = int(parts[1])
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando PIX da oferta...'
                }, timeout=3)
                
                # Buscar dados da campanha e botão
                from app import app, db
                from models import RemarketingCampaign
                
                with app.app_context():
                    campaign = db.session.get(RemarketingCampaign, campaign_id)
                    if campaign and campaign.buttons:
                        # ✅ CORREÇÃO: Parsear JSON se for string
                        buttons_list = campaign.buttons
                        if isinstance(campaign.buttons, str):
                            import json
                            try:
                                buttons_list = json.loads(campaign.buttons)
                            except:
                                buttons_list = []
                        
                        if btn_idx < len(buttons_list):
                            btn = buttons_list[btn_idx]
                            price = float(btn.get('price', 0))
                            description = btn.get('description', 'Produto Remarketing')
                    else:
                        price = 0
                        description = 'Produto Remarketing'
                
                logger.info(f"📢 COMPRA VIA REMARKETING | Campanha: {campaign_id} | Produto: {description} | Valor: R$ {price:.2f}")
                
                # Gerar PIX direto (sem order bump em remarketing)
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', ''))
                )
                
                if pix_data and pix_data.get('pix_code'):
                    # ✅ PIX em linha única dentro de <code> para copiar com um toque
                    payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data.get('pix_code')}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                    
                    verify_button = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f"verify_{pix_data.get('payment_id')}"
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message,
                        buttons=verify_button
                    )
                    
                    logger.info(f"✅ PIX ENVIADO (Remarketing)! ID: {pix_data.get('payment_id')}")
                    
                    # Atualizar stats da campanha
                    from app import app, db
                    from models import RemarketingCampaign
                    with app.app_context():
                        campaign = RemarketingCampaign.query.get(campaign_id)
                        if campaign:
                            campaign.total_clicks += 1
                            db.session.commit()
                else:
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                    )
            
            # Resposta do ORDER BUMP - SIM
            elif callback_data.startswith('bump_yes_'):
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '✅ Order bump adicionado! Gerando PIX...'
                }, timeout=3)
                
                # ✅ NOVO FORMATO: bump_yes_INDEX
                button_index = int(callback_data.replace('bump_yes_', ''))
                
                # Buscar dados do botão e order bump pela configuração
                main_buttons = config.get('main_buttons', [])
                if button_index < len(main_buttons):
                    button_data = main_buttons[button_index]
                    original_price = float(button_data.get('price', 0))
                    description = button_data.get('description', 'Produto')
                    order_bump = button_data.get('order_bump', {})
                    bump_price = float(order_bump.get('price', 0))
                else:
                    original_price = 0
                    bump_price = 0
                    description = 'Produto'
                
                total_price = original_price + bump_price
                final_description = f"{description} + Bônus"
                
                logger.info(f"✅ Cliente ACEITOU order bump! Total: R$ {total_price:.2f}")
                
                # Gerar PIX com valor TOTAL (produto + order bump) + ANALYTICS
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=total_price,
                    description=final_description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    order_bump_shown=True,
                    order_bump_accepted=True,
                    order_bump_value=bump_price
                )
                
                if pix_data and pix_data.get('pix_code'):
                    # ✅ PIX em linha única dentro de <code> para copiar com um toque
                    payment_message = f"""🎯 <b>Produto:</b> {final_description}
💰 <b>Valor:</b> R$ {total_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX gerado COM order bump!")
                    
                    # ✅ CORREÇÃO: Buscar config atualizada do BANCO (não da memória)
                    from app import app, db
                    from models import Bot as BotModel
                    
                    with app.app_context():
                        bot = db.session.get(BotModel, bot_id)
                        if bot and bot.config:
                            config = bot.config.to_dict()
                        else:
                            config = {}
                    
                    logger.info(f"🔍 DEBUG Downsells (Order Bump) - bot_id: {bot_id}")
                    logger.info(f"🔍 DEBUG Downsells (Order Bump) - enabled: {config.get('downsells_enabled', False)}")
                    logger.info(f"🔍 DEBUG Downsells (Order Bump) - list: {config.get('downsells', [])}")
                    
                    if config.get('downsells_enabled', False):
                        downsells = config.get('downsells', [])
                        logger.info(f"🔍 DEBUG Downsells (Order Bump) - downsells encontrados: {len(downsells)}")
                        if downsells and len(downsells) > 0:
                            self.schedule_downsells(
                                bot_id=bot_id,
                                payment_id=pix_data.get('payment_id'),
                                chat_id=chat_id,
                                downsells=downsells,
                                original_price=total_price,  # ✅ Preço com order bump
                                original_button_index=button_index
                            )
                        else:
                            logger.warning(f"⚠️ Downsells habilitados mas lista vazia! (Order Bump)")
                    else:
                        logger.info(f"ℹ️ Downsells desabilitados ou não configurados (Order Bump)")
            
            # Resposta do ORDER BUMP - NÃO
            elif callback_data.startswith('bump_no_'):
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando PIX do valor original...'
                }, timeout=3)
                
                # ✅ NOVO FORMATO: bump_no_INDEX
                button_index = int(callback_data.replace('bump_no_', ''))
                
                # Buscar dados do botão pela configuração
                main_buttons = config.get('main_buttons', [])
                if button_index < len(main_buttons):
                    button_data = main_buttons[button_index]
                    price = float(button_data.get('price', 0))
                    description = button_data.get('description', 'Produto')
                else:
                    price = 0
                    description = 'Produto'
                
                logger.info(f"❌ Cliente RECUSOU order bump. Gerando PIX do valor original...")
                
                # Gerar PIX com valor ORIGINAL (sem order bump) + ANALYTICS
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    order_bump_shown=True,
                    order_bump_accepted=False,
                    order_bump_value=0.0
                )
                
                if pix_data and pix_data.get('pix_code'):
                    # ✅ PIX em linha única dentro de <code> para copiar com um toque
                    payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX gerado SEM order bump!")
                    
                    # ✅ CORREÇÃO: Buscar config atualizada do BANCO (não da memória)
                    from app import app, db
                    from models import Bot as BotModel
                    
                    with app.app_context():
                        bot = db.session.get(BotModel, bot_id)
                        if bot and bot.config:
                            config = bot.config.to_dict()
                        else:
                            config = {}
                    
                    logger.info(f"🔍 DEBUG Downsells (bump_no) - bot_id: {bot_id}")
                    logger.info(f"🔍 DEBUG Downsells (bump_no) - enabled: {config.get('downsells_enabled', False)}")
                    logger.info(f"🔍 DEBUG Downsells (bump_no) - list: {config.get('downsells', [])}")
                    
                    if config.get('downsells_enabled', False):
                        downsells = config.get('downsells', [])
                        logger.info(f"🔍 DEBUG Downsells (bump_no) - downsells encontrados: {len(downsells)}")
                        if downsells and len(downsells) > 0:
                            self.schedule_downsells(
                                bot_id=bot_id,
                                payment_id=pix_data.get('payment_id'),
                                chat_id=chat_id,
                                downsells=downsells,
                                original_price=price,  # ✅ Preço original (sem order bump)
                                original_button_index=button_index
                            )
                        else:
                            logger.warning(f"⚠️ Downsells habilitados mas lista vazia! (bump_no)")
                    else:
                        logger.info(f"ℹ️ Downsells desabilitados ou não configurados (bump_no)")
            
            # ✅ NOVO: Múltiplos Order Bumps - Aceitar
            elif callback_data.startswith('multi_bump_yes_'):
                # Formato: multi_bump_yes_USER_KEY_BUMP_INDEX_TOTAL_PRICE_CENTAVOS
                parts = callback_data.replace('multi_bump_yes_', '').split('_')
                user_key = f"{parts[0]}_{parts[1]}"
                bump_index = int(parts[2])
                total_price = float(parts[3]) / 100  # Converter centavos para reais
                
                logger.info(f"🎁 Order Bump {bump_index + 1} ACEITO | User: {user_key} | Valor Total: R$ {total_price:.2f}")
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '✅ Bônus adicionado!'
                }, timeout=3)
                
                # Atualizar sessão
                if user_key in self.order_bump_sessions:
                    session = self.order_bump_sessions[user_key]
                    current_bump = session['order_bumps'][bump_index]
                    bump_price = float(current_bump.get('price', 0))
                    
                    # Adicionar bump aceito
                    session['accepted_bumps'].append(current_bump)
                    session['total_bump_value'] += bump_price
                    session['current_index'] = bump_index + 1
                    
                    logger.info(f"🎁 Bump aceito: {current_bump.get('description', 'Bônus')} (+R$ {bump_price:.2f})")
                    
                    # Exibir próximo order bump ou finalizar
                    self._show_next_order_bump(bot_id, token, chat_id, user_key)
                else:
                    logger.error(f"❌ Sessão de order bump não encontrada: {user_key}")
            
            # ✅ NOVO: Múltiplos Order Bumps - Recusar
            elif callback_data.startswith('multi_bump_no_'):
                # Formato: multi_bump_no_USER_KEY_BUMP_INDEX_CURRENT_PRICE_CENTAVOS
                parts = callback_data.replace('multi_bump_no_', '').split('_')
                user_key = f"{parts[0]}_{parts[1]}"
                bump_index = int(parts[2])
                current_price = float(parts[3]) / 100  # Converter centavos para reais
                
                logger.info(f"🎁 Order Bump {bump_index + 1} RECUSADO | User: {user_key} | Valor Atual: R$ {current_price:.2f}")
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '❌ Bônus recusado'
                }, timeout=3)
                
                # Atualizar sessão
                if user_key in self.order_bump_sessions:
                    session = self.order_bump_sessions[user_key]
                    session['current_index'] = bump_index + 1
                    
                    logger.info(f"🎁 Bump recusado: {session['order_bumps'][bump_index].get('description', 'Bônus')}")
                    
                    # Exibir próximo order bump ou finalizar
                    self._show_next_order_bump(bot_id, token, chat_id, user_key)
                else:
                    logger.error(f"❌ Sessão de order bump não encontrada: {user_key}")
            
            # ✅ NOVO: Order Bump Downsell - Aceitar
            elif callback_data.startswith('downsell_bump_yes_'):
                # Formato: downsell_bump_yes_DOWNSELL_INDEX_TOTAL_PRICE_CENTAVOS
                parts = callback_data.replace('downsell_bump_yes_', '').split('_')
                downsell_idx = int(parts[0])
                total_price = float(parts[1]) / 100  # Converter centavos para reais
                
                logger.info(f"🎁 Order Bump Downsell ACEITO | Downsell: {downsell_idx} | Valor Total: R$ {total_price:.2f}")
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
                
                # Gerar PIX com valor total (downsell + order bump)
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=total_price,
                    description=f"Oferta Especial + Bônus",
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    order_bump_shown=True,
                    order_bump_accepted=True,
                    order_bump_value=total_price - (total_price * 0.7),  # Estimativa do bump
                    is_downsell=True,
                    downsell_index=downsell_idx
                )
                
                if pix_data and pix_data.get('pix_code'):
                    payment_message = f"""🎯 <b>Produto:</b> Oferta Especial + Bônus
💰 <b>Valor:</b> R$ {total_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX DOWNSELL COM ORDER BUMP ENVIADO! ID: {pix_data.get('payment_id')}")
                else:
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                    )
            
            # ✅ NOVO: Order Bump Downsell - Recusar
            elif callback_data.startswith('downsell_bump_no_'):
                # Formato: downsell_bump_no_DOWNSELL_INDEX_DOWNSELL_PRICE_CENTAVOS
                parts = callback_data.replace('downsell_bump_no_', '').split('_')
                downsell_idx = int(parts[0])
                downsell_price = float(parts[1]) / 100  # Converter centavos para reais
                
                logger.info(f"🎁 Order Bump Downsell RECUSADO | Downsell: {downsell_idx} | Valor: R$ {downsell_price:.2f}")
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
                
                # Gerar PIX apenas com valor do downsell (sem order bump)
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=downsell_price,
                    description="Oferta Especial",
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    order_bump_shown=True,
                    order_bump_accepted=False,
                    order_bump_value=0.0,
                    is_downsell=True,
                    downsell_index=downsell_idx
                )
                
                if pix_data and pix_data.get('pix_code'):
                    payment_message = f"""🎯 <b>Produto:</b> Oferta Especial
💰 <b>Valor:</b> R$ {downsell_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX DOWNSELL SEM ORDER BUMP ENVIADO! ID: {pix_data.get('payment_id')}")
                else:
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                    )
            
            # ✅ NOVO: Downsell com formato simplificado
            elif callback_data.startswith('dwnsl_'):
                # ✅ NOVO FORMATO PERCENTUAL: dwnsl_DOWNSELL_IDX_BUTTON_IDX_PRICE_CENTAVOS
                # Este formato é usado quando o downsell tem modo percentual e mostra múltiplos botões
                parts = callback_data.replace('dwnsl_', '').split('_')
                downsell_idx = int(parts[0])
                button_idx = int(parts[1])
                price = float(parts[2]) / 100  # Converter centavos para reais
                
                # Buscar configuração para pegar nome do produto
                # ✅ Recarregar config do banco (pode ter sido alterada)
                from app import app, db
                from models import Bot as BotModel
                
                product_name = f'Produto {button_idx + 1}'  # Default
                description = f"Downsell {downsell_idx + 1} - {product_name}"
                
                with app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        fresh_config = bot.config.to_dict()
                        main_buttons = fresh_config.get('main_buttons', [])
                        if button_idx < len(main_buttons):
                            product_name = main_buttons[button_idx].get('text', product_name)
                            description = f"{product_name} (Downsell {downsell_idx + 1})"
                
                logger.info(f"💜 DOWNSELL PERCENTUAL CLICADO | Downsell: {downsell_idx} | Produto: {product_name} | Valor: R$ {price:.2f}")
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
                
                # Gerar PIX do downsell
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    is_downsell=True,
                    downsell_index=downsell_idx
                )
                
                if pix_data and pix_data.get('pix_code'):
                    payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX DOWNSELL PERCENTUAL ENVIADO! ID: {pix_data.get('payment_id')}")
                else:
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                    )
            
            elif callback_data.startswith('downsell_'):
                # Formato: downsell_INDEX_PRICE_CENTAVOS_BUTTON_INDEX
                parts = callback_data.replace('downsell_', '').split('_')
                logger.info(f"🔍 DEBUG downsell callback_data: {callback_data}")
                logger.info(f"🔍 DEBUG downsell parts: {parts}")
                
                downsell_idx = int(parts[0])
                
                # ✅ CORREÇÃO: Detectar formato antigo vs novo
                if len(parts) == 4:
                    # Formato antigo: downsell_INDEX_BUTTON_PRICE_BUTTON
                    original_button_idx = int(parts[1])
                    price_cents = int(parts[2])
                    logger.info(f"🔍 Formato ANTIGO detectado: idx={downsell_idx}, btn={original_button_idx}, price_cents={price_cents}")
                elif len(parts) == 3:
                    # Formato novo: downsell_INDEX_PRICE_BUTTON
                    price_cents = int(parts[1])
                    original_button_idx = int(parts[2])
                    logger.info(f"🔍 Formato NOVO detectado: idx={downsell_idx}, price_cents={price_cents}, btn={original_button_idx}")
                else:
                    logger.error(f"❌ Formato de callback_data inválido: {callback_data}")
                    return
                
                price = float(price_cents) / 100  # Converter centavos para reais
                
                logger.info(f"🔍 DEBUG downsell parsed: idx={downsell_idx}, price_cents={price_cents}, price={price:.2f}, original_button={original_button_idx}")
                
                # ✅ VALIDAÇÃO: Preço deve ser > 0
                if price <= 0:
                    logger.error(f"❌ Downsell com preço inválido: R$ {price:.2f} (centavos: {price_cents})")
                    logger.error(f"❌ CALLBACK_DATA PROBLEMÁTICO: {callback_data}")
                    logger.error(f"❌ PARTS PROBLEMÁTICAS: {parts}")
                    return
                
                # ✅ CORREÇÃO CRÍTICA: Se preço for muito baixo, calcular valor real do downsell
                if price < 1.00:  # Menos de R$ 1,00
                    logger.warning(f"⚠️ Downsell com preço muito baixo (R$ {price:.2f}), calculando valor real")
                    
                    # ✅ CORREÇÃO: Buscar configuração do downsell para calcular valor real
                    from app import app, db
                    from models import Bot as BotModel
                    
                    with app.app_context():
                        bot = db.session.get(BotModel, bot_id)
                        if bot and bot.config:
                            config = bot.config.to_dict()
                            downsells = config.get('downsells', [])
                            
                            if downsell_idx < len(downsells):
                                downsell_config = downsells[downsell_idx]
                                discount_percentage = float(downsell_config.get('discount_percentage', 50))
                                
                                # ✅ CORREÇÃO: Usar preço original do botão clicado
                                main_buttons = config.get('main_buttons', [])
                                if original_button_idx < len(main_buttons):
                                    original_button = main_buttons[original_button_idx]
                                    original_price = float(original_button.get('price', 0))
                                    
                                    if original_price > 0:
                                        price = original_price * (1 - discount_percentage / 100)
                                        logger.info(f"✅ Valor real calculado: R$ {original_price:.2f} com {discount_percentage}% OFF = R$ {price:.2f}")
                                    else:
                                        price = 9.97  # Fallback
                                        logger.warning(f"⚠️ Preço original não encontrado, usando fallback R$ {price:.2f}")
                                else:
                                    price = 9.97  # Fallback
                                    logger.warning(f"⚠️ Botão original não encontrado, usando fallback R$ {price:.2f}")
                            else:
                                price = 9.97  # Fallback
                                logger.warning(f"⚠️ Configuração de downsell não encontrada, usando fallback R$ {price:.2f}")
                        else:
                            price = 9.97  # Fallback
                            logger.warning(f"⚠️ Configuração do bot não encontrada, usando fallback R$ {price:.2f}")
                
                # ✅ QI 500 FIX V2: Buscar descrição do BOTÃO ORIGINAL que gerou o downsell
                from app import app, db
                from models import Bot as BotModel
                
                # Default seguro (sem índice de downsell)
                description = "Oferta Especial"
                
                with app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        fresh_config = bot.config.to_dict()
                        main_buttons = fresh_config.get('main_buttons', [])
                        
                        # Buscar o botão ORIGINAL (não o índice do downsell)
                        if original_button_idx >= 0 and original_button_idx < len(main_buttons):
                            button_data = main_buttons[original_button_idx]
                            product_name = button_data.get('description') or button_data.get('text') or f'Produto {original_button_idx + 1}'
                            description = f"{product_name} (Downsell)"
                            logger.info(f"✅ Descrição do produto original encontrada: {product_name}")
                        else:
                            # Fallback: Se não encontrar o botão, usar genérico
                            description = "Oferta Especial (Downsell)"
                            logger.warning(f"⚠️ Botão original {original_button_idx} não encontrado em {len(main_buttons)} botões")
                
                button_index = -1  # Sinalizar que é downsell
                
                logger.info(f"💙 DOWNSELL FIXO CLICADO | Downsell: {downsell_idx} | Botão Original: {original_button_idx} | Produto: {description} | Valor: R$ {price:.2f}")
                
                # ✅ VERIFICAR SE TEM ORDER BUMP PARA ESTE DOWNSELL
                from app import app, db
                from models import Bot as BotModel
                
                order_bump = None
                with app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                        downsells = config.get('downsells', [])
                        
                        if downsell_idx < len(downsells):
                            downsell_config = downsells[downsell_idx]
                            order_bump = downsell_config.get('order_bump', {})
                
                if order_bump and order_bump.get('enabled'):
                    # Responder callback - AGUARDANDO order bump
                    requests.post(url, json={
                        'callback_query_id': callback_id,
                        'text': '🎁 Oferta especial para você!'
                    }, timeout=3)
                    
                    logger.info(f"🎁 Order Bump detectado para downsell {downsell_idx + 1}!")
                    self._show_downsell_order_bump(bot_id, token, chat_id, user_info, 
                                                 price, description, downsell_idx, order_bump)
                    return  # Aguarda resposta do order bump
                
                # SEM ORDER BUMP - Gerar PIX direto
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
                
                # Gerar PIX do downsell
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    is_downsell=True,
                    downsell_index=downsell_idx
                )
                
                if pix_data and pix_data.get('pix_code'):
                    # ✅ PIX em linha única dentro de <code> para copiar com um toque
                    payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                    
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX DOWNSELL ENVIADO! ID: {pix_data.get('payment_id')}")
                else:
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                    )
            
            # Botão de compra (VERIFICAR SE TEM ORDER BUMP)
            elif callback_data.startswith('buy_'):
                # ✅ NOVO FORMATO: buy_INDEX (mais simples, evita BUTTON_DATA_INVALID)
                # Extrair índice do botão
                button_index = int(callback_data.replace('buy_', ''))
                
                # Buscar dados do botão pela configuração
                main_buttons = config.get('main_buttons', [])
                if button_index < len(main_buttons):
                    button_data = main_buttons[button_index]
                    price = float(button_data.get('price', 0))
                    description = button_data.get('description', 'Produto')
                else:
                    price = 0
                    description = 'Produto'
                
                logger.info(f"💰 Produto: {description} | Valor: R$ {price:.2f} | Botão: {button_index}")
                
                # ✅ VERIFICAR SE TEM ORDER BUMPS PARA ESTE BOTÃO
                order_bumps = button_data.get('order_bumps', []) if button_index < len(main_buttons) else []
                enabled_order_bumps = [bump for bump in order_bumps if bump.get('enabled')]
                
                if enabled_order_bumps:
                    # Responder callback - AGUARDANDO order bump
                    requests.post(url, json={
                        'callback_query_id': callback_id,
                        'text': '🎁 Oferta especial para você!'
                    }, timeout=3)
                    
                    logger.info(f"🎁 {len(enabled_order_bumps)} Order Bumps detectados para este botão!")
                    self._show_multiple_order_bumps(bot_id, token, chat_id, user_info, 
                                                   price, description, button_index, enabled_order_bumps)
                    return  # Aguarda resposta dos order bumps
                
                # SEM ORDER BUMP - Gerar PIX direto
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
                
                logger.info(f"📝 Sem order bump - gerando PIX direto...")
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', ''))
                )
                
                if pix_data and pix_data.get('pix_code'):
                    # Enviar PIX para o cliente
                    payment_message = f"""
🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque para copiar o código PIX</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>
                    """
                    
                    # Botão para VERIFICAR PAGAMENTO
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"✅ PIX ENVIADO! ID: {pix_data.get('payment_id')}")
                    
                    # ✅ CORREÇÃO: Buscar config atualizada do BANCO (não da memória)
                    from app import app, db
                    from models import Bot as BotModel
                    
                    with app.app_context():
                        bot = db.session.get(BotModel, bot_id)
                        if bot and bot.config:
                            config = bot.config.to_dict()
                        else:
                            config = {}
                    
                    logger.info(f"🔍 DEBUG Downsells - bot_id: {bot_id}")
                    logger.info(f"🔍 DEBUG Downsells - enabled: {config.get('downsells_enabled', False)}")
                    logger.info(f"🔍 DEBUG Downsells - list type: {type(config.get('downsells', []))}")
                    logger.info(f"🔍 DEBUG Downsells - list content: {config.get('downsells', [])}")
                    
                    if config.get('downsells_enabled', False):
                        downsells = config.get('downsells', [])
                        logger.info(f"🔍 DEBUG Downsells - downsells encontrados: {len(downsells)}")
                        logger.info(f"🔍 DEBUG Downsells - is empty?: {len(downsells) == 0}")
                        if downsells and len(downsells) > 0:
                            self.schedule_downsells(
                                bot_id=bot_id,
                                payment_id=pix_data.get('payment_id'),
                                chat_id=chat_id,
                                downsells=downsells,
                                original_price=price,  # ✅ Preço do botão clicado
                                original_button_index=button_index
                            )
                        else:
                            logger.warning(f"⚠️ Downsells habilitados mas lista vazia!")
                    else:
                        logger.info(f"ℹ️ Downsells desabilitados ou não configurados")
                    
                    logger.info(f"{'='*60}\n")
                elif pix_data is not None and pix_data.get('rate_limit'):
                    # Rate limit ativado: cliente já tem PIX pendente e quer gerar outro
                    logger.warning(f"⚠️ Rate limit: cliente precisa aguardar {pix_data.get('wait_time')}")
                    
                    rate_limit_message = f"""
⏳ <b>AGUARDE PARA GERAR NOVO PIX</b>

Você já tem um PIX pendente para outro produto.

⏰ <b>Por favor, aguarde {pix_data.get('wait_time', 'alguns segundos')}</b> para gerar um novo PIX para um produto diferente.

💡 <b>Ou:</b> Pague o PIX atual e depois gere um novo PIX.

<i>Você pode verificar seu PIX atual em "Verificar Pagamento"</i>
                    """
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=rate_limit_message.strip()
                    )
                elif pix_data is None:
                    # PIX não foi gerado (erro no gateway)
                    logger.error(f"❌ pix_data é None - erro no gateway")
                    error_message = """
❌ <b>ERRO AO GERAR PAGAMENTO</b>

Desculpe, não foi possível processar seu pagamento.

<b>Entre em contato com o suporte.</b>
                    """
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=error_message.strip()
                    )
                else:
                    # Erro CRÍTICO ao gerar PIX
                    logger.error(f"❌ FALHA CRÍTICA: Não foi possível gerar PIX!")
                    logger.error(f"Verifique suas credenciais no painel!")
                    
                    error_message = """
❌ <b>ERRO AO GERAR PAGAMENTO</b>

Desculpe, não foi possível processar seu pagamento.

<b>Entre em contato com o suporte.</b>
                    """
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=error_message.strip()
                    )
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar callback: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_verify_payment(self, bot_id: int, token: str, chat_id: int, 
                               payment_id: str, user_info: Dict[str, Any]):
        """
        Verifica status do pagamento e libera acesso se pago
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            payment_id: ID do pagamento
            user_info: Informações do usuário
        """
        try:
            from models import Payment, Bot, Gateway, db
            from app import app
            
            with app.app_context():
                # Buscar pagamento no banco
                payment = Payment.query.filter_by(payment_id=payment_id).first()
                
                if not payment:
                    logger.warning(f"⚠️ Pagamento não encontrado: {payment_id}")
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Pagamento não encontrado. Entre em contato com o suporte."
                    )
                    return
                
                logger.info(f"📊 Status do pagamento LOCAL: {payment.status}")
                
                # ✅ PARADISE: Consulta manual DESATIVADA (usa apenas webhooks)
                # O job automático (check_paradise_pending_sales.py) processa pagamentos a cada 2 minutos
                # Se Paradise enviar webhook, o sistema marca automaticamente
                # Ao clicar em "Verificar Pagamento", apenas verifica o status NO BANCO
                if payment.status == 'pending':
                    if payment.gateway_type == 'paradise':
                        logger.info(f"📡 Paradise: Webhook será processado automaticamente pelo job")
                        logger.info(f"⏰ Se pagamento já está aprovado no painel Paradise, aguarde até 2 minutos")
                    else:
                        # Outros gateways podem ter consulta manual
                        logger.info(f"🔍 Gateway {payment.gateway_type}: Consultando status na API...")
                        
                        bot = payment.bot
                        gateway = Gateway.query.filter_by(
                            user_id=bot.user_id,
                            gateway_type=payment.gateway_type,
                            is_verified=True
                        ).first()
                        
                        if gateway:
                            # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
                            # Prioridade: user.commission_percentage > gateway.split_percentage > 2.0 (padrão)
                            user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
                            
                            credentials = {
                                'client_id': gateway.client_id,
                                'client_secret': gateway.client_secret,
                                'api_key': gateway.api_key,
                                'product_hash': gateway.product_hash,
                                'offer_hash': gateway.offer_hash,
                                'store_id': gateway.store_id,
                                'split_user_id': gateway.split_user_id,
                                'split_percentage': user_commission
                            }
                            
                            payment_gateway = GatewayFactory.create_gateway(
                                gateway_type=payment.gateway_type,
                                credentials=credentials
                            )
                            
                            if payment_gateway:
                                # ✅ TODOS os gateways aceitam apenas 1 argumento (transaction_id)
                                api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                                
                                if api_status and api_status.get('status') == 'paid':
                                    if payment.status == 'pending':
                                        logger.info(f"✅ API confirmou pagamento! Atualizando status...")
                                        payment.status = 'paid'
                                        payment.paid_at = datetime.now()
                                        payment.bot.total_sales += 1
                                        payment.bot.total_revenue += payment.amount
                                        payment.bot.owner.total_sales += 1
                                        payment.bot.owner.total_revenue += payment.amount
                                        
                                        # ✅ META PIXEL PURCHASE (ANTES DO COMMIT!)
                                        try:
                                            from app import send_meta_pixel_purchase_event
                                            logger.info(f"📊 Disparando Meta Pixel Purchase para {payment.payment_id}")
                                            send_meta_pixel_purchase_event(payment)
                                            logger.info(f"✅ Meta Pixel Purchase enviado")
                                        except Exception as e:
                                            logger.error(f"❌ Erro ao enviar Meta Purchase: {e}")
                                        
                                        db.session.commit()
                                        logger.info(f"💾 Pagamento atualizado via consulta ativa")
                                        
                                        # ✅ CRÍTICO: Recarregar objeto do banco para garantir status atualizado
                                        db.session.refresh(payment)
                                        
                                        # ✅ VERIFICAR CONQUISTAS
                                        try:
                                            from app import check_and_unlock_achievements
                                            new_achievements = check_and_unlock_achievements(payment.bot.owner)
                                            if new_achievements:
                                                logger.info(f"🏆 {len(new_achievements)} conquista(s) desbloqueada(s)!")
                                        except Exception as e:
                                            logger.warning(f"⚠️ Erro ao verificar conquistas: {e}")
                                elif api_status:
                                    logger.info(f"⏳ API retornou status: {api_status.get('status')}")
                
                # ✅ CRÍTICO: Recarregar objeto do banco antes de verificar status final
                db.session.refresh(payment)
                logger.info(f"📊 Status FINAL do pagamento: {payment.status}")
                
                if payment.status == 'paid':
                    # PAGAMENTO CONFIRMADO! Liberar acesso
                    logger.info(f"✅ PAGAMENTO CONFIRMADO! Liberando acesso...")
                    
                    # ============================================================================
                    # ⚠️ META PIXEL REMOVIDO AQUI - JÁ FOI DISPARADO NA CONSULTA ATIVA (linha 2144)
                    # ============================================================================
                    
                    # Cancelar downsells agendados
                    self.cancel_downsells(payment.payment_id)
                    
                    bot = payment.bot
                    bot_config = self.active_bots.get(bot_id, {}).get('config', {})
                    access_link = bot_config.get('access_link', '')
                    custom_success_message = bot_config.get('success_message', '').strip()
                    
                    # Usar mensagem personalizada ou padrão
                    if custom_success_message:
                        # Substituir variáveis
                        success_message = custom_success_message
                        success_message = success_message.replace('{produto}', payment.product_name or 'Produto')
                        success_message = success_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                        success_message = success_message.replace('{link}', access_link or 'Link não configurado')
                    elif access_link:
                        success_message = f"""
✅ <b>PAGAMENTO CONFIRMADO!</b>

🎉 <b>Parabéns!</b> Seu pagamento foi aprovado com sucesso!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor pago:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

<b>Aproveite!</b> 🚀
                        """
                    else:
                        success_message = "✅ Pagamento confirmado! Entre em contato com o suporte para receber seu acesso."
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=success_message.strip()
                    )
                    
                    logger.info(f"✅ Acesso liberado para {user_info.get('first_name')}")
                else:
                    # PAGAMENTO AINDA PENDENTE
                    logger.info(f"⏳ Pagamento ainda pendente...")
                    
                    bot = payment.bot
                    bot_config = self.active_bots.get(bot_id, {}).get('config', {})
                    custom_pending_message = bot_config.get('pending_message', '').strip()
                    pix_code = payment.product_description or 'Aguardando...'
                    
                    # Usar mensagem personalizada ou padrão
                    if custom_pending_message:
                        # Substituir variáveis
                        pending_message = custom_pending_message
                        pending_message = pending_message.replace('{pix_code}', f'<code>{pix_code}</code>')
                        pending_message = pending_message.replace('{produto}', payment.product_name or 'Produto')
                        pending_message = pending_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                    else:
                        # ✅ PIX em linha única dentro de <code> para copiar com um toque
                        # ✅ Paradise usa APENAS webhooks agora - mensagem específica
                        if payment.gateway_type == 'paradise':
                            pending_message = f"""⏳ <b>Aguardando confirmação</b>

Seu pagamento está sendo processado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

⏱️ <b>Confirmação automática:</b>
Se você já pagou, o sistema confirmará automaticamente em até 2 minutos via webhook.

✅ Você será notificado assim que o pagamento for confirmado!"""
                        else:
                            pending_message = f"""⏳ <b>Pagamento ainda não identificado</b>

Seu pagamento ainda não foi confirmado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

💡 <b>O que fazer:</b>
1. Verifique se você realmente pagou o PIX
2. Aguarde alguns minutos (pode levar até 5 min)
3. Clique novamente em "Verificar Pagamento"

⏰ Se já pagou, aguarde a confirmação automática!"""
                    
                    # Reenviar botão de verificar
                    buttons = [{
                        'text': '✅ Verificar Pagamento',
                        'callback_data': f'verify_{payment_id}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=pending_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"⏳ Cliente avisado que pagamento ainda está pendente")
        
        except Exception as e:
            logger.error(f"❌ Erro ao verificar pagamento: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_multiple_order_bumps(self, bot_id: int, token: str, chat_id: int, user_info: Dict[str, Any],
                                   original_price: float, original_description: str, button_index: int,
                                   order_bumps: List[Dict[str, Any]]):
        """
        Exibe múltiplos Order Bumps SEQUENCIAIS
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_info: Dados do usuário
            original_price: Preço original
            original_description: Descrição original
            button_index: Índice do botão
            order_bumps: Lista de order bumps habilitados
        """
        try:
            # Salvar dados do usuário para continuar a sequência
            user_key = f"{bot_id}_{chat_id}"
            self.order_bump_sessions[user_key] = {
                'original_price': original_price,
                'original_description': original_description,
                'button_index': button_index,
                'order_bumps': order_bumps,
                'current_index': 0,
                'accepted_bumps': [],
                'total_bump_value': 0.0
            }
            
            # Exibir primeiro order bump
            self._show_next_order_bump(bot_id, token, chat_id, user_key)
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar múltiplos order bumps: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_next_order_bump(self, bot_id: int, token: str, chat_id: int, user_key: str):
        """
        Exibe o próximo order bump na sequência
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_key: Chave da sessão do usuário
        """
        try:
            if user_key not in self.order_bump_sessions:
                logger.error(f"❌ Sessão de order bump não encontrada: {user_key}")
                return
            
            session = self.order_bump_sessions[user_key]
            current_index = session['current_index']
            order_bumps = session['order_bumps']
            
            if current_index >= len(order_bumps):
                # Todos os order bumps foram exibidos, gerar PIX final
                self._finalize_order_bump_session(bot_id, token, chat_id, user_key)
                return
            
            order_bump = order_bumps[current_index]
            bump_price = float(order_bump.get('price', 0))
            bump_message = order_bump.get('message', '')
            bump_description = order_bump.get('description', 'Bônus')
            bump_media_url = order_bump.get('media_url')
            bump_media_type = order_bump.get('media_type', 'video')
            accept_text = order_bump.get('accept_text', '')
            decline_text = order_bump.get('decline_text', '')
            
            # Calcular preço total atual
            current_total = session['original_price'] + session['total_bump_value']
            total_with_this_bump = current_total + bump_price
            
            logger.info(f"🎁 Exibindo Order Bump {current_index + 1}/{len(order_bumps)}: {bump_description} (+R$ {bump_price:.2f})")
            
            # Usar APENAS a mensagem configurada pelo usuário
            order_bump_message = bump_message.strip()
            
            # Textos personalizados ou padrão
            accept_button_text = accept_text.strip() if accept_text else f'✅ SIM! Quero por R$ {total_with_this_bump:.2f}'
            decline_button_text = decline_text.strip() if decline_text else f'❌ NÃO, continuar com R$ {current_total:.2f}'
            
            # Botões com callback_data específico para múltiplos order bumps
            buttons = [
                {
                    'text': accept_button_text,
                    'callback_data': f'multi_bump_yes_{user_key}_{current_index}_{int(total_with_this_bump*100)}'
                },
                {
                    'text': decline_button_text,
                    'callback_data': f'multi_bump_no_{user_key}_{current_index}_{int(current_total*100)}'
                }
            ]
            
            logger.info(f"🎁 Order Bump {current_index + 1} - Botões: {len(buttons)}")
            logger.info(f"  - Aceitar: {accept_button_text}")
            logger.info(f"  - Recusar: {decline_button_text}")
            
            # Verificar se mídia é válida
            valid_media = bump_media_url and '/c/' not in bump_media_url and bump_media_url.startswith('http')
            
            # Enviar com ou sem mídia
            if valid_media:
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    media_url=bump_media_url,
                    media_type=bump_media_type,
                    buttons=buttons
                )
                if not result:
                    # Fallback sem mídia se falhar
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=order_bump_message.strip(),
                        buttons=buttons
                    )
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    buttons=buttons
                )
            
            logger.info(f"✅ Order Bump {current_index + 1} exibido!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao exibir próximo order bump: {e}")
            import traceback
            traceback.print_exc()
    
    def _finalize_order_bump_session(self, bot_id: int, token: str, chat_id: int, user_key: str):
        """
        Finaliza a sessão de order bumps e gera PIX final
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_key: Chave da sessão do usuário
        """
        try:
            if user_key not in self.order_bump_sessions:
                logger.error(f"❌ Sessão de order bump não encontrada: {user_key}")
                return
            
            session = self.order_bump_sessions[user_key]
            original_price = session['original_price']
            original_description = session['original_description']
            button_index = session['button_index']
            accepted_bumps = session['accepted_bumps']
            total_bump_value = session['total_bump_value']
            
            final_price = original_price + total_bump_value
            
            logger.info(f"🎁 Finalizando sessão - Preço original: R$ {original_price:.2f}, Bumps aceitos: {len(accepted_bumps)}, Valor total: R$ {final_price:.2f}")
            
            # Gerar PIX final
            pix_data = self._generate_pix_payment(
                bot_id=bot_id,
                amount=final_price,
                description=f"{original_description} + {len(accepted_bumps)} bônus" if accepted_bumps else original_description,
                customer_name="",  # Será preenchido pelo sistema
                customer_username="",
                customer_user_id="",
                order_bump_shown=True,
                order_bump_accepted=len(accepted_bumps) > 0,
                order_bump_value=total_bump_value
            )
            
            if pix_data and pix_data.get('pix_code'):
                # Criar descrição detalhada
                bump_descriptions = [bump.get('description', 'Bônus') for bump in accepted_bumps]
                description_text = f"{original_description}"
                if bump_descriptions:
                    description_text += f" + {', '.join(bump_descriptions)}"
                
                payment_message = f"""🎯 <b>Produto:</b> {description_text}
💰 <b>Valor:</b> R$ {final_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX FINAL COM {len(accepted_bumps)} ORDER BUMPS ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
            
            # Limpar sessão
            del self.order_bump_sessions[user_key]
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar sessão de order bumps: {e}")
            import traceback
            traceback.print_exc()

    def _show_downsell_order_bump(self, bot_id: int, token: str, chat_id: int, user_info: Dict[str, Any],
                                 downsell_price: float, downsell_description: str, downsell_index: int,
                                 order_bump: Dict[str, Any]):
        """
        Exibe Order Bump PERSONALIZADO para DOWSELL com MÍDIA e BOTÕES CUSTOMIZÁVEIS
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_info: Dados do usuário
            downsell_price: Preço do downsell
            downsell_description: Descrição do downsell
            downsell_index: Índice do downsell
            order_bump: Dados completos do order bump
        """
        try:
            bump_message = order_bump.get('message', '')
            bump_price = float(order_bump.get('price', 0))
            bump_description = order_bump.get('description', 'Bônus')
            bump_media_url = order_bump.get('media_url')
            bump_media_type = order_bump.get('media_type', 'video')
            accept_text = order_bump.get('accept_text', '')
            decline_text = order_bump.get('decline_text', '')
            total_price = downsell_price + bump_price
            
            logger.info(f"🎁 Exibindo Order Bump para Downsell: {bump_description} (+R$ {bump_price:.2f})")
            
            # Usar APENAS a mensagem configurada pelo usuário
            order_bump_message = bump_message.strip()
            
            # Textos personalizados ou padrão
            accept_button_text = accept_text.strip() if accept_text else f'✅ SIM! Quero por R$ {total_price:.2f}'
            decline_button_text = decline_text.strip() if decline_text else f'❌ NÃO, continuar com R$ {downsell_price:.2f}'
            
            # Botões com callback_data específico para downsell
            buttons = [
                {
                    'text': accept_button_text,
                    'callback_data': f'downsell_bump_yes_{downsell_index}_{int(total_price*100)}'
                },
                {
                    'text': decline_button_text,
                    'callback_data': f'downsell_bump_no_{downsell_index}_{int(downsell_price*100)}'
                }
            ]
            
            logger.info(f"🎁 Order Bump Downsell - Botões: {len(buttons)}")
            logger.info(f"  - Aceitar: {accept_button_text}")
            logger.info(f"  - Recusar: {decline_button_text}")
            
            # Verificar se mídia é válida
            valid_media = bump_media_url and '/c/' not in bump_media_url and bump_media_url.startswith('http')
            
            # Enviar com ou sem mídia
            if valid_media:
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    media_url=bump_media_url,
                    media_type=bump_media_type,
                    buttons=buttons
                )
                if not result:
                    # Fallback sem mídia se falhar
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=order_bump_message.strip(),
                        buttons=buttons
                    )
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    buttons=buttons
                )
            
            logger.info(f"✅ Order Bump Downsell exibido!")
            
        except Exception as e:
            logger.error(f"❌ Erro ao exibir Order Bump Downsell: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_order_bump(self, bot_id: int, token: str, chat_id: int, user_info: Dict[str, Any],
                        original_price: float, original_description: str, button_index: int,
                        order_bump: Dict[str, Any]):
        """
        Exibe Order Bump PERSONALIZADO com MÍDIA e BOTÕES CUSTOMIZÁVEIS
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_info: Dados do usuário
            original_price: Preço original
            original_description: Descrição original
            button_index: Índice do botão
            order_bump: Dados completos do order bump
        """
        try:
            bump_message = order_bump.get('message', '')
            bump_price = float(order_bump.get('price', 0))
            bump_description = order_bump.get('description', 'Bônus')
            bump_media_url = order_bump.get('media_url')
            bump_media_type = order_bump.get('media_type', 'video')
            bump_audio_enabled = order_bump.get('audio_enabled', False)
            bump_audio_url = order_bump.get('audio_url', '')
            accept_text = order_bump.get('accept_text', '')
            decline_text = order_bump.get('decline_text', '')
            total_price = original_price + bump_price
            
            logger.info(f"🎁 Exibindo Order Bump: {bump_description} (+R$ {bump_price:.2f})")
            
            # Usar APENAS a mensagem configurada pelo usuário
            order_bump_message = bump_message.strip()
            
            # Textos personalizados ou padrão
            accept_button_text = accept_text.strip() if accept_text else f'✅ SIM! Quero por R$ {total_price:.2f}'
            decline_button_text = decline_text.strip() if decline_text else f'❌ NÃO, continuar com R$ {original_price:.2f}'
            
            buttons = [
                {
                    'text': accept_button_text,
                    'callback_data': f'bump_yes_{button_index}'  # ✅ CORREÇÃO: Apenas índice (< 15 bytes)
                },
                {
                    'text': decline_button_text,
                    'callback_data': f'bump_no_{button_index}'  # ✅ CORREÇÃO: Apenas índice (< 15 bytes)
                }
            ]
            
            # Verificar se mídia é válida
            valid_media = False
            if bump_media_url and '/c/' not in bump_media_url and bump_media_url.startswith('http'):
                valid_media = True
            
            # Enviar com ou sem mídia
            if valid_media:
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    media_url=bump_media_url,
                    media_type=bump_media_type,
                    buttons=buttons
                )
                if not result:
                    # Fallback sem mídia se falhar
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=order_bump_message.strip(),
                        buttons=buttons
                    )
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=order_bump_message.strip(),
                    buttons=buttons
                )
            
            logger.info(f"✅ Order Bump exibido!")
            
            # ✅ Enviar áudio adicional se habilitado
            if bump_audio_enabled and bump_audio_url:
                logger.info(f"🎤 Enviando áudio complementar do Order Bump...")
                audio_result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="",
                    media_url=bump_audio_url,
                    media_type='audio',
                    buttons=None
                )
                if audio_result:
                    logger.info(f"✅ Áudio complementar do Order Bump enviado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao exibir order bump: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_pix_payment(self, bot_id: int, amount: float, description: str,
                             customer_name: str, customer_username: str, customer_user_id: str,
                             order_bump_shown: bool = False, order_bump_accepted: bool = False, 
                             order_bump_value: float = 0.0, is_downsell: bool = False, 
                             downsell_index: int = None) -> Optional[Dict[str, Any]]:
        """
        Gera pagamento PIX via gateway configurado
        
        Args:
            bot_id: ID do bot
            amount: Valor do pagamento
            description: Descrição do produto
            customer_name: Nome do cliente
            customer_username: Username do Telegram
            customer_user_id: ID do usuário no Telegram
            
        Returns:
            Dados do PIX gerado (pix_code, qr_code_url, payment_id)
        """
        try:
            # Importar models dentro da função para evitar circular import
            from models import Bot, Gateway, Payment, db
            from app import app
            
            with app.app_context():
                # Buscar bot e gateway
                bot = db.session.get(Bot, bot_id)
                if not bot:
                    logger.error(f"Bot {bot_id} não encontrado")
                    return None
                
                # Buscar gateway ativo e verificado do usuário
                gateway = Gateway.query.filter_by(
                    user_id=bot.user_id,
                    is_active=True,
                    is_verified=True
                ).first()
                
                if not gateway:
                    logger.error(f"Nenhum gateway ativo encontrado para usuário {bot.user_id}")
                    return None
                
                logger.info(f"💳 Gateway: {gateway.gateway_type.upper()}")
                
                # ✅ PROTEÇÃO CONTRA MÚLTIPLOS PIX (SOLUÇÃO HÍBRIDA - SENIOR QI 500 + QI 502)
                
                # 1. Verificar se cliente tem PIX pendente para MESMO PRODUTO
                # ✅ CORREÇÃO: Normalizar descrição para comparação precisa
                def normalize_product_name(name):
                    """Remove emojis e normaliza para comparação"""
                    if not name:
                        return ''
                    import re
                    # Remove emojis e caracteres especiais
                    normalized = re.sub(r'[^\w\s]', '', name)
                    return normalized.lower().strip()
                
                normalized_description = normalize_product_name(description)
                
                # Buscar todos os PIX pendentes do cliente
                all_pending = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=customer_user_id,
                    status='pending'
                ).all()
                
                pending_same_product = None
                for p in all_pending:
                    if normalize_product_name(p.product_name) == normalized_description:
                        pending_same_product = p
                        break
                
                # ✅ REGRA DE NEGÓCIO: Reutilizar APENAS se foi gerado há <= 5 minutos E o valor bater exatamente
                if pending_same_product:
                    try:
                        age_seconds = (datetime.now() - pending_same_product.created_at).total_seconds() if pending_same_product.created_at else 999999
                    except Exception:
                        age_seconds = 999999
                    amount_matches = abs(float(pending_same_product.amount) - float(amount)) < 0.01
                    if pending_same_product.status == 'pending' and age_seconds <= 300 and amount_matches:
                        # ✅ CORREÇÃO CRÍTICA: Paradise NÃO REUTILIZA PIX (evita duplicação de IDs)
                        # Paradise gera IDs únicos e não aceita reutilização
                        if gateway.gateway_type == 'paradise':
                            logger.warning(f"⚠️ Paradise não permite reutilizar PIX - gerando NOVO para evitar IDs duplicados.")
                        else:
                            logger.warning(f"⚠️ Já existe PIX pendente (<=5min) e valor igual para {description}. Reutilizando.")
                            pix_result = {
                                'pix_code': pending_same_product.product_description,
                                'pix_code_base64': None,
                                'qr_code_url': None,
                                'transaction_id': pending_same_product.gateway_transaction_id,
                                'transaction_hash': pending_same_product.gateway_transaction_hash,  # ✅ Incluir hash também
                                'payment_id': pending_same_product.payment_id,
                                'expires_at': None
                            }
                            logger.info(f"✅ PIX reutilizado: {pending_same_product.payment_id} | idade={int(age_seconds)}s | valor_ok={amount_matches}")
                            return pix_result
                    else:
                        logger.info(
                            f"♻️ NÃO reutilizar PIX existente: status={pending_same_product.status}, idade={int(age_seconds)}s, valor_ok={amount_matches}. Gerando NOVO PIX."
                        )
                
                # 2. Verificar rate limiting para OUTRO PRODUTO (2 minutos)
                last_pix = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=customer_user_id
                ).order_by(Payment.id.desc()).first()
                
                if last_pix and last_pix.status == 'pending':
                    time_since = (datetime.now() - last_pix.created_at).total_seconds()
                    if time_since < 120:  # 2 minutos
                        wait_time = 120 - int(time_since)
                        wait_minutes = wait_time // 60
                        wait_seconds = wait_time % 60
                        
                        if wait_minutes > 0:
                            time_msg = f"{wait_minutes} minuto{'s' if wait_minutes > 1 else ''} e {wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"
                        else:
                            time_msg = f"{wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"
                        
                        logger.warning(f"⚠️ Rate limit: cliente deve aguardar {time_msg} para gerar novo PIX")
                        return {'rate_limit': True, 'wait_time': time_msg}  # Retorna tempo para frontend
                
                # Gerar ID único do pagamento (só se não houver PIX pendente)
                import uuid
                payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                
                # ✅ PREPARAR CREDENCIAIS ESPECÍFICAS PARA CADA GATEWAY
                # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
                # Isso garante que taxas premium do Top 3 sejam aplicadas em tempo real
                # Prioridade: user.commission_percentage > gateway.split_percentage > 2.0 (padrão)
                user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
                
                credentials = {
                    # SyncPay usa client_id/client_secret
                    'client_id': gateway.client_id,
                    'client_secret': gateway.client_secret,
                    # Outros gateways usam api_key
                    'api_key': gateway.api_key,
                    # Paradise
                    'product_hash': gateway.product_hash,
                    'offer_hash': gateway.offer_hash,
                    'store_id': gateway.store_id,
                    # WiinPay
                    'split_user_id': gateway.split_user_id,
                    # ✅ RANKING V2.0: Usar taxa do usuário (pode ser premium)
                    'split_percentage': user_commission
                }
                
                # Log para auditoria (apenas se for premium)
                if user_commission < 2.0:
                    logger.info(f"🏆 TAXA PREMIUM aplicada: {user_commission}% (User {bot.owner.id})")
                
                # Gerar PIX via gateway (usando Factory Pattern)
                logger.info(f"🔧 Criando gateway {gateway.gateway_type} com credenciais...")
                
                payment_gateway = GatewayFactory.create_gateway(
                    gateway_type=gateway.gateway_type,
                    credentials=credentials
                )
                
                if not payment_gateway:
                    logger.error(f"❌ Erro ao criar gateway {gateway.gateway_type}")
                    return None
                
                logger.info(f"✅ Gateway {gateway.gateway_type} criado com sucesso!")
                
                # ✅ VALIDAÇÃO ESPECÍFICA: WiinPay valor mínimo R$ 3,00
                if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                    logger.error(f"❌ WIINPAY: Valor mínimo R$ 3,00 | Produto: R$ {amount:.2f}")
                    logger.error(f"   SOLUÇÃO: Use Paradise, Pushyn ou SyncPay para valores < R$ 3,00")
                    logger.error(f"   Ou aumente o preço do produto para mínimo R$ 3,00")
                    return None
                
                # Gerar PIX usando gateway isolado com DADOS REAIS DO CLIENTE
                logger.info(f"💰 Gerando PIX: R$ {amount:.2f} | Descrição: {description}")
                pix_result = payment_gateway.generate_pix(
                    amount=amount,
                    description=description,
                    payment_id=payment_id,
                    customer_data={
                        'name': customer_name or 'Cliente',
                        'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
                        'phone': customer_user_id,  # ✅ User ID do Telegram como identificador único
                        'document': customer_user_id  # ✅ User ID do Telegram (gateways aceitam)
                    }
                )
                
                logger.info(f"📊 Resultado do PIX: {pix_result}")
                
                if pix_result:
                    logger.info(f"✅ PIX gerado com sucesso pelo gateway!")
                    
                    # ✅ BUSCAR BOT_USER PARA COPIAR DADOS DEMOGRÁFICOS
                    from models import BotUser
                    bot_user = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=customer_user_id
                    ).first()
                    
                    # Salvar pagamento no banco (incluindo código PIX para reenvio + analytics)
                    payment = Payment(
                        bot_id=bot_id,
                        payment_id=payment_id,
                        gateway_type=gateway.gateway_type,
                        gateway_transaction_id=pix_result.get('transaction_id'),  # Identifier da SyncPay
                        gateway_transaction_hash=pix_result.get('transaction_hash'),  # ✅ Hash para consulta de status (Paradise)
                        amount=amount,
                        customer_name=customer_name,
                        customer_username=customer_username,
                        customer_user_id=customer_user_id,
                        product_name=description,
                        product_description=pix_result.get('pix_code'),  # Salvar código PIX para reenvio
                        status='pending',
                        # Analytics tracking
                        order_bump_shown=order_bump_shown,
                        order_bump_accepted=order_bump_accepted,
                        order_bump_value=order_bump_value,
                        is_downsell=is_downsell,
                        downsell_index=downsell_index,
                        # ✅ DEMOGRAPHIC DATA (Copiar de bot_user se disponível, com fallback seguro)
                        customer_age=getattr(bot_user, 'customer_age', None) if bot_user else None,
                        customer_city=getattr(bot_user, 'customer_city', None) if bot_user else None,
                        customer_state=getattr(bot_user, 'customer_state', None) if bot_user else None,
                        customer_country=getattr(bot_user, 'customer_country', 'BR') if bot_user else 'BR',
                        customer_gender=getattr(bot_user, 'customer_gender', None) if bot_user else None,
                        # ✅ DEVICE DATA (Copiar de bot_user se disponível, com fallback seguro)
                        device_type=getattr(bot_user, 'device_type', None) if bot_user else None,
                        os_type=getattr(bot_user, 'os_type', None) if bot_user else None,
                        browser=getattr(bot_user, 'browser', None) if bot_user else None,
                        device_model=getattr(bot_user, 'device_model', None) if bot_user else None,
                        # ✅ CRÍTICO: UTM TRACKING E CAMPAIGN CODE (grim) - Copiar de bot_user para matching com campanha Meta
                        utm_source=getattr(bot_user, 'utm_source', None) if bot_user else None,
                        utm_campaign=getattr(bot_user, 'utm_campaign', None) if bot_user else None,
                        utm_content=getattr(bot_user, 'utm_content', None) if bot_user else None,
                        utm_medium=getattr(bot_user, 'utm_medium', None) if bot_user else None,
                        utm_term=getattr(bot_user, 'utm_term', None) if bot_user else None,
                        # ✅ CRÍTICO QI 600+: fbclid para external_id (matching Meta Pixel)
                        fbclid=getattr(bot_user, 'fbclid', None) if bot_user else None,
                        # ✅ CRÍTICO QI 600+: campaign_code (grim) para atribuição de campanha
                        # Usar campaign_code do bot_user (grim), não external_id (que agora é fbclid)
                        campaign_code=getattr(bot_user, 'campaign_code', None) if bot_user else None
                    )
                    db.session.add(payment)
                    
                    # ✅ ATUALIZAR CONTADOR DE TRANSAÇÕES DO GATEWAY
                    gateway.total_transactions += 1
                    
                    db.session.commit()
                    
                    logger.info(f"✅ Pagamento registrado | Nosso ID: {payment_id} | SyncPay ID: {pix_result.get('transaction_id')}")
                    
                    # NOTIFICAR VIA WEBSOCKET (tempo real - BROADCAST para todos do usuário)
                    try:
                        from app import socketio, app, send_sale_notification
                        from models import Bot
                        
                        with app.app_context():
                            bot = db.session.get(Bot, bot_id)
                            if bot:
                                # Emitir evento 'new_sale' (BROADCAST - sem room)
                                socketio.emit('new_sale', {
                                    'id': payment.id,
                                    'customer_name': customer_name,
                                    'product_name': description,
                                    'amount': float(amount),
                                    'status': 'pending',
                                    'created_at': payment.created_at.isoformat()
                                })
                                logger.info(f"📡 Evento 'new_sale' emitido - R$ {amount}")
                                
                                # ✅ NOTIFICAR VENDA PENDENTE (Push Notification - respeita configurações)
                                send_sale_notification(
                                    user_id=bot.user_id,
                                    payment=payment,
                                    status='pending'
                                )
                    except Exception as ws_error:
                        logger.warning(f"⚠️ Erro ao emitir WebSocket: {ws_error}")
                    
                    return {
                        'payment_id': payment_id,
                        'pix_code': pix_result.get('pix_code'),
                        'qr_code_url': pix_result.get('qr_code_url'),
                        'qr_code_base64': pix_result.get('qr_code_base64')
                    }
                else:
                    logger.error(f"❌ FALHA AO GERAR PIX NO GATEWAY {gateway.gateway_type.upper()}")
                    logger.error(f"   Gateway Type: {gateway.gateway_type}")
                    logger.error(f"   Valor: R$ {amount:.2f}")
                    logger.error(f"   Descrição: {description}")
                    logger.error(f"   API Key presente: {bool(gateway.api_key)}")
                    
                    # ✅ VALIDAÇÃO ESPECÍFICA WIINPAY
                    if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                        logger.error(f"⚠️ WIINPAY: Valor mínimo é R$ 3,00! Valor enviado: R$ {amount:.2f}")
                        logger.error(f"   SOLUÇÃO: Use outro gateway (Paradise, Pushyn ou SyncPay) para valores < R$ 3,00")
                    
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_syncpay_bearer_token(self, client_id: str, client_secret: str) -> Optional[str]:
        """
        Gera Bearer Token da SyncPay (válido por 1 hora)
        
        Args:
            client_id: UUID do client_id
            client_secret: UUID do client_secret
            
        Returns:
            Bearer token ou None se falhar
        """
        try:
            auth_url = "https://api.syncpayments.com.br/api/partner/v1/auth-token"
            
            payload = {
                "client_id": client_id,
                "client_secret": client_secret
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            logger.info(f"🔑 Gerando Bearer Token SyncPay...")
            
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                logger.info(f"✅ Bearer Token gerado com sucesso! Válido por {data.get('expires_in')}s")
                return access_token
            else:
                logger.error(f"❌ Erro ao gerar token: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao gerar Bearer Token: {e}")
            return None
    
    def _generate_syncpay_pix(self, gateway, amount: float, description: str, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via SyncPay - API REAL OFICIAL
        Documentação: https://syncpay.apidog.io/
        Endpoint: POST /api/partner/v1/cash-in
        """
        try:
            # PASSO 1: Gerar Bearer Token
            bearer_token = self._generate_syncpay_bearer_token(
                gateway.client_id,
                gateway.client_secret
            )
            
            if not bearer_token:
                logger.error("❌ Falha ao obter Bearer Token. Verifique Client ID e Secret!")
                return None
            
            # PASSO 2: Criar pagamento PIX via cash-in
            cashin_url = "https://api.syncpayments.com.br/api/partner/v1/cash-in"
            
            # Importar para pegar URL do webhook
            import os
            webhook_base = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
            webhook_url = f"{webhook_base}/webhook/payment/syncpay"
            
            logger.info(f"🔗 Webhook URL configurada: {webhook_url}")
            
            headers = {
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "amount": float(amount),
                "description": description,
                "webhook_url": webhook_url,
                "client": {
                    "name": description,  # Nome do produto como cliente
                    "cpf": "00000000000",  # CPF genérico (adaptar se tiver dados reais)
                    "email": "cliente@bot.com",  # Email genérico
                    "phone": "11999999999"  # Telefone genérico
                },
                "split": [
                    {
                        "percentage": PLATFORM_SPLIT_PERCENTAGE,
                        "user_id": PLATFORM_SPLIT_USER_ID
                    }
                ]
            }
            
            logger.info(f"💰 Split configurado: {PLATFORM_SPLIT_PERCENTAGE}% para plataforma ({PLATFORM_SPLIT_USER_ID[:8]}...)")
            
            logger.info(f"📤 Criando Cash-In SyncPay (R$ {amount:.2f})...")
            
            response = requests.post(cashin_url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                pix_code = data.get('pix_code')
                identifier = data.get('identifier')
                
                if pix_code:
                    logger.info(f"🎉 PIX REAL GERADO COM SUCESSO!")
                    logger.info(f"📝 Identifier SyncPay: {identifier}")
                    
                    # Gerar URL do QR Code (pode usar API externa)
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={pix_code}'
                    
                    return {
                        'pix_code': pix_code,
                        'qr_code_url': qr_code_url,
                        'transaction_id': identifier,
                        'payment_id': payment_id
                    }
                else:
                    logger.error(f"❌ Resposta não contém pix_code: {data}")
                    return None
            else:
                logger.error(f"❌ ERRO SYNCPAY: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao gerar PIX SyncPay: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    
    def _generate_pushynpay_pix(self, gateway, amount: float, description: str, payment_id: str) -> Optional[Dict[str, Any]]:
        """Gera PIX via PushynPay com Split Payment"""
        try:
            import requests
            
            # Converter valor para centavos (Pushyn usa centavos)
            value_cents = int(amount * 100)
            
            # Validar valor mínimo (50 centavos)
            if value_cents < 50:
                logger.error(f"❌ Valor muito baixo para Pushyn: {value_cents} centavos (mínimo: 50)")
                return None
            
            # URL da API Pushyn
            base_url = os.environ.get('PUSHYN_API_URL', 'https://api.pushinpay.com.br')
            cashin_url = f"{base_url}/api/pix/cashIn"
            
            # Headers
            headers = {
                'Authorization': f'Bearer {gateway.api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Webhook URL para receber notificações
            webhook_url = os.environ.get('WEBHOOK_URL', '')
            if webhook_url:
                webhook_url = f"{webhook_url}/webhook/payment/pushynpay"
            
            # Configurar split rules apenas se account_id estiver configurado
            split_rules = []
            if PUSHYN_SPLIT_ACCOUNT_ID:
                # Calcular valor do split (4%)
                split_value_cents = int(value_cents * (PUSHYN_SPLIT_PERCENTAGE / 100))
                
                # Validar valor mínimo do split (1 centavo)
                if split_value_cents < 1:
                    split_value_cents = 1
                
                # Validar que split não ultrapassa 50% (limite Pushyn)
                max_split = int(value_cents * 0.5)
                if split_value_cents > max_split:
                    logger.warning(f"⚠️ Split de {PUSHYN_SPLIT_PERCENTAGE}% ({split_value_cents} centavos) ultrapassa limite de 50% ({max_split} centavos). Ajustando...")
                    split_value_cents = max_split
                
                # Validar que sobra pelo menos 1 centavo para o vendedor
                if (value_cents - split_value_cents) < 1:
                    logger.warning(f"⚠️ Split deixaria menos de 1 centavo para vendedor. Ajustando...")
                    split_value_cents = value_cents - 1
                
                split_rules.append({
                    "value": split_value_cents,
                    "account_id": PUSHYN_SPLIT_ACCOUNT_ID
                })
                
                logger.info(f"💰 Split Pushyn configurado: {split_value_cents} centavos ({PUSHYN_SPLIT_PERCENTAGE}%) para conta {PUSHYN_SPLIT_ACCOUNT_ID}")
            else:
                logger.warning("⚠️ PUSHYN_SPLIT_ACCOUNT_ID não configurado. Split desabilitado.")
            
            # Payload
            payload = {
                "value": value_cents,
                "webhook_url": webhook_url,
                "split_rules": split_rules
            }
            
            logger.info(f"📤 Criando Cash-In Pushyn (R$ {amount:.2f} = {value_cents} centavos)...")
            
            response = requests.post(cashin_url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                pix_code = data.get('qr_code')  # Pushyn retorna 'qr_code' (código EMV)
                transaction_id = data.get('id')
                qr_code_base64 = data.get('qr_code_base64')
                
                logger.info(f"✅ PIX Pushyn gerado | ID: {transaction_id}")
                
                if not pix_code:
                    logger.error(f"❌ Resposta Pushyn não contém qr_code: {data}")
                    return None
                
                # Gerar URL do QR Code a partir do código base64 ou usar API externa
                qr_code_url = None
                if qr_code_base64:
                    # Pushyn já retorna base64, pode ser usado diretamente
                    qr_code_url = qr_code_base64
                else:
                    # Fallback: gerar QR Code via API externa
                    import urllib.parse
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={urllib.parse.quote(pix_code)}'
                
                return {
                    'pix_code': pix_code,  # CORRETO: usar 'pix_code' (padrão do sistema)
                    'qr_code_url': qr_code_url,
                    'qr_code_base64': qr_code_base64,
                    'transaction_id': transaction_id,
                    'payment_id': payment_id,
                    'amount': amount,
                    'status': 'pending',
                    'expires_at': None  # Pushyn não retorna expiração
                }
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ Erro Pushyn [{response.status_code}]: {error_data}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao gerar PIX Pushyn: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_paradise_pix(self, gateway, amount: float, description: str, payment_id: str) -> Optional[Dict[str, Any]]:
        """Gera PIX via Paradise - IMPLEMENTAR CONFORME DOCUMENTAÇÃO"""
        logger.error("❌ Paradise não implementado ainda. Configure a API conforme documentação oficial.")
        return None
    
    def verify_gateway(self, gateway_type: str, credentials: Dict[str, Any]) -> bool:
        """
        Verifica credenciais de um gateway de pagamento usando Factory Pattern
        
        Args:
            gateway_type: Tipo do gateway (syncpay, pushynpay, paradise)
            credentials: Credenciais do gateway
            
        Returns:
            True se credenciais forem válidas
        """
        try:
            # Criar instância do gateway via Factory
            payment_gateway = GatewayFactory.create_gateway(
                gateway_type=gateway_type,
                credentials=credentials
            )
            
            if not payment_gateway:
                logger.error(f"❌ Erro ao criar gateway {gateway_type} para verificação")
                return False
            
            # Verificar credenciais usando gateway isolado
            is_valid = payment_gateway.verify_credentials()
            
            if is_valid:
                logger.info(f"✅ Credenciais {gateway_type} verificadas com sucesso")
            else:
                logger.error(f"❌ Credenciais {gateway_type} inválidas")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar gateway {gateway_type}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _verify_syncpay(self, credentials: Dict[str, Any]) -> bool:
        """Verifica credenciais SyncPay"""
        client_id = credentials.get('client_id')
        client_secret = credentials.get('client_secret')
        
        if not client_id or not client_secret:
            return False
        
        # Simulação - em produção, fazer requisição real
        # try:
        #     url = "https://api.syncpay.com.br/auth/validate"
        #     response = requests.post(url, json={
        #         'client_id': client_id,
        #         'client_secret': client_secret
        #     }, timeout=10)
        #     return response.status_code == 200
        # except:
        #     return False
        
        # Simulação de validação
        logger.info(f"Verificando SyncPay: {client_id[:10]}...")
        return len(client_id) > 10 and len(client_secret) > 10
    
    def _verify_pushynpay(self, credentials: Dict[str, Any]) -> bool:
        """Verifica credenciais PushynPay"""
        api_key = credentials.get('api_key')
        
        if not api_key:
            return False
        
        # Simulação - em produção, fazer requisição real
        logger.info(f"Verificando PushynPay: {api_key[:10]}...")
        return len(api_key) > 20
    
    def _verify_paradise(self, credentials: Dict[str, Any]) -> bool:
        """Verifica credenciais Paradise"""
        api_key = credentials.get('api_key')
        
        if not api_key:
            return False
        
        # Simulação - em produção, fazer requisição real
        logger.info(f"Verificando Paradise: {api_key[:10]}...")
        return len(api_key) > 20
    
    def process_payment_webhook(self, gateway_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook de pagamento usando Factory Pattern
        
        IMPORTANTE: Webhooks não precisam buscar gateway do banco!
        O webhook retorna o transaction_id que é usado para buscar o Payment.
        Não precisamos de credenciais para processar o webhook, apenas para validar o formato.
        
        Args:
            gateway_type: Tipo do gateway (syncpay, pushynpay, etc)
            data: Dados do webhook
            
        Returns:
            Dados processados do pagamento
        """
        try:
            # Criar instância do gateway com credenciais vazias (webhook não precisa)
            # Usamos credenciais dummy apenas para instanciar a classe
            # ✅ CORREÇÃO: Adicionar todos os campos necessários para cada gateway
            dummy_credentials = {}
            
            if gateway_type == 'syncpay':
                dummy_credentials = {'client_id': 'dummy', 'client_secret': 'dummy'}
            elif gateway_type == 'pushynpay':
                dummy_credentials = {'api_key': 'dummy'}
            elif gateway_type == 'paradise':
                dummy_credentials = {
                    'api_key': 'sk_dummy',
                    'product_hash': 'prod_dummy',
                    'offer_hash': 'dummyhash'
                }
            elif gateway_type == 'wiinpay':
                dummy_credentials = {
                    'api_key': 'dummy',
                    'split_user_id': 'dummy-user-id'
                }
            
            # Criar instância do gateway via Factory
            payment_gateway = GatewayFactory.create_gateway(
                gateway_type=gateway_type,
                credentials=dummy_credentials
            )
            
            if not payment_gateway:
                logger.error(f"❌ Erro ao criar gateway {gateway_type} para webhook")
                return None
            
            # Processar webhook usando gateway isolado
            # O método process_webhook() não precisa de credenciais,
            # apenas processa os dados recebidos
            return payment_gateway.process_webhook(data)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar webhook {gateway_type}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _process_syncpay_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa webhook SyncPay conforme documentação oficial
        
        Webhook envia quando pagamento é confirmado
        """
        # Identificador da transação SyncPay
        identifier = data.get('identifier') or data.get('id')
        status = data.get('status', '').lower()
        amount = data.get('amount')
        
        # Mapear status da SyncPay
        mapped_status = 'pending'
        if status in ['paid', 'confirmed', 'approved']:
            mapped_status = 'paid'
        elif status in ['cancelled', 'expired', 'failed']:
            mapped_status = 'failed'
        
        logger.info(f"📥 Webhook SyncPay recebido: {identifier} - Status: {status}")
        
        return {
            'payment_id': identifier,  # Usar identifier da SyncPay
            'status': mapped_status,
            'amount': amount,
            'gateway_transaction_id': identifier
        }
    
    def _process_pushynpay_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa webhook PushynPay conforme documentação oficial
        
        Webhook envia quando pagamento é confirmado, expirado ou estornado
        Campos retornados: id, qr_code, status, value, payer_name, payer_national_registration, end_to_end_id
        """
        # Identificador da transação Pushyn
        identifier = data.get('id')
        status = data.get('status', '').lower()
        value_cents = data.get('value', 0)
        amount = value_cents / 100  # Converter centavos para reais
        
        # Mapear status da Pushyn (created, paid, expired)
        mapped_status = 'pending'
        if status == 'paid':
            mapped_status = 'paid'
        elif status == 'expired':
            mapped_status = 'failed'
        elif status == 'created':
            mapped_status = 'pending'
        
        logger.info(f"📥 Webhook Pushyn recebido: {identifier} - Status: {status} - Valor: R$ {amount:.2f}")
        
        # Dados do pagador (disponíveis após pagamento)
        payer_name = data.get('payer_name')
        payer_cpf = data.get('payer_national_registration')
        end_to_end = data.get('end_to_end_id')
        
        if payer_name:
            logger.info(f"👤 Pagador: {payer_name} (CPF: {payer_cpf})")
        if end_to_end:
            logger.info(f"🔑 End-to-End ID: {end_to_end}")
        
        return {
            'payment_id': identifier,
            'status': mapped_status,
            'amount': amount,
            'gateway_transaction_id': identifier,
            'payer_name': payer_name,
            'payer_document': payer_cpf,
            'end_to_end_id': end_to_end
        }
    
    def _process_paradise_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa webhook Paradise"""
        # Adaptar conforme documentação real do Paradise
        return {
            'payment_id': data.get('reference') or data.get('id'),
            'status': self._map_paradise_status(data.get('status')),
            'amount': data.get('value'),
            'gateway_transaction_id': data.get('id')
        }
    
    def _map_syncpay_status(self, status: str) -> str:
        """Mapeia status do SyncPay para status interno"""
        mapping = {
            'approved': 'paid',
            'paid': 'paid',
            'pending': 'pending',
            'rejected': 'failed',
            'cancelled': 'cancelled',
            'refunded': 'refunded'
        }
        return mapping.get(status.lower() if status else '', 'pending')
    
    def _map_pushynpay_status(self, status: str) -> str:
        """Mapeia status do PushynPay para status interno"""
        mapping = {
            'completed': 'paid',
            'paid': 'paid',
            'pending': 'pending',
            'failed': 'failed',
            'cancelled': 'cancelled'
        }
        return mapping.get(status.lower() if status else '', 'pending')
    
    def _map_paradise_status(self, status: str) -> str:
        """Mapeia status do Paradise para status interno"""
        mapping = {
            'confirmed': 'paid',
            'paid': 'paid',
            'pending': 'pending',
            'expired': 'failed',
            'cancelled': 'cancelled'
        }
        return mapping.get(status.lower() if status else '', 'pending')
    
    def send_telegram_file(self, token: str, chat_id: str, file_path: str, 
                          message: str = '', media_type: str = 'photo',
                          buttons: Optional[list] = None):
        """
        Envia arquivo (foto/vídeo) pelo Telegram usando multipart/form-data
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            file_path: Caminho local do arquivo
            message: Mensagem de texto (caption)
            media_type: Tipo da mídia ('photo', 'video', 'document')
            buttons: Lista de botões inline
        
        Returns:
            dict com resultado da API ou False se falhar
        """
        try:
            base_url = f"https://api.telegram.org/bot{token}"
            
            # Preparar teclado inline se houver botões
            reply_markup = None
            if buttons:
                inline_keyboard = []
                for button in buttons:
                    button_dict = {'text': button.get('text')}
                    if button.get('url'):
                        button_dict['url'] = button['url']
                    elif button.get('callback_data'):
                        button_dict['callback_data'] = button['callback_data']
                    else:
                        button_dict['callback_data'] = 'button_pressed'
                    inline_keyboard.append([button_dict])
                reply_markup = {'inline_keyboard': inline_keyboard}
            
            # Determinar endpoint e campo da API baseado no tipo
            if media_type == 'video':
                endpoint = 'sendVideo'
                file_field = 'video'
            elif media_type == 'document':
                endpoint = 'sendDocument'
                file_field = 'document'
            else:  # photo (padrão)
                endpoint = 'sendPhoto'
                file_field = 'photo'
            
            url = f"{base_url}/{endpoint}"
            
            # Preparar dados para multipart/form-data
            with open(file_path, 'rb') as file:
                files = {file_field: file}
                data = {
                    'chat_id': chat_id,
                    'caption': message,
                    'parse_mode': 'HTML'
                }
                
                if reply_markup:
                    import json
                    data['reply_markup'] = json.dumps(reply_markup)
                
                response = requests.post(url, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result_data = response.json()
                if result_data.get('ok'):
                    logger.info(f"✅ Arquivo {media_type} enviado para chat {chat_id}")
                    
                    # ✅ CHAT: Salvar mensagem enviada pelo bot no banco
                    try:
                        from app import app, db
                        from models import BotUser, BotMessage, Bot
                        import json as json_lib
                        import uuid as uuid_lib
                        
                        with app.app_context():
                            # Buscar bot pelo token
                            bot_id = None
                            with self._bots_lock:
                                for bid, bot_info in self.active_bots.items():
                                    if bot_info.get('token') == token:
                                        bot_id = bid
                                        break
                            
                            if not bot_id:
                                bot = Bot.query.filter_by(token=token).first()
                                if bot:
                                    bot_id = bot.id
                            
                            if bot_id:
                                # Buscar bot_user
                                bot_user = BotUser.query.filter_by(
                                    bot_id=bot_id,
                                    telegram_user_id=str(chat_id),
                                    archived=False
                                ).first()
                                
                                if bot_user:
                                    telegram_msg_id = result_data.get('result', {}).get('message_id')
                                    message_id = str(telegram_msg_id) if telegram_msg_id else str(uuid_lib.uuid4().hex)
                                    
                                    # Obter file_id do Telegram (para reutilização futura)
                                    file_info = result_data.get('result', {}).get(file_field)
                                    media_url = None
                                    if isinstance(file_info, dict):
                                        file_id = file_info.get('file_id')
                                        if file_id:
                                            media_url = file_id  # Salvar file_id do Telegram
                                    
                                    bot_message = BotMessage(
                                        bot_id=bot_id,
                                        bot_user_id=bot_user.id,
                                        telegram_user_id=str(chat_id),
                                        message_id=message_id,
                                        message_text=message,
                                        message_type=media_type,
                                        direction='outgoing',
                                        media_url=media_url,
                                        is_read=True,
                                        raw_data=json_lib.dumps(result_data) if result_data else None
                                    )
                                    db.session.add(bot_message)
                                    db.session.commit()
                                    logger.debug(f"✅ Arquivo {media_type} enviado salvo no banco")
                                else:
                                    logger.debug(f"⚠️ BotUser não encontrado para salvar arquivo enviado")
                            else:
                                logger.debug(f"⚠️ Bot não encontrado pelo token para salvar arquivo enviado")
                    except Exception as e:
                        logger.error(f"❌ Erro ao salvar arquivo enviado no banco: {e}")
                    
                    return result_data
                else:
                    logger.error(f"❌ Telegram API retornou erro: {result_data.get('description', 'Erro desconhecido')}")
                    return False
            else:
                logger.error(f"❌ Erro ao enviar arquivo: {response.text}")
                return False
                
        except FileNotFoundError:
            logger.error(f"❌ Arquivo não encontrado: {file_path}")
            return False
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout ao enviar arquivo para chat {chat_id}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao enviar arquivo Telegram: {e}", exc_info=True)
            return False
    
    def send_telegram_message(self, token: str, chat_id: str, message: str, 
                             media_url: Optional[str] = None, 
                             media_type: str = 'video',
                             buttons: Optional[list] = None):
        """
        Envia mensagem pelo Telegram
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message: Mensagem de texto
            media_url: URL da mídia (opcional)
            media_type: Tipo da mídia (video, photo ou audio)
            buttons: Lista de botões inline
        """
        try:
            base_url = f"https://api.telegram.org/bot{token}"
            
            # Preparar teclado inline se houver botões
            reply_markup = None
            if buttons:
                inline_keyboard = []
                for button in buttons:
                    button_dict = {'text': button.get('text')}
                    
                    # ✅ CORREÇÃO CRÍTICA: Botão com URL usa 'url', botão com callback usa 'callback_data'
                    # Na API do Telegram, são mutuamente exclusivos - não pode ter ambos!
                    if button.get('url'):
                        # Botão de redirecionamento (link externo)
                        button_dict['url'] = button['url']
                        logger.debug(f"🔗 Botão de link: {button.get('text')} → {button['url'][:50]}...")
                    elif button.get('callback_data'):
                        # Botão de callback (gera PIX, verifica pagamento, etc)
                        button_dict['callback_data'] = button['callback_data']
                        logger.debug(f"🔘 Botão de callback: {button.get('text')} → {button['callback_data']}")
                    else:
                        # Fallback: se não tiver nenhum, usar callback padrão
                        button_dict['callback_data'] = 'button_pressed'
                        logger.warning(f"⚠️ Botão sem 'url' nem 'callback_data': {button.get('text')} - usando fallback")
                    
                    inline_keyboard.append([button_dict])
                reply_markup = {'inline_keyboard': inline_keyboard}
            
            # Enviar mídia + mensagem
            if media_url:
                if media_type == 'video':
                    url = f"{base_url}/sendVideo"
                    payload = {
                        'chat_id': chat_id,
                        'video': media_url,
                        'caption': message,
                        'parse_mode': 'HTML'
                    }
                elif media_type == 'audio':
                    url = f"{base_url}/sendAudio"
                    payload = {
                        'chat_id': chat_id,
                        'audio': media_url,
                        'caption': message,
                        'parse_mode': 'HTML'
                    }
                else:  # photo
                    url = f"{base_url}/sendPhoto"
                    payload = {
                        'chat_id': chat_id,
                        'photo': media_url,
                        'caption': message,
                        'parse_mode': 'HTML'
                    }
                
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                
                response = requests.post(url, json=payload, timeout=3)
            else:
                # Enviar apenas mensagem
                url = f"{base_url}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                
                response = requests.post(url, json=payload, timeout=3)
            
            if response.status_code == 200:
                result_data = response.json()
                if result_data.get('ok'):
                    logger.info(f"✅ Mensagem enviada para chat {chat_id}")
                    
                    # ✅ CHAT: Salvar mensagem enviada pelo bot no banco
                    try:
                        from app import app, db
                        from models import BotUser, BotMessage, Bot
                        import json
                        import uuid as uuid_lib
                        
                        with app.app_context():
                            # Buscar bot pelo token para obter bot_id
                            bot_id = None
                            with self._bots_lock:
                                for bid, bot_info in self.active_bots.items():
                                    if bot_info.get('token') == token:
                                        bot_id = bid
                                        break
                            
                            # Se não encontrou pelos bots ativos, buscar no banco
                            if not bot_id:
                                bot = Bot.query.filter_by(token=token).first()
                                if bot:
                                    bot_id = bot.id
                            
                            if bot_id:
                                # Buscar bot_user pelo bot_id e telegram_user_id
                                bot_user = BotUser.query.filter_by(
                                    bot_id=bot_id,
                                    telegram_user_id=str(chat_id),
                                    archived=False
                                ).first()
                                
                                if bot_user:
                                    telegram_msg_id = result_data.get('result', {}).get('message_id')
                                    message_id = str(telegram_msg_id) if telegram_msg_id else str(uuid_lib.uuid4().hex)
                                    
                                    bot_message = BotMessage(
                                        bot_id=bot_id,
                                        bot_user_id=bot_user.id,
                                        telegram_user_id=str(chat_id),
                                        message_id=message_id,
                                        message_text=message,
                                        message_type='text' if not media_url else media_type,
                                        direction='outgoing',
                                        is_read=True,  # Mensagens do bot já são "lidas"
                                        raw_data=json.dumps(result_data) if result_data else None
                                    )
                                    db.session.add(bot_message)
                                    db.session.commit()
                                    logger.debug(f"✅ Mensagem enviada pelo bot salva no banco: {message[:50]}...")
                                else:
                                    logger.debug(f"⚠️ BotUser não encontrado para salvar mensagem enviada: bot_id={bot_id}, chat_id={chat_id}")
                            else:
                                logger.debug(f"⚠️ Bot não encontrado pelo token para salvar mensagem enviada")
                    except Exception as e:
                        logger.error(f"❌ Erro ao salvar mensagem enviada pelo bot: {e}")
                        # Não interromper o fluxo se falhar ao salvar
                    
                    # Retornar dados completos se sucesso, senão True para compatibilidade
                    return result_data if result_data.get('result') else True
                else:
                    logger.error(f"❌ Telegram API retornou erro: {result_data.get('description', 'Erro desconhecido')}")
                    return False
            else:
                logger.error(f"❌ Erro ao enviar mensagem: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout ao enviar mensagem para chat {chat_id}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem Telegram: {e}")
            return False
    
    def get_bot_status(self, bot_id: int, verify_telegram: bool = False) -> Dict[str, Any]:
        """
        Obtém status de um bot
        
        Args:
            bot_id: ID do bot
            verify_telegram: Se True, verifica REALMENTE se bot responde no Telegram
        
        Returns:
            Informações de status
        """
        # ✅ CORREÇÃO: Acessar com LOCK
        with self._bots_lock:
            if bot_id not in self.active_bots:
                return {
                    'is_running': False,
                    'status': 'stopped'
                }
            
            bot_info = self.active_bots[bot_id].copy()
            token = bot_info.get('token')
        
        # ✅ VERIFICAÇÃO REAL: Se solicitado, verificar se bot responde no Telegram
        if verify_telegram and token:
            try:
                url = f"https://api.telegram.org/bot{token}/getMe"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if not data.get('ok'):
                        # Token inválido ou bot não responde
                        logger.warning(f"⚠️ Bot {bot_id} não responde no Telegram (token inválido/bloqueado)")
                        return {
                            'is_running': False,
                            'status': 'offline',
                            'reason': 'telegram_unreachable'
                        }
                else:
                    # Erro de conexão
                    logger.warning(f"⚠️ Bot {bot_id} não acessível via Telegram API (status {response.status_code})")
                    return {
                        'is_running': False,
                        'status': 'offline',
                        'reason': 'api_error'
                    }
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar bot {bot_id} no Telegram: {e}")
                return {
                    'is_running': False,
                    'status': 'offline',
                    'reason': 'verification_failed'
                }
        
        # Bot está em active_bots e (se verificado) responde no Telegram
        return {
            'is_running': True,
            'status': bot_info['status'],
            'started_at': bot_info['started_at'].isoformat(),
            'uptime': (datetime.now() - bot_info['started_at']).total_seconds()
        }
    
    def schedule_downsells(self, bot_id: int, payment_id: str, chat_id: int, downsells: list, original_price: float = 0, original_button_index: int = -1):
        """
        Agenda downsells para um pagamento pendente
        
        Args:
            bot_id: ID do bot
            payment_id: ID do pagamento
            chat_id: ID do chat
            downsells: Lista de downsells configurados
            original_price: Preço do botão original (para cálculo percentual)
            original_button_index: Índice do botão original clicado
        """
        logger.info(f"🚨 FUNCAO SCHEDULE_DOWNSELLS CHAMADA! bot_id={bot_id}, payment_id={payment_id}")
        try:
            logger.info(f"🔍 DEBUG Schedule - scheduler existe: {self.scheduler is not None}")
            logger.info(f"🔍 DEBUG Schedule - downsells: {downsells}")
            logger.info(f"🔍 DEBUG Schedule - downsells vazio: {not downsells}")
            
            if not self.scheduler:
                logger.error(f"❌ Scheduler não está disponível!")
                return
            
            if not downsells:
                logger.warning(f"⚠️ Lista de downsells está vazia!")
                return
            
            logger.info(f"📅 Agendando {len(downsells)} downsell(s) para pagamento {payment_id}")
            
            for i, downsell in enumerate(downsells):
                delay_minutes = int(downsell.get('delay_minutes', 5))  # Converter para int
                job_id = f"downsell_{bot_id}_{payment_id}_{i}"
                
                # Calcular data/hora de execução
                run_time = datetime.now() + timedelta(minutes=delay_minutes)
                logger.info(f"🔍 DEBUG Agendamento - Hora atual: {datetime.now()}")
                logger.info(f"🔍 DEBUG Agendamento - Hora execução: {run_time}")
                
                # Agendar downsell com preço original para cálculo percentual
                self.scheduler.add_job(
                    id=job_id,
                    func=self._send_downsell,
                    args=[bot_id, payment_id, chat_id, downsell, i, original_price, original_button_index],
                    trigger='date',
                    run_date=run_time,
                    replace_existing=True
                )
                
                logger.info(f"✅ Downsell {i+1} agendado para {delay_minutes} minutos")
                
        except Exception as e:
            logger.error(f"❌ Erro ao agendar downsells: {e}")
    
    def _send_downsell(self, bot_id: int, payment_id: str, chat_id: int, downsell: dict, index: int, original_price: float = 0, original_button_index: int = -1):
        """
        Envia downsell agendado
        
        Args:
            bot_id: ID do bot
            payment_id: ID do pagamento
            chat_id: ID do chat
            downsell: Configuração do downsell
            index: Índice do downsell
            original_price: Preço do botão original (para cálculo percentual)
            original_button_index: Índice do botão original clicado
        """
        logger.info(f"🚨 FUNCAO _SEND_DOWNSELL CHAMADA! bot_id={bot_id}, payment_id={payment_id}, index={index}")
        logger.info(f"🔍 DEBUG _send_downsell - downsell config: {downsell}")
        logger.info(f"🔍 DEBUG _send_downsell - original_price: {original_price}")
        logger.info(f"🔍 DEBUG _send_downsell - original_button_index: {original_button_index}")
        
        try:
            logger.info(f"🔍 DEBUG _send_downsell - Verificando pagamento...")
            # Verificar se pagamento ainda está pendente
            if not self._is_payment_pending(payment_id):
                logger.info(f"💰 Pagamento {payment_id} já foi pago, cancelando downsell {index+1}")
                return
            logger.info(f"✅ Pagamento ainda está pendente")
            
            # Verificar se bot ainda está ativo
            logger.info(f"🔍 DEBUG _send_downsell - Verificando bot...")
            if bot_id not in self.active_bots:
                logger.warning(f"🤖 Bot {bot_id} não está mais ativo, cancelando downsell {index+1}")
                return
            logger.info(f"✅ Bot está ativo")
            
            # ✅ CORREÇÃO: Acessar com LOCK
            with self._bots_lock:
                if bot_id not in self.active_bots:
                    return
                bot_info = self.active_bots[bot_id].copy()
            
            token = bot_info['token']
            
            # ✅ CRÍTICO: Buscar config atualizada do BANCO (não usar cache da memória)
            # Isso garante que mudanças recentes na configuração sejam refletidas
            from app import app, db
            from models import Bot as BotModel
            
            with app.app_context():
                bot = BotModel.query.get(bot_id)
                if bot and bot.config:
                    config = bot.config.to_dict()
                    logger.info(f"🔄 Config recarregada do banco para downsell")
                else:
                    # Fallback: usar config da memória se não encontrar no banco
                    config = bot_info.get('config', {})
                    logger.warning(f"⚠️ Usando config da memória para downsell")
            
            # Verificar se downsells ainda estão habilitados
            logger.info(f"🔍 DEBUG _send_downsell - Verificando se downsells estão habilitados...")
            if not config.get('downsells_enabled', False):
                logger.info(f"📵 Downsells desabilitados, cancelando downsell {index+1}")
                return
            logger.info(f"✅ Downsells estão habilitados")
            
            message = downsell.get('message', '')
            media_url = downsell.get('media_url', '')
            media_type = downsell.get('media_type', 'video')
            audio_enabled = downsell.get('audio_enabled', False)
            audio_url = downsell.get('audio_url', '')
            
            # ✅ NOVO: Calcular preço baseado no modo (fixo ou percentual)
            pricing_mode = downsell.get('pricing_mode', 'fixed')
            logger.info(f"🔍 DEBUG pricing_mode: {pricing_mode}")
            
            # 🎯 ESTRATÉGIA DE CONVERSÃO: MODO PERCENTUAL = TODOS OS BOTÕES COM DESCONTO
            if pricing_mode == 'percentage':
                discount_percentage = float(downsell.get('discount_percentage', 50))
                discount_percentage = max(1, min(95, discount_percentage))  # Validar 1-95%
                
                # Buscar TODOS os botões principais do config
                main_buttons = config.get('main_buttons', [])
                
                if main_buttons and len(main_buttons) > 0:
                    # ✅ MÚLTIPLOS BOTÕES: Aplicar desconto em cada produto
                    buttons = []
                    logger.info(f"💜 MODO PERCENTUAL: {discount_percentage}% OFF em TODOS os produtos!")
                    
                    for btn_index, btn in enumerate(main_buttons):
                        original_btn_price = float(btn.get('price', 0))
                        logger.info(f"🔍 DEBUG btn_index={btn_index}, btn={btn}, original_btn_price={original_btn_price}")
                        
                        if original_btn_price <= 0:
                            logger.warning(f"⚠️ Botão {btn_index} sem preço válido: {original_btn_price}")
                            continue  # Pular botões sem preço
                        
                        # Calcular preço com desconto
                        discounted_price = original_btn_price * (1 - discount_percentage / 100)
                        logger.info(f"🔍 DEBUG cálculo: {original_btn_price} * (1 - {discount_percentage}/100) = {discounted_price}")
                        
                        # Validar mínimo
                        if discounted_price < 0.50:
                            logger.warning(f"⚠️ Preço {btn.get('text', 'Produto')} muito baixo após desconto, pulando")
                            continue
                        
                        # Texto do botão: Nome + Percentual (sem mostrar valor)
                        btn_text = f"🔥 {btn.get('text', 'Produto')} ({int(discount_percentage)}% OFF)"
                        
                        buttons.append({
                            'text': btn_text,
                            'callback_data': f'downsell_{index}_{int(discounted_price*100)}_{btn_index}'  # Formato: downsell_INDEX_PRICE_ORIGINAL_BTN
                        })
                        
                        logger.info(f"  ✅ {btn.get('text')}: R$ {original_btn_price:.2f} → R$ {discounted_price:.2f} ({discount_percentage}% OFF)")
                    
                    if len(buttons) == 0:
                        logger.error(f"❌ Nenhum botão válido após aplicar desconto percentual")
                        return
                    
                    logger.info(f"🎯 Total de {len(buttons)} opções de compra com desconto")
                    
                else:
                    # Fallback: se não tiver main_buttons, usar preço original (comportamento antigo)
                    logger.info(f"🔍 DEBUG fallback - original_price: {original_price}")
                    logger.info(f"🔍 DEBUG fallback - discount_percentage: {discount_percentage}")
                    
                    if original_price > 0:
                        price = original_price * (1 - discount_percentage / 100)
                        logger.info(f"💜 MODO PERCENTUAL (fallback): {discount_percentage}% OFF de R$ {original_price:.2f} = R$ {price:.2f}")
                    else:
                        # ✅ CORREÇÃO CRÍTICA: Se original_price for 0, usar preço padrão de downsell
                        logger.warning(f"⚠️ original_price é 0! Usando preço padrão para downsell")
                        price = 9.97  # Preço padrão para downsells
                        logger.info(f"💜 MODO PERCENTUAL (corrigido): Usando preço padrão R$ {price:.2f}")
                    
                    if price < 0.50:
                        logger.error(f"❌ Preço muito baixo (R$ {price:.2f}), mínimo R$ 0,50")
                        return
                    
                    button_text = downsell.get('button_text', '').strip()
                    if not button_text:
                        button_text = f'🛒 Comprar por R$ {price:.2f} ({int(discount_percentage)}% OFF)'
                    
                    buttons = [{
                        'text': button_text,
                        'callback_data': f'downsell_{index}_{int(price*100)}_{0}'  # Formato: downsell_INDEX_PRICE_ORIGINAL_BTN
                    }]
            
            else:
                # 💙 MODO FIXO: Um único botão com preço fixo (comportamento original)
                price = float(downsell.get('price', 0))
                logger.info(f"💙 MODO FIXO: R$ {price:.2f}")
                
                if price < 0.50:
                    logger.error(f"❌ Preço muito baixo (R$ {price:.2f}), mínimo R$ 0,50")
                    return
                
                button_text = downsell.get('button_text', '').strip()
                if not button_text:
                    button_text = f'🛒 Comprar por R$ {price:.2f}'
                
                buttons = [{
                    'text': button_text,
                    'callback_data': f'downsell_{index}_{int(price*100)}_{0}'  # Formato: downsell_INDEX_PRICE_ORIGINAL_BTN
                }]
            
            # ✅ VERIFICAR SE TEM ORDER BUMP PARA ESTE DOWNSELL
            order_bump = downsell.get('order_bump', {})
            
            logger.info(f"🔍 DEBUG _send_downsell - Botões criados: {len(buttons)}")
            logger.info(f"  - message: {message}")
            logger.info(f"  - media_url: {media_url}")
            logger.info(f"  - order_bump_enabled: {order_bump.get('enabled', False)}")
            
            logger.info(f"📨 Enviando downsell {index+1} para chat {chat_id}")
            
            # Enviar mensagem com ou sem mídia
            if media_url and '/c/' not in media_url and media_url.startswith('http'):
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    media_url=media_url,
                    media_type=media_type,
                    buttons=buttons
                )
                if not result:
                    # Fallback sem mídia se falhar
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        buttons=buttons
                    )
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    buttons=buttons
                )
            
            logger.info(f"✅ Downsell {index+1} enviado com sucesso!")
            
            # ✅ Enviar áudio adicional se habilitado
            if audio_enabled and audio_url:
                logger.info(f"🎤 Enviando áudio complementar do Downsell {index+1}...")
                audio_result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="",
                    media_url=audio_url,
                    media_type='audio',
                    buttons=None
                )
                if audio_result:
                    logger.info(f"✅ Áudio complementar do Downsell {index+1} enviado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar downsell {index+1}: {e}")
            import traceback
            traceback.print_exc()
    
    def _is_payment_pending(self, payment_id: str) -> bool:
        """
        Verifica se pagamento ainda está pendente
        
        Args:
            payment_id: ID do pagamento
            
        Returns:
            True se ainda está pendente
        """
        try:
            from app import app, db
            from models import Payment
            
            with app.app_context():
                payment = Payment.query.filter_by(payment_id=payment_id).first()
                logger.info(f"🔍 DEBUG _is_payment_pending - payment_id: {payment_id}")
                if payment:
                    logger.info(f"🔍 DEBUG _is_payment_pending - status: {payment.status}")
                    return payment.status == 'pending'
                else:
                    logger.warning(f"⚠️ Pagamento {payment_id} não encontrado no banco!")
                    return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao verificar status do pagamento {payment_id}: {e}")
            return False
    
    def count_eligible_leads(self, bot_id: int, target_audience: str = 'non_buyers', 
                            days_since_last_contact: int = 3, exclude_buyers: bool = True) -> int:
        """
        Conta quantos leads são elegíveis para remarketing
        
        Args:
            bot_id: ID do bot
            target_audience: Tipo de público (all, non_buyers, abandoned_cart, inactive)
            days_since_last_contact: Dias mínimos sem contato
            exclude_buyers: Excluir quem já comprou
            
        Returns:
            Quantidade de leads elegíveis
        """
        from app import app, db
        from models import BotUser, Payment, RemarketingBlacklist
        from datetime import datetime, timedelta
        
        with app.app_context():
            # Data limite de último contato
            contact_limit = datetime.now() - timedelta(days=days_since_last_contact)
            
            # Query base: usuários do bot (apenas ativos, não arquivados)
            query = BotUser.query.filter_by(bot_id=bot_id, archived=False)
            
            # Filtro: último contato há X dias
            if days_since_last_contact > 0:
                query = query.filter(BotUser.last_interaction <= contact_limit)
            
            # Filtro: excluir blacklist
            blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                bot_id=bot_id
            ).all()
            blacklist_ids = [b[0] for b in blacklist_ids]
            if blacklist_ids:
                query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
            
            # Filtro: excluir compradores
            if exclude_buyers:
                buyer_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid'
                ).distinct().all()
                buyer_ids = [b[0] for b in buyer_ids if b[0]]
                if buyer_ids:
                    query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
            
            # Filtro por tipo de público
            if target_audience == 'abandoned_cart':
                # Usuários que geraram PIX mas não pagaram
                abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'pending'
                ).distinct().all()
                abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                if abandoned_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                else:
                    return 0
            
            elif target_audience == 'inactive':
                # Inativos há 7+ dias
                inactive_limit = datetime.now() - timedelta(days=7)
                query = query.filter(BotUser.last_interaction <= inactive_limit)
            
            return query.count()
    
    def send_remarketing_campaign(self, campaign_id: int, bot_token: str):
        """
        Envia campanha de remarketing em background
        
        Args:
            campaign_id: ID da campanha
            bot_token: Token do bot
        """
        from app import app, db, socketio
        from models import RemarketingCampaign, BotUser, Payment, RemarketingBlacklist
        from datetime import datetime, timedelta
        import time
        
        def send_campaign():
            with app.app_context():
                campaign = db.session.get(RemarketingCampaign, campaign_id)
                if not campaign:
                    return
                
                # Atualizar status
                campaign.status = 'sending'
                campaign.started_at = datetime.now()
                db.session.commit()
                
                logger.info(f"📢 Iniciando envio de remarketing: {campaign.name}")
                
                # Buscar leads elegíveis (apenas usuários ativos, não arquivados)
                contact_limit = datetime.now() - timedelta(days=campaign.days_since_last_contact)
                
                query = BotUser.query.filter_by(bot_id=campaign.bot_id, archived=False)
                
                # Filtro de último contato
                if campaign.days_since_last_contact > 0:
                    query = query.filter(BotUser.last_interaction <= contact_limit)
                
                # Excluir blacklist
                blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                    bot_id=campaign.bot_id
                ).all()
                blacklist_ids = [b[0] for b in blacklist_ids]
                if blacklist_ids:
                    query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                
                # Excluir compradores
                if campaign.exclude_buyers:
                    buyer_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == campaign.bot_id,
                        Payment.status == 'paid'
                    ).distinct().all()
                    buyer_ids = [b[0] for b in buyer_ids if b[0]]
                    if buyer_ids:
                        query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                
                # Segmentação por público
                if campaign.target_audience == 'abandoned_cart':
                    abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == campaign.bot_id,
                        Payment.status == 'pending'
                    ).distinct().all()
                    abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                    if abandoned_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                
                elif campaign.target_audience == 'inactive':
                    inactive_limit = datetime.now() - timedelta(days=7)
                    query = query.filter(BotUser.last_interaction <= inactive_limit)
                
                leads = query.all()
                campaign.total_targets = len(leads)
                db.session.commit()
                
                logger.info(f"🎯 {campaign.total_targets} leads elegíveis")
                
                # Enviar em batches (20 msgs/segundo)
                batch_size = 20
                for i in range(0, len(leads), batch_size):
                    batch = leads[i:i+batch_size]
                    
                    for lead in batch:
                        try:
                            # Personalizar mensagem
                            message = campaign.message.replace('{nome}', lead.first_name or 'Cliente')
                            message = message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])
                            
                            # Preparar botões (converter para formato de callback_data)
                            remarketing_buttons = []
                            if campaign.buttons:
                                # ✅ CORREÇÃO: Parsear JSON se for string
                                buttons_list = campaign.buttons
                                if isinstance(campaign.buttons, str):
                                    import json
                                    try:
                                        buttons_list = json.loads(campaign.buttons)
                                    except:
                                        buttons_list = []
                                
                                for btn_idx, btn in enumerate(buttons_list):
                                    if btn.get('price') and btn.get('description'):
                                        # Botão de compra - gera PIX
                                        # ✅ NOVO FORMATO: rmkt_CAMPAIGN_BTN_INDEX (< 20 bytes)
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Comprar'),
                                            'callback_data': f"rmkt_{campaign.id}_{btn_idx}"
                                        })
                                    elif btn.get('url'):
                                        # Botão de URL
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Link'),
                                            'url': btn.get('url')
                                        })
                            
                            # Log dos botões para debug
                            logger.info(f"📤 Enviando para {lead.first_name} com {len(remarketing_buttons)} botão(ões)")
                            for btn in remarketing_buttons:
                                logger.info(f"   🔘 Botão: {btn.get('text')} | callback: {btn.get('callback_data', 'N/A')[:50]}")
                            
                            # Enviar mensagem
                            result = self.send_telegram_message(
                                token=bot_token,
                                chat_id=lead.telegram_user_id,
                                message=message,
                                media_url=campaign.media_url,
                                media_type=campaign.media_type,
                                buttons=remarketing_buttons
                            )
                            
                            if result:
                                campaign.total_sent += 1
                                
                                # ✅ Enviar áudio adicional se habilitado
                                if campaign.audio_enabled and campaign.audio_url:
                                    logger.info(f"🎤 Enviando áudio complementar para {lead.first_name}...")
                                    audio_result = self.send_telegram_message(
                                        token=bot_token,
                                        chat_id=lead.telegram_user_id,
                                        message="",
                                        media_url=campaign.audio_url,
                                        media_type='audio',
                                        buttons=None
                                    )
                            else:
                                campaign.total_failed += 1
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao enviar para {lead.telegram_user_id}: {e}")
                            if "bot was blocked" in str(e).lower():
                                campaign.total_blocked += 1
                                # Adicionar na blacklist
                                blacklist = RemarketingBlacklist(
                                    bot_id=campaign.bot_id,
                                    telegram_user_id=lead.telegram_user_id,
                                    reason='bot_blocked'
                                )
                                db.session.add(blacklist)
                            else:
                                campaign.total_failed += 1
                    
                    # Commit do batch
                    db.session.commit()
                    
                    # Emitir progresso via WebSocket
                    socketio.emit('remarketing_progress', {
                        'campaign_id': campaign.id,
                        'sent': campaign.total_sent,
                        'failed': campaign.total_failed,
                        'blocked': campaign.total_blocked,
                        'total': campaign.total_targets,
                        'percentage': round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                    })
                    
                    # Rate limiting (20 msgs/segundo)
                    time.sleep(1)
                
                # Finalizar campanha
                campaign.status = 'completed'
                campaign.completed_at = datetime.now()
                db.session.commit()
                
                logger.info(f"✅ Campanha concluída: {campaign.total_sent}/{campaign.total_targets} enviados")
                
                # Emitir conclusão
                socketio.emit('remarketing_completed', {
                    'campaign_id': campaign.id,
                    'total_sent': campaign.total_sent,
                    'total_failed': campaign.total_failed,
                    'total_blocked': campaign.total_blocked
                })
        
        # Executar em thread separada
        thread = threading.Thread(target=send_campaign)
        thread.daemon = True
        thread.start()
    
    def cancel_downsells(self, payment_id: str):
        """
        Cancela downsells agendados para um pagamento
        
        Args:
            payment_id: ID do pagamento
        """
        try:
            if not self.scheduler:
                return
            
            # Encontrar e remover jobs de downsell para este pagamento
            jobs_to_remove = []
            for job_id in self.scheduler.get_jobs():
                if job_id.id.startswith(f"downsell_") and payment_id in job_id.id:
                    jobs_to_remove.append(job_id.id)
            
            for job_id in jobs_to_remove:
                self.scheduler.remove_job(job_id)
                logger.info(f"🚫 Downsell cancelado: {job_id}")
                
        except Exception as e:
            logger.error(f"Erro ao cancelar downsells para pagamento {payment_id}: {e}")

