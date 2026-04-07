"""
Bot Manager - Gerenciador de Bots do Telegram
Responsável por validar tokens, iniciar/parar bots e processar webhooks
"""

import requests
from requests.adapters import HTTPAdapter
import threading
import time
import logging
import json
import subprocess
import socket
import urllib3.util.connection
from urllib3.util.retry import Retry
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz
from redis_manager import get_redis_connection
import hashlib
import hmac
from flow_engine_router_v8 import get_message_router
from internal_logic.services.bot_messenger import BotMessenger
from internal_logic.services.bot_runner import BotRunner
from internal_logic.services.flow_engine import FlowEngine
from internal_logic.services.payment_service import PaymentService, get_payment_service

logger = logging.getLogger(__name__)

# Configurar logging para este módulo
logger.setLevel(logging.INFO)


def checkActiveFlow(config: Dict[str, Any]) -> bool:
    """
    ✅ V8 ULTRA: Verifica se Flow Editor está ativo e válido
    
    Função centralizada para detecção de modo ativo.
    Garante parse consistente e verificação robusta.
    
    Args:
        config: Dicionário de configuração do bot
        
    Returns:
        True se flow está ativo E tem steps válidos
        False caso contrário (inclui flow desabilitado, vazio ou inválido)
    """
    import json
    
    # ✅ Parsear flow_enabled (pode vir como string "True"/"False" ou boolean)
    flow_enabled_raw = config.get('flow_enabled', False)
    
    if isinstance(flow_enabled_raw, str):
        flow_enabled = flow_enabled_raw.lower().strip() in ('true', '1', 'yes', 'on', 'enabled')
    elif isinstance(flow_enabled_raw, bool):
        flow_enabled = flow_enabled_raw
    elif isinstance(flow_enabled_raw, (int, float)):
        flow_enabled = bool(flow_enabled_raw)
    else:
        flow_enabled = False  # Default seguro: desabilitado
    
    # ✅ Se flow não está habilitado, retornar False imediatamente
    if not flow_enabled:
        return False
    
    # ✅ Parsear flow_steps (pode vir como string JSON ou list)
    flow_steps_raw = config.get('flow_steps', [])
    flow_steps = []
    
    if flow_steps_raw:
        if isinstance(flow_steps_raw, str):
            try:
                # Tentar parsear como JSON
                parsed = json.loads(flow_steps_raw)
                if isinstance(parsed, list):
                    flow_steps = parsed
                else:
                    logger.warning(f"⚠️ flow_steps JSON não é lista: {type(parsed)}")
                    flow_steps = []
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"⚠️ Erro ao parsear flow_steps JSON: {e}")
                flow_steps = []
        elif isinstance(flow_steps_raw, list):
            flow_steps = flow_steps_raw
        else:
            logger.warning(f"⚠️ flow_steps tem tipo inesperado: {type(flow_steps_raw)}")
            flow_steps = []
    
    # ✅ Retornar True apenas se flow está ativo E tem steps válidos
    is_active = flow_enabled is True and flow_steps and isinstance(flow_steps, list) and len(flow_steps) > 0
    
    if is_active:
        logger.info(f"✅ Flow Editor ATIVO: {len(flow_steps)} steps configurados")
    else:
        logger.info(f" Flow Editor INATIVO: flow_enabled={flow_enabled}, steps_count={len(flow_steps)}")
    
    return is_active

# Forçar urllib3/requests a ignorar IPv6 (evita NameResolutionError com IPv6 instável)
urllib3.util.connection.HAS_IPV6 = False
try:
    requests.packages.urllib3.util.connection.HAS_IPV6 = False  # type: ignore[attr-defined]
except AttributeError:
    pass


def _ipv4_only_family() -> int:
    return socket.AF_INET


urllib3.util.connection.allowed_gai_family = _ipv4_only_family
try:
    requests.packages.urllib3.util.connection.allowed_gai_family = _ipv4_only_family  # type: ignore[attr-defined]
except AttributeError:
    pass

# Compatibilidade com eventlet: create_connection do socket verde não aceita "family"
try:
    import eventlet.green.socket as eventlet_socket  # type: ignore[import]

    _green_create_connection = eventlet_socket.create_connection

    def _create_connection_ipv4(address, timeout=None, source_address=None, **kwargs):
        """
        Compat layer para eventlet >=0.33 com urllib3>=2, removendo kwargs não suportados.
        """
        kwargs.pop("family", None)
        return _green_create_connection(address, timeout, source_address, **kwargs)

    eventlet_socket.create_connection = _create_connection_ipv4
    socket.create_connection = _create_connection_ipv4
except ImportError:
    # eventlet não disponível (execução síncrona/local)
    pass

# urllib3>=2 passa family/flags para create_connection; eventlet ignora.
_original_create_connection = urllib3.util.connection.create_connection


def _create_connection_strip_family(address, timeout=None, source_address=None, **kwargs):
    kwargs.pop("family", None)
    kwargs.pop("flags", None)
    return _original_create_connection(address, timeout, source_address, **kwargs)


urllib3.util.connection.create_connection = _create_connection_strip_family
try:
    requests.packages.urllib3.util.connection.create_connection = _create_connection_strip_family  # type: ignore[attr-defined]
except AttributeError:
    pass

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
        from internal_logic.core.models import PoolBot, RedirectPool
        
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
        
        # ✅ CRÍTICO V4.1: RECUPERAR DADOS COMPLETOS DO REDIS (MESMO DO PAGEVIEW!)
        # ViewContent DEVE usar os MESMOS dados do PageView para garantir matching perfeito!
        from utils.tracking_service import TrackingServiceV4
        from utils.meta_pixel import MetaPixelAPI
        from utils.encryption import decrypt
        
        tracking_service_v4 = TrackingServiceV4()
        tracking_data = {}
        
        # ✅ PRIORIDADE 1: Recuperar do tracking_token (se disponível)
        if hasattr(bot_user, 'tracking_session_id') and bot_user.tracking_session_id:
            tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
            logger.info(f"✅ ViewContent - tracking_data recuperado do Redis: {len(tracking_data)} campos")
        
        # ✅ PRIORIDADE 2: Se não tem tracking_token, usar dados do BotUser (fallback)
        if not tracking_data:
            tracking_data = {
                'fbclid': getattr(bot_user, 'fbclid', None),
                'fbp': getattr(bot_user, 'fbp', None),
                'fbc': getattr(bot_user, 'fbc', None),
                'client_ip': getattr(bot_user, 'ip_address', None),
                'client_user_agent': getattr(bot_user, 'user_agent', None),
                'utm_source': getattr(bot_user, 'utm_source', None),
                'utm_campaign': getattr(bot_user, 'utm_campaign', None),
                'campaign_code': getattr(bot_user, 'campaign_code', None)
            }
            logger.info(f"✅ ViewContent - usando dados do BotUser (fallback)")
        
        # ✅ CRÍTICO: Construir user_data usando MetaPixelAPI._build_user_data() (MESMO DO PAGEVIEW!)
        # Isso garante que external_id seja hashado corretamente e fbp/fbc sejam incluídos
        
        # ✅ CORREÇÃO CRÍTICA: Normalizar external_id para garantir matching consistente com PageView/Purchase
        # Se fbclid > 80 chars, normalizar para hash MD5 (32 chars) - MESMO algoritmo usado em todos os eventos
        from utils.meta_pixel import normalize_external_id
        external_id_raw = tracking_data.get('fbclid') or getattr(bot_user, 'fbclid', None)
        external_id_value = normalize_external_id(external_id_raw) if external_id_raw else None
        if external_id_value != external_id_raw and external_id_raw:
            logger.info(f"✅ ViewContent - external_id normalizado: {external_id_value} (original len={len(external_id_raw)})")
            logger.info(f"✅ ViewContent - MATCH GARANTIDO com PageView/Purchase (mesmo algoritmo de normalização)")
        elif external_id_value:
            logger.info(f"✅ ViewContent - external_id usado original: {external_id_value[:30]}... (len={len(external_id_value)})")
        
        fbp_value = tracking_data.get('fbp') or getattr(bot_user, 'fbp', None)
        
        # ✅ CORREÇÃO CRÍTICA: Verificar fbc_origin para garantir que só enviamos fbc real (cookie)
        # ✅ CRÍTICO: Aceitar fbc se veio do cookie OU foi gerado conforme documentação Meta
        # Meta aceita _fbc gerado quando fbclid está presente na URL (conforme documentação oficial)
        fbc_value = None
        fbc_origin = tracking_data.get('fbc_origin')
        
        # ✅ PRIORIDADE 1: tracking_data com fbc (cookie OU generated_from_fbclid)
        # Meta aceita ambos conforme documentação oficial
        if tracking_data.get('fbc') and fbc_origin in ('cookie', 'generated_from_fbclid'):
            fbc_value = tracking_data.get('fbc')
            logger.info(f"[META VIEWCONTENT] ViewContent - fbc recuperado do tracking_data (origem: {fbc_origin}): {fbc_value[:50]}...")
        # ✅ PRIORIDADE 2: BotUser (assumir que veio de cookie se foi salvo via process_start_async)
        elif bot_user and getattr(bot_user, 'fbc', None):
            fbc_value = bot_user.fbc
            logger.info(f"[META VIEWCONTENT] ViewContent - fbc recuperado do BotUser (assumido como real): {fbc_value[:50]}...")
        else:
            logger.warning(f"[META VIEWCONTENT] ViewContent - fbc ausente ou ignorado (origem: {fbc_origin or 'ausente'}) - Meta terá atribuição reduzida")
        
        ip_value = tracking_data.get('client_ip') or getattr(bot_user, 'ip_address', None)
        ua_value = tracking_data.get('client_user_agent') or getattr(bot_user, 'user_agent', None)
        
        # ✅ Usar _build_user_data para garantir formato correto (hash SHA256, array external_id, etc)
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=str(bot_user.telegram_user_id),  # ✅ Telegram ID
            external_id=external_id_value,  # ✅ fbclid normalizado (será hashado)
            email=None,  # BotUser não tem email
            phone=None,  # BotUser não tem phone
            client_ip=ip_value,
            client_user_agent=ua_value,
            fbp=fbp_value,  # ✅ CRÍTICO: FBP do PageView
            fbc=fbc_value  # ✅ CRÍTICO: FBC do PageView (apenas se real/cookie)
        )
        
        # ✅ Construir custom_data (filtrar None/vazios)
        custom_data = {
            'content_type': 'product'
        }
        if pool.id:
            custom_data['content_ids'] = [str(pool.id)]
        if pool.name:
            custom_data['content_name'] = pool.name
        if bot.id:
            custom_data['bot_id'] = bot.id
        if bot.username:
            custom_data['bot_username'] = bot.username
        if tracking_data.get('utm_source') or getattr(bot_user, 'utm_source', None):
            custom_data['utm_source'] = tracking_data.get('utm_source') or getattr(bot_user, 'utm_source', None)
        if tracking_data.get('utm_campaign') or getattr(bot_user, 'utm_campaign', None):
            custom_data['utm_campaign'] = tracking_data.get('utm_campaign') or getattr(bot_user, 'utm_campaign', None)
        if tracking_data.get('campaign_code') or getattr(bot_user, 'campaign_code', None):
            custom_data['campaign_code'] = tracking_data.get('campaign_code') or getattr(bot_user, 'campaign_code', None)
        
        # ✅ CRÍTICO: event_source_url (mesmo do PageView)
        event_source_url = tracking_data.get('event_source_url') or tracking_data.get('first_page')
        if not event_source_url and pool.slug:
            event_source_url = f'https://app.grimbots.online/go/{pool.slug}'
        
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
            'event_source_url': event_source_url,  # ✅ ADICIONAR
            'user_data': user_data,  # ✅ AGORA COMPLETO (fbp, fbc, external_id hashado, ip, ua)
            'custom_data': custom_data  # ✅ Sempre dict (nunca None)
        }
        
        # ✅ LOG: Verificar dados enviados
        external_ids = user_data.get('external_id', [])
        attributes_count = sum([
            1 if external_ids else 0,
            1 if user_data.get('em') else 0,
            1 if user_data.get('ph') else 0,
            1 if user_data.get('client_ip_address') else 0,
            1 if user_data.get('client_user_agent') else 0,
            1 if user_data.get('fbp') else 0,
            1 if user_data.get('fbc') else 0
        ])
        logger.info(f"[META VIEWCONTENT] ViewContent - User Data: {attributes_count}/7 atributos | " +
                   f"external_id={'✅' if external_ids else '❌'} | " +
                   f"fbp={'✅' if user_data.get('fbp') else '❌'} | " +
                   f"fbc={'✅' if user_data.get('fbc') else '❌'} | " +
                   f"ip={'✅' if user_data.get('client_ip_address') else '❌'} | " +
                   f"ua={'✅' if user_data.get('client_user_agent') else '❌'}")
        
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
        from internal_logic.core.models import get_brazil_time
        bot_user.meta_viewcontent_sent_at = get_brazil_time()
        
        # Commit da flag
        from internal_logic.core.extensions import db
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


# ============================================================================
# Helpers de tempo (horário do Brasil, mesmo em servidores fora do fuso)
# ============================================================================
try:
    _pytz = pytz.timezone('America/Sao_Paulo') if pytz else None
except Exception:
    _pytz = None


def get_brazil_time():
    """Retorna datetime no fuso de São Paulo.

    - Tenta usar pytz (mais preciso para DST).
    - Fallback: UTC-3 manual.
    - Último fallback: datetime.now() se algo der errado.
    """
    if _pytz:
        try:
            return datetime.now(_pytz)
        except Exception:
            pass
    try:
        return datetime.utcnow() - timedelta(hours=3)
    except Exception:
        return datetime.now()

from gateway_factory import GatewayFactory
from redis_manager import get_redis_connection
from redis_bot_state import redis_bot_state, get_namespaced_bot_state  # ✅ ISOLAMENTO: Importar factory V2
import json
import random
import time

class BotManager:
    """Gerenciador de bots Telegram - Com estado centralizado em Redis (Namespace Isolado V2)"""
    
    def __init__(self, socketio=None, scheduler=None, user_id=None, **kwargs):
        """
        Inicializa o BotManager com namespace isolado.
        
        ⚠️ Compatibilidade legada: Todos os parâmetros são opcionais.
        
        Args:
            socketio: Instância do SocketIO (opcional)
            scheduler: Agendador (opcional, compatibilidade legacy)
            user_id: ID do usuário para namespace isolado (opcional, fallback=1)
            **kwargs: Argumentos adicionais
        """
        # 🛑 BLINDAGEM REMOVIDA: user_id é opcional para compatibilidade com webhooks legados
        if not user_id:
            user_id = kwargs.get('user_id', None) or 1  # Fallback seguro
        
        self.socketio = socketio
        self.user_id = user_id
        
        # ✅ ISOLAMENTO NAMESPACE V2: Sempre usar estado isolado
        self.bot_state = get_namespaced_bot_state(user_id)
        logger.info(f"✅ BotManager inicializado com namespace isolado: gb:{user_id}:*")
        
        self.bot_threads: Dict[int, threading.Thread] = {}
        
        # ✅ CACHE DE RATE LIMITING (em memória - por worker)
        self.rate_limit_cache = {}  # {user_key: timestamp}
        
        # ✅ SESSÕES DE ORDER BUMP MIGRADAS PARA REDIS (multi-worker)
        # Chaves: gb:ob_session:{user_key} (TTL 10 min)
        # Chaves: gb:pix_cache:{user_key} (TTL 5 min)
        # Redis TTL faz cleanup automático - sem threads necessárias
        
        # ✅ LIMPEZA AUTOMÁTICA DO CACHE (a cada 5 minutos)
        def cleanup_cache():
            while True:
                time.sleep(300)  # 5 minutos
                from internal_logic.core.models import get_brazil_time
                now = get_brazil_time()
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
        
        # ✅ CONTROLE DE CONCORRÊNCIA: Limitar threads de remarketing simultâneas
        # Sistema multi-usuário: permite até 15 campanhas simultâneas para fluidez
        # Aumentado para suportar múltiplos usuários fazendo campanhas ao mesmo tempo
        self.remarketing_semaphore = threading.BoundedSemaphore(15)  # Máximo 15 campanhas simultâneas
        self.remarketing_queue = []  # Fila de campanhas aguardando (transparente para usuário)
        self.active_remarketing_campaigns = set()  # IDs de campanhas ativas

        # ✅ MESSENGER SERVICE: Delegação de envio de mensagens
        self.messenger = BotMessenger(max_concurrent=10)
        logger.info("✅ BotMessenger injetado no BotManager")

        # ✅ RUNNER SERVICE: Ciclo de vida dos bots (start, stop, polling)
        self.runner = BotRunner(
            bot_state=self.bot_state,
            on_update_received=self._process_telegram_update
        )
        logger.info("✅ BotRunner injetado no BotManager")

        # ✅ FLOW ENGINE: Processamento de mensagens e funil
        self.flow_engine = FlowEngine(
            messenger=self.messenger,
            bot_state=self.bot_state
        )
        logger.info("✅ FlowEngine injetado no BotManager")

        self._remarketing_workers_lock = threading.Lock()
        self._remarketing_workers: Dict[int, Dict[str, Any]] = {}

        # ✅ PATCH: Session reutilizável + Retry/Backoff para envios pesados (sendVideo)
        # Regra: manter impacto ZERO em outros tipos de mensagem; Session será usada somente em send_video_safe.
        self._telegram_session = requests.Session()
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(['GET', 'POST']),
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=50,
            pool_maxsize=50,
        )
        self._telegram_session.mount('https://', adapter)
        self._telegram_session.mount('http://', adapter)

        # ✅ PATCH: Rate limit POR TOKEN (thread-safe)
        self._telegram_rate_lock = threading.Lock()
        self._telegram_last_send_ts: Dict[str, float] = {}
        self._telegram_min_interval_seconds = 1.2
        logger.info("BotManager inicializado")

    # =============================================================
    # Helpers de formatação
    # =============================================================
    def _format_button_text(self, text: str, price: float, price_position: str = None) -> str:
        """Formata texto do botão com preço antes ou depois."""
        position = price_position or 'after'
        if position == 'before':
            return f"R$ {price:.2f} - {text}"
        return f"{text} - R$ {price:.2f}"

    def _start_remarketing_worker(self, *, bot_id: int, bot_token: str) -> None:
        try:
            if not bot_id or not bot_token:
                return

            with self._remarketing_workers_lock:
                existing = self._remarketing_workers.get(bot_id)
                if existing and existing.get('thread') and existing['thread'].is_alive():
                    if existing.get('token') != bot_token:
                        existing['token'] = bot_token
                    return

                stop_event = threading.Event()

                def _worker():
                    self._remarketing_worker_loop(bot_id=bot_id, stop_event=stop_event)

                thread = threading.Thread(target=_worker, name=f"remarketing-worker-bot-{bot_id}")
                thread.daemon = True
                self._remarketing_workers[bot_id] = {
                    'thread': thread,
                    'stop_event': stop_event,
                    'token': bot_token
                }
                thread.start()
                logger.info(f"🧵 Remarketing worker por bot iniciado: bot_id={bot_id} thread_name={thread.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar remarketing worker: bot_id={bot_id} err={e}", exc_info=True)

    def _get_remarketing_worker_token(self, bot_id: int) -> Optional[str]:
        try:
            with self._remarketing_workers_lock:
                info = self._remarketing_workers.get(bot_id) or {}
                return info.get('token')
        except Exception:
            return None

    def _remarketing_worker_loop(self, *, bot_id: int, stop_event: threading.Event) -> None:
        from redis_manager import get_redis_connection
        import json
        import random
        import time

        queue_key = f"gb:{self.user_id}:remarketing:queue:{bot_id}"
        logger.info(f"🚀 Remarketing worker ativo e drenando fila: {queue_key}")
        msg_counter = 0
        next_long_pause_after = random.randint(15, 25)

        while not stop_event.is_set():
            try:
                redis_conn = get_redis_connection()
                item = redis_conn.blpop(queue_key, timeout=5)
                if not item:
                    continue

                _, raw = item
                try:
                    job = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode('utf-8'))
                except Exception:
                    logger.warning(f"⚠️ Remarketing job inválido (JSON parse falhou): bot_id={bot_id}")
                    continue
                logger.debug(f"📥 Remarketing dequeue bot_id={bot_id} chat_id={job.get('telegram_user_id')}")

                job_type = job.get('type')
                if job_type == 'campaign_done':
                    campaign_id = job.get('campaign_id')
                    try:
                        from flask import current_app
                        from internal_logic.core.extensions import db, socketio
                        from internal_logic.core.models import RemarketingCampaign, get_brazil_time
                        with current_app.app_context():
                            campaign = db.session.get(RemarketingCampaign, int(campaign_id)) if campaign_id else None
                            if campaign:
                                db.session.refresh(campaign)
                                campaign.status = 'completed'
                                campaign.completed_at = get_brazil_time()
                                db.session.commit()
                                logger.info(
                                    f"🏁 Campaign DONE bot_id={bot_id} "
                                    f"sent={campaign.total_sent} "
                                    f"failed={campaign.total_failed} "
                                    f"blocked={campaign.total_blocked}"
                                )
                                try:
                                    socketio.emit('remarketing_completed', {
                                        'campaign_id': campaign.id,
                                        'total_sent': campaign.total_sent,
                                        'total_failed': campaign.total_failed,
                                        'total_blocked': campaign.total_blocked
                                    })
                                except Exception:
                                    pass
                                logger.info(f"✅ Remarketing campaign finalizada via sentinel: campaign_id={campaign.id}")
                    except Exception as e:
                        logger.error(f"❌ Erro ao finalizar campanha via sentinel: bot_id={bot_id} err={e}", exc_info=True)
                    continue

                campaign_id = job.get('campaign_id')
                chat_id = job.get('telegram_user_id')
                message = job.get('message')
                media_url = job.get('media_url')
                media_type = job.get('media_type')
                buttons = job.get('buttons')
                audio_enabled = bool(job.get('audio_enabled'))
                audio_url = job.get('audio_url')

                token = self._get_remarketing_worker_token(bot_id)
                if not token:
                    token = job.get('bot_token')
                if not token:
                    logger.error(f"❌ Remarketing worker sem token: bot_id={bot_id} campaign_id={campaign_id}")
                    continue

                send_result = None
                try:
                    send_result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        media_url=media_url,
                        media_type=media_type,
                        buttons=buttons
                    )
                except Exception as send_error:
                    logger.error(
                        f"❌ ERRO REAL AO ENVIAR REMARKETING | bot_id={bot_id} "
                        f"campaign_id={campaign_id} chat_id={chat_id} err={send_error}",
                        exc_info=True
                    )
                    send_result = {'error': True, 'error_code': -1, 'description': str(send_error)}

                sent_inc = 0
                failed_inc = 0
                blocked_inc = 0

                error_code = None
                if isinstance(send_result, dict) and send_result.get('error'):
                    error_code = int(send_result.get('error_code') or 0)
                    desc = (send_result.get('description') or '').lower()
                    if error_code == 403 and ('bot was blocked' in desc or 'forbidden: bot was blocked' in desc):
                        blocked_inc = 1
                        try:
                            from flask import current_app
                            from internal_logic.core.extensions import db
                            from internal_logic.core.models import RemarketingBlacklist
                            with current_app.app_context():
                                existing = db.session.query(RemarketingBlacklist).filter_by(
                                    bot_id=bot_id,
                                    telegram_user_id=str(chat_id)
                                ).first()
                                if not existing:
                                    db.session.add(RemarketingBlacklist(bot_id=bot_id, telegram_user_id=str(chat_id), reason='bot_blocked'))
                                    db.session.commit()
                        except Exception:
                            pass
                    elif error_code == 401:
                        failed_inc = 1
                    else:
                        failed_inc = 1
                elif send_result:
                    sent_inc = 1
                    if audio_enabled and audio_url:
                        try:
                            self.send_telegram_message(
                                token=token,
                                chat_id=str(chat_id),
                                message="",
                                media_url=audio_url,
                                media_type='audio',
                                buttons=None
                            )
                        except Exception:
                            pass
                else:
                    failed_inc = 1

                if failed_inc and error_code in (0, -1):
                    time.sleep(2)
                    continue

                try:
                    if campaign_id:
                        from flask import current_app
                        from internal_logic.core.extensions import db, socketio
                        from internal_logic.core.models import RemarketingCampaign
                        with current_app.app_context():
                            campaign = db.session.get(RemarketingCampaign, int(campaign_id))
                            if campaign:
                                db.session.refresh(campaign)
                                campaign.total_sent += sent_inc
                                campaign.total_failed += failed_inc
                                campaign.total_blocked += blocked_inc
                                db.session.commit()
                                try:
                                    socketio.emit('remarketing_progress', {
                                        'campaign_id': campaign.id,
                                        'sent': campaign.total_sent,
                                        'failed': campaign.total_failed,
                                        'blocked': campaign.total_blocked,
                                        'total': campaign.total_targets,
                                        'percentage': round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                                    })
                                except Exception:
                                    pass
                except Exception as update_error:
                    logger.debug(f"⚠️ Falha ao atualizar contadores do remarketing (não crítico): {update_error}")

                msg_counter += 1
                time.sleep(random.uniform(1.2, 2.5))

                if msg_counter % 100 == 0:
                    logger.info(f"⏸️ Micro pause remarketing bot_id={bot_id} msgs={msg_counter}")
                    time.sleep(random.uniform(10, 20))
            except Exception as e:
                logger.error(f"❌ Erro no remarketing worker loop: bot_id={bot_id} err={e}", exc_info=True)
                try:
                    time.sleep(5)
                except Exception:
                    pass

    def _rate_limit_telegram_by_token(self, token: str) -> None:
        """Rate limit thread-safe por token. Não muda fluxo, apenas evita flood de conexões."""
        if not token:
            return

        now = time.time()
        sleep_for = 0.0
        with self._telegram_rate_lock:
            last_ts = self._telegram_last_send_ts.get(token)
            if last_ts is not None:
                elapsed = now - last_ts
                if elapsed < self._telegram_min_interval_seconds:
                    sleep_for = self._telegram_min_interval_seconds - elapsed
            self._telegram_last_send_ts[token] = now + sleep_for

        if sleep_for > 0:
            time.sleep(sleep_for)

    def _blacklist_user_deactivated(self, token: str, chat_id: str) -> None:
        """Blacklist definitiva para 'user is deactivated' (best-effort; não quebra execução se falhar)."""
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import RemarketingBlacklist, Bot

            with current_app.app_context():
                bot_id = None
                # ✅ REDIS BRAIN: Buscar bot pelo token no Redis
                # Como não temos índice reverso no Redis, buscar no banco
                bot = Bot.query.filter_by(token=token).first()
                if bot:
                    bot_id = bot.id

                if not bot_id:
                    return

                existing = db.session.query(RemarketingBlacklist).filter_by(
                    bot_id=bot_id,
                    telegram_user_id=str(chat_id)
                ).first()
                if existing:
                    return

                blacklist = RemarketingBlacklist(
                    bot_id=bot_id,
                    telegram_user_id=str(chat_id),
                    reason='user_deactivated'
                )
                db.session.add(blacklist)
                db.session.commit()
                logger.info(f"🚫 Usuário {chat_id} adicionado à blacklist do bot {bot_id} (user is deactivated)")
        except Exception as e:
            logger.warning(f"⚠️ Falha ao adicionar blacklist (user is deactivated) para chat {chat_id}: {e}")

    def send_video_safe(self, token: str, chat_id: str, *,
                        media_url: Optional[str] = None,
                        caption: str = '',
                        reply_markup: Optional[dict] = None,
                        file_path: Optional[str] = None) -> Optional[requests.Response]:
        """Envio seguro de sendVideo (URL remota ou upload local). Usa Session + retry/backoff + rate limit."""
        try:
            base_url = f"https://api.telegram.org/bot{token}"
            url = f"{base_url}/sendVideo"

            self._rate_limit_telegram_by_token(token)

            timeout = (5, 45)

            if file_path:
                with open(file_path, 'rb') as file:
                    files = {'video': file}
                    data = {
                        'chat_id': chat_id,
                        'caption': caption or '',
                        'parse_mode': 'HTML'
                    }
                    if reply_markup:
                        data['reply_markup'] = json.dumps(reply_markup)
                    with self.messenger.telegram_http_semaphore:
                        response = self._telegram_session.post(url, files=files, data=data, timeout=timeout)
            else:
                payload = {
                    'chat_id': chat_id,
                    'video': media_url,
                    'parse_mode': 'HTML'
                }
                if caption:
                    payload['caption'] = caption
                if reply_markup:
                    payload['reply_markup'] = reply_markup
                with self.messenger.telegram_http_semaphore:
                    response = self._telegram_session.post(url, json=payload, timeout=timeout)

            # ✅ Validar HTTP 5xx sem quebrar fluxo (retry já ocorreu no adapter)
            try:
                if response is not None and response.status_code >= 500:
                    response.raise_for_status()
            except requests.HTTPError:
                pass

            # Tratar definitivamente user is deactivated
            try:
                if response is not None and response.status_code == 403:
                    data = response.json() if response.content else {}
                    desc = (data.get('description') or '').lower()
                    if 'user is deactivated' in desc:
                        self._blacklist_user_deactivated(token, chat_id)
            except Exception:
                pass

            return response
        except FileNotFoundError:
            logger.error(f"❌ Arquivo não encontrado: {file_path}")
            return None
        except (requests.exceptions.Timeout, requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            logger.error(f"❌ Erro de rede ao enviar vídeo para chat {chat_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado em send_video_safe para chat {chat_id}: {e}", exc_info=True)
            return None
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Valida token do bot no Telegram
        Returns dict com bot_info e error_type (None se OK)
        """
        url = f"https://api.telegram.org/bot{token}/getMe"
        max_attempts = 5
        backoff_seconds = [1, 2, 4, 8]
        last_exception = None

        for attempt in range(1, max_attempts + 1):
            try:
                with self.messenger.telegram_http_semaphore:
                    response = requests.get(url, timeout=15)
                data = response.json()

                if not data.get('ok'):
                    if 'description' in data:
                        desc = data['description'].lower()
                        if 'bot was blocked by the user' in desc:
                            error = Exception('Bot bloqueado pelo usuário')
                            error.error_type = 'blocked'
                            raise error
                        elif 'bot token is invalid' in desc:
                            error = Exception('Token inválido ou banido pelo Telegram')
                            error.error_type = 'invalid_token'
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

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"Timeout ao validar token (tentativa {attempt}/{max_attempts})")
            except requests.exceptions.RequestException as e:
                last_exception = e
                message = str(e)
                keywords = ('Failed to resolve', 'NameResolutionError', 'Temporary failure in name resolution')
                if attempt < max_attempts and any(keyword in message for keyword in keywords):
                    wait = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)]
                    logger.warning(f"Falha de DNS/Conexão ao validar token (tentativa {attempt}/{max_attempts}): {message}. Retentativa em {wait}s")
                    time.sleep(wait)
                    continue
                if any(keyword in message for keyword in keywords):
                    logger.error(f"Erro ao validar token após {attempt} tentativas: {message}")
                    break  # sair do loop e acionar fallback
                
                logger.error(f"Erro ao validar token: {e}")
                error = Exception(f"Erro de conexão com API do Telegram: {message}")
                error.error_type = 'connection_error'
                raise error
            except Exception as e:
                if not hasattr(e, 'error_type'):
                    e.error_type = 'unknown'
                logger.error(f"Erro ao validar token: {e} (tipo: {getattr(e, 'error_type', 'unknown')})")
                raise

            # Se chegamos aqui, foi timeout e vamos tentar novamente
            if attempt < max_attempts:
                wait = backoff_seconds[min(attempt - 1, len(backoff_seconds) - 1)]
                time.sleep(wait)

        # Se esgotaram as tentativas com requests, tentar fallback com curl
        message = str(last_exception) if last_exception else 'desconhecido'
        logger.warning("Falha persistente ao validar token via requests; tentando fallback com curl")
        logger.warning(f"Última exceção registrada: {message}")

        try:
            cmd = [
                'curl',
                '--silent',
                '--show-error',
                '--max-time', '20',
                '--retry', '5',
                '--retry-all-errors',
                '--retry-delay', '2',
                '--retry-max-time', '60',
                f'https://api.telegram.org/bot{token}/getMe'
            ]
            completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.debug(f"curl stdout: {completed.stdout[:200]}")
            data = json.loads(completed.stdout)

            if not data.get('ok'):
                error = Exception(data.get('description', 'Token inválido'))
                error.error_type = 'invalid_token'
                raise error

            bot_info = data.get('result', {})
            logger.info(f"Token validado via fallback curl: @{bot_info.get('username')}")
            return {
                'bot_info': bot_info,
                'error_type': None
            }
        except Exception as curl_exc:
            logger.error(f"Fallback curl também falhou: {curl_exc}")
            if isinstance(curl_exc, subprocess.CalledProcessError):
                logger.error(f"curl stdout: {curl_exc.stdout}")
                logger.error(f"curl stderr: {curl_exc.stderr}")

        error = Exception('Erro de conexão com API do Telegram após múltiplas tentativas')
        error.error_type = 'connection_error'
        raise error
    
    def start_bot(self, bot_id: int, token: str, config: Dict[str, Any]):
        """
        Inicia um bot Telegram - Delegado ao BotRunner
        
        ✅ REFATORADO: Ciclo de vida delegado ao serviço BotRunner
        
        Args:
            bot_id: ID do bot no banco
            token: Token do bot
            config: Configuração do bot
        """
        return self.runner.start_bot(bot_id, token, config)
    
    def stop_bot(self, bot_id: int):
        """
        Para um bot Telegram - Delegado ao BotRunner
        
        ✅ REFATORADO: Ciclo de vida delegado ao serviço BotRunner
        
        Args:
            bot_id: ID do bot no banco
        """
        return self.runner.stop_bot(bot_id)
    
    def update_bot_config(self, bot_id: int, config: Dict[str, Any]):
        """
        Atualiza configuração de um bot em tempo real via Redis
        
        Args:
            bot_id: ID do bot
            config: Nova configuração
        """
        # ✅ REDIS BRAIN: Atualizar config no Redis (visível para todos os workers)
        if self.bot_state.update_bot_config(bot_id, config):
            logger.info(f"🔧 Configuração do bot {bot_id} atualizada no Redis")
            logger.info(f"🔍 DEBUG Config - downsells_enabled: {config.get('downsells_enabled', False)}")
            logger.info(f"🔍 DEBUG Config - downsells: {config.get('downsells', [])}")
        else:
            logger.warning(f"⚠️ Bot {bot_id} não está ativo no Redis para atualizar configuração")
    
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
            # ✅ REDIS BRAIN: Verificar se bot está ativo no Redis
            bot_info = self.bot_state.get_bot_data(bot_id)
            if not bot_info or bot_info.get('status') != 'running':
                logger.info(f"Monitor do bot {bot_id} encerrado (status não-running ou removido)")
                break

            try:
                # Heartbeat (mantém conexões em tempo real e sinaliza vivacidade)
                from internal_logic.core.models import get_brazil_time
                # 🔥 CRÍTICO: Blindagem UI - não deixar WebSocket afetar processamento core
                try:
                    if self.socketio:
                        self.socketio.emit('bot_heartbeat', {
                            'bot_id': bot_id,
                            'timestamp': get_brazil_time().isoformat(),
                            'status': 'online'
                        }, room=f'bot_{bot_id}')
                except Exception as ws_error:
                    logger.debug(f"Falha não-crítica na UI (WebSocket ignorado): {ws_error}")
                    pass  # O processamento da mensagem DEVE continuar!

                # Registrar heartbeat compartilhado (Redis) para ambientes multi-worker
                try:
                    import redis, time as _t
                    r = get_redis_connection()
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
                        # ✅ REDIS BRAIN: Buscar token do Redis
                        bot_data = self.bot_state.get_bot_data(bot_id)
                        token = bot_data.get('token') if bot_data else None
                        if token:
                            import os, requests as _rq
                            expected_base = os.environ.get('WEBHOOK_URL', '')
                            if expected_base:
                                expected_url = f"{expected_base}/webhook/telegram/{bot_id}"
                                info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
                                with self.messenger.telegram_http_semaphore:
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
                                                with self.messenger.telegram_http_semaphore:
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
                                                    seconds=5,
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
                with self.messenger.telegram_http_semaphore:
                    response = requests.post(url, json={'url': webhook_url}, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"Webhook configurado: {webhook_url}")
                    # Verificar estado do webhook imediatamente
                    try:
                        info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
                        with self.messenger.telegram_http_semaphore:
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
                                    with self.messenger.telegram_http_semaphore:
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
                                        seconds=5,
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
                        seconds=5,
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
        try:
            # ✅ REDIS BRAIN: Verificar se bot está ativo no Redis
            bot_data = self.bot_state.get_bot_data(bot_id)
            if not bot_data or bot_data.get('status') != 'running':
                logger.warning(f"⚠️ Bot {bot_id} não está ativo no Redis, não enviando mensagem")
                return
            
            # ✅ REDIS BRAIN: Buscar offset/poll_count do Redis (transientes)
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
            with self.telegram_http_semaphore:
                response = requests.get(url, params={'offset': offset, 'timeout': 25}, timeout=30)
            
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
                            self._process_telegram_update(bot_id, update)
                        
                        # ✅ OTIMIZAÇÃO: Atualizar offset uma única vez após processar todos
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
            import time
            time.sleep(5)  # ✅ DEFESA: Evitar loop infinito de CPU em caso de erro contínuo
    
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
        
        # ✅ CORREÇÃO: Loop com verificação no Redis
        while True:
            bot_data = self.bot_state.get_bot_data(bot_id)
            if not bot_data or bot_data.get('status') != 'running':
                break
            try:
                poll_count += 1
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                
                # Log a cada 5 polls para mostrar que está funcionando
                if poll_count % 5 == 0:
                    logger.info(f"📡 Bot {bot_id} polling ativo (ciclo {poll_count}) - Thread: {threading.current_thread().name}")
                
                with self.messenger.telegram_http_semaphore:
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
    
    def _process_telegram_update(self, bot_id: int, user_id: int, update: Dict[str, Any], isolated_state=None):
        """
        Processa update recebido do Telegram
        
        # ✅ ISOLAMENTO NAMESPACE V2: Agora recebe user_id e usa estado isolado
        - user_id: ID do dono do bot (para namespace gb:{user_id}:*)
        - isolated_state: Opcional - estado Redis já isolado (se None, usa self.bot_state)
        
        # ✅ QI 500: ANTI-DUPLICAÇÃO ABSOLUTO
        - Lock por update_id para evitar processamento duplicado
        - Garante que cada update é processado apenas 1 vez
        - Previne reset múltiplo, pixel duplicado, mensagens duplicadas
        
        Args:
            bot_id: ID do bot
            user_id: ID do dono do bot (para isolamento de namespace)
            update: Dados do update
            isolated_state: Estado Redis isolado (opcional, para performance)
        """
        # ✅ ISOLAMENTO: Usar estado isolado se fornecido, senão usar self.bot_state
        bot_state = isolated_state if isolated_state else self.bot_state
        
        # ✅ ISOLAMENTO: Lock de update com namespace do usuário
        import redis
        redis_conn = get_redis_connection()
        lock_key = f"gb:{user_id}:lock:update:{update.get('update_id')}"
        
        try:
            # ✅ QI 500: ANTI-DUPLICAÇÃO - Lock por update_id (PRIMEIRA COISA)
            update_id = update.get('update_id')
            if update_id is None:
                logger.warning(f"⚠️ Update sem update_id - ignorando")
                return
            
            try:
                # ✅ ISOLAMENTO: Lock com namespace do usuário
                if redis_conn.get(lock_key):
                    logger.warning(f"⚠️ Update {update_id} já processado — ignorando duplicado (anti-duplicação)")
                    return
                
                # Adquirir lock (expira em 20 segundos)
                acquired = redis_conn.set(lock_key, "1", ex=20, nx=True)
                if not acquired:
                    logger.warning(f"⚠️ Update {update_id} já está sendo processado — ignorando duplicado")
                    return
                
                logger.debug(f"🔒 Lock adquirido para update {update_id} (user_id={user_id})")
            except Exception as e:
                logger.error(f"❌ Erro ao verificar lock update: {e}")
                # Fail-open: se Redis falhar, permitir processar
                pass
            
            # ✅ ISOLAMENTO: Verificar se bot está ativo no Redis ISOLADO
            if not bot_state.is_bot_active(bot_id):
                logger.warning(f"⚠️ Bot {bot_id} não está ativo no Redis (namespace gb:{user_id}:), tentando auto-start")
                
                # ✅ ISOLAMENTO: Verificar se outro worker está tentando auto-start (namespace isolado)
                if bot_state.is_autostart_locked(bot_id):
                    logger.info(f"🔒 Outro worker está iniciando bot {bot_id} (user_id={user_id}) - aguardando")
                    import time
                    for _ in range(10):
                        time.sleep(0.5)
                        if bot_state.is_bot_active(bot_id):
                            logger.info(f"✅ Bot {bot_id} foi iniciado por outro worker")
                            break
                    else:
                        logger.warning(f"⚠️ Timeout aguardando bot {bot_id}")
                        return
                else:
                    # Tentar auto-start com lock (namespace isolado)
                    try:
                        from flask import current_app
                        from internal_logic.core.extensions import db
                        from internal_logic.core.models import Bot, BotConfig
                        with current_app.app_context():
                            bot = db.session.get(Bot, bot_id)
                            if bot and bot.is_active:  # 🔥 CRÍTICO: Removida verificação de user_id - webhook é stateless
                                config_obj = bot.config or BotConfig.query.filter_by(bot_id=bot.id).first()
                                config_dict = config_obj.to_dict() if config_obj else {}
                                # ✅ Usar o método de registro do bot_state isolado
                                bot_state.register_bot(bot.id, bot.token, config_dict)
                    except Exception as autostart_error:
                        logger.error(f"❌ Falha ao auto-start bot {bot_id} durante webhook: {autostart_error}")
                
                # Verificar novamente
                if not bot_state.is_bot_active(bot_id):
                    logger.warning(f"⚠️ Bot {bot_id} ainda indisponível após auto-start. Acionando FALLBACK para banco de dados...")
                    # NÃO retornar - vamos tentar fallback no banco
                    bot_info = None  # Marcar para fallback
                else:
                    # Bot está ativo, obter dados do Redis
                    bot_info = bot_state.get_bot_data(bot_id)
            else:
                # Bot já estava ativo, obter dados do Redis
                bot_info = bot_state.get_bot_data(bot_id)
            
            # ✅ FALLBACK CRÍTICO: Se Redis falhou, buscar direto do banco
            if not bot_info:
                logger.warning(f"🤖 Bot {bot_id} não encontrado no Redis. Acionando FALLBACK LEGADO (Via Expressa)!")
                try:
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Bot, BotConfig
                    
                    with current_app.app_context():
                        # 🔥 CRÍTICO: Limpar transação pendente antes de começar
                        db.session.rollback()
                        
                        db_bot = db.session.get(Bot, bot_id)
                        if not db_bot:
                            logger.error(f"❌ Bot {bot_id} não existe no banco de dados!")
                            return  # Bot realmente não existe
                            
                        # Buscar config
                        try:
                            db_config = db_bot.config or BotConfig.query.filter_by(bot_id=bot_id).first()
                            config_dict = db_config.to_dict() if db_config else {}
                        except Exception as config_err:
                            db.session.rollback()  # Limpa erro de transação
                            logger.error(f"⚠️ Erro ao buscar config: {config_err}")
                            config_dict = {}  # Continua sem config
                        
                        # Criar bot_info manualmente do banco
                        bot_info = {
                            'token': db_bot.token,
                            'config': config_dict
                        }
                        logger.info(f"✅ FALLBACK: Bot {bot_id} carregado direto do banco!")
                        
                except Exception as fallback_error:
                    logger.error(f"❌ FALLBACK falhou para bot {bot_id}: {fallback_error}")
                    # 🔥 CRÍTICO: Limpar transação suja antes de retornar
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    return  # Se fallback falhou, realmente não podemos processar
            
            token = bot_info['token']
            config = bot_info['config']
            
            logger.info(f"💬 Processando update {update_id} para bot {bot_id} (user_id={user_id})")
            
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
                        from flask import current_app
                        from internal_logic.core.extensions import db
                        from internal_logic.core.models import BotUser, BotMessage
                        import json
                        from datetime import datetime, timedelta
                        
                        with current_app.app_context():
                            # Buscar ou criar bot_user
                            bot_user = BotUser.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id,
                                archived=False
                            ).first()
                            
                            # Se não existe, criar (será atualizado depois no /start se necessário)
                            # ✅ CORREÇÃO CRÍTICA: Tratamento de race condition
                            if not bot_user:
                                try:
                                    bot_user = BotUser(
                                        bot_id=bot_id,
                                        telegram_user_id=telegram_user_id,
                                        first_name=user.get('first_name', 'Usuário'),
                                        username=user.get('username', ''),
                                        archived=False
                                    )
                                    db.session.add(bot_user)
                                    db.session.flush()  # Obter ID sem commit (detecta duplicação)
                                except Exception as e:
                                    # ✅ RACE CONDITION: Outro processo criou entre a busca e o add
                                    db.session.rollback()
                                    logger.debug(f"⚠️ Race condition ao criar BotUser (esperado em /start), buscando: {e}")
                                    # Buscar novamente (pode ter sido criado pelo outro processo ou no /start)
                                    bot_user = BotUser.query.filter_by(
                                        bot_id=bot_id,
                                        telegram_user_id=telegram_user_id,
                                        archived=False
                                    ).first()
                                    if not bot_user:
                                        # Se ainda não encontrou, buscar sem filtro archived
                                        bot_user = BotUser.query.filter_by(
                                            bot_id=bot_id,
                                            telegram_user_id=telegram_user_id
                                        ).first()
                            
                            # ✅ CRÍTICO: Gerar message_id único se não existir
                            telegram_msg_id = message.get('message_id')
                            if not telegram_msg_id:
                                # Se não tem message_id, gerar um baseado no timestamp + texto
                                import hashlib
                                from internal_logic.core.models import get_brazil_time
                                unique_id = f"{telegram_user_id}_{get_brazil_time().timestamp()}_{text[:20]}"
                                telegram_msg_id = hashlib.md5(unique_id.encode()).hexdigest()[:16]
                                logger.warning(f"⚠️ Mensagem sem message_id do Telegram, gerando ID único: {telegram_msg_id}")
                            
                            telegram_msg_id_str = str(telegram_msg_id)
                            
                            # ============================================================================
                            # ✅ QI 10000: ANTI-DUPLICAÇÃO ROBUSTA - Lock por chat+comando
                            # ============================================================================
                            # Lock adicional por chat_id+texto para prevenir race conditions
                            lock_acquired = False
                            try:
                                import redis
                                redis_conn_msg = get_redis_connection()
                                # Lock específico para esta mensagem (chat_id + hash do texto)
                                import hashlib
                                text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
                                msg_lock_key = f"gb:{self.user_id}:lock:msg:{bot_id}:{telegram_user_id}:{text_hash}"
                                
                                # Tentar adquirir lock (expira em 3 segundos)
                                lock_acquired = redis_conn_msg.set(msg_lock_key, "1", ex=3, nx=True)
                                if not lock_acquired:
                                    logger.warning(f"⛔ Mensagem já está sendo processada: {text[:30]}... (lock: {msg_lock_key})")
                                    return  # Sair sem processar
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao verificar lock de mensagem: {e} - continuando")
                                # Fail-open: se Redis falhar, continuar (melhor que bloquear tudo)
                            
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
                                from internal_logic.core.models import get_brazil_time
                                recent_window = get_brazil_time() - timedelta(seconds=5)
                                similar_message = BotMessage.query.filter(
                                    BotMessage.bot_id == bot_id,
                                    BotMessage.telegram_user_id == telegram_user_id,
                                    BotMessage.message_text == text,
                                    BotMessage.direction == 'incoming',
                                    BotMessage.created_at >= recent_window
                                ).first()
                                
                                if similar_message:
                                    existing_message = similar_message
                                    logger.warning(f"⛔ Mensagem similar encontrada nos últimos 5s, pulando duplicação: {text[:30]}...")
                            
                            if not existing_message:
                                try:
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
                                    from internal_logic.core.models import get_brazil_time
                                    bot_user.last_interaction = get_brazil_time()
                                    
                                    db.session.commit()
                                    logger.info(f"✅ Mensagem recebida salva no banco: '{text[:50]}...' (message_id: {telegram_msg_id_str})")
                                except Exception as db_error:
                                    # ✅ QI 10000: Tratar erro de constraint única (se existir)
                                    db.session.rollback()
                                    # Verificar novamente se foi salva por outro processo
                                    existing_check = BotMessage.query.filter_by(
                                        bot_id=bot_id,
                                        telegram_user_id=telegram_user_id,
                                        message_id=telegram_msg_id_str,
                                        direction='incoming'
                                    ).first()
                                    if existing_check:
                                        logger.warning(f"⛔ Mensagem já foi salva por outro processo: {telegram_msg_id_str}")
                                    else:
                                        logger.error(f"❌ Erro ao salvar mensagem: {db_error}")
                            else:
                                logger.warning(f"⛔ Mensagem já existe no banco, pulando: {telegram_msg_id_str}")
                    except Exception as e:
                        logger.error(f"❌ Erro ao salvar mensagem recebida: {e}", exc_info=True)
                        # Não interromper o fluxo se falhar ao salvar
                
                # 🔥 V8 ULTRA: Usar MessageRouter V8 como único ponto de entrada
                # Garante atomicidade e previne race conditions
                try:
                    router = get_message_router(self)
                    
                    # Extrair parâmetro do deep link (se houver)
                    start_param = None
                    message_type = "text"
                    
                    if text.startswith('/start'):
                        message_type = "start"
                        if len(text) > 6 and text[6] == ' ':  # "/start " tem 7 caracteres
                            start_param = text[7:].strip()  # Tudo após "/start "
                    
                    # ✅ V∞: MessageRouter V8 - ÚNICO PONTO DE ENTRADA (sem fallback)
                    router.process_message(
                        bot_id=bot_id,
                        token=token,
                        config=config,
                        chat_id=chat_id,
                        telegram_user_id=telegram_user_id,
                        message=message,
                        message_type=message_type,
                        callback_data=None
                    )
                except Exception as router_error:
                    logger.error(f"❌ Erro no MessageRouter V8: {router_error}", exc_info=True)
                    # Não interromper o fluxo, apenas logar o erro
                
                # ✅ SISTEMA DE ASSINATURAS - Processar new_chat_member e left_chat_member
                if 'new_chat_members' in message:
                    # Lista de novos membros
                    new_members = message['new_chat_members']
                    chat_info = message.get('chat', {})
                    chat_type = chat_info.get('type', '')
                    
                    # ✅ Processar apenas em grupos/supergrupos
                    if chat_type in ['group', 'supergroup']:
                        logger.info(f"👥 Novo(s) membro(s) adicionado(s) ao grupo {chat_info.get('id')} (tipo: {chat_type})")
                        
                        for new_member in new_members:
                            member_id = str(new_member.get('id', ''))
                            member_name = new_member.get('first_name', 'Usuário')
                            
                            # ✅ Verificar se não é o próprio bot
                            try:
                                bot_me = requests.post(
                                    f"https://api.telegram.org/bot{token}/getMe",
                                    timeout=5
                                ).json()
                                bot_user_id = str(bot_me.get('result', {}).get('id', ''))
                                
                                if member_id == bot_user_id:
                                    logger.debug(f"Bot {bot_user_id} foi adicionado ao grupo (ignorando)")
                                    continue
                            except:
                                pass  # Se falhar, continuar mesmo assim
                            
                            logger.info(f"   → Novo membro: {member_name} (ID: {member_id})")
                            
                            # ✅ CORREÇÃO 5: Detectar migrate_to_chat_id (grupo convertido)
                            migrate_to_chat_id = message.get('migrate_to_chat_id')
                            if migrate_to_chat_id:
                                logger.info(f"🔄 CORREÇÃO 5: Grupo convertido! Chat ID antigo: {chat_info.get('id')} → Novo: {migrate_to_chat_id}")
                                try:
                                    from flask import current_app
                                    from internal_logic.core.extensions import db
                                    from internal_logic.core.models import Subscription
                                    with current_app.app_context():
                                        # Atualizar todas as subscriptions com chat_id antigo
                                        from utils.subscriptions import normalize_vip_chat_id
                                        old_chat_id_raw = str(chat_info.get('id'))
                                        new_chat_id_raw = str(migrate_to_chat_id)
                                        old_chat_id_str = normalize_vip_chat_id(old_chat_id_raw)
                                        new_chat_id_str = normalize_vip_chat_id(new_chat_id_raw)
                                        updated = Subscription.query.filter_by(
                                            bot_id=bot_id,
                                            vip_chat_id=old_chat_id_str
                                        ).update({'vip_chat_id': new_chat_id_str})
                                        db.session.commit()
                                        if updated > 0:
                                            logger.info(f"✅ CORREÇÃO 5: {updated} subscription(s) atualizada(s) com novo chat_id: {new_chat_id_str}")
                                except Exception as migrate_error:
                                    logger.error(f"❌ CORREÇÃO 5: Erro ao atualizar chat_id após migração: {migrate_error}")
                            
                            # ✅ Processar subscription (usar chat_id correto)
                            final_chat_id = migrate_to_chat_id if migrate_to_chat_id else chat_info.get('id')
                            self._handle_new_chat_member(
                                bot_id=bot_id,
                                chat_id=final_chat_id,
                                telegram_user_id=member_id
                            )
                
                if 'left_chat_member' in message:
                    # Usuário saiu do grupo
                    left_member = message['left_chat_member']
                    chat_info = message.get('chat', {})
                    chat_type = chat_info.get('type', '')
                    
                    if chat_type in ['group', 'supergroup']:
                        member_id = str(left_member.get('id', ''))
                        member_name = left_member.get('first_name', 'Usuário')
                        
                        logger.info(f"👋 Usuário {member_name} (ID: {member_id}) saiu do grupo {chat_info.get('id')}")
                        # ✅ CORREÇÃO 12: Cancelar subscriptions ativas quando usuário sai do grupo
                        try:
                            from flask import current_app
                            from internal_logic.core.extensions import db
                            from internal_logic.core.models import Subscription
                            from datetime import datetime, timezone
                            
                            with current_app.app_context():
                                from utils.subscriptions import normalize_vip_chat_id
                                chat_id_raw = str(chat_info.get('id'))
                                chat_id_str = normalize_vip_chat_id(chat_id_raw)
                                active_subscriptions = Subscription.query.filter(
                                    Subscription.bot_id == bot_id,
                                    Subscription.telegram_user_id == member_id,
                                    Subscription.vip_chat_id == chat_id_str,
                                    Subscription.status == 'active'
                                ).all()
                                
                                for sub in active_subscriptions:
                                    logger.info(f"🔴 Cancelando subscription {sub.id} - usuário {member_id} saiu do grupo {chat_id_str}")
                                    sub.status = 'cancelled'
                                    sub.removed_at = datetime.now(timezone.utc)
                                    sub.removed_by = 'system_user_left'
                                    db.session.commit()
                                    logger.info(f"✅ Subscription {sub.id} cancelada")
                        except Exception as cancel_error:
                            logger.error(f"❌ Erro ao cancelar subscriptions quando usuário saiu: {cancel_error}")
            
            # 🔥 V8 ULTRA: Processar callback via MessageRouter V8
            elif 'callback_query' in update:
                callback = update['callback_query']
                callback_data = callback.get('data', '')
                logger.info(f"🔘 BOTÃO CLICADO: {callback_data}")
                
                try:
                    router = get_message_router(self)
                    
                    # Obter chat_id e telegram_user_id do callback
                    message_from_callback = callback.get('message', {})
                    chat_id = message_from_callback.get('chat', {}).get('id')
                    user = callback.get('from', {})
                    telegram_user_id = str(user.get('id', ''))
                    
                    if not chat_id:
                        logger.warning("⚠️ Callback sem chat_id, usando método tradicional")
                        self._handle_callback_query(bot_id, token, config, callback)
                        return
                    
                    # Processar via MessageRouter V8
                    result = router.process_message(
                        bot_id=bot_id,
                        token=token,
                        config=config,
                        chat_id=chat_id,
                        telegram_user_id=telegram_user_id,
                        message=callback,
                        message_type="callback",
                        callback_data=callback_data
                    )
                    
                    if not result.get('processed', False):
                        logger.warning(f"⚠️ Callback não processado pelo router: {result.get('reason', 'unknown')}")
                        # Fallback: processar via método tradicional
                        self._handle_callback_query(bot_id, token, config, callback)
                    
                except Exception as router_error:
                    logger.error(f"❌ Erro no MessageRouter V8 para callback: {router_error}", exc_info=True)
                    # Fallback: processar via método tradicional
                    self._handle_callback_query(bot_id, token, config, callback)
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar update do bot {bot_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_telegram_update_direct(self, bot_id: int, token: str, config: Dict[str, Any], 
                                         update: Dict[str, Any]) -> None:
        """
        🔥 FALLBACK LEGADO: Processa update SEM verificar Redis/state
        
        Usado quando o bot não está registrado no Redis ou quando
        o caminho normal falha. Implementação direta similar ao código legado.
        
        Args:
            bot_id: ID do bot
            token: Token do bot Telegram
            config: Configuração do bot
            update: Update do Telegram
        """
        try:
            logger.info(f"🚀 [FALLBACK DIRECT] Processando update para bot {bot_id}")
            
            # 🔥 CRÍTICO: Limpar transação pendente no início
            try:
                from flask import current_app
                from internal_logic.core.extensions import db
                db.session.rollback()
            except Exception:
                pass  # Ignora se não conseguir
            
            update_id = update.get('update_id')
            
            # Processar mensagem diretamente (sem Redis locks/state)
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                user = message.get('from', {})
                telegram_user_id = str(user.get('id', ''))
                
                logger.info(f"💬 [FALLBACK] De: {user.get('first_name', 'Usuário')} | Msg: '{text[:50]}...'")
                
                # Verificar se é comando /start
                if text and text.strip() == '/start':
                    logger.info(f"⭐ [FALLBACK] Comando /start detectado")
                    self._handle_start_command(bot_id, token, config, chat_id, message, None)
                    return
                
                # Mensagem de texto normal - usar MessageRouter
                try:
                    from flow_engine_router_v8 import get_message_router
                    router = get_message_router(self)
                    
                    result = router.process_message(
                        bot_id=bot_id,
                        token=token,
                        config=config,
                        chat_id=chat_id,
                        telegram_user_id=telegram_user_id,
                        message=message,
                        message_type='text'
                    )
                    
                    logger.info(f"✅ [FALLBACK] Mensagem processada via Router: {result}")
                    
                except Exception as router_error:
                    logger.error(f"❌ [FALLBACK] Erro no Router: {router_error}")
                    # Fallback último recurso: processar direto
                    self._handle_text_message(bot_id, token, config, chat_id, message)
                    
            elif 'callback_query' in update:
                # Callback query - processar diretamente
                callback = update['callback_query']
                message = callback.get('message', {})
                chat_id = message.get('chat', {}).get('id')
                callback_data = callback.get('data', '')
                
                if chat_id and callback_data:
                    logger.info(f"🔘 [FALLBACK] Callback: {callback_data}")
                    self._handle_callback_query(bot_id, token, config, callback)
                    
            logger.info(f"✅ [FALLBACK DIRECT] Update {update_id} processado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ [FALLBACK DIRECT] Erro ao processar: {e}")
            # 🔥 CRÍTICO: Limpar transação suja antes de propagar erro
            try:
                from internal_logic.core.extensions import db
                db.session.rollback()
            except Exception:
                pass
            import traceback
            traceback.print_exc()
            raise  # Propagar erro para que o caller saiba que falhou
    
    def _handle_text_message(self, bot_id: int, token: str, config: Dict[str, Any], 
                            chat_id: int, message: Dict[str, Any]):
        """
        Processa mensagens de texto (não comandos)
        
        # Lock variables - MUST be declared at function start to avoid scope issues
        lock_acquired = False
        lock_key = None
        
        # ✅ CORREÇÃO CRÍTICA QI 600+:
        - Verifica se há conversa ativa (mensagens do bot nos últimos 30 min)
        - Se houver conversa ativa, NÃO reinicia funil (apenas salva mensagem)
        - Se NÃO houver conversa ativa, reinicia funil (usuário retornando)
        
        PROTEÇÕES IMPLEMENTADAS:
        - Verificação de conversa ativa (30 minutos)
        - Rate limiting (máximo 1 mensagem por minuto para reiniciar funil)
        - Não envia Meta Pixel ViewContent (evita duplicação)
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser, Bot, BotMessage
            from datetime import datetime, timedelta
            
            with current_app.app_context():
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
                
                from internal_logic.core.models import get_brazil_time
                now = get_brazil_time()
                
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
                    # ✅ CONVERSA ATIVA: Verificar se há step com condições aguardando resposta
                    text = message.get('text', '').strip()
                    
                    # ✅ NOVO: Buscar step atual com função atômica
                    try:
                        current_step_id = self._get_current_step_atomic(bot_id, telegram_user_id)
                        
                        if current_step_id:
                            logger.info(f"🔍 Step ativo encontrado: {current_step_id} - processando condições")
                            
                            # Buscar step no fluxo
                            flow_steps = config.get('flow_steps', [])
                            current_step = self._find_step_by_id(flow_steps, current_step_id)
                            
                            if current_step:
                                # ✅ QI 500: Avaliar condições do step com parâmetros completos
                                next_step_id = self._evaluate_conditions(
                                    current_step, 
                                    user_input=text, 
                                    context={},
                                    bot_id=bot_id,
                                    telegram_user_id=telegram_user_id,
                                    step_id=current_step_id
                                )
                                
                                if next_step_id:
                                    logger.info(f"✅ Condição matchou! Continuando para step: {next_step_id}")
                                    # ✅ NOVO: Limpar step atual e tentativas globais
                                    try:
                                        redis_conn = get_redis_connection()
                                        if redis_conn:
                                            current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                            redis_conn.delete(current_step_key)
                                            
                                            # ✅ NOVO: Limpar tentativas globais quando condição matcha
                                            global_attempts_key = f"flow_global_attempts:{bot_id}:{telegram_user_id}:{current_step_id}"
                                            redis_conn.delete(global_attempts_key)
                                    except:
                                        pass
                                    # ✅ NOVO: Buscar snapshot do Redis se disponível
                                    flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                    
                                    # Continuar fluxo no próximo step
                                    self._execute_flow_recursive(
                                        bot_id, token, config, chat_id, telegram_user_id, next_step_id,
                                        recursion_depth=0,
                                        visited_steps=set(),
                                        flow_snapshot=flow_snapshot
                                    )
                                    return
                                else:
                                    logger.info(f"⚠️ Nenhuma condição matchou para texto: '{text[:50]}...'")
                                    
                                    # ✅ QI 500: Verificar se há step de erro definido
                                    error_step_id = current_step.get('error_step_id')
                                    if error_step_id:
                                        logger.info(f"🔄 Usando step de erro: {error_step_id}")
                                        try:
                                            redis_conn = get_redis_connection()
                                            if redis_conn:
                                                current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                                redis_conn.delete(current_step_key)
                                        except:
                                            pass
                                        # ✅ NOVO: Buscar snapshot do Redis
                                        flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                        self._execute_flow_recursive(
                                            bot_id, token, config, chat_id, telegram_user_id, error_step_id,
                                            recursion_depth=0, visited_steps=set(), flow_snapshot=flow_snapshot
                                        )
                                        return
                                    
                                    # ✅ QI 500: Verificar se há conexão retry (comportamento antigo)
                                    connections = current_step.get('connections', {})
                                    retry_step_id = connections.get('retry')
                                    if retry_step_id:
                                        logger.info(f"🔄 Usando conexão retry: {retry_step_id}")
                                        try:
                                            redis_conn = get_redis_connection()
                                            if redis_conn:
                                                current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                                redis_conn.delete(current_step_key)
                                        except:
                                            pass
                                        # ✅ NOVO: Buscar snapshot do Redis
                                        flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                        self._execute_flow_recursive(
                                            bot_id, token, config, chat_id, telegram_user_id, retry_step_id,
                                            recursion_depth=0, visited_steps=set(), flow_snapshot=flow_snapshot
                                        )
                                        return
                                    
                                    # ✅ QI 500: Fallback padrão - enviar mensagem de erro com limite de tentativas
                                    error_message = current_step.get('config', {}).get('error_message') or "⚠️ Resposta não reconhecida. Por favor, tente novamente."
                                    
                                    # ✅ NOVO: Limite global de tentativas por usuário (evita loop infinito)
                                    try:
                                        redis_conn = get_redis_connection()
                                        if redis_conn:
                                            global_attempts_key = f"flow_global_attempts:{bot_id}:{telegram_user_id}:{current_step_id}"
                                            global_attempts = redis_conn.get(global_attempts_key)
                                            global_attempts = int(global_attempts) if global_attempts else 0
                                            
                                            # Limite global: 10 tentativas por step
                                            max_global_attempts = 10
                                            if global_attempts >= max_global_attempts:
                                                logger.warning(f"⚠️ Limite global de tentativas ({max_global_attempts}) atingido para step {current_step_id}")
                                                # Limpar step ativo e enviar mensagem final
                                                current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                                redis_conn.delete(current_step_key)
                                                final_message = "⚠️ Muitas tentativas incorretas. Por favor, reinicie o bot com /start."
                                                self.send_telegram_message(
                                                    token=token,
                                                    chat_id=str(chat_id),
                                                    message=final_message,
                                                    buttons=None
                                                )
                                                return
                                            
                                            # Incrementar tentativas globais
                                            redis_conn.incr(global_attempts_key)
                                            redis_conn.expire(global_attempts_key, 3600)  # Expira em 1 hora
                                    except:
                                        pass  # Se Redis falhar, continuar (fail-open)
                                    
                                    self.send_telegram_message(
                                        token=token,
                                        chat_id=str(chat_id),
                                        message=error_message,
                                        buttons=None
                                    )
                                    logger.info(f"💬 Mensagem de erro enviada - mantendo step ativo para retry")
                                    # Não limpar Redis - permite nova tentativa
                                    return
                        else:
                            logger.debug(f"💬 Nenhum step ativo - mensagem será apenas salva")
                    except Exception as e:
                        logger.error(f"❌ Erro ao processar condições: {e}", exc_info=True)
                    
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
        
        # ✅ CRÍTICO: Respeita flow_enabled - se fluxo visual está ativo, não envia welcome_message
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser
            from datetime import datetime
            import json
            
            # ✅ V8 ULTRA: Verificação centralizada de modo ativo
            is_flow_active = checkActiveFlow(config)
            
            logger.info(f"🔍 _send_welcome_message_only: is_flow_active={is_flow_active}")
            
            # ✅ Se fluxo visual está ativo, NÃO enviar welcome_message
            if is_flow_active:
                logger.info(f"🚫 _send_welcome_message_only: Fluxo visual ativo - BLOQUEANDO welcome_message")
                logger.info(f"🚫 Usuário retornou mas fluxo visual está ativo - executando fluxo em vez de welcome")
                
                # Executar fluxo visual em vez de enviar welcome_message
                try:
                    user_from = message.get('from', {})
                    telegram_user_id = str(user_from.get('id', ''))
                    self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
                    logger.info(f"✅ Fluxo visual executado em _send_welcome_message_only")
                except Exception as e:
                    logger.error(f"❌ Erro ao executar fluxo em _send_welcome_message_only: {e}", exc_info=True)
                    # Mesmo com erro, não enviar welcome_message quando fluxo está ativo
                
                return  # ✅ SAIR SEM ENVIAR welcome_message
            
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser
            
            with current_app.app_context():
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
                        price = float(btn.get('price', 0))
                        button_text = self._format_button_text(btn['text'], price, btn.get('price_position'))
                        buttons.append({
                            'text': button_text,
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
                        from internal_logic.core.models import get_brazil_time
                        bot_user.welcome_sent_at = get_brazil_time()
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
    
    def _check_start_lock(self, chat_id: int) -> bool:
        """
        # ✅ QI 500: Lock para evitar /start duplicado
        
        Retorna True se pode processar (lock adquirido)
        Retorna False se já está processando (lock já existe)
        """
        try:
            import redis
            redis_conn = get_redis_connection()
            lock_key = f"gb:{self.user_id}:lock:start:{chat_id}"
            
            # Tentar adquirir lock (expira em 3 segundos)
            acquired = redis_conn.set(lock_key, "1", ex=3, nx=True)
            
            if acquired:
                logger.info(f"🔒 Lock adquirido para /start: chat_id={chat_id}")
                return True
            else:
                logger.warning(f"⚠️ /start duplicado bloqueado: chat_id={chat_id} (já processando)")
                return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar lock /start: {e}")
            # Em caso de erro, permitir processar (fail open)
            return True
    
    def send_funnel_step_sequential(self, token: str, chat_id: str, 
                                   text: str = None,
                                   media_url: str = None,
                                   media_type: str = None,
                                   buttons: list = None,
                                   delay_between: float = 0.2):
        """
        # ✅ QI 500: Envia step do funil SEQUENCIALMENTE (garante ordem)
        
        # ✅ QI 10000: ANTI-DUPLICAÇÃO - Lock por chat+hash(texto) antes de enviar
        
        # ✅ NOVA LÓGICA: Se texto > 1024 caracteres (limite do Telegram para caption) E tem mídia:
           1. Mídia PRIMEIRO (sem caption)
           2. Texto completo COM botões (depois da mídia)
        
        # ✅ LÓGICA PADRÃO: Se texto <= 1024 caracteres E tem mídia:
           1. Mídia COM caption e botões
        
        # ✅ LÓGICA SEM MÍDIA: Se não tem mídia:
           1. Texto com botões (se houver texto)
           2. OU Botões separados (se não houver texto)
        
        Tudo na mesma thread, com delay entre envios.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            text: Texto da mensagem
            media_url: URL da mídia
            media_type: Tipo da mídia (photo, video, audio)
            buttons: Lista de botões
            delay_between: Delay em segundos entre envios (padrão 0.2s)
        
        Returns:
            bool: True se todos os envios foram bem-sucedidos
        """
        import time
        import hashlib
        
        # ============================================================================
        # ✅ QI 10000: ANTI-DUPLICAÇÃO ROBUSTA - Lock único sincronizado para mídia + texto
        # ============================================================================
        # Gerar hash do conteúdo (texto + mídia + botões) para garantir consistência
        content_hash = hashlib.md5(
            f"{text or ''}{media_url or ''}{str(buttons or [])}".encode('utf-8')
        ).hexdigest()[:12]  # 12 caracteres para maior unicidade
        
        # Lock único e sincronizado para mídia + texto completo
        media_text_lock_key = f"gb:{self.user_id}:lock:send_media_and_text:{chat_id}:{content_hash}"
        redis_conn_send = None
        lock_acquired = False
        
        # Variáveis para finally (garantir que estão no escopo)
        lock_to_release = None
        
        try:
            import redis
            redis_conn_send = get_redis_connection()
            
            # Tentar adquirir lock (expira em 15 segundos - tempo suficiente para mídia + texto completo)
            lock_acquired = redis_conn_send.set(media_text_lock_key, "1", ex=15, nx=True)
            if not lock_acquired:
                logger.warning(f"⛔ Lock de envio já adquirido: chat_id={chat_id}, hash={content_hash} - BLOQUEANDO DUPLICAÇÃO")
                return False  # Sair sem enviar (duplicação detectada)
            else:
                logger.debug(f"🔒 Lock de envio adquirido: {media_text_lock_key} (expira em 15s)")
                lock_to_release = media_text_lock_key  # Marcar para liberar no finally
        except Exception as e:
            logger.warning(f"⚠️ Erro ao verificar lock de envio: {e} - continuando")
            # Fail-open: se Redis falhar, continuar (melhor que bloquear tudo)
        
        try:
            # ✅ QI 10000: Log para rastrear envios
            logger.info(f"📤 Enviando mensagem do funil: chat_id={chat_id}, texto_len={len(text) if text else 0}, tem_midia={bool(media_url)}")
            
            base_url = f"https://api.telegram.org/bot{token}"
            all_success = True
            
            # 1️⃣ ENVIAR TEXTO (se houver e NÃO houver mídia - se houver mídia, texto será caption)
            if text and text.strip() and not media_url:
                logger.info(f"📝 Enviando texto sequencial...")
                url = f"{base_url}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200 and response.json().get('ok'):
                    logger.info(f"✅ Texto enviado")
                else:
                    logger.error(f"❌ Falha ao enviar texto: {response.text}")
                    all_success = False
                
                time.sleep(delay_between)  # ✅ QI 500: Delay entre envios
            
            # 2️⃣ ENVIAR MÍDIA (se houver)
            if media_url:
                logger.info(f"🖼️ Enviando mídia sequencial ({media_type})...")
                CAPTION_LIMIT = 1024  # ✅ Limite real do Telegram para caption
                text_sent_separately = False
                inline_keyboard: List[List[Dict[str, str]]] = []
                if buttons:
                    for button in buttons:
                        button_dict = {'text': button.get('text')}
                        if button.get('url'):
                            button_dict['url'] = button['url']
                        elif button.get('callback_data'):
                            button_dict['callback_data'] = button['callback_data']
                        else:
                            button_dict['callback_data'] = 'button_pressed'
                        inline_keyboard.append([button_dict])

                # ✅ NOVA LÓGICA: Se texto > 1024, enviar mídia PRIMEIRO (sem caption), depois texto completo com botões
                text_exceeds_caption = text and len(text or '') > CAPTION_LIMIT
                
                if text_exceeds_caption:
                    logger.info(f"📊 Texto excede limite de caption ({len(text)} > {CAPTION_LIMIT}). Enviando mídia PRIMEIRO (sem caption), depois texto completo com botões...")
                    text_sent_separately = True  # Marcar que texto será enviado separadamente
                else:
                    # Texto <= 1024: pode usar como caption
                    logger.info(f"📊 Texto dentro do limite de caption ({len(text) if text else 0} <= {CAPTION_LIMIT}). Usando como caption da mídia.")

                # Preparar caption (apenas se texto <= 1024)
                caption_text = ''
                if text and text.strip() and not text_sent_separately:
                    caption_text = text[:CAPTION_LIMIT] if len(text) > CAPTION_LIMIT else text

                # ✅ PASSO 1: ENVIAR MÍDIA (SEM caption se texto > 1024, COM caption se texto <= 1024)
                if media_type == 'photo':
                    url = f"{base_url}/sendPhoto"
                    payload = {
                        'chat_id': chat_id,
                        'photo': media_url,
                        'parse_mode': 'HTML'
                    }
                    if caption_text:
                        payload['caption'] = caption_text
                elif media_type == 'video':
                    url = f"{base_url}/sendVideo"
                    payload = {
                        'chat_id': chat_id,
                        'video': media_url,
                        'parse_mode': 'HTML'
                    }
                    if caption_text:
                        payload['caption'] = caption_text
                elif media_type == 'audio':
                    url = f"{base_url}/sendAudio"
                    payload = {
                        'chat_id': chat_id,
                        'audio': media_url,
                        'parse_mode': 'HTML'
                    }
                    if caption_text:
                        payload['caption'] = caption_text
                else:
                    logger.warning(f"⚠️ Tipo de mídia desconhecido: {media_type}")
                    all_success = False
                    media_url = None  # Não enviar mídia inválida

                if media_url:
                    # ✅ Adicionar botões à mídia APENAS se texto <= 1024 (texto será caption)
                    # Se texto > 1024, botões vão no texto separado
                    if inline_keyboard and not text_sent_separately:
                        payload['reply_markup'] = {'inline_keyboard': inline_keyboard}

                    if media_type == 'video':
                        response = self.send_video_safe(
                            token=token,
                            chat_id=chat_id,
                            media_url=media_url,
                            caption=caption_text,
                            reply_markup=payload.get('reply_markup')
                        )
                        if response is None:
                            all_success = False
                            response = type('obj', (object,), {'status_code': 0, 'json': lambda *_: {'ok': False}, 'text': 'send_video_safe failed'})()
                    else:
                        response = requests.post(url, json=payload, timeout=10)
                    if response.status_code == 200 and response.json().get('ok'):
                        logger.info(f"✅ Mídia enviada{' com caption' if caption_text else ' sem caption'} {'e botões' if inline_keyboard and not text_sent_separately else ''}")
                    else:
                        logger.error(f"❌ Falha ao enviar mídia: {response.text}")
                        all_success = False

                    time.sleep(delay_between)  # ✅ Delay entre envios

                    # ✅ PASSO 2: Se texto > 1024, enviar texto completo COM BOTÕES após mídia
                    if text_exceeds_caption:
                        # ========================================================================
                        # ✅ LOCK ESPECÍFICO PARA TEXTO COMPLETO (ANTI-DUPLICAÇÃO)
                        # ========================================================================
                        text_only_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:12]
                        text_complete_lock_key = f"gb:{self.user_id}:lock:send_text_only:{chat_id}:{text_only_hash}"

                        text_lock_acquired = False
                        redis_conn_text = None

                        try:
                            import redis
                            redis_conn_text = get_redis_connection()
                            text_lock_acquired = redis_conn_text.set(text_complete_lock_key, "1", ex=10, nx=True)
                            if not text_lock_acquired:
                                logger.warning(f"⛔ TEXTO COMPLETO já está sendo enviado: chat_id={chat_id}, hash={text_only_hash} - BLOQUEANDO DUPLICAÇÃO")
                                return all_success  # Retornar sucesso parcial (mídia já foi enviada)
                            else:
                                logger.info(f"🔒 Lock de texto completo adquirido: {text_complete_lock_key} (expira em 10s)")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao verificar lock de texto completo: {e} - continuando")

                        try:
                            # ✅ Verificação adicional no banco (anti-duplicação)
                            try:
                                from flask import current_app
                                from internal_logic.core.extensions import db
                                from internal_logic.core.models import BotMessage
                                from datetime import timedelta
                                from internal_logic.core.models import get_brazil_time

                                with current_app.app_context():
                                    recent_window = get_brazil_time() - timedelta(seconds=5)
                                    existing_text = BotMessage.query.filter(
                                        BotMessage.telegram_user_id == str(chat_id),
                                        BotMessage.message_text == text,
                                        BotMessage.direction == 'outgoing',
                                        BotMessage.created_at >= recent_window
                                    ).first()

                                    if existing_text:
                                        logger.warning(f"⛔ Texto completo já foi enviado recentemente (últimos 5s): chat_id={chat_id} - BLOQUEANDO DUPLICAÇÃO")
                                        if text_lock_acquired and redis_conn_text:
                                            try:
                                                redis_conn_text.delete(text_complete_lock_key)
                                                logger.debug(f"🔓 Lock liberado após detecção de duplicação no banco")
                                            except:
                                                pass
                                        return all_success  # Retornar sucesso parcial (mídia já foi enviada)
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao verificar duplicação no banco: {e} - continuando")

                            # ✅ ENVIAR TEXTO COMPLETO COM BOTÕES (após mídia)
                            logger.info(f"📝 Enviando texto completo após mídia (len={len(text)}, hash={text_only_hash})...")
                            url_msg = f"{base_url}/sendMessage"
                            payload_msg = {
                                'chat_id': chat_id,
                                'text': text,  # ✅ Texto completo
                                'parse_mode': 'HTML'
                            }
                            
                            # ✅ Adicionar botões ao texto completo
                            if inline_keyboard:
                                payload_msg['reply_markup'] = {'inline_keyboard': inline_keyboard}

                            logger.info(f"🚀 Enviando texto completo com botões após mídia: chat_id={chat_id}, hash={text_only_hash}")

                            response_msg = requests.post(url_msg, json=payload_msg, timeout=10)

                            # ✅ Log após enviar para confirmar
                            if response_msg.status_code == 200:
                                result_data = response_msg.json()
                                if result_data.get('ok'):
                                    message_id_sent = result_data.get('result', {}).get('message_id')
                                    logger.info(f"✅ Texto completo com botões enviado após mídia (message_id={message_id_sent}, hash={text_only_hash})")
                                    
                                    # ✅ Salvar mensagem enviada no banco para verificação futura (anti-duplicação)
                                    try:
                                        from flask import current_app
                                        from internal_logic.core.extensions import db
                                        from internal_logic.core.models import BotMessage, BotUser
                                        from internal_logic.core.models import get_brazil_time

                                        with current_app.app_context():
                                            bot_user = BotUser.query.filter_by(
                                                telegram_user_id=str(chat_id)
                                            ).order_by(BotUser.last_interaction.desc()).first()

                                            if bot_user:
                                                telegram_msg_id = result_data.get('result', {}).get('message_id')
                                                message_id = str(telegram_msg_id) if telegram_msg_id else f"text_complete_{int(time.time())}"

                                                # Verificar se já existe antes de salvar
                                                existing = BotMessage.query.filter_by(
                                                    bot_id=bot_user.bot_id,
                                                    telegram_user_id=str(chat_id),
                                                    message_id=message_id,
                                                    direction='outgoing'
                                                ).first()

                                                if not existing:
                                                    bot_message = BotMessage(
                                                        bot_id=bot_user.bot_id,
                                                        bot_user_id=bot_user.id,
                                                        telegram_user_id=str(chat_id),
                                                        message_id=message_id,
                                                        message_text=text,  # ✅ Texto completo (não apenas restante)
                                                        message_type='text',
                                                        direction='outgoing',
                                                        is_read=True
                                                    )
                                                    db.session.add(bot_message)
                                                    db.session.commit()
                                                    logger.debug(f"✅ Texto completo salvo no banco para verificação futura")
                                    except Exception as e:
                                        logger.debug(f"⚠️ Erro ao salvar texto completo no banco (não crítico): {e}")
                                else:
                                    logger.error(f"❌ Telegram API retornou erro: {result_data.get('description', 'Erro desconhecido')}")
                                    all_success = False
                            else:
                                logger.error(f"❌ HTTP {response_msg.status_code}: {response_msg.text[:200]}")
                                all_success = False
                        finally:
                            # ✅ SEMPRE liberar lock de texto completo após envio (ou erro)
                            if text_lock_acquired and redis_conn_text:
                                try:
                                    redis_conn_text.delete(text_complete_lock_key)
                                    logger.debug(f"🔓 Lock de texto completo liberado: {text_complete_lock_key}")
                                except Exception as e:
                                    logger.debug(f"⚠️ Erro ao liberar lock de texto completo (não crítico): {e}")

                        time.sleep(delay_between)  # ✅ Delay entre envios

            # 3️⃣ ENVIAR BOTÕES (se houver e NÃO foram enviados com mídia)
            if buttons and not media_url:
                # Preparar teclado inline
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
                
                logger.info(f"🔘 Enviando botões sequencial...")
                url = f"{base_url}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': text[:100] if text else "⬇️ Escolha uma opção",
                    'parse_mode': 'HTML',
                    'reply_markup': reply_markup
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200 and response.json().get('ok'):
                    logger.info(f"✅ Botões enviados")
                else:
                    logger.error(f"❌ Falha ao enviar botões: {response.text}")
                    all_success = False
            
            return all_success
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar step sequencial: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # ✅ QI 10000: Liberar lock após envio completo (ou erro)
            # Nota: Lock expira automaticamente em 15s, mas liberar manualmente é melhor prática
            if lock_acquired and redis_conn_send and lock_to_release:
                try:
                    redis_conn_send.delete(lock_to_release)
                    logger.debug(f"🔓 Lock liberado: {lock_to_release}")
                except Exception as e:
                    logger.debug(f"⚠️ Erro ao liberar lock (não crítico, expira automaticamente em 15s): {e}")
    
    def _find_step_by_id(self, flow_steps: list, step_id: str) -> Dict[str, Any]:
        """
        Busca step por ID no fluxo
        
        # ✅ VALIDAÇÃO: Sanitiza step_id antes de buscar
        # ✅ CRÍTICO: Compara IDs como strings (pode vir como número ou string)
        """
        if not step_id:
            return None
        
        # Converter step_id para string para comparação
        step_id_str = str(step_id).strip()
        
        if not step_id_str:
            return None
        
        if not flow_steps or not isinstance(flow_steps, list):
            logger.warning(f"⚠️ _find_step_by_id: flow_steps inválido (tipo: {type(flow_steps)})")
            return None
        
        for step in flow_steps:
            if not isinstance(step, dict):
                continue
            
            step_id_candidate = step.get('id')
            if step_id_candidate is None:
                continue
            
            # ✅ CRÍTICO: Comparar como strings (pode ser número ou string)
            if str(step_id_candidate).strip() == step_id_str:
                logger.info(f"✅ Step encontrado: id={step_id_candidate} (tipo: {type(step_id_candidate)})")
                return step
        
        logger.warning(f"⚠️ Step {step_id_str} não encontrado em {len(flow_steps)} steps")
        return None
    
    def _validate_condition(self, condition: Dict[str, Any]) -> tuple:
        """
        # ✅ QI 500: Valida estrutura de uma condição
        
        Returns:
            (is_valid: bool, error_message: str)
        """
        if not isinstance(condition, dict):
            return False, "Condição deve ser um objeto"
        
        condition_type = condition.get('type')
        if not condition_type or not isinstance(condition_type, str):
            return False, "Condição deve ter 'type' (string)"
        
        valid_types = ['text_validation', 'button_click', 'payment_status', 'time_elapsed']
        if condition_type not in valid_types:
            return False, f"Tipo de condição inválido: {condition_type}. Válidos: {valid_types}"
        
        target_step = condition.get('target_step')
        if not target_step or not isinstance(target_step, str) or not target_step.strip():
            return False, "Condição deve ter 'target_step' (string não vazia)"
        
        # Validações específicas por tipo
        if condition_type == 'text_validation':
            validation = condition.get('validation', 'any')
            valid_validations = ['email', 'phone', 'cpf', 'contains', 'equals', 'any']
            if validation not in valid_validations:
                return False, f"Validação de texto inválida: {validation}"
            
            if validation in ('contains', 'equals'):
                value = condition.get('value')
                if not value or not isinstance(value, str):
                    return False, f"Validação '{validation}' requer 'value' (string)"
        
        elif condition_type == 'button_click':
            button_text = condition.get('button_text')
            if not button_text or not isinstance(button_text, str):
                return False, "Condição 'button_click' requer 'button_text' (string)"
        
        elif condition_type == 'payment_status':
            status = condition.get('status', 'paid')
            valid_statuses = ['paid', 'pending', 'failed', 'expired']
            if status not in valid_statuses:
                return False, f"Status de pagamento inválido: {status}"
        
        elif condition_type == 'time_elapsed':
            minutes = condition.get('minutes', 5)
            if not isinstance(minutes, (int, float)) or minutes < 1:
                return False, "Condição 'time_elapsed' requer 'minutes' (número >= 1)"
        
        # Validar max_attempts se presente
        max_attempts = condition.get('max_attempts')
        if max_attempts is not None:
            if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 100:
                return False, "max_attempts deve ser um inteiro entre 1 e 100"
        
        # Validar fallback_step se presente
        fallback_step = condition.get('fallback_step')
        if fallback_step is not None:
            if not isinstance(fallback_step, str) or not fallback_step.strip():
                return False, "fallback_step deve ser uma string não vazia"
        
        return True, ""
    
    def _evaluate_conditions(self, step: Dict[str, Any], user_input: str = None, 
                            context: Dict[str, Any] = None, bot_id: int = None, 
                            telegram_user_id: str = None, step_id: str = None) -> Optional[str]:
        """
        # ✅ QI 500: Avalia condições do step e retorna próximo step_id
        
        # ✅ NOVO: Validação completa de condições antes de avaliar
        # ✅ NOVO: Validação de max_attempts com fallback
        # ✅ NOVO: Suporte a step de erro padrão
        
        Args:
            step: Step atual com condições
            user_input: Input do usuário (texto, callback_data, etc.)
            context: Contexto adicional (payment_status, etc.)
            bot_id: ID do bot (para Redis)
            telegram_user_id: ID do usuário (para Redis)
            step_id: ID do step atual (para Redis)
        
        Returns:
            step_id do próximo step ou None se nenhuma condição matchou
        """
        if not step or not isinstance(step, dict):
            return None
        
        conditions = step.get('conditions', [])
        if not conditions or not isinstance(conditions, list) or len(conditions) == 0:
            return None
        
        # ✅ VALIDAÇÃO: Filtrar condições inválidas
        valid_conditions = []
        for idx, condition in enumerate(conditions):
            is_valid, error_msg = self._validate_condition(condition)
            if not is_valid:
                logger.error(f"❌ Condição {idx} do step {step_id} inválida: {error_msg}")
                logger.error(f"   Condição: {condition}")
                continue
            valid_conditions.append(condition)
        
        if not valid_conditions:
            logger.warning(f"⚠️ Nenhuma condição válida no step {step_id}")
            return None
        
        # Ordenar por ordem (order)
        sorted_conditions = sorted(valid_conditions, key=lambda c: c.get('order', 0))
        
        # ✅ NOVO: Verificar max_attempts antes de avaliar
        try:
            import redis
            redis_conn = get_redis_connection()
        except:
            redis_conn = None
        
        for condition in sorted_conditions:
            condition_type = condition.get('type')
            condition_id = condition.get('id', f"cond_{sorted_conditions.index(condition)}")
            
            # ✅ NOVO: Verificar max_attempts (apenas para condições de texto/button)
            if condition_type in ('text_validation', 'button_click') and redis_conn and bot_id and telegram_user_id and step_id:
                max_attempts = condition.get('max_attempts')
                if max_attempts and max_attempts > 0:
                    attempt_key = f"flow_attempts:{bot_id}:{telegram_user_id}:{step_id}:{condition_id}"
                    try:
                        attempts = redis_conn.get(attempt_key)
                        attempts = int(attempts) if attempts else 0
                        
                        if attempts >= max_attempts:
                            logger.warning(f"⚠️ Máximo de tentativas ({max_attempts}) atingido para condição {condition_id}")
                            # Retornar fallback_step se definido
                            fallback_step = condition.get('fallback_step')
                            if fallback_step:
                                logger.info(f"🔄 Usando fallback_step: {fallback_step}")
                                return fallback_step
                            # Se não tem fallback, continuar para próxima condição
                            continue
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao verificar max_attempts: {e}")
            
            # Avaliar condição
            matched = False
            
            if condition_type == 'text_validation':
                if user_input and self._match_text_validation(condition, user_input):
                    matched = True
                    # ✅ NOVO: Resetar tentativas quando matcha
                    if redis_conn and bot_id and telegram_user_id and step_id:
                        attempt_key = f"flow_attempts:{bot_id}:{telegram_user_id}:{step_id}:{condition_id}"
                        try:
                            redis_conn.delete(attempt_key)
                        except:
                            pass
            
            elif condition_type == 'button_click':
                # ✅ NOVO: Passar step completo para match correto
                if user_input and self._match_button_click(condition, user_input, step=step):
                    matched = True
                    # ✅ NOVO: Resetar tentativas quando matcha
                    if redis_conn and bot_id and telegram_user_id and step_id:
                        attempt_key = f"flow_attempts:{bot_id}:{telegram_user_id}:{step_id}:{condition_id}"
                        try:
                            redis_conn.delete(attempt_key)
                        except:
                            pass
            
            elif condition_type == 'payment_status':
                if context and self._match_payment_status(condition, context):
                    matched = True
            
            elif condition_type == 'time_elapsed':
                # ✅ NOVO: Passar parâmetros adicionais para calcular tempo decorrido
                if self._match_time_elapsed(condition, context or {}, bot_id, telegram_user_id, step_id):
                    matched = True
            
            if matched:
                return condition.get('target_step')
            
            # ✅ NOVO: Incrementar tentativas se não matchou (apenas para condições de texto/button)
            if condition_type in ('text_validation', 'button_click') and redis_conn and bot_id and telegram_user_id and step_id:
                max_attempts = condition.get('max_attempts')
                if max_attempts and max_attempts > 0:
                    attempt_key = f"flow_attempts:{bot_id}:{telegram_user_id}:{step_id}:{condition_id}"
                    try:
                        redis_conn.incr(attempt_key)
                        redis_conn.expire(attempt_key, 3600)  # Expira em 1 hora
                    except:
                        pass
        
        return None  # Nenhuma condição matchou
    
    def _match_text_validation(self, condition: Dict[str, Any], user_input: str) -> bool:
        """Valida texto do usuário baseado na condição"""
        if not user_input or not user_input.strip():
            return False
        
        validation = condition.get('validation', 'any')
        user_input_clean = user_input.strip()
        
        if validation == 'email':
            import re
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            return bool(re.match(email_pattern, user_input_clean))
        
        elif validation == 'phone':
            import re
            # Telefone brasileiro: (XX) XXXXX-XXXX ou XXXXXXXXXXX
            phone_pattern = r'^(\+55\s?)?(\(?\d{2}\)?\s?)?\d{4,5}-?\d{4}$'
            return bool(re.match(phone_pattern, user_input_clean))
        
        elif validation == 'cpf':
            return self._validate_cpf(user_input_clean)
        
        elif validation == 'contains':
            keyword = condition.get('value', '').lower()
            return keyword in user_input_clean.lower()
        
        elif validation == 'equals':
            value = condition.get('value', '').strip().lower()
            return user_input_clean.lower() == value
        
        elif validation == 'any':
            return bool(user_input_clean)
        
        return False
    
    def _match_button_click(self, condition: Dict[str, Any], callback_data: str, step: Dict[str, Any] = None) -> bool:
        """
        # ✅ QI 500: Verifica se callback_data corresponde ao botão da condição
        
        # ✅ CORREÇÃO: Match exato usando índice do botão quando disponível
        """
        if not callback_data or not isinstance(callback_data, str):
            return False
        
        button_text = condition.get('button_text', '').strip()
        if not button_text:
            return False
        
        # ✅ NOVO: Se callback_data é do formato flow_step_{step_id}_btn_{idx}
        # E temos acesso ao step, fazer match exato por índice
        if callback_data.startswith('flow_step_') and step:
            try:
                # Formato: flow_step_{step_id}_btn_{idx}
                parts = callback_data.replace('flow_step_', '').split('_')
                if len(parts) >= 2 and parts[1].startswith('btn'):
                    btn_idx_str = parts[1].replace('btn', '')
                    if btn_idx_str:
                        btn_idx = int(btn_idx_str)
                        step_config = step.get('config', {})
                        custom_buttons = step_config.get('custom_buttons', [])
                        
                        # Verificar se índice é válido e texto corresponde
                        if btn_idx < len(custom_buttons):
                            actual_button = custom_buttons[btn_idx]
                            expected_text = button_text.lower().strip()
                            actual_text = actual_button.get('text', '').strip().lower()
                            
                            # ✅ MATCH EXATO: Comparar texto do botão
                            if expected_text == actual_text:
                                logger.debug(f"✅ Button click match exato: '{expected_text}' == '{actual_text}' (índice {btn_idx})")
                                return True
                            else:
                                logger.debug(f"❌ Button click não matchou: '{expected_text}' != '{actual_text}' (índice {btn_idx})")
                                return False
            except (ValueError, IndexError, TypeError) as e:
                logger.debug(f"⚠️ Erro ao extrair índice do botão: {e} - usando fallback")
        
        # ✅ FALLBACK: Match por texto (case insensitive) para outros formatos
        # Mas apenas se callback_data contém button_text como substring completa
        callback_lower = callback_data.lower()
        button_lower = button_text.lower()
        
        # Match exato (preferencial)
        if button_lower == callback_lower:
            return True
        
        # Match por substring (menos confiável, mas necessário para compatibilidade)
        if button_lower in callback_lower:
            logger.debug(f"⚠️ Button click match por substring: '{button_lower}' in '{callback_lower}'")
            return True
        
        return False
    
    def _match_payment_status(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Verifica se status de pagamento corresponde à condição"""
        expected_status = condition.get('status', 'paid')
        actual_status = context.get('payment_status')
        
        return actual_status == expected_status
    
    def _match_time_elapsed(self, condition: Dict[str, Any], context: Dict[str, Any], 
                           bot_id: int = None, telegram_user_id: str = None, step_id: str = None) -> bool:
        """
        # ✅ QI 500: Verifica se tempo decorrido corresponde à condição
        
        # ✅ NOVO: Implementação funcional usando Redis para rastrear timestamp
        """
        required_minutes = condition.get('minutes', 5)
        
        # ✅ NOVO: Buscar timestamp do step do Redis
        if bot_id and telegram_user_id and step_id:
            try:
                redis_conn = get_redis_connection()
                if redis_conn:
                    timestamp_key = f"flow_step_timestamp:{bot_id}:{telegram_user_id}"
                    step_timestamp = redis_conn.get(timestamp_key)
                    
                    if step_timestamp:
                        step_timestamp = int(step_timestamp) if isinstance(step_timestamp, (str, bytes)) else step_timestamp
                        import time
                        elapsed_seconds = int(time.time()) - step_timestamp
                        elapsed_minutes = elapsed_seconds / 60
                        
                        logger.debug(f"⏱️ Tempo decorrido: {elapsed_minutes:.1f} minutos (requerido: {required_minutes})")
                        return elapsed_minutes >= required_minutes
            except Exception as e:
                logger.warning(f"⚠️ Erro ao calcular tempo decorrido: {e}")
        
        # Fallback: usar context se disponível
        elapsed_minutes = context.get('elapsed_minutes', 0)
        return elapsed_minutes >= required_minutes
    
    def _validate_cpf(self, cpf: str) -> bool:
        """
        # ✅ QI 500: Valida CPF com dígitos verificadores
        
        # ✅ NOVO: Validação robusta de edge cases
        
        Args:
            cpf: CPF a ser validado (pode conter formatação)
        
        Returns:
            True se CPF é válido, False caso contrário
        """
        import re
        
        # ✅ VALIDAÇÃO: Verificar se cpf é string válida
        if not cpf or not isinstance(cpf, str):
            return False
        
        # Remover formatação
        cpf_clean = re.sub(r'\D', '', cpf)
        
        # ✅ VALIDAÇÃO: Verificar se tem apenas números após limpeza
        if not cpf_clean.isdigit():
            return False
        
        # Verificar tamanho
        if len(cpf_clean) != 11:
            return False
        
        cpf = cpf_clean
        
        # CPFs conhecidos como inválidos (todos dígitos iguais)
        if cpf == cpf[0] * 11:
            return False
        
        # Validar dígitos verificadores
        def calculate_digit(cpf: str, weights: list) -> int:
            """Calcula dígito verificador"""
            total = sum(int(cpf[i]) * weights[i] for i in range(len(weights)))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        # Validar primeiro dígito
        weights_1 = [10, 9, 8, 7, 6, 5, 4, 3, 2]
        digit_1 = calculate_digit(cpf, weights_1)
        if int(cpf[9]) != digit_1:
            return False
        
        # Validar segundo dígito
        weights_2 = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
        digit_2 = calculate_digit(cpf, weights_2)
        if int(cpf[10]) != digit_2:
            return False
        
        return True
    
    def _save_payment_flow_step_id(self, payment_id: str, step_id: str) -> bool:
        """
        # ✅ QI 500: Salva flow_step_id no payment de forma atômica
        
        Returns:
            bool: True se salvou com sucesso
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Payment
            
            with current_app.app_context():
                # ✅ Buscar payment com lock (SELECT FOR UPDATE)
                payment = db.session.query(Payment).filter_by(payment_id=payment_id).with_for_update().first()
                
                if not payment:
                    logger.error(f"❌ Payment não encontrado: {payment_id}")
                    return False
                
                # ✅ Validar que payment ainda está pending (evita sobrescrever se já foi processado)
                if payment.status != 'pending':
                    logger.warning(f"⚠️ Payment {payment_id} já está {payment.status} - não atualizando flow_step_id")
                    return False
                
                # Salvar flow_step_id
                payment.flow_step_id = step_id
                
                # ✅ Commit atômico
                db.session.commit()
                
                # ✅ Verificar se foi salvo corretamente
                db.session.refresh(payment)
                if payment.flow_step_id == step_id:
                    logger.info(f"✅ flow_step_id salvo atomicamente: {step_id} para payment {payment_id}")
                    return True
                else:
                    logger.error(f"❌ flow_step_id não foi salvo corretamente!")
                    return False
        
        except Exception as e:
            logger.error(f"❌ Erro ao salvar flow_step_id: {e}", exc_info=True)
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    def _build_step_buttons(self, step: Dict[str, Any], config: Dict[str, Any] = None) -> list:
        """
        # ✅ QI 500: Constrói lista de botões para um step (customizados + cadastrados)
        
        Returns:
            list: Lista de botões no formato Telegram API
        """
        buttons = []
        step_config = step.get('config', {})
        step_id = step.get('id', '')
        
        if config is None:
            config = {}
        
        # ✅ 1. Processar botões customizados primeiro
        custom_buttons = step_config.get('custom_buttons', [])
        if custom_buttons and len(custom_buttons) > 0:
            for idx, custom_btn in enumerate(custom_buttons):
                btn_text = custom_btn.get('text', '')
                target_step = custom_btn.get('target_step', '')
                
                if btn_text:
                    # Criar callback_data no formato: flow_step_{step_id}_btn_{idx}
                    action = f"btn_{idx}"
                    callback_data = f"flow_step_{step_id}_{action}"
                    buttons.append({
                        'text': btn_text,
                        'callback_data': callback_data
                    })
                    logger.info(f"🔘 Botão customizado criado: '{btn_text}' → {target_step if target_step else 'nenhum'} (callback: {callback_data})")
        
        # ✅ 2. Processar botões cadastrados (se não houver customizados ou adicionar junto)
        selected_buttons = step_config.get('selected_buttons', [])
        if selected_buttons:
            main_buttons = config.get('main_buttons', []) if config else []
            redirect_buttons = config.get('redirect_buttons', []) if config else []
            
            for selected in selected_buttons:
                btn_type = selected.get('type')
                btn_index = selected.get('index')
                
                if btn_type == 'main' and btn_index is not None:
                    if btn_index < len(main_buttons):
                        btn = main_buttons[btn_index]
                        if btn.get('text') and btn.get('price'):
                            price = float(btn.get('price', 0))
                            button_text = f"{btn['text']} - R$ {price:.2f}"
                            buttons.append({
                                'text': button_text,
                                'callback_data': f"buy_{btn_index}"
                            })
                elif btn_type == 'redirect' and btn_index is not None:
                    if btn_index < len(redirect_buttons):
                        btn = redirect_buttons[btn_index]
                        if btn.get('text') and btn.get('url'):
                            buttons.append({
                                'text': btn['text'],
                                'url': btn['url']
                            })
        
        return buttons
    
    def _execute_step(self, step: Dict[str, Any], token: str, chat_id: int, delay: float = 0, config: Dict[str, Any] = None):
        """
        # ✅ QI 500: Executa um step do fluxo com tratamento de erro robusto
        """
        import time
        
        logger.info(f"🎬 _execute_step chamado: step_id={step.get('id')}, step_type={step.get('type')}")
        
        # ✅ VALIDAÇÃO: Verificar se step é válido
        if not step or not isinstance(step, dict):
            logger.error(f"❌ Step inválido: {step}")
            return
        
        step_type = step.get('type')
        if not step_type or not isinstance(step_type, str):
            logger.error(f"❌ Step sem tipo válido: {step}")
            return
        
        step_config = step.get('config', {})
        if config is None:
            config = {}
        
        logger.info(f"🎬 Executando step tipo '{step_type}' com config: {step_config}")
        
        # ✅ TRATAMENTO DE ERRO: Try/except para cada tipo de step
        try:
            if step_type == 'content':
                # ✅ Processar botões (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                message_text = step_config.get('message', '')
                media_url = step_config.get('media_url')
                media_type = step_config.get('media_type', 'video')
                
                logger.info(f"📤 Enviando step 'content': mensagem_len={len(message_text) if message_text else 0}, media_url={bool(media_url)}, media_type={media_type}, buttons={len(buttons)}")
                
                # 🔥 V8 ULTRA: Verificar se step tem conteúdo antes de enviar
                if not message_text and not media_url:
                    logger.error(f"❌ Step 'content' não tem mensagem nem mídia configurada! step_id={step.get('id')}")
                    # Enviar mensagem de aviso ao usuário
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="⚠️ Esta etapa não tem conteúdo configurado. Entre em contato com o suporte."
                    )
                    return  # Não continuar se não tem conteúdo
                
                result = self.send_funnel_step_sequential(
                    token=token,
                    chat_id=str(chat_id),
                    text=message_text or '',  # Garantir string vazia se None
                    media_url=media_url,
                    media_type=media_type,
                    buttons=buttons,
                    delay_between=delay
                )
                
                if result:
                    logger.info(f"✅ Step 'content' enviado com sucesso: resultado={result}")
                else:
                    logger.error(f"❌ Falha ao enviar step 'content': resultado={result}")
            elif step_type == 'message':
                # ✅ Processar botões (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                message_text = step_config.get('message', '')
                if not message_text or not message_text.strip():
                    logger.error(f"❌ Step 'message' não tem mensagem configurada! step_id={step.get('id')}")
                    # Enviar mensagem de aviso ao usuário
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="⚠️ Esta etapa não tem mensagem configurada. Entre em contato com o suporte."
                    )
                    return  # Não continuar se não tem mensagem
                
                logger.info(f"📤 Enviando step 'message' com mensagem: {message_text[:50]}...")
                logger.info(f"📤 Botões: {len(buttons)} botões configurados")
                
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message_text,
                    buttons=buttons if buttons else None
                )
                
                if result:
                    logger.info(f"✅ Step 'message' enviado com sucesso: resultado={result}")
                else:
                    logger.error(f"❌ Falha ao enviar step 'message': resultado={result}")
            elif step_type == 'audio':
                # ✅ Processar botões (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message='',
                    media_url=step_config.get('audio_url'),
                    media_type='audio',
                    buttons=buttons if buttons else None
                )
            elif step_type == 'video':
                # ✅ Processar botões (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=step_config.get('message', ''),
                    media_url=step_config.get('media_url'),
                    media_type='video',
                    buttons=buttons
                )
            elif step_type == 'buttons':
                # ✅ NOVO: Verificar se usa botões contextuais ou globais
                use_custom_buttons = step_config.get('use_custom_buttons', False)
                buttons = []
                
                if use_custom_buttons:
                    # ✅ Botões contextuais (específicos do step)
                    custom_buttons = step_config.get('custom_buttons', [])
                    step_id = step.get('id', '')
                    
                    for idx, custom_btn in enumerate(custom_buttons):
                        btn_text = custom_btn.get('text', '')
                        target_step = custom_btn.get('target_step', '')
                        
                        if btn_text and target_step:
                            # Criar callback_data no formato: flow_step_{step_id}_{action}
                            action = f"btn_{idx}"
                            callback_data = f"flow_step_{step_id}_{action}"
                            buttons.append({
                                'text': btn_text,
                                'callback_data': callback_data
                            })
                            logger.info(f"🔘 Botão contextual criado: '{btn_text}' → {target_step} (callback: {callback_data})")
                else:
                    # ✅ Botões globais (comportamento antigo)
                    selected_buttons = step_config.get('selected_buttons', [])
                    
                    # Buscar botões do config completo (main_buttons e redirect_buttons)
                    main_buttons = config.get('main_buttons', []) if config else []
                    redirect_buttons = config.get('redirect_buttons', []) if config else []
                    
                    # Construir lista de botões baseada nos selecionados
                    for selected in selected_buttons:
                        btn_type = selected.get('type')
                        btn_index = selected.get('index')
                        
                        if btn_type == 'main' and btn_index is not None:
                            if btn_index < len(main_buttons):
                                btn = main_buttons[btn_index]
                                if btn.get('text') and btn.get('price'):
                                    price = float(btn.get('price', 0))
                                    button_text = self._format_button_text(btn['text'], price, btn.get('price_position'))
                                    buttons.append({
                                        'text': button_text,
                                        'callback_data': f"buy_{btn_index}"
                                    })
                        elif btn_type == 'redirect' and btn_index is not None:
                            if btn_index < len(redirect_buttons):
                                btn = redirect_buttons[btn_index]
                                if btn.get('text') and btn.get('url'):
                                    buttons.append({
                                        'text': btn['text'],
                                        'url': btn['url']
                                    })
                
                if buttons:
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=step_config.get('message', '⬇️ Escolha uma opção'),
                        buttons=buttons
                    )
            
            # Delay antes do próximo step
            if delay > 0:
                time.sleep(delay)
        
        except Exception as e:
            logger.error(f"❌ Erro ao executar step tipo '{step_type}': {e}", exc_info=True)
            # ✅ FALLBACK: Enviar mensagem de erro genérica
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="⚠️ Erro ao processar esta etapa. Tente novamente."
                )
            except:
                pass
            raise  # Re-raise para caller decidir o que fazer
        
        # Delay antes do próximo step
        if delay > 0:
            time.sleep(delay)
    
    def _save_current_step_atomic(self, bot_id: int, telegram_user_id: str, step_id: str, ttl: int = 7200) -> bool:
        """
        # ✅ QI 500: Salva step atual com lock atômico (evita race conditions)
        
        # ✅ NOVO: TTL aumentado para 2 horas (evita perda de estado em sessões longas)
        # ✅ NOVO: Timeout em operações Redis
        
        Returns:
            bool: True se salvou com sucesso, False se falhou
        """
        try:
            import time
            redis_conn = get_redis_connection()
            if not redis_conn:
                logger.warning("⚠️ Redis não disponível - usando fallback")
                return False
            
            # ✅ VALIDAÇÃO: Sanitizar telegram_user_id
            if not telegram_user_id or not isinstance(telegram_user_id, str) or not telegram_user_id.strip():
                logger.error(f"❌ telegram_user_id inválido: {telegram_user_id}")
                return False
            
            telegram_user_id = telegram_user_id.strip()
            
            lock_key = f"lock:flow_step:{bot_id}:{telegram_user_id}"
            step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
            
            # ✅ NOVO: Timeout de 2 segundos para operações Redis
            try:
                # Tentar adquirir lock (expira em 5 segundos)
                lock_acquired = redis_conn.set(lock_key, "1", ex=5, nx=True)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao adquirir lock (timeout?): {e}")
                return False
            
            if not lock_acquired:
                logger.warning(f"⛔ Lock já adquirido para {step_key} - aguardando...")
                # Aguardar até 2 segundos para lock ser liberado
                for _ in range(20):  # 20 tentativas de 0.1s = 2s total
                    time.sleep(0.1)
                    try:
                        if redis_conn.set(lock_key, "1", ex=5, nx=True):
                            lock_acquired = True
                            break
                    except:
                        pass
                
                if not lock_acquired:
                    logger.error(f"❌ Não foi possível adquirir lock após 2s - abortando")
                    return False
            
            try:
                # ✅ NOVO: TTL aumentado para 2 horas (7200 segundos)
                redis_conn.set(step_key, step_id, ex=ttl)
                
                # ✅ NOVO: Salvar timestamp para time_elapsed
                timestamp_key = f"flow_step_timestamp:{bot_id}:{telegram_user_id}"
                try:
                    redis_conn.set(timestamp_key, int(time.time()), ex=ttl)
                    logger.debug(f"⏱️ Timestamp salvo para time_elapsed: {timestamp_key}")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao salvar timestamp (não crítico): {e}")
                
                logger.info(f"✅ Step atual salvo atomicamente: {step_id} (TTL: {ttl}s)")
                return True
            except Exception as e:
                logger.error(f"❌ Erro ao salvar step atual (timeout?): {e}")
                return False
            finally:
                # Sempre liberar lock
                try:
                    redis_conn.delete(lock_key)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"❌ Erro ao salvar step atual: {e}", exc_info=True)
            return False
    
    def _get_current_step_atomic(self, bot_id: int, telegram_user_id: str) -> Optional[str]:
        """
        # ✅ QI 500: Busca step atual com validação e timeout
        
        Returns:
            str: step_id ou None se não encontrado
        """
        try:
            redis_conn = get_redis_connection()
            if not redis_conn:
                return None
            
            # ✅ NOVO: Timeout de 2 segundos para operações Redis
            step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
            try:
                step_id = redis_conn.get(step_key)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao buscar step atual (timeout?): {e}")
                return None
            
            if step_id:
                step_id = step_id.decode('utf-8') if isinstance(step_id, bytes) else step_id
                # Validar que step_id não está vazio
                if step_id and step_id.strip():
                    return step_id.strip()
            
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao buscar step atual: {e}", exc_info=True)
            return None
    
    def _get_flow_snapshot_from_redis(self, bot_id: int, telegram_user_id: str) -> Optional[Dict[str, Any]]:
        """
        # ✅ QI 500: Busca snapshot de config do Redis
        
        Returns:
            Dict com snapshot ou None se não encontrado
        """
        try:
            import json
            redis_conn = get_redis_connection()
            if not redis_conn:
                return None
            
            snapshot_key = f"flow_snapshot:{bot_id}:{telegram_user_id}"
            try:
                snapshot_json = redis_conn.get(snapshot_key)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao buscar snapshot (timeout?): {e}")
                return None
            
            if snapshot_json:
                snapshot_json = snapshot_json.decode('utf-8') if isinstance(snapshot_json, bytes) else snapshot_json
                snapshot = json.loads(snapshot_json)
                logger.info(f"✅ Snapshot recuperado do Redis: {snapshot_key}")
                return snapshot
            
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao buscar snapshot: {e}", exc_info=True)
            return None
    
    def _execute_flow(self, bot_id: int, token: str, config: Dict[str, Any], 
                      chat_id: int, telegram_user_id: str):
        """
        # ✅ QI 500: Executa fluxo visual configurado - com snapshot de config
        
        # ✅ SEGURO: Fallback para welcome_message se fluxo inválido
        # ✅ HÍBRIDO: Síncrono até payment, assíncrono após callback
        # ✅ INTELIGENTE: Usa flow_start_step_id ou fallback automático (order=1 ou primeiro step)
        # ✅ SNAPSHOT: Cria snapshot da config no início (evita mudanças durante execução)
        """
        try:
            import json
            import time
            
            # ✅ CRÍTICO: Parsear flow_steps se for string JSON
            flow_steps_raw = config.get('flow_steps', [])
            flow_steps = []
            
            if flow_steps_raw:
                if isinstance(flow_steps_raw, str):
                    try:
                        flow_steps = json.loads(flow_steps_raw)
                        logger.info(f"✅ flow_steps parseado de JSON em _execute_flow: {len(flow_steps)} steps")
                    except Exception as e:
                        logger.error(f"❌ Erro ao parsear flow_steps em _execute_flow: {e}")
                        raise ValueError(f"Fluxo inválido (JSON malformado): {e}")
                elif isinstance(flow_steps_raw, list):
                    flow_steps = flow_steps_raw
                else:
                    logger.error(f"❌ flow_steps tem tipo inválido em _execute_flow: {type(flow_steps_raw)}")
                    raise ValueError("Fluxo inválido (tipo incorreto)")
            
            if not flow_steps or len(flow_steps) == 0:
                logger.warning("⚠️ Fluxo vazio - usando welcome_message")
                raise ValueError("Fluxo vazio")
            
            # ✅ NOVO: Criar snapshot da config no início
            flow_snapshot = {
                'flow_steps': json.dumps(flow_steps),
                'flow_start_step_id': config.get('flow_start_step_id'),
                'flow_enabled': config.get('flow_enabled', False),
                'main_buttons': json.dumps(config.get('main_buttons', [])),
                'redirect_buttons': json.dumps(config.get('redirect_buttons', [])),
                'snapshot_timestamp': int(time.time())
            }
            
            # ✅ Salvar snapshot no Redis (expira em 24h)
            try:
                redis_conn = get_redis_connection()
                if redis_conn:
                    snapshot_key = f"flow_snapshot:{bot_id}:{telegram_user_id}"
                    redis_conn.set(snapshot_key, json.dumps(flow_snapshot), ex=86400)
                    logger.info(f"✅ Snapshot de config salvo: {snapshot_key}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao salvar snapshot: {e} - continuando sem snapshot")
                flow_snapshot = None
            
            # ✅ IDENTIFICAR STEP INICIAL (QI 500: Prioridade inteligente)
            start_step_id = config.get('flow_start_step_id')
            start_step = None
            
            logger.info(f"🔍 Buscando step inicial: flow_start_step_id={start_step_id} (tipo: {type(start_step_id)})")
            logger.info(f"🔍 Total de steps no fluxo: {len(flow_steps)}")
            logger.info(f"🔍 IDs dos steps: {[str(s.get('id')) for s in flow_steps if isinstance(s, dict)]}")
            
            if start_step_id:
                # Buscar step específico marcado como inicial
                logger.info(f"🔍 Tentando encontrar step inicial com ID: {start_step_id}")
                start_step = self._find_step_by_id(flow_steps, start_step_id)
                if start_step:
                    logger.info(f"✅ Step inicial encontrado: {start_step_id} (tipo: {start_step.get('type')}, order: {start_step.get('order', 0)})")
                else:
                    logger.warning(f"⚠️ Step inicial {start_step_id} não encontrado - usando fallback")
                    logger.warning(f"⚠️ IDs disponíveis: {[str(s.get('id')) for s in flow_steps if isinstance(s, dict)]}")
                    start_step_id = None
            
            if not start_step:
                # FALLBACK 1: Buscar step com order=1
                sorted_steps = sorted(flow_steps, key=lambda x: x.get('order', 0))
                for step in sorted_steps:
                    if step.get('order') == 1:
                        start_step = step
                        start_step_id = step.get('id')
                        logger.info(f"🎯 Usando step com order=1: {start_step_id}")
                        break
                
                # FALLBACK 2: Se não encontrou order=1, usar primeiro step (menor order)
                if not start_step:
                    if sorted_steps:
                        start_step = sorted_steps[0]
                        start_step_id = start_step.get('id')
                        logger.info(f"🎯 Usando primeiro step (order={start_step.get('order', 0)}): {start_step_id}")
                    else:
                        logger.error(f"❌ Nenhum step encontrado no fluxo")
                        raise ValueError("Nenhum step disponível")
            
            # ✅ V8 ULTRA: Proteção contra loops já existe em _execute_flow_recursive via visited_steps
            # Não precisa validar ciclos aqui - visited_steps vai detectar e parar loops automaticamente
            
            # Executar recursivamente a partir do step inicial
            logger.info(f"🚀 Iniciando fluxo a partir do step inicial: {start_step_id} (tipo: {type(start_step_id)}, order={start_step.get('order', 0)})")
            logger.info(f"🚀 Step inicial completo: {start_step}")
            logger.info(f"🚀 Step inicial tipo: {start_step.get('type')}")
            logger.info(f"🚀 Step inicial config: {start_step.get('config', {})}")
            logger.info(f"🚀 Step inicial mensagem: {start_step.get('config', {}).get('message', '')[:100] if start_step.get('config', {}).get('message') else 'VAZIA'}")
            logger.info(f"🚀 Chamando _execute_flow_recursive com step_id={start_step_id}")
            
            self._execute_flow_recursive(
                bot_id, token, config, chat_id, telegram_user_id, str(start_step_id),  # ✅ Garantir string
                recursion_depth=0,
                visited_steps=set(),
                flow_snapshot=flow_snapshot
            )
            
            logger.info(f"✅ _execute_flow_recursive concluído para step {start_step_id}")
            
        except ValueError as e:
            # Erro de validação (fluxo vazio, step não encontrado, etc)
            logger.error(f"❌ Erro de validação ao executar fluxo: {e}", exc_info=True)
            # 🔥 V8 ULTRA: Enviar mensagem de erro ao usuário em vez de apenas fazer raise
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="⚠️ Erro na configuração do fluxo. Entre em contato com o suporte."
                )
            except Exception as e2:
                logger.error(f"❌ Erro ao enviar mensagem de erro: {e2}")
            raise  # Re-raise para caller decidir fallback
        except Exception as e:
            logger.error(f"❌ Erro ao executar fluxo: {e}", exc_info=True)
            # 🔥 V8 ULTRA: Enviar mensagem de erro ao usuário em vez de apenas fazer raise
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="⚠️ Erro ao processar fluxo. Tente novamente ou entre em contato com o suporte."
                )
            except Exception as e2:
                logger.error(f"❌ Erro ao enviar mensagem de erro: {e2}")
            raise  # Re-raise para caller decidir fallback
    
    def _execute_flow_recursive(self, bot_id: int, token: str, config: Dict[str, Any],
                                chat_id: int, telegram_user_id: str, step_id: str,
                                recursion_depth: int = 0, visited_steps: set = None,
                                flow_snapshot: Dict[str, Any] = None):
        """
        # ✅ QI 500: Executa step recursivamente - THREAD-SAFE e ROBUSTO
        
        # ✅ RECURSÃO LIMITADA: Máximo 50 steps (proteção contra loops infinitos)
        # ✅ DETECÇÃO DE LOOPS: Usa visited_steps para detectar ciclos
        # ✅ SNAPSHOT DE CONFIG: Usa snapshot se disponível (evita mudanças durante execução)
        
        Args:
            recursion_depth: Profundidade atual (passado como parâmetro, não atributo)
            visited_steps: Set de steps já visitados (detecta loops)
            flow_snapshot: Snapshot da config no início do fluxo
        """
        import time
        from flask import current_app
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Payment
        
        if visited_steps is None:
            visited_steps = set()
        
        # ✅ Proteção contra loops infinitos
        if recursion_depth >= 50:
            logger.error(f"❌ Profundidade máxima atingida (50) para step {step_id}")
            self.send_telegram_message(
                token=token,
                chat_id=str(chat_id),
                message="⚠️ Fluxo muito longo detectado. Entre em contato com o suporte."
            )
            return
        
        # ✅ Detectar loops circulares
        if step_id in visited_steps:
            logger.error(f"❌ Loop circular detectado: step {step_id} já foi visitado")
            logger.error(f"   Steps visitados: {list(visited_steps)}")
            self.send_telegram_message(
                token=token,
                chat_id=str(chat_id),
                message="⚠️ Erro no fluxo detectado. Entre em contato com o suporte."
            )
            return
        
        # Adicionar step atual aos visitados
        visited_steps.add(step_id)
        
        try:
            # ✅ NOVO: Usar snapshot se disponível
            if flow_snapshot:
                import json
                flow_steps = json.loads(flow_snapshot.get('flow_steps', '[]'))
                main_buttons = json.loads(flow_snapshot.get('main_buttons', '[]'))
                redirect_buttons = json.loads(flow_snapshot.get('redirect_buttons', '[]'))
                
                # Criar config a partir do snapshot
                config_from_snapshot = {
                    'flow_steps': flow_steps,
                    'flow_start_step_id': flow_snapshot.get('flow_start_step_id'),
                    'flow_enabled': flow_snapshot.get('flow_enabled', False),
                    'main_buttons': main_buttons,
                    'redirect_buttons': redirect_buttons
                }
                # Mesclar com config atual (priorizar snapshot, mas manter outros campos)
                config = {**config, **config_from_snapshot}
            else:
                # ✅ CRÍTICO: Parsear flow_steps se necessário (pode vir como string JSON)
                flow_steps_raw = config.get('flow_steps', [])
                flow_steps = []
                if flow_steps_raw:
                    if isinstance(flow_steps_raw, str):
                        try:
                            import json
                            flow_steps = json.loads(flow_steps_raw)
                            logger.info(f"✅ flow_steps parseado de JSON em _execute_flow_recursive: {len(flow_steps)} steps")
                        except Exception as e:
                            logger.error(f"❌ Erro ao parsear flow_steps em _execute_flow_recursive: {e}")
                            flow_steps = []
                    elif isinstance(flow_steps_raw, list):
                        flow_steps = flow_steps_raw
                    else:
                        logger.error(f"❌ flow_steps tem tipo inválido em _execute_flow_recursive: {type(flow_steps_raw)}")
                        flow_steps = []
            
            logger.info(f"🔍 Buscando step {step_id} em {len(flow_steps)} steps disponíveis")
            logger.info(f"🔍 IDs dos steps disponíveis: {[s.get('id') for s in flow_steps if isinstance(s, dict)]}")
            
            step = self._find_step_by_id(flow_steps, step_id)
            
            if not step:
                logger.error(f"❌ Step {step_id} não encontrado no fluxo")
                logger.error(f"❌ flow_steps tem {len(flow_steps)} steps")
                logger.error(f"❌ Tipos dos steps: {[type(s) for s in flow_steps]}")
                # ✅ FALLBACK: Tentar encontrar step inicial ou enviar mensagem de erro
                self._handle_missing_step(bot_id, token, config, chat_id, telegram_user_id)
                return
            
            step_type = step.get('type')
            step_config = step.get('config', {})
            delay = step.get('delay_seconds', 0)
            connections = step.get('connections', {})
            
            logger.info(f"✅ Step {step_id} encontrado!")
            logger.info(f"🎯 Executando step {step_id} (tipo: {step_type}, ordem: {step.get('order', 0)})")
            logger.info(f"🎯 Config do step: {step_config}")
            logger.info(f"🎯 Connections: {connections}")
            logger.info(f"🎯 Mensagem do step: {step_config.get('message', '')[:100] if step_config.get('message') else 'VAZIA'}")
            logger.info(f"🎯 Media URL: {step_config.get('media_url', 'NÃO CONFIGURADA')}")
            logger.info(f"🎯 Custom buttons: {len(step_config.get('custom_buttons', []))} botões")
            logger.info(f"🎯 Media URL: {step_config.get('media_url', 'NÃO CONFIGURADA')}")
            logger.info(f"🎯 Custom buttons: {len(step_config.get('custom_buttons', []))} botões")
            
            # ✅ Payment para aqui (aguarda callback verify_)
            if step_type == 'payment':
                logger.info(f"💰 Step payment detectado - gerando PIX e parando fluxo")
                
                # ✅ VALIDAÇÃO CRÍTICA: Verificar conexões obrigatórias ANTES de gerar PIX
                has_next = bool(connections.get('next'))
                has_pending = bool(connections.get('pending'))
                
                if not has_next and not has_pending:
                    logger.error(f"❌ Step payment {step_id} não tem conexões obrigatórias (next ou pending)")
                    error_message = "⚠️ Erro de configuração: Step de pagamento sem conexões definidas. Entre em contato com o suporte."
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=error_message
                    )
                    return  # Não gerar PIX se não tem conexões
                
                # Validar que conexões apontam para steps existentes
                if has_next:
                    next_step_id = connections.get('next')
                    if not self._find_step_by_id(flow_steps, next_step_id):
                        logger.error(f"❌ Step payment {step_id} tem conexão 'next' apontando para step inexistente: {next_step_id}")
                        error_message = "⚠️ Erro de configuração: Conexão inválida no step de pagamento. Entre em contato com o suporte."
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=error_message
                        )
                        return
                
                if has_pending:
                    pending_step_id = connections.get('pending')
                    if not self._find_step_by_id(flow_steps, pending_step_id):
                        logger.error(f"❌ Step payment {step_id} tem conexão 'pending' apontando para step inexistente: {pending_step_id}")
                        error_message = "⚠️ Erro de configuração: Conexão inválida no step de pagamento. Entre em contato com o suporte."
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=error_message
                        )
                        return
                
                # ✅ NOVO: Buscar contexto do botão clicado (se disponível)
                # Isso será implementado quando rastrearmos botão até payment step
                context = visited_steps  # Por enquanto, usar visited_steps como contexto
                button_context = getattr(self, f'_button_context_{bot_id}_{telegram_user_id}', None)
                
                # Buscar dados do botão principal (primeiro main_button) para gerar PIX
                main_buttons = config.get('main_buttons', [])
                amount = 0.0
                description = 'Produto'
                button_index = 0
                
                # ✅ NOVO: Usar contexto do botão se disponível
                if button_context and isinstance(button_context, dict):
                    button_index = button_context.get('button_index')
                    if button_index is not None and button_index < len(main_buttons):
                        selected_button = main_buttons[button_index]
                        amount = float(selected_button.get('price', 0))
                        description = selected_button.get('description', 'Produto') or selected_button.get('text', 'Produto')
                        logger.info(f"💰 Usando botão do contexto: índice={button_index}, valor=R$ {amount:.2f}")
                    # Limpar contexto após usar
                    if hasattr(self, f'_button_context_{bot_id}_{telegram_user_id}'):
                        delattr(self, f'_button_context_{bot_id}_{telegram_user_id}')
                elif main_buttons and len(main_buttons) > 0:
                    # Fallback: primeiro botão
                    first_button = main_buttons[0]
                    amount = float(first_button.get('price', 0))
                    description = first_button.get('description', 'Produto') or first_button.get('text', 'Produto')
                    button_index = 0
                    logger.warning(f"⚠️ Usando primeiro botão (contexto não disponível)")
                
                # Usar valores do step se especificados (sobrescreve botão)
                if step_config.get('amount'):
                    amount = float(step_config.get('amount'))
                    logger.info(f"💰 Usando valor do step: R$ {amount:.2f}")
                if step_config.get('description'):
                    description = step_config.get('description')
                
                # Gerar PIX
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=amount,
                    description=description,
                    customer_name='Cliente',
                    customer_username='',
                    customer_user_id=telegram_user_id,
                    order_bump_shown=False,
                    order_bump_accepted=False,
                    order_bump_value=0.0
                )
                # ✅ UX FIX: Tratamento Amigável de Rate Limit
                if pix_data and pix_data.get('rate_limit'):
                    wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                    self.send_telegram_message(
                        chat_id=chat_id,
                        message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                        token=token
                    )
                    return
                
                if pix_data and pix_data.get('pix_code'):
                    # ✅ NOVO: Salvar flow_step_id atomicamente
                    payment_id = pix_data.get('payment_id')
                    if payment_id:
                        success = self._save_payment_flow_step_id(payment_id, step_id)
                        if not success:
                            logger.error(f"❌ Falha ao salvar flow_step_id - fluxo pode não continuar após pagamento")
                    
                    # Enviar mensagem de PIX
                    payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {amount:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data.get('pix_code')}</code>

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
                    
                    logger.info(f"✅ PIX gerado - fluxo pausado aguardando callback verify_")
                else:
                    logger.error(f"❌ Erro ao gerar PIX no fluxo")
                
                return  # Para aqui, aguarda callback
            
            # ✅ Access finaliza fluxo
            elif step_type == 'access':
                logger.info(f"✅ Step access detectado - finalizando fluxo")
                
                link = step_config.get('link') or config.get('access_link', '')
                message = step_config.get('message', 'Acesso liberado!')
                
                buttons = []
                if link:
                    buttons.append({
                        'text': '✅ Acessar',
                        'url': link
                    })
                
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    buttons=buttons if buttons else None
                )
                
                return  # Fim do fluxo
            
            # ✅ Executar step normalmente (content, message, audio, video, buttons)
            else:
                logger.info(f"🎬 Executando step tipo '{step_type}' (id={step_id})")
                logger.info(f"🎬 Config do step: {step_config}")
                logger.info(f"🎬 Mensagem do step: {step_config.get('message', '')[:100] if step_config.get('message') else 'VAZIA'}")
                
                # 🔥 V8 ULTRA: Verificar se step tem mensagem antes de executar
                if step_type == 'message' and not step_config.get('message'):
                    logger.warning(f"⚠️ Step {step_id} tipo 'message' não tem mensagem configurada!")
                    # Enviar mensagem de aviso ao usuário
                    try:
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="⚠️ Esta etapa não tem mensagem configurada. Entre em contato com o suporte."
                        )
                    except Exception as e:
                        logger.error(f"❌ Erro ao enviar mensagem de aviso: {e}")
                
                # 🔥 V8 ULTRA: Executar step com tratamento de erro robusto
                try:
                    self._execute_step(step, token, chat_id, delay, config=config)
                    logger.info(f"✅ Step {step_id} executado com sucesso")
                except Exception as e:
                    logger.error(f"❌ Erro ao executar step {step_id}: {e}", exc_info=True)
                    # Enviar mensagem de erro ao usuário
                    try:
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="⚠️ Erro ao processar esta etapa. Tente novamente ou entre em contato com o suporte."
                        )
                    except Exception as e2:
                        logger.error(f"❌ Erro ao enviar mensagem de erro: {e2}")
                    # Continuar para próximo step mesmo com erro (não quebrar fluxo completo)
                
                # ✅ NOVO: Priorizar condições sobre conexões diretas
                # Se step tem condições, aguardar input do usuário (não continuar automaticamente)
                conditions = step.get('conditions', [])
                if conditions and len(conditions) > 0:
                    logger.info(f"⏸️ Step {step_id} tem {len(conditions)} condição(ões) - aguardando input do usuário")
                    # ✅ NOVO: Salvar step atual com lock atômico (TTL aumentado para 2 horas)
                    success = self._save_current_step_atomic(bot_id, telegram_user_id, step_id, ttl=7200)
                    if not success:
                        logger.error(f"❌ Falha ao salvar step atual atomicamente - condições podem não funcionar")
                    # Fluxo pausa aqui - será continuado quando usuário enviar mensagem/clicar botão
                    return
                
                # Fallback: usar conexões diretas (comportamento antigo)
                next_step_id = connections.get('next')
                logger.info(f"🔍 Verificando conexões: next_step_id={next_step_id}, connections={connections}")
                
                if next_step_id:
                    logger.info(f"➡️ Continuando para próximo step: {next_step_id}")
                    self._execute_flow_recursive(
                        bot_id, token, config, chat_id, telegram_user_id, next_step_id,
                        recursion_depth=recursion_depth + 1,
                        visited_steps=visited_steps.copy(),  # Cópia para não compartilhar entre branches
                        flow_snapshot=flow_snapshot
                    )
                else:
                    # Sem próximo step - fim do fluxo
                    logger.info(f"✅ Fluxo finalizado - sem próximo step (step {step_id} não tem conexão 'next')")
                    # ✅ V∞: Limpar estado do Redis quando fluxo termina
                    try:
                        redis_conn = get_redis_connection()
                        if redis_conn:
                            current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                            redis_conn.delete(current_step_key)
                            logger.info(f"✅ [FLOW V∞] Estado do fluxo limpo do Redis (fluxo finalizado)")
                    except Exception as e:
                        logger.warning(f"⚠️ [FLOW V∞] Erro ao limpar estado do Redis: {e}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao executar step {step_id}: {e}", exc_info=True)
            # ✅ FALLBACK: Enviar mensagem de erro ao usuário
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="⚠️ Erro ao processar fluxo. Tente novamente ou entre em contato com o suporte."
                )
            except:
                pass
        finally:
            # Remover step atual dos visitados (permite revisitar em branches diferentes)
            visited_steps.discard(step_id)
            
            # ✅ V∞: Salvar estado do flow no Redis após cada step (24h TTL)
            try:
                redis_conn = get_redis_connection()
                if redis_conn:
                    current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                    redis_conn.setex(current_step_key, 86400, step_id)  # 24h
                    logger.debug(f"✅ [FLOW V∞] Estado salvo no Redis: {step_id} (TTL: 24h)")
            except Exception as e:
                logger.warning(f"⚠️ [FLOW V∞] Erro ao salvar estado no Redis: {e}")
    
    def continue_flow_if_active(self, bot, chat_id, telegram_user_id):
        """
        # ✅ V∞: Se o usuário estiver no meio do flow, continuar automaticamente.
        
        Args:
            bot: Objeto Bot
            chat_id: ID do chat
            telegram_user_id: ID do usuário no Telegram
            
        Returns:
            bool: True se flow foi continuado, False caso contrário
        """
        try:
            redis_conn = get_redis_connection()
            if not redis_conn:
                return False
            
            key = f"gb:{self.user_id}:flow_current_step:{bot.id}:{telegram_user_id}"
            step_id = redis_conn.get(key)
            
            if step_id:
                step_id = step_id.decode() if isinstance(step_id, bytes) else step_id
                logger.info(f"🔄 [FLOW V∞] Continuando fluxo ativo: step={step_id}")
                
                config = bot.config.to_dict() if bot.config else {}
                
                # Buscar snapshot do Redis
                flow_snapshot = self._get_flow_snapshot_from_redis(bot.id, telegram_user_id)
                
                # Continuar fluxo
                self._execute_flow_recursive(
                    bot.id, bot.token, config,
                    chat_id, telegram_user_id,
                    step_id,
                    recursion_depth=0,
                    visited_steps=set(),
                    flow_snapshot=flow_snapshot
                )
                return True
            
            return False
        except Exception as e:
            logger.error(f"❌ [FLOW V∞] Erro ao continuar fluxo: {e}", exc_info=True)
            return False
    
    def _handle_missing_step(self, bot_id: int, token: str, config: Dict[str, Any],
                             chat_id: int, telegram_user_id: str):
        """
        # ✅ QI 500: Fallback quando step não é encontrado
        """
        try:
            # Limpar step atual do Redis
            redis_conn = get_redis_connection()
            if redis_conn:
                current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                redis_conn.delete(current_step_key)
            
            # Tentar reiniciar fluxo do início
            flow_enabled = config.get('flow_enabled', False)
            if flow_enabled:
                logger.info(f"🔄 Tentando reiniciar fluxo do início...")
                self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
            else:
                # Fallback para welcome_message
                logger.info(f"🔄 Usando welcome_message como fallback...")
                welcome_message = config.get('welcome_message', 'Olá! Bem-vindo!')
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=welcome_message
                )
        except Exception as e:
            logger.error(f"❌ Erro no fallback de missing step: {e}", exc_info=True)
    
    def _execute_flow_step_async(self, bot_id: int, token: str, config: Dict[str, Any],
                                  chat_id: int, telegram_user_id: str, step_id: str):
        """
        # ✅ QI 500: Executa step do fluxo de forma assíncrona (via RQ)
        
        # ✅ ASSÍNCRONO: Pode ser pesado (access pode enviar múltiplas mensagens)
        # ✅ SNAPSHOT: Busca snapshot do Redis para manter consistência
        # ✅ IDEMPOTÊNCIA: Verifica se step já foi executado (evita duplicação)
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            
            with current_app.app_context():
                # ✅ NOVO: Buscar snapshot do Redis primeiro (prioridade sobre config atual)
                telegram_user_id_str = str(telegram_user_id) if telegram_user_id else ''
                flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id_str)
                
                if flow_snapshot:
                    # Usar snapshot se disponível
                    import json
                    flow_steps = json.loads(flow_snapshot.get('flow_steps', '[]'))
                    main_buttons = json.loads(flow_snapshot.get('main_buttons', '[]'))
                    redirect_buttons = json.loads(flow_snapshot.get('redirect_buttons', '[]'))
                    
                    config_from_snapshot = {
                        'flow_steps': flow_steps,
                        'flow_start_step_id': flow_snapshot.get('flow_start_step_id'),
                        'flow_enabled': flow_snapshot.get('flow_enabled', False),
                        'main_buttons': main_buttons,
                        'redirect_buttons': redirect_buttons
                    }
                    # Mesclar com config atual (priorizar snapshot)
                    config = {**config, **config_from_snapshot}
                    logger.info(f"✅ Usando snapshot de config para step {step_id}")
                else:
                    # Fallback: buscar config atual do banco
                    from internal_logic.core.models import Bot
                    bot = Bot.query.get(bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                        logger.info(f"⚠️ Snapshot não encontrado, usando config atual do banco")
                
                # ✅ NOVO: Idempotência - verificar se step já foi executado recentemente
                try:
                    redis_conn = get_redis_connection()
                    if redis_conn:
                        execution_key = f"flow_step_executed:{bot_id}:{telegram_user_id_str}:{step_id}"
                        already_executed = redis_conn.get(execution_key)
                        if already_executed:
                            logger.warning(f"⛔ Step {step_id} já foi executado recentemente - pulando (idempotência)")
                            return
                        # Marcar como executado (expira em 5 minutos)
                        redis_conn.set(execution_key, "1", ex=300)
                except:
                    pass  # Se Redis falhar, continuar (fail-open)
                
                # Executar step recursivamente
                self._execute_flow_recursive(
                    bot_id, token, config, chat_id, telegram_user_id_str, step_id,
                    recursion_depth=0,
                    visited_steps=set(),
                    flow_snapshot=flow_snapshot
                )
                
                logger.info(f"✅ Step {step_id} executado com sucesso (assíncrono)")
        
        except Exception as e:
            logger.error(f"❌ Erro ao executar step {step_id} (assíncrono): {e}", exc_info=True)
    
    def _reset_user_funnel(self, bot_id: int, chat_id: int, telegram_user_id: str, db_session=None):
        """
        # ✅ QI 500: RESET ABSOLUTO DO FUNIL
        
        Limpa TODOS os estados e sessões do funil:
        - Sessões de order bump (Redis)
        - Cache de rate limiting (memória)
        - welcome_sent = False (ESSENCIAL - permite novo welcome)
        - last_interaction = agora
        - Qualquer estado relacionado ao funil
        
        Esta função é chamada SEMPRE que /start é recebido,
        independente de conversa ativa ou histórico.
        """
        try:
            # ✅ REDIS MIGRATION: Limpar sessões de order bump no Redis
            user_key_orderbump = f"orderbump_{chat_id}"
            session_key = f"gb:ob_session:{user_key_orderbump}"
            pix_cache_key = f"gb:pix_cache:{user_key_orderbump}"
            
            redis_conn = get_redis_connection()
            deleted_session = redis_conn.delete(session_key)
            deleted_cache = redis_conn.delete(pix_cache_key)
            
            if deleted_session or deleted_cache:
                logger.info(f"🧹 Sessão de order bump limpa no Redis: {user_key_orderbump} (session={deleted_session}, cache={deleted_cache})")
            
            # Limpar cache de rate limiting (em memória - por worker)
            user_key_rate = f"{bot_id}_{telegram_user_id}"
            if user_key_rate in self.rate_limit_cache:
                del self.rate_limit_cache[user_key_rate]
                logger.info(f"🧹 Rate limit cache limpo: {user_key_rate}")
            
            # ✅ QI 500: RESET COMPLETO NO BANCO (ESSENCIAL)
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser, get_brazil_time
            
            # Usar sessão fornecida ou criar nova
            if db_session:
                session = db_session
                in_context = True
            else:
                session = None
                in_context = False
            
            def do_reset():
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id,
                    archived=False
                ).first()
                
                if bot_user:
                    # ✅ QI 500: RESET COMPLETO - ESSENCIAL para permitir novo welcome
                    bot_user.welcome_sent = False  # ✅ ESSENCIAL - sem isso, funil nunca recomeça
                    bot_user.welcome_sent_at = None
                    bot_user.last_interaction = get_brazil_time()  # Atualizar última interação
                    # Usar sessão correta
                    current_session = session if session else db.session
                    current_session.commit()
                    logger.info(f"🧹 Estado do funil resetado no banco: welcome_sent=False, last_interaction=agora")
                else:
                    logger.warning(f"⚠️ BotUser não encontrado para reset: bot_id={bot_id}, telegram_user_id={telegram_user_id}")
            
            if in_context:
                # Já estamos em app_context, fazer reset direto
                do_reset()
            else:
                # Criar novo app_context
                from flask import current_app
                with current_app.app_context():
                    do_reset()
            
            logger.info(f"✅ Funil completamente resetado para bot_id={bot_id}, chat_id={chat_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao resetar funil: {e}")
            import traceback
            traceback.print_exc()
            # Não interromper o fluxo se falhar
    
    def _handle_start_command(self, bot_id: int, token: str, config: Dict[str, Any], 
                             chat_id: int, message: Dict[str, Any], start_param: str = None):
        """
        Processa comando /start - FAST RESPONSE MODE (QI 200)
        
        # ✅ REGRA ABSOLUTA QI 200: /start SEMPRE reinicia o funil
        - Ignora conversa ativa
        - Ignora histórico
        - Ignora steps anteriores
        - Zera tudo e começa do zero
        
        # ✅ OTIMIZAÇÃO QI 200: Resposta <50ms
        - Envia mensagem IMEDIATAMENTE
        - Processa tarefas pesadas em background via RQ
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot (será recarregada do banco)
            chat_id: ID do chat
            message: Dados da mensagem
            start_param: Parâmetro do deep link (ex: "acesso", "promo123", None se não houver)
        """
        try:
            # ✅ QI 200: PRIORIDADE MÁXIMA - Resetar funil ANTES de qualquer verificação
            user_from = message.get('from', {})
            telegram_user_id = str(user_from.get('id', ''))
            first_name = user_from.get('first_name', 'Usuário')
            
            logger.info(f"⭐ COMANDO /START recebido - Reiniciando funil FORÇADAMENTE (regra absoluta)")

            # ✅ EXTRAÇÃO FORÇADA DO START PARAM (fallback se não veio pelo argumento)
            if not start_param:
                try:
                    text_msg = message.get('text') if isinstance(message, dict) else None
                    if text_msg and isinstance(text_msg, str):
                        parts = text_msg.split()
                        if len(parts) > 1:
                            start_param = parts[1].strip()
                            logger.info(f"🔧 start_param recuperado do texto: '{start_param}'")
                except Exception as e:
                    logger.warning(f"⚠️ Falha ao extrair start_param do texto: {e}")

            # ✅ PATCH: extrair pixel_id transportado no start_param (formato token__px_<pixel>) sem sobrescrever tracking base
            pixel_id_from_start = None
            if start_param and '__px_' in start_param:
                parts = start_param.split('__px_', 1)
                if parts and parts[0]:
                    start_param = parts[0]
                if len(parts) > 1 and parts[1]:
                    pixel_id_from_start = parts[1]
                    logger.info(f"✅ Pixel transportado no start_param preservado: {pixel_id_from_start}")

            # ============================================================================
            # ✅ HIDRATAÇÃO DE TRACKING (PRIORIDADE MÁXIMA - ANTES DE QUALQUER RESET)
            # ============================================================================
            logger.info(f"🔍 Tentando processar tracking para param: '{start_param}'")
            try:
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import BotUser
                if start_param:
                    with current_app.app_context():
                        bot_user_track = BotUser.query.filter_by(
                            bot_id=bot_id,
                            telegram_user_id=telegram_user_id,
                            archived=False
                        ).first()
                        # ✅ Preservar pixel_id transportado sem sobrescrever associação existente
                        if bot_user_track and pixel_id_from_start and not bot_user_track.campaign_code:
                            bot_user_track.campaign_code = pixel_id_from_start
                            db.session.commit()
                            logger.info(f"✅ Pixel do funil associado ao BotUser {bot_user_track.id} via start_param (campanha não sobrescrita)")
                        if bot_user_track:
                            import json as _json
                            tracking_key = f"tracking:{start_param}"
                            redis_conn = get_redis_connection()
                            raw_payload = redis_conn.get(tracking_key) if redis_conn else None
                            if raw_payload:
                                payload = _json.loads(raw_payload)
                                bot_user_track.fbclid = payload.get('fbclid') or bot_user_track.fbclid
                                bot_user_track.fbp = payload.get('fbp') or bot_user_track.fbp
                                bot_user_track.fbc = payload.get('fbc') or bot_user_track.fbc
                                bot_user_track.last_fbclid = payload.get('fbclid') or bot_user_track.last_fbclid
                                bot_user_track.last_fbp = payload.get('fbp') or bot_user_track.last_fbp
                                bot_user_track.last_fbc = payload.get('fbc') or bot_user_track.last_fbc
                                bot_user_track.user_agent = payload.get('client_user_agent') or bot_user_track.user_agent
                                bot_user_track.ip_address = payload.get('client_ip') or bot_user_track.ip_address
                                bot_user_track.utm_source = payload.get('utm_source') or bot_user_track.utm_source
                                bot_user_track.utm_campaign = payload.get('utm_campaign') or bot_user_track.utm_campaign
                                bot_user_track.utm_content = payload.get('utm_content') or bot_user_track.utm_content
                                bot_user_track.utm_medium = payload.get('utm_medium') or bot_user_track.utm_medium
                                bot_user_track.utm_term = payload.get('utm_term') or bot_user_track.utm_term
                                bot_user_track.click_timestamp = datetime.now()
                                db.session.commit()
                                logger.info(f"🔗 TRACKING LINKED: User {bot_user_track.id} -> FBCLID: {bot_user_track.fbclid}")
            except Exception as e:
                logger.warning(f"⚠️ Falha na hidratação inicial de tracking via start_param={start_param}: {e}")
            
            # ============================================================================
            # ✅ PATCH QI 900 - ANTI-REPROCESSAMENTO DE /START
            # ============================================================================
            # PATCH 1: Bloquear múltiplos /start em sequência (intervalo de 5s)
            try:
                import redis
                import time as _time
                redis_conn = get_redis_connection()
                last_start_key = f"gb:{self.user_id}:last_start:{chat_id}"
                last_start = redis_conn.get(last_start_key)
                now = int(_time.time())
                
                if last_start and now - int(last_start) < 5:
                    logger.info(f"⛔ Bloqueado /start duplicado em menos de 5s: chat_id={chat_id}")
                    return  # Sair sem processar
                
                # Registrar timestamp do /start atual (expira em 5s)
                redis_conn.set(last_start_key, now, ex=5)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar anti-duplicação de /start: {e} - continuando processamento")
            
            # PATCH 2: Se já enviou welcome, nunca mais envia
            try:
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import BotUser
                with current_app.app_context():
                    bot_user = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id,
                        archived=False
                    ).first()
                    
                    if bot_user and bot_user.welcome_sent:
                        logger.info(f"🔁 Flag welcome_sent resetada para permitir novo /start: chat_id={chat_id}")
                        bot_user.welcome_sent = False
                        bot_user.welcome_sent_at = None
                        db.session.commit()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar/resetar welcome_sent: {e} - continuando processamento")
            
            # ============================================================================
            # ✅ QI 500: Lock para evitar /start duplicado (lock adicional de segurança)
            # ============================================================================
            if not self._check_start_lock(chat_id):
                logger.warning(f"⚠️ /start duplicado bloqueado - já está processando")
                return  # Sair sem processar
            
            # ✅ QI 200: FAST RESPONSE MODE - Buscar apenas config mínima (1 query rápida)
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot, BotUser
            
            # Buscar config do banco e fazer reset NO MESMO CONTEXTO (rápido - apenas 1 query)
            with current_app.app_context():
                # ✅ QI 500: RESET ABSOLUTO NO MESMO CONTEXTO (garante commit imediato)
                self._reset_user_funnel(bot_id, chat_id, telegram_user_id, db_session=db.session)
                
                bot = db.session.get(Bot, bot_id)
                if bot and bot.config:
                    config = bot.config.to_dict()
                else:
                    config = config or {}
                
                # ✅ QI 500: VERIFICAR welcome_sent APÓS reset (garantir que foi resetado)
                bot_user_check = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id,
                    archived=False
                ).first()
                
                if bot_user_check and bot_user_check.welcome_sent:
                    # Se ainda está True, forçar reset novamente (proteção extra)
                    logger.warning(f"⚠️ welcome_sent ainda True após reset - forçando reset novamente")
                    bot_user_check.welcome_sent = False
                    bot_user_check.welcome_sent_at = None
                    db.session.commit()
                
                # ✅ ISOLAMENTO: Enfileirar processamento com user_id no payload
                try:
                    from internal_logic.workers import enqueue_with_user
                    from tasks_async import task_queue, process_start_async
                    if task_queue and self.user_id:
                        enqueue_with_user(
                            queue=task_queue,
                            user_id=self.user_id,  # ✅ user_id do BotManager
                            func=process_start_async,
                            bot_id=bot_id,
                            token=token,
                            config=config,
                            chat_id=chat_id,
                            message=message,
                            start_param=start_param
                        )
                    elif task_queue:
                        # Fallback sem user_id (legacy)
                        task_queue.enqueue(
                            process_start_async,
                            bot_id=bot_id,
                            token=token,
                            config=config,
                            chat_id=chat_id,
                            message=message,
                            start_param=start_param
                        )
                except Exception as e:
                    logger.warning(f"Erro ao enfileirar task async: {e}")
            
            # ============================================================================
            # ✅ V8 ULTRA: Verificação centralizada de modo ativo
            # ============================================================================
            is_flow_active = checkActiveFlow(config)
            
            # ✅ CRÍTICO: Default é SEMPRE True para garantir que welcome seja enviado quando flow não está ativo
            should_send_welcome = True  # Default: enviar welcome (CRÍTICO para clientes sem fluxo)
            
            logger.info(f"🔍 Verificação de modo: is_flow_active={is_flow_active}, should_send_welcome={should_send_welcome}")
            
            # ✅ CRÍTICO: Se flow está ativo, NUNCA enviar welcome_message
            if is_flow_active:
                logger.info(f"🎯 FLUXO VISUAL ATIVO - Executando fluxo visual")
                logger.info(f"🚫 BLOQUEANDO welcome_message, main_buttons, redirect_buttons, welcome_audio")
                
                # ✅ CRÍTICO: Definir should_send_welcome = False ANTES de executar
                # Isso garante que mesmo se _execute_flow falhar, welcome não será enviado
                should_send_welcome = False
                
                try:
                    logger.info(f"🚀 Chamando _execute_flow...")
                    logger.info(f"🚀 Config flow_enabled: {config.get('flow_enabled')}")
                    logger.info(f"🚀 Config flow_steps count: {len(config.get('flow_steps', [])) if isinstance(config.get('flow_steps'), list) else 'N/A'}")
                    logger.info(f"🚀 Config flow_start_step_id: {config.get('flow_start_step_id')}")
                    
                    self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
                    logger.info(f"✅ _execute_flow concluído sem exceções")
                    
                    # Marcar welcome_sent após fluxo iniciar
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import BotUser
                    
                    with current_app.app_context():
                        try:
                            bot_user_update = BotUser.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id
                            ).first()
                            if bot_user_update:
                                bot_user_update.welcome_sent = True
                                from internal_logic.core.models import get_brazil_time
                                bot_user_update.welcome_sent_at = get_brazil_time()
                                db.session.commit()
                                logger.info(f"✅ Fluxo iniciado - welcome_sent=True")
                        except Exception as e:
                            logger.error(f"Erro ao marcar welcome_sent: {e}")
                    
                    logger.info(f"✅ Fluxo visual executado com sucesso - should_send_welcome=False (confirmado)")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao executar fluxo: {e}", exc_info=True)
                    # ✅ CRÍTICO: Mesmo com erro, NÃO enviar welcome_message
                    # O fluxo visual está ativo, então não deve usar sistema tradicional
                    should_send_welcome = False
                    logger.warning(f"⚠️ Fluxo falhou mas welcome_message está BLOQUEADO (flow_enabled=True)")
                    logger.warning(f"⚠️ Usuário não receberá welcome_message nem mensagem do fluxo")
            else:
                # ✅ Fluxo não está ativo - usar welcome_message normalmente
                logger.info(f"📝 Fluxo visual desabilitado ou vazio - usando welcome_message normalmente")
                should_send_welcome = True
                logger.info(f"✅ should_send_welcome confirmado como True (fluxo não ativo)")
            
            # ============================================================================
            # ✅ QI 200: ENVIAR MENSAGEM IMEDIATAMENTE (<50ms)
            # Processamento pesado foi enfileirado para background
            # ============================================================================
            logger.info(f"🔍 DECISÃO FINAL: should_send_welcome={should_send_welcome} (is_flow_active={is_flow_active})")
            logger.info(f"🔍 Condição para enviar welcome: should_send_welcome={should_send_welcome}")
            
            if should_send_welcome:
                logger.info(f"✅ ENVIANDO welcome_message - fluxo visual NÃO está ativo ou está vazio")
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
                        price = float(btn.get('price', 0))
                        button_text = self._format_button_text(btn['text'], price, btn.get('price_position'))
                        buttons.append({
                            'text': button_text,
                            'callback_data': f"buy_{index}"  # ✅ CORREÇÃO: Usar apenas o índice (max 10 bytes)
                        })
                
                # Adicionar botões de redirecionamento (com URL)
                for btn in redirect_buttons:
                    if btn.get('text') and btn.get('url'):
                        buttons.append({
                            'text': btn['text'],
                            'url': btn['url']  # Botão com URL abre direto no navegador
                        })
                
                # ✅ QI 500: Enviar tudo SEQUENCIALMENTE (garante ordem)
                # Verificar se URL de mídia é válida (não pode ser canal privado)
                valid_media = False
                if welcome_media_url:
                    # URLs de canais privados começam com /c/ - não funcionam
                    if '/c/' not in welcome_media_url and welcome_media_url.startswith('http'):
                        valid_media = True
                    else:
                        logger.info(f"⚠️ Mídia de canal privado detectada - enviando só texto")
                
                # ✅ QI 500: Usar função sequencial para garantir ordem
                # Texto sempre enviado (como caption se houver mídia, ou mensagem separada)
                result = self.send_funnel_step_sequential(
                    token=token,
                    chat_id=str(chat_id),
                    text=welcome_message,  # Sempre enviar texto (será caption se houver mídia)
                    media_url=welcome_media_url if valid_media else None,
                    media_type=welcome_media_type if valid_media else None,
                    buttons=buttons,
                    delay_between=0.2  # ✅ QI 500: Delay de 0.2s entre envios
                )
                
                if result:
                    logger.info(f"✅ Mensagem /start enviada com {len(buttons)} botão(ões)")
                    
                    # ✅ MARCAR COMO ENVIADO NO BANCO
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import BotUser
                    
                    with current_app.app_context():
                        try:
                            bot_user_update = BotUser.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id
                            ).first()
                            if bot_user_update:
                                bot_user_update.welcome_sent = True
                                from internal_logic.core.models import get_brazil_time
                                bot_user_update.welcome_sent_at = get_brazil_time()
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
                # ✅ Fluxo visual está ativo - welcome_message está bloqueado
                logger.info(f"✅ should_send_welcome=False - welcome_message BLOQUEADO (fluxo visual ativo)")
                logger.info(f"✅ Apenas o fluxo visual será executado, sem welcome_message tradicional")
            
            # ✅ CORREÇÃO: Emitir evento via WebSocket apenas para o dono do bot
            try:
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot
                with current_app.app_context():
                    bot = db.session.get(Bot, bot_id)
                    if bot:
                        # 🔥 CRÍTICO: Blindagem UI - WebSocket nunca deve abortar transação
                        try:
                            if self.socketio:
                                self.socketio.emit('bot_interaction', {
                                    'bot_id': bot_id,
                                    'type': 'start',
                                    'chat_id': chat_id,
                                    'user': message.get('from', {}).get('first_name', 'Usuário')
                                }, room=f'user_{bot.user_id}')
                        except Exception as ws_error:
                            logger.debug(f"Falha não-crítica na UI (WebSocket ignorado): {ws_error}")
                            pass  # Processamento continua mesmo se UI falhar
            except Exception as db_error:
                logger.warning(f"⚠️ Erro ao buscar bot para WebSocket (não crítico): {db_error}")
            
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
            
            # ✅ V∞: Callback de Botão Customizado do Flow (formato: flow_{stepId}_{index})
            if callback_data.startswith('flow_') and not callback_data.startswith('flow_step_'):
                try:
                    # Parse: flow_{stepId}_{index}
                    parts = callback_data.split('_', 2)  # ['flow', '{stepId}', '{index}']
                    if len(parts) == 3:
                        step_id = parts[1]
                        btn_index = int(parts[2])
                        
                        # Responder callback
                        requests.post(url, json={
                            'callback_query_id': callback_id,
                            'text': '⏳ Processando...'
                        }, timeout=3)
                        
                        telegram_user_id = str(user_info.get('id', ''))
                        
                        # Buscar config e steps
                        import json
                        flow_steps_raw = config.get('flow_steps', [])
                        if isinstance(flow_steps_raw, str):
                            flow_steps = json.loads(flow_steps_raw)
                        else:
                            flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []
                        
                        # Encontrar step
                        step = self._find_step_by_id(flow_steps, step_id)
                        if not step:
                            logger.warning(f"⚠️ Step {step_id} não encontrado no fluxo")
                            return
                        
                        custom_buttons = step.get('config', {}).get('custom_buttons', [])
                        if btn_index >= len(custom_buttons):
                            logger.warning(f"⚠️ Índice de botão inválido: {btn_index} (total: {len(custom_buttons)})")
                            return
                        
                        target_step = custom_buttons[btn_index].get('target_step')
                        if not target_step:
                            logger.warning(f"⚠️ Botão {btn_index} não tem target_step definido")
                            return
                        
                        logger.info(f"✅ [FLOW V∞] Callback customizado: step={step_id}, button={btn_index}, target={target_step}")
                        
                        # Limpar step atual do Redis
                        try:
                            redis_conn = get_redis_connection()
                            if redis_conn:
                                current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                                redis_conn.delete(current_step_key)
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao limpar step atual do Redis: {e}")
                        
                        # Buscar snapshot do Redis
                        flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                        
                        # Executar step destino
                        self._execute_flow_recursive(
                            bot_id, token, config,
                            chat_id, telegram_user_id,
                            target_step,
                            recursion_depth=0,
                            visited_steps=set(),
                            flow_snapshot=flow_snapshot
                        )
                        return
                        
                except ValueError as e:
                    logger.error(f"❌ [FLOW V∞] Erro ao parsear callback flow_: {e}")
                except Exception as e:
                    logger.error(f"❌ [FLOW V∞] Erro callback flow_: {e}", exc_info=True)
                return
            
            # ✅ NOVO: Botão contextual do fluxo (formato: flow_step_{step_id}_{action}) - COMPATIBILIDADE
            if callback_data.startswith('flow_step_'):
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '⏳ Processando...'
                }, timeout=3)
                
                # Extrair step_id e action do callback_data
                # Formato: flow_step_{step_id}_btn_{idx}
                # ✅ CORREÇÃO: step_id pode conter underscores, então usar rsplit para pegar action corretamente
                callback_without_prefix = callback_data.replace('flow_step_', '')
                
                # Buscar pelo padrão _btn_ para dividir corretamente (action sempre é btn_{idx})
                if '_btn_' in callback_without_prefix:
                    # Dividir no último _btn_ para pegar step_id completo
                    parts = callback_without_prefix.rsplit('_btn_', 1)
                    source_step_id = parts[0]
                    action = 'btn_' + parts[1] if len(parts) > 1 else ''
                else:
                    # Fallback: usar split tradicional (compatibilidade com formato antigo)
                    parts = callback_without_prefix.split('_', 1)
                    source_step_id = parts[0]
                    action = parts[1] if len(parts) > 1 else ''
                
                logger.info(f"🔘 Botão contextual clicado: step={source_step_id}, action={action}")
                
                # Buscar step no fluxo
                flow_steps = config.get('flow_steps', [])
                source_step = self._find_step_by_id(flow_steps, source_step_id)
                
                if source_step:
                    telegram_user_id = str(user_info.get('id', ''))
                    
                    # ✅ QI 500: Avaliar condições de button_click ANTES de usar target_step do botão
                    conditions = source_step.get('conditions', [])
                    if conditions and len(conditions) > 0:
                        try:
                            redis_conn = get_redis_connection()
                            current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                            
                            # Avaliar condições com parâmetros completos
                            next_step_id = self._evaluate_conditions(
                                source_step,
                                user_input=callback_data,
                                context={},
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id,
                                step_id=source_step_id
                            )
                            
                            if next_step_id:
                                logger.info(f"✅ Condição de button_click matchou! Continuando para step: {next_step_id}")
                                # Limpar step atual do Redis
                                redis_conn.delete(current_step_key)
                                # Continuar fluxo no step da condição (sobrescreve target_step do botão)
                                self._execute_flow_recursive(bot_id, token, config, chat_id, telegram_user_id, next_step_id)
                                return
                            else:
                                logger.info(f"⚠️ Nenhuma condição de button_click matchou para callback: {callback_data}")
                                # Fallback: usar target_step do botão (comportamento antigo)
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao avaliar condições de button_click: {e} - usando target_step do botão")
                    
                    # ✅ Fallback: Buscar botão correspondente no step (comportamento antigo)
                    step_config = source_step.get('config', {})
                    custom_buttons = step_config.get('custom_buttons', [])
                    
                    # Extrair índice do botão do action (formato: btn_{idx})
                    btn_idx = None
                    if action.startswith('btn_'):
                        try:
                            btn_idx = int(action.replace('btn_', ''))
                        except:
                            pass
                    
                    if btn_idx is not None and btn_idx < len(custom_buttons):
                        target_step_id = custom_buttons[btn_idx].get('target_step')
                        if target_step_id:
                            logger.info(f"✅ Continuando fluxo para step: {target_step_id} (target_step do botão)")
                            # ✅ NOVO: Limpar step atual atomicamente
                            try:
                                redis_conn = get_redis_connection()
                                if redis_conn:
                                    current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                                    redis_conn.delete(current_step_key)
                            except:
                                pass
                            # ✅ NOVO: Buscar snapshot do Redis
                            flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                            
                            # Continuar fluxo no step de destino
                            self._execute_flow_recursive(
                                bot_id, token, config, chat_id, telegram_user_id, target_step_id,
                                recursion_depth=0, visited_steps=set(), flow_snapshot=flow_snapshot
                            )
                            return
                        else:
                            logger.warning(f"⚠️ Botão contextual sem target_step definido")
                    else:
                        logger.warning(f"⚠️ Índice de botão inválido: {btn_idx}")
                else:
                    logger.warning(f"⚠️ Step não encontrado: {source_step_id}")
                
                return
            
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
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import RemarketingCampaign
                
                with current_app.app_context():
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
                    customer_user_id=str(user_info.get('id', '')),
                    is_remarketing=True,  # ✅ CORREÇÃO CRÍTICA: Marcar como remarketing
                    remarketing_campaign_id=campaign_id  # ✅ Salvar ID da campanha
                )
                # ✅ UX FIX: Tratamento Amigável de Rate Limit
                if pix_data and pix_data.get('rate_limit'):
                    wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                    self.send_telegram_message(
                        chat_id=chat_id,
                        message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                        token=token
                    )
                    return
                
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
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import RemarketingCampaign
                    with current_app.app_context():
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
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Bot as BotModel
                    
                    with current_app.app_context():
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
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Bot as BotModel
                    
                    with current_app.app_context():
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
                # ✅ REDIS MIGRATION: Formato: multi_bump_yes_CHAT_ID_BUMP_INDEX_TOTAL_PRICE_CENTAVOS
                parts = callback_data.replace('multi_bump_yes_', '').split('_')
                chat_id_from_callback = int(parts[0])
                user_key = f"orderbump_{chat_id_from_callback}"
                bump_index = int(parts[1])
                total_price = float(parts[2]) / 100  # Converter centavos para reais
                
                logger.info(f"🎁 Order Bump {bump_index + 1} ACEITO | User: {user_key} | Valor Total: R$ {total_price:.2f}")
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '✅ Bônus adicionado!'
                }, timeout=3)
                
                # ✅ REDIS MIGRATION: Buscar sessão do Redis
                redis_conn = get_redis_connection()
                session_key = f"gb:ob_session:{user_key}"
                pix_cache_key = f"gb:pix_cache:{user_key}"
                
                session_json = redis_conn.get(session_key)
                if session_json:
                    session = json.loads(session_json)
                    
                    # ✅ VALIDAÇÃO: Verificar se chat_id do callback corresponde ao chat_id da sessão
                    session_chat_id = session.get('chat_id')
                    if session_chat_id and session_chat_id != chat_id_from_callback:
                        logger.error(f"❌ Chat ID mismatch: callback de chat {chat_id_from_callback}, mas sessão é do chat {session_chat_id}!")
                        return
                    
                    session_bot_id = session.get('bot_id', bot_id)
                    
                    # ✅ VALIDAÇÃO: Verificar se bot_id do callback corresponde ao bot_id da sessão
                    if session_bot_id != bot_id:
                        logger.warning(f"⚠️ Bot ID mismatch: callback de bot {bot_id}, mas sessão é do bot {session_bot_id}. Usando bot_id da sessão.")
                        session_bot_data = self.bot_state.get_bot_data(session_bot_id)
                        if session_bot_data:
                            token = session_bot_data['token']
                            bot_id = session_bot_id
                        else:
                            logger.error(f"❌ Bot {session_bot_id} da sessão não está mais ativo no Redis!")
                            return
                    
                    # ✅ CORREÇÃO: Usar chat_id da sessão (mais confiável)
                    chat_id = session.get('chat_id', chat_id)
                    
                    current_bump = session['order_bumps'][bump_index]
                    bump_price = float(current_bump.get('price', 0))
                    
                    # Adicionar bump aceito
                    session['accepted_bumps'].append(current_bump)
                    session['total_bump_value'] += bump_price
                    session['current_index'] = bump_index + 1
                    
                    logger.info(f"🎁 Bump aceito: {current_bump.get('description', 'Bônus')} (+R$ {bump_price:.2f})")
                    
                    # ✅ REDIS MIGRATION: Salvar sessão atualizada no Redis (TTL 10 min renovado)
                    redis_conn.setex(session_key, 600, json.dumps(session))
                    
                    # Exibir próximo order bump ou finalizar (usar bot_id correto)
                    self._show_next_order_bump(bot_id, token, chat_id, user_key)
                else:
                    # ✅ REDIS MIGRATION: Verificar cache de PIX no Redis antes de mostrar erro
                    pix_cache_json = redis_conn.get(pix_cache_key)
                    if pix_cache_json:
                        cached = json.loads(pix_cache_json)
                        logger.info(f"🔄 Callback 'SIM' - Reenviando PIX do cache Redis: {cached['pix_data'].get('payment_id')}")
                        self._send_pix_message(token, chat_id, cached['pix_data'], "🔄 Reenviando seu PIX:")
                        return  # ✅ Sucesso - não é erro
                    
                    # ✅ PROTEÇÃO: Sessão já foi finalizada (usuário clicou em botão antigo)
                    logger.warning(f"⚠️ Sessão de order bump não encontrada no Redis (já finalizada): {user_key} | Callback já processado")
            
            # ✅ NOVO: Múltiplos Order Bumps - Recusar
            elif callback_data.startswith('multi_bump_no_'):
                # ✅ REDIS MIGRATION: Formato: multi_bump_no_CHAT_ID_BUMP_INDEX_CURRENT_PRICE_CENTAVOS
                parts = callback_data.replace('multi_bump_no_', '').split('_')
                chat_id_from_callback = int(parts[0])
                user_key = f"orderbump_{chat_id_from_callback}"
                bump_index = int(parts[1])
                current_price = float(parts[2]) / 100  # Converter centavos para reais
                
                logger.info(f"🎁 Order Bump {bump_index + 1} RECUSADO | User: {user_key} | Valor Atual: R$ {current_price:.2f}")
                
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '❌ Bônus recusado'
                }, timeout=3)
                
                # ✅ REDIS MIGRATION: Buscar sessão do Redis
                redis_conn = get_redis_connection()
                session_key = f"gb:ob_session:{user_key}"
                pix_cache_key = f"gb:pix_cache:{user_key}"
                
                session_json = redis_conn.get(session_key)
                if session_json:
                    session = json.loads(session_json)
                    
                    # ✅ VALIDAÇÃO: Verificar se chat_id do callback corresponde ao chat_id da sessão
                    session_chat_id = session.get('chat_id')
                    if session_chat_id and session_chat_id != chat_id_from_callback:
                        logger.error(f"❌ Chat ID mismatch: callback de chat {chat_id_from_callback}, mas sessão é do chat {session_chat_id}!")
                        return
                    
                    session_bot_id = session.get('bot_id', bot_id)
                    
                    # ✅ VALIDAÇÃO: Verificar se bot_id do callback corresponde ao bot_id da sessão
                    if session_bot_id != bot_id:
                        logger.warning(f"⚠️ Bot ID mismatch: callback de bot {bot_id}, mas sessão é do bot {session_bot_id}. Usando bot_id da sessão.")
                        session_bot_data = self.bot_state.get_bot_data(session_bot_id)
                        if session_bot_data:
                            token = session_bot_data['token']
                            bot_id = session_bot_id
                        else:
                            logger.error(f"❌ Bot {session_bot_id} da sessão não está mais ativo no Redis!")
                            return
                    
                    # ✅ CORREÇÃO: Usar chat_id da sessão (mais confiável)
                    chat_id = session.get('chat_id', chat_id)
                    
                    session['current_index'] = bump_index + 1
                    
                    logger.info(f"🎁 Bump recusado: {session['order_bumps'][bump_index].get('description', 'Bônus')}")
                    
                    # ✅ REDIS MIGRATION: Salvar sessão atualizada no Redis (TTL 10 min renovado)
                    redis_conn.setex(session_key, 600, json.dumps(session))
                    
                    # Exibir próximo order bump ou finalizar (usar bot_id correto)
                    self._show_next_order_bump(bot_id, token, chat_id, user_key)
                else:
                    # ✅ REDIS MIGRATION: Verificar cache de PIX no Redis antes de mostrar erro
                    pix_cache_json = redis_conn.get(pix_cache_key)
                    if pix_cache_json:
                        cached = json.loads(pix_cache_json)
                        logger.info(f"🔄 Callback 'NÃO' - Reenviando PIX do cache Redis: {cached['pix_data'].get('payment_id')}")
                        self._send_pix_message(token, chat_id_from_callback, cached['pix_data'], "🔄 Reenviando seu PIX:")
                        return  # ✅ Sucesso - não é erro
                    
                    # ✅ PROTEÇÃO: Sessão já foi finalizada (usuário clicou em botão antigo)
                    logger.warning(f"⚠️ Sessão de order bump não encontrada no Redis (já finalizada): {user_key} | Callback já processado")
            
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
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                product_name = f'Produto {button_idx + 1}'  # Default
                description = f"Downsell {downsell_idx + 1} - {product_name}"
                
                with current_app.app_context():
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
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Bot as BotModel
                    
                    with current_app.app_context():
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
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                # Default seguro (sem índice de downsell)
                description = "Oferta Especial"
                
                with current_app.app_context():
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
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                order_bump = None
                with current_app.app_context():
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
            
            elif callback_data.startswith('upsell_'):
                # ✅ UPSELL: Formato idêntico ao downsell: upsell_INDEX_PRICE_CENTAVOS_BUTTON_INDEX
                parts = callback_data.replace('upsell_', '').split('_')
                logger.info(f"🔍 DEBUG upsell callback_data: {callback_data}")
                logger.info(f"🔍 DEBUG upsell parts: {parts}")
                
                upsell_idx = int(parts[0])
                
                # ✅ CORREÇÃO: Detectar formato antigo vs novo (similar ao downsell)
                if len(parts) == 4:
                    # Formato antigo: upsell_INDEX_BUTTON_PRICE_BUTTON
                    original_button_idx = int(parts[1])
                    price_cents = int(parts[2])
                    logger.info(f"🔍 Formato ANTIGO detectado: idx={upsell_idx}, btn={original_button_idx}, price_cents={price_cents}")
                elif len(parts) == 3:
                    # Formato novo: upsell_INDEX_PRICE_BUTTON
                    price_cents = int(parts[1])
                    original_button_idx = int(parts[2])
                    logger.info(f"🔍 Formato NOVO detectado: idx={upsell_idx}, price_cents={price_cents}, btn={original_button_idx}")
                else:
                    logger.error(f"❌ Formato de callback_data inválido: {callback_data}")
                    return
                
                price = float(price_cents) / 100  # Converter centavos para reais
                
                logger.info(f"🔍 DEBUG upsell parsed: idx={upsell_idx}, price_cents={price_cents}, price={price:.2f}, original_button={original_button_idx}")
                
                # ✅ VALIDAÇÃO: Preço deve ser > 0
                if price <= 0:
                    logger.error(f"❌ Upsell com preço inválido: R$ {price:.2f} (centavos: {price_cents})")
                    logger.error(f"❌ CALLBACK_DATA PROBLEMÁTICO: {callback_data}")
                    logger.error(f"❌ PARTS PROBLEMÁTICAS: {parts}")
                    return
                
                # ✅ CORREÇÃO CRÍTICA: Se preço for muito baixo, calcular valor real do upsell
                if price < 1.00:  # Menos de R$ 1,00
                    logger.warning(f"⚠️ Upsell com preço muito baixo (R$ {price:.2f}), calculando valor real")
                    
                    # ✅ CORREÇÃO: Buscar configuração do upsell para calcular valor real
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Bot as BotModel
                    
                    with current_app.app_context():
                        bot = db.session.get(BotModel, bot_id)
                        if bot and bot.config:
                            config = bot.config.to_dict()
                            upsells = config.get('upsells', [])
                            
                            if upsell_idx < len(upsells):
                                upsell_config = upsells[upsell_idx]
                                discount_percentage = float(upsell_config.get('discount_percentage', 50))
                                
                                # ✅ CORREÇÃO: Usar preço original do botão clicado
                                main_buttons = config.get('main_buttons', [])
                                if original_button_idx < len(main_buttons):
                                    original_button = main_buttons[original_button_idx]
                                    original_price = float(original_button.get('price', 0))
                                    
                                    if original_price > 0:
                                        price = original_price * (1 - discount_percentage / 100)
                                        logger.info(f"✅ Valor real calculado: R$ {original_price:.2f} com {discount_percentage}% OFF = R$ {price:.2f}")
                                    else:
                                        price = 97.00  # Fallback para upsell
                                        logger.warning(f"⚠️ Preço original não encontrado, usando fallback R$ {price:.2f}")
                                else:
                                    price = 97.00  # Fallback para upsell
                                    logger.warning(f"⚠️ Botão original não encontrado, usando fallback R$ {price:.2f}")
                            else:
                                price = 97.00  # Fallback para upsell
                                logger.warning(f"⚠️ Configuração de upsell não encontrada, usando fallback R$ {price:.2f}")
                        else:
                            price = 97.00  # Fallback para upsell
                            logger.warning(f"⚠️ Configuração do bot não encontrada, usando fallback R$ {price:.2f}")
                
                # ✅ QI 500 FIX V2: Buscar descrição do BOTÃO ORIGINAL que gerou o upsell
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                # Default seguro (sem índice de upsell)
                description = "Oferta Especial"
                
                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        fresh_config = bot.config.to_dict()
                        main_buttons = fresh_config.get('main_buttons', [])
                        
                        # Buscar o botão ORIGINAL (não o índice do upsell)
                        if original_button_idx >= 0 and original_button_idx < len(main_buttons):
                            button_data = main_buttons[original_button_idx]
                            product_name = button_data.get('description') or button_data.get('text') or f'Produto {original_button_idx + 1}'
                            description = f"{product_name} (Upsell)"
                            logger.info(f"✅ Descrição do produto original encontrada: {product_name}")
                        else:
                            # Fallback: Se não encontrar o botão, usar genérico
                            description = "Oferta Especial (Upsell)"
                            logger.warning(f"⚠️ Botão original {original_button_idx} não encontrado em {len(main_buttons)} botões")
                
                button_index = -1  # Sinalizar que é upsell
                
                logger.info(f"💙 UPSELL CLICADO | Upsell: {upsell_idx} | Botão Original: {original_button_idx} | Produto: {description} | Valor: R$ {price:.2f}")
                
                # ✅ VERIFICAR SE TEM ORDER BUMP PARA ESTE UPSELL
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                order_bump = None
                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                        upsells = config.get('upsells', [])
                        
                        if upsell_idx < len(upsells):
                            upsell_config = upsells[upsell_idx]
                            order_bump = upsell_config.get('order_bump', {})
                
                if order_bump and order_bump.get('enabled'):
                    # Responder callback - AGUARDANDO order bump
                    requests.post(url, json={
                        'callback_query_id': callback_id,
                        'text': '🎁 Oferta especial para você!'
                    }, timeout=3)
                    
                    logger.info(f"🎁 Order Bump detectado para upsell {upsell_idx + 1}!")
                    # ✅ TODO: Criar função _show_upsell_order_bump similar ao _show_downsell_order_bump
                    # Por ora, processar sem order bump
                    logger.warning(f"⚠️ Order bump para upsell ainda não implementado, processando direto")
                
                # SEM ORDER BUMP - Gerar PIX direto
                # Responder callback
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
                
                # Gerar PIX do upsell
                pix_data = self._generate_pix_payment(
                    bot_id=bot_id,
                    amount=price,
                    description=description,
                    customer_name=user_info.get('first_name', ''),
                    customer_username=user_info.get('username', ''),
                    customer_user_id=str(user_info.get('id', '')),
                    is_upsell=True,  # ✅ Marcar como upsell
                    upsell_index=upsell_idx  # ✅ Passar índice do upsell
                )
                # ✅ UX FIX: Tratamento Amigável de Rate Limit
                if pix_data and pix_data.get('rate_limit'):
                    wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                    self.send_telegram_message(
                        chat_id=chat_id,
                        message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                        token=token
                    )
                    return
                
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
                    
                    logger.info(f"✅ PIX UPSELL ENVIADO! ID: {pix_data.get('payment_id')}")
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
                    # ✅ REDIS MIGRATION: Permitir que usuário escolha dentro do funil
                    # Se já existe sessão ativa no Redis, CANCELAR automaticamente e iniciar nova
                    user_key = f"orderbump_{chat_id}"
                    session_key = f"gb:ob_session:{user_key}"
                    
                    redis_conn = get_redis_connection()
                    existing_session_json = redis_conn.get(session_key)
                    
                    if existing_session_json:
                        existing_session = json.loads(existing_session_json)
                        existing_button_index = existing_session.get('button_index')
                        existing_description = existing_session.get('original_description', 'Produto')
                        
                        # ✅ SOLUÇÃO: Cancelar sessão anterior automaticamente
                        logger.info(f"🔄 Nova intenção de compra detectada! Cancelando sessão anterior (botão {existing_button_index}) e iniciando nova (botão {button_index})")
                        
                        # Remover sessão anterior do Redis
                        redis_conn.delete(session_key)
                        # Também limpar cache de PIX associado
                        pix_cache_key = f"gb:pix_cache:{user_key}"
                        redis_conn.delete(pix_cache_key)
                        
                        logger.info(f"✅ Sessão anterior cancelada automaticamente. Nova oferta iniciada para botão {button_index}")
                    
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
                    customer_user_id=str(user_info.get('id', '')),
                    button_index=button_index,  # ✅ SISTEMA DE ASSINATURAS
                    button_config=button_data   # ✅ SISTEMA DE ASSINATURAS
                )
                # ✅ UX FIX: Tratamento Amigável de Rate Limit
                if pix_data and pix_data.get('rate_limit'):
                    wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                    self.send_telegram_message(
                        chat_id=chat_id,
                        message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                        token=token
                    )
                    return
                
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
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Bot as BotModel
                    
                    with current_app.app_context():
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
            from internal_logic.core.models import Payment, Bot, Gateway
            from internal_logic.core.extensions import db
            from flask import current_app
            
            with current_app.app_context():
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
                    elif payment.gateway_type == 'umbrellapag':
                        # ✅ CORREÇÃO CRÍTICA UMBRELLAPAY: Verificação dupla com intervalo
                        logger.info(f"🔍 [VERIFY UMBRELLAPAY] Iniciando verificação dupla para payment_id={payment.payment_id}")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                        logger.info(f"   Status atual: {payment.status}")
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Verificar se gateway_transaction_id existe
                        if not payment.gateway_transaction_id or not payment.gateway_transaction_id.strip():
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] gateway_transaction_id não encontrado para payment_id={payment.payment_id}")
                            return
                        
                        # ✅ ETAPA 1: Verificar se existe webhook recente (<2 minutos)
                        from internal_logic.core.models import WebhookEvent, get_brazil_time
                        from datetime import timedelta
                        import time
                        
                        dois_minutos_atras = get_brazil_time() - timedelta(minutes=2)
                        try:
                            webhook_recente = WebhookEvent.query.filter(
                                WebhookEvent.gateway_type == 'umbrellapag',
                                WebhookEvent.transaction_id == payment.gateway_transaction_id,
                                WebhookEvent.received_at >= dois_minutos_atras
                            ).order_by(WebhookEvent.received_at.desc()).first()
                        except Exception as e:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao buscar webhook recente: {e}", exc_info=True)
                            webhook_recente = None
                        
                        if webhook_recente:
                            logger.info(f"⏳ [VERIFY UMBRELLAPAY] Webhook recente encontrado (recebido em {webhook_recente.received_at})")
                            logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.info(f"   Status do webhook: {webhook_recente.status}")
                            logger.info(f"   Aguardando processamento do webhook... Não atualizando manualmente")
                            
                            # Recarregar payment para ver se webhook já atualizou
                            try:
                                db.session.refresh(payment)
                                if payment.status == 'paid':
                                    logger.info(f"✅ [VERIFY UMBRELLAPAY] Webhook já atualizou o pagamento! Status: {payment.status}")
                                else:
                                    logger.info(f"⏳ [VERIFY UMBRELLAPAY] Webhook ainda não processou. Aguarde até 2 minutos.")
                            except Exception as e:
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao recarregar payment: {e}", exc_info=True)
                            return  # Não fazer consulta manual se webhook recente existe
                        
                        # ✅ ETAPA 2: Verificação dupla com intervalo (3 segundos)
                        try:
                            bot = payment.bot
                            if not bot:
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Bot não encontrado para payment_id={payment.payment_id}")
                                return
                            
                            gateway = Gateway.query.filter_by(
                                user_id=bot.user_id,
                                gateway_type=payment.gateway_type,
                                is_verified=True
                            ).first()
                            
                            if not gateway:
                                logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Gateway não encontrado para gateway_type={payment.gateway_type}, user_id={bot.user_id}")
                                return
                            
                            # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
                            user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
                            
                            credentials = {
                                'api_key': gateway.api_key,
                                'product_hash': gateway.product_hash
                            }
                            
                            payment_gateway = GatewayFactory.create_gateway(
                                gateway_type=payment.gateway_type,
                                credentials=credentials
                            )
                            
                            if not payment_gateway:
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Não foi possível criar instância do gateway")
                                return
                            
                            # ✅ CONSULTA 1 com retry e tratamento de erro
                            logger.info(f"🔍 [VERIFY UMBRELLAPAY] Consulta 1/2: Verificando status na API...")
                            logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                            
                            try:
                                api_status_1 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                                status_1 = api_status_1.get('status') if api_status_1 else None
                                logger.info(f"📊 [VERIFY UMBRELLAPAY] Consulta 1 retornou: status={status_1}")
                            except Exception as e:
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro na consulta 1: {e}", exc_info=True)
                                logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                                return
                            
                            # ✅ VALIDAÇÃO: Não atualizar se payment já está paid
                            try:
                                db.session.refresh(payment)
                                if not payment:  # Payment pode ter sido deletado
                                    logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Payment não encontrado após refresh")
                                    return
                                
                                if payment.status == 'paid':
                                    logger.info(f"✅ [VERIFY UMBRELLAPAY] Pagamento já está PAID no sistema. Não atualizar.")
                                    return
                            except Exception as e:
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao recarregar payment: {e}", exc_info=True)
                                return
                            
                            # ✅ Aguardar 3 segundos
                            logger.info(f"⏳ [VERIFY UMBRELLAPAY] Aguardando 3 segundos antes da consulta 2...")
                            time.sleep(3)
                            
                            # ✅ CONSULTA 2 com retry e tratamento de erro
                            logger.info(f"🔍 [VERIFY UMBRELLAPAY] Consulta 2/2: Verificando status na API novamente...")
                            logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                            
                            try:
                                api_status_2 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                                status_2 = api_status_2.get('status') if api_status_2 else None
                                logger.info(f"📊 [VERIFY UMBRELLAPAY] Consulta 2 retornou: status={status_2}")
                            except Exception as e:
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro na consulta 2: {e}", exc_info=True)
                                logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                                return
                            
                            # ✅ VALIDAÇÃO FINAL: Só atualizar se AMBAS as consultas retornarem 'paid'
                            if status_1 == 'paid' and status_2 == 'paid':
                                # ✅ Verificar novamente se payment ainda está pending (evitar race condition)
                                try:
                                    db.session.refresh(payment)
                                    if not payment:  # Payment pode ter sido deletado
                                        logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Payment não encontrado após refresh final")
                                        return
                                    
                                    if payment.status == 'paid':
                                        logger.info(f"✅ [VERIFY UMBRELLAPAY] Pagamento já foi atualizado por outro processo. Não atualizar novamente.")
                                        return
                                except Exception as e:
                                    logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao recarregar payment final: {e}", exc_info=True)
                                    return
                                
                                logger.info(f"✅ [VERIFY UMBRELLAPAY] VERIFICAÇÃO DUPLA CONFIRMADA: Ambas consultas retornaram 'paid'")
                                logger.info(f"   Payment ID: {payment.payment_id}")
                                logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                                logger.info(f"   Atualizando pagamento para 'paid'...")
                                
                                try:
                                    payment.status = 'paid'
                                    payment.paid_at = get_brazil_time()
                                    payment.bot.total_sales += 1
                                    payment.bot.total_revenue += payment.amount
                                    payment.bot.owner.total_sales += 1
                                    payment.bot.owner.total_revenue += payment.amount
                                    
                                    # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                                    # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                                    logger.info(f"✅ [VERIFY UMBRELLAPAY] Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
                                    
                                    # ✅ COMMIT ATÔMICO com rollback em caso de erro
                                    db.session.commit()
                                    logger.info(f"💾 [VERIFY UMBRELLAPAY] Pagamento atualizado via verificação dupla")
                                    
                                    # ✅ CRÍTICO: Recarregar objeto do banco para garantir status atualizado
                                    db.session.refresh(payment)
                                    
                                    # ✅ VALIDAÇÃO PÓS-UPDATE: Verificar se status foi atualizado corretamente
                                    if payment.status == 'paid':
                                        logger.info(f"✅ [VERIFY UMBRELLAPAY] Validação pós-update: Status confirmado como 'paid'")
                                    else:
                                        logger.error(f"🚨 [VERIFY UMBRELLAPAY] ERRO CRÍTICO: Status não foi atualizado corretamente!")
                                        logger.error(f"   Esperado: 'paid', Atual: {payment.status}")
                                        logger.error(f"   Payment ID: {payment.payment_id}")
                                    
                                    # ✅ VERIFICAR CONQUISTAS
                                    try:
                                        from internal_logic.services.achievements import check_and_unlock_achievements
                                        new_achievements = check_and_unlock_achievements(payment.bot.owner)
                                        if new_achievements:
                                            logger.info(f"🏆 [VERIFY UMBRELLAPAY] {len(new_achievements)} conquista(s) desbloqueada(s)!")
                                    except Exception as e:
                                        logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Erro ao verificar conquistas: {e}", exc_info=True)
                                    
                                    # ============================================================================
                                    # ✅ UPSELLS AUTOMÁTICOS - APÓS VERIFICAÇÃO MANUAL
                                    # ✅ CORREÇÃO CRÍTICA QI 500: Processar upsells quando pagamento é confirmado via verificação manual
                                    # ============================================================================
                                    logger.info(f"🔍 [UPSELLS VERIFY] Verificando condições: status='{payment.status}', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")
                                    
                                    if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                        logger.info(f"✅ [UPSELLS VERIFY] Condições atendidas! Processando upsells para payment {payment.payment_id}")
                                        try:
                                            # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                            from internal_logic.core.models import Payment as PaymentModel
                                            payment_check = PaymentModel.query.filter_by(payment_id=payment.payment_id).first()
                                            
                                            # ✅ CORREÇÃO CRÍTICA QI 500: Verificar scheduler ANTES de verificar jobs
                                            if not self.scheduler:
                                                logger.error(f"❌ CRÍTICO: Scheduler não está disponível! Upsells NÃO serão agendados!")
                                                logger.error(f"   Payment ID: {payment.payment_id}")
                                                logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                            else:
                                                # ✅ DIAGNÓSTICO: Verificar se scheduler está rodando
                                                try:
                                                    scheduler_running = self.scheduler.running
                                                    if not scheduler_running:
                                                        logger.error(f"❌ CRÍTICO: Scheduler existe mas NÃO está rodando!")
                                                        logger.error(f"   Payment ID: {payment.payment_id}")
                                                        logger.error(f"   Upsells NÃO serão executados se scheduler não estiver rodando!")
                                                except Exception as scheduler_check_error:
                                                    logger.warning(f"⚠️ Não foi possível verificar se scheduler está rodando: {scheduler_check_error}")
                                                
                                                # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                                upsells_already_scheduled = False
                                                try:
                                                    # Verificar se já existe job de upsell para este payment
                                                    for i in range(10):  # Verificar até 10 upsells possíveis
                                                        job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                        existing_job = self.scheduler.get_job(job_id)
                                                        if existing_job:
                                                            upsells_already_scheduled = True
                                                            logger.info(f"ℹ️ Upsells já foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                            logger.info(f"   Job encontrado: {job_id}, próxima execução: {existing_job.next_run_time}")
                                                            break
                                                except Exception as check_error:
                                                    logger.error(f"❌ ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                                    logger.warning(f"⚠️ Continuando mesmo com erro na verificação (pode causar duplicação)")
                                                    # ✅ Não bloquear se houver erro na verificação - deixar tentar agendar
                                            
                                            if self.scheduler and not upsells_already_scheduled:
                                                upsells = payment.bot.config.get_upsells()
                                                
                                                if upsells:
                                                    logger.info(f"🎯 [UPSELLS VERIFY] Verificando upsells para produto: {payment.product_name}")
                                                    
                                                    # Filtrar upsells que fazem match com o produto comprado
                                                    matched_upsells = []
                                                    for upsell in upsells:
                                                        trigger_product = upsell.get('trigger_product', '')
                                                        
                                                        # Match: trigger vazio (todas compras) OU produto específico
                                                        if not trigger_product or trigger_product == payment.product_name:
                                                            matched_upsells.append(upsell)
                                                    
                                                    if matched_upsells:
                                                        logger.info(f"✅ [UPSELLS VERIFY] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")
                                                        
                                                        # ✅ CORREÇÃO: Usar função específica para upsells (não downsells)
                                                        self.schedule_upsells(
                                                            bot_id=payment.bot_id,
                                                            payment_id=payment.payment_id,
                                                            chat_id=int(payment.customer_user_id),
                                                            upsells=matched_upsells,
                                                            original_price=payment.amount,
                                                            original_button_index=payment.button_index if payment.button_index is not None else -1
                                                        )
                                                        
                                                        logger.info(f"📅 [UPSELLS VERIFY] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                    else:
                                                        logger.info(f"ℹ️ [UPSELLS VERIFY] Nenhum upsell configurado para '{payment.product_name}' (trigger_product não faz match)")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY] Lista de upsells vazia no config do bot")
                                            else:
                                                if not self.scheduler:
                                                    logger.error(f"❌ [UPSELLS VERIFY] Scheduler não disponível - upsells não serão agendados")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY] Upsells já foram agendados anteriormente para payment {payment.payment_id} (evitando duplicação)")
                                                
                                        except Exception as e:
                                            logger.error(f"❌ [UPSELLS VERIFY] Erro ao processar upsells: {e}", exc_info=True)
                                            import traceback
                                            traceback.print_exc()
                                        
                                except Exception as e:
                                    logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao atualizar payment: {e}", exc_info=True)
                                    db.session.rollback()
                                    logger.error(f"   Rollback executado. Payment não foi atualizado.")
                                    return
                            
                            elif status_1 == 'paid' and status_2 != 'paid':
                                logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] DISCREPÂNCIA DETECTADA: Consulta 1=paid, Consulta 2={status_2}")
                                logger.warning(f"   Transaction ID: {payment.gateway_transaction_id}")
                                logger.warning(f"   Não atualizando - inconsistência detectada. Aguardando webhook ou próxima verificação.")
                            
                            elif status_1 != 'paid' and status_2 == 'paid':
                                logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] DISCREPÂNCIA DETECTADA: Consulta 1={status_1}, Consulta 2=paid")
                                logger.warning(f"   Transaction ID: {payment.gateway_transaction_id}")
                                logger.warning(f"   Não atualizando - inconsistência detectada. Aguardando webhook ou próxima verificação.")
                            
                            else:
                                logger.info(f"⏳ [VERIFY UMBRELLAPAY] Ambas consultas retornaram: {status_1} e {status_2} (não é 'paid')")
                                logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                                logger.info(f"   Pagamento ainda pendente no gateway")
                                
                        except Exception as e:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro crítico na verificação: {e}", exc_info=True)
                            logger.error(f"   Payment ID: {payment.payment_id}")
                            logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                            return
                    else:
                        # Outros gateways podem ter consulta manual (comportamento antigo)
                        logger.info(f"🔍 Gateway {payment.gateway_type}: Consultando status na API...")
                        
                        bot = payment.bot
                        gateway = Gateway.query.filter_by(
                            user_id=bot.user_id,
                            gateway_type=payment.gateway_type,
                            is_verified=True
                        ).first()
                        
                        if gateway:
                            # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
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
                                api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                                
                                if api_status and api_status.get('status') == 'paid':
                                    if payment.status == 'pending':
                                        logger.info(f"✅ API confirmou pagamento! Atualizando status...")
                                        payment.status = 'paid'
                                        from internal_logic.core.models import get_brazil_time
                                        payment.paid_at = get_brazil_time()
                                        payment.bot.total_sales += 1
                                        payment.bot.total_revenue += payment.amount
                                        payment.bot.owner.total_sales += 1
                                        payment.bot.owner.total_revenue += payment.amount
                                        
                                        # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                                        # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                                        logger.info(f"✅ Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
                                        
                                        db.session.commit()
                                        logger.info(f"💾 Pagamento atualizado via consulta ativa")
                                        
                                        db.session.refresh(payment)
                                        
                                        try:
                                            from internal_logic.services.achievements import check_and_unlock_achievements
                                            new_achievements = check_and_unlock_achievements(payment.bot.owner)
                                            if new_achievements:
                                                logger.info(f"🏆 {len(new_achievements)} conquista(s) desbloqueada(s)!")
                                        except Exception as e:
                                            logger.warning(f"⚠️ Erro ao verificar conquistas: {e}")
                                        
                                        # ============================================================================
                                        # ✅ UPSELLS AUTOMÁTICOS - APÓS VERIFICAÇÃO MANUAL (OUTROS GATEWAYS)
                                        # ✅ CORREÇÃO CRÍTICA QI 500: Processar upsells quando pagamento é confirmado via verificação manual (outros gateways)
                                        # ============================================================================
                                        logger.info(f"🔍 [UPSELLS VERIFY OTHER] Verificando condições: status='paid', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")
                                        
                                        if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                            logger.info(f"✅ [UPSELLS VERIFY OTHER] Condições atendidas! Processando upsells para payment {payment.payment_id}")
                                            try:
                                                # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                                from internal_logic.core.models import Payment as PaymentModel
                                                payment_check = PaymentModel.query.filter_by(payment_id=payment.payment_id).first()
                                                
                                                # ✅ CORREÇÃO CRÍTICA QI 500: Verificar scheduler ANTES de verificar jobs
                                                if not self.scheduler:
                                                    logger.error(f"❌ CRÍTICO: Scheduler não está disponível! Upsells NÃO serão agendados!")
                                                    logger.error(f"   Payment ID: {payment.payment_id}")
                                                    logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                                else:
                                                    # ✅ DIAGNÓSTICO: Verificar se scheduler está rodando
                                                    try:
                                                        scheduler_running = self.scheduler.running
                                                        if not scheduler_running:
                                                            logger.error(f"❌ CRÍTICO: Scheduler existe mas NÃO está rodando!")
                                                            logger.error(f"   Payment ID: {payment.payment_id}")
                                                            logger.error(f"   Upsells NÃO serão executados se scheduler não estiver rodando!")
                                                    except Exception as scheduler_check_error:
                                                        logger.warning(f"⚠️ Não foi possível verificar se scheduler está rodando: {scheduler_check_error}")
                                                    
                                                    # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                                    upsells_already_scheduled = False
                                                    try:
                                                        # Verificar se já existe job de upsell para este payment
                                                        for i in range(10):  # Verificar até 10 upsells possíveis
                                                            job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                            existing_job = self.scheduler.get_job(job_id)
                                                            if existing_job:
                                                                upsells_already_scheduled = True
                                                                logger.info(f"ℹ️ Upsells já foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                                logger.info(f"   Job encontrado: {job_id}, próxima execução: {existing_job.next_run_time}")
                                                                break
                                                    except Exception as check_error:
                                                        logger.error(f"❌ ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                                        logger.warning(f"⚠️ Continuando mesmo com erro na verificação (pode causar duplicação)")
                                                        # ✅ Não bloquear se houver erro na verificação - deixar tentar agendar
                                                
                                                if self.scheduler and not upsells_already_scheduled:
                                                    upsells = payment.bot.config.get_upsells()
                                                    
                                                    if upsells:
                                                        logger.info(f"🎯 [UPSELLS VERIFY OTHER] Verificando upsells para produto: {payment.product_name}")
                                                        
                                                        # Filtrar upsells que fazem match com o produto comprado
                                                        matched_upsells = []
                                                        for upsell in upsells:
                                                            trigger_product = upsell.get('trigger_product', '')
                                                            
                                                            # Match: trigger vazio (todas compras) OU produto específico
                                                            if not trigger_product or trigger_product == payment.product_name:
                                                                matched_upsells.append(upsell)
                                                        
                                                        if matched_upsells:
                                                            logger.info(f"✅ [UPSELLS VERIFY OTHER] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")
                                                            
                                                            # ✅ CORREÇÃO: Usar função específica para upsells (não downsells)
                                                            self.schedule_upsells(
                                                                bot_id=payment.bot_id,
                                                                payment_id=payment.payment_id,
                                                                chat_id=int(payment.customer_user_id),
                                                                upsells=matched_upsells,
                                                                original_price=payment.amount,
                                                                original_button_index=-1
                                                            )
                                                            
                                                            logger.info(f"📅 [UPSELLS VERIFY OTHER] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                        else:
                                                            logger.info(f"ℹ️ [UPSELLS VERIFY OTHER] Nenhum upsell configurado para '{payment.product_name}' (trigger_product não faz match)")
                                                    else:
                                                        logger.info(f"ℹ️ [UPSELLS VERIFY OTHER] Lista de upsells vazia no config do bot")
                                                else:
                                                    if not self.scheduler:
                                                        logger.error(f"❌ [UPSELLS VERIFY OTHER] Scheduler não disponível - upsells não serão agendados")
                                                    else:
                                                        logger.info(f"ℹ️ [UPSELLS VERIFY OTHER] Upsells já foram agendados anteriormente para payment {payment.payment_id} (evitando duplicação)")
                                                    
                                            except Exception as e:
                                                logger.error(f"❌ [UPSELLS VERIFY OTHER] Erro ao processar upsells: {e}", exc_info=True)
                                                import traceback
                                                traceback.print_exc()
                                        
                                        # ✅ ENVIAR ENTREGÁVEL após confirmar pagamento (outros gateways)
                                        try:
                                            # TODO: Importar send_payment_delivery do local correto
                                            # from internal_logic.services.payment_processor import send_payment_delivery
                                            logger.info(f"📦 [VERIFY OTHER] Enviando entregável via send_payment_delivery para {payment.payment_id}")
                                            
                                            db.session.refresh(payment)
                                            
                                            if payment.status == 'paid':
                                                resultado = send_payment_delivery(payment, self)
                                                if resultado:
                                                    logger.info(f"✅ [VERIFY OTHER] Entregável enviado com sucesso via send_payment_delivery")
                                                else:
                                                    logger.warning(f"⚠️ [VERIFY OTHER] send_payment_delivery retornou False para {payment.payment_id}")
                                        except Exception as e:
                                            logger.error(f"❌ [VERIFY OTHER] Erro ao enviar entregável via send_payment_delivery: {e}", exc_info=True)
                                elif api_status:
                                    logger.info(f"⏳ API retornou status: {api_status.get('status')}")
                
                # ✅ CRÍTICO: Recarregar objeto do banco antes de verificar status final
                db.session.refresh(payment)
                logger.info(f"📊 Status FINAL do pagamento: {payment.status}")
                
                # ✅ CRÍTICO: Validação dupla - verificar status ANTES de qualquer ação
                if payment.status == 'paid':
                    # ✅ CRÍTICO: Refresh novamente para garantir que não há race condition
                    db.session.refresh(payment)
                    
                    # ✅ CRÍTICO: Validação final antes de liberar acesso
                    if payment.status != 'paid':
                        logger.error(
                            f"❌ ERRO GRAVE: Status mudou após refresh! Esperado: 'paid', Atual: {payment.status}"
                        )
                        logger.error(f"   Payment ID: {payment.payment_id}")
                        return
                    
                    # PAGAMENTO CONFIRMADO! Liberar acesso
                    logger.info(f"✅ PAGAMENTO CONFIRMADO! Liberando acesso...")
                    
                    # ============================================================================
                    # ✅ V∞: FLOW ENGINE - INTEGRAÇÃO COMPLETA COM PAGAMENTO
                    # ============================================================================
                    flow_processed = False
                    if payment.flow_step_id:
                        bot_flow = Bot.query.get(bot_id)
                        if bot_flow and bot_flow.config:
                            flow_config = bot_flow.config.to_dict()
                            flow_enabled = flow_config.get('flow_enabled', False)
                            
                            # Parsear flow_steps se necessário
                            import json
                            flow_steps_raw = flow_config.get('flow_steps', [])
                            if isinstance(flow_steps_raw, str):
                                try:
                                    flow_steps = json.loads(flow_steps_raw)
                                except:
                                    flow_steps = []
                            else:
                                flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []
                            
                            if flow_enabled and flow_steps:
                                # Buscar step atual do fluxo
                                current_step = self._find_step_by_id(flow_steps, payment.flow_step_id)
                                
                                if current_step:
                                    connections = current_step.get('connections', {})
                                    telegram_user_id = str(user_info.get('id', ''))
                                    
                                    # ✅ V∞: Determinar próximo step baseado em status
                                    if payment.status == 'paid':
                                        next_step_id = connections.get('next')
                                    else:
                                        next_step_id = connections.get('pending')
                                    
                                    # ✅ V∞: EXECUTAR PRÓXIMO STEP DIRETAMENTE (não assíncrono)
                                    if next_step_id:
                                        logger.info(f"🚀 [FLOW V∞] Payment {payment.status} - executando step: {next_step_id}")
                                        
                                        # Buscar snapshot do Redis
                                        flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                        
                                        try:
                                            # Executar próximo step diretamente
                                            self._execute_flow_recursive(
                                                bot_id, token, flow_config,
                                                chat_id, telegram_user_id,
                                                next_step_id,
                                                recursion_depth=0,
                                                visited_steps=set(),
                                                flow_snapshot=flow_snapshot
                                            )
                                            flow_processed = True
                                            logger.info(f"✅ [FLOW V∞] Próximo step executado: {next_step_id}")
                                            return  # ✅ SAIR - fluxo processado, não executar código tradicional
                                        except Exception as e:
                                            logger.error(f"❌ [FLOW V∞] Erro ao executar próximo step: {e}", exc_info=True)
                                            # Continuar para fallback tradicional
                                else:
                                    logger.error(f"❌ [FLOW V∞] Step {payment.flow_step_id} não encontrado mais na config atual")
                    
                    # ✅ FALLBACK: Se fluxo não processou, usar comportamento tradicional
                    if not flow_processed:
                        # ============================================================================
                        # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado via botão verify
                        # ============================================================================
                        # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                        # ✅ Não disparar Purchase quando pagamento é confirmado (via webhook ou botão verify)
                        logger.info(f"✅ Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
                        
                        # Cancelar downsells agendados
                        self.cancel_downsells(payment.payment_id)
                    
                        # ✅ CRÍTICO: Usar send_payment_delivery para garantir validação consistente
                        try:
                            # TODO: Importar send_payment_delivery do local correto
                            # from internal_logic.services.payment_processor import send_payment_delivery
                            logger.info(f"📦 [VERIFY] Enviando entregável via send_payment_delivery para {payment.payment_id}")
                            
                            # ✅ CRÍTICO: Refresh antes de chamar send_payment_delivery
                            db.session.refresh(payment)
                            
                            # ✅ CRÍTICO: Validar status ANTES de chamar send_payment_delivery
                            if payment.status == 'paid':
                                resultado = send_payment_delivery(payment, self)
                                if resultado:
                                    logger.info(f"✅ [VERIFY] Entregável enviado com sucesso via send_payment_delivery")
                                    
                                    # ============================================================================
                                    # ✅ UPSELLS AUTOMÁTICOS - APÓS VERIFICAÇÃO MANUAL (PAGAMENTO JÁ PAID)
                                    # ✅ CORREÇÃO CRÍTICA QI 500: Processar upsells quando pagamento já está paid
                                    # ============================================================================
                                    logger.info(f"🔍 [UPSELLS VERIFY] Verificando condições: status='{payment.status}', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")
                                    
                                    if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                        logger.info(f"✅ [UPSELLS VERIFY] Condições atendidas! Processando upsells para payment {payment.payment_id}")
                                        try:
                                            # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                            from internal_logic.core.models import Payment as PaymentModel
                                            payment_check = PaymentModel.query.filter_by(payment_id=payment.payment_id).first()
                                            
                                            # ✅ CORREÇÃO CRÍTICA QI 500: Verificar scheduler ANTES de verificar jobs
                                            if not self.scheduler:
                                                logger.error(f"❌ CRÍTICO: Scheduler não está disponível! Upsells NÃO serão agendados!")
                                                logger.error(f"   Payment ID: {payment.payment_id}")
                                                logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                            else:
                                                # ✅ DIAGNÓSTICO: Verificar se scheduler está rodando
                                                try:
                                                    scheduler_running = self.scheduler.running
                                                    if not scheduler_running:
                                                        logger.error(f"❌ CRÍTICO: Scheduler existe mas NÃO está rodando!")
                                                        logger.error(f"   Payment ID: {payment.payment_id}")
                                                        logger.error(f"   Upsells NÃO serão executados se scheduler não estiver rodando!")
                                                except Exception as scheduler_check_error:
                                                    logger.warning(f"⚠️ Não foi possível verificar se scheduler está rodando: {scheduler_check_error}")
                                                
                                                # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                                upsells_already_scheduled = False
                                                try:
                                                    # Verificar se já existe job de upsell para este payment
                                                    for i in range(10):  # Verificar até 10 upsells possíveis
                                                        job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                        existing_job = self.scheduler.get_job(job_id)
                                                        if existing_job:
                                                            upsells_already_scheduled = True
                                                            logger.info(f"ℹ️ Upsells já foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                            logger.info(f"   Job encontrado: {job_id}, próxima execução: {existing_job.next_run_time}")
                                                            break
                                                except Exception as check_error:
                                                    logger.error(f"❌ ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                                    logger.warning(f"⚠️ Continuando mesmo com erro na verificação (pode causar duplicação)")
                                                    # ✅ Não bloquear se houver erro na verificação - deixar tentar agendar
                                            
                                            if self.scheduler and not upsells_already_scheduled:
                                                upsells = payment.bot.config.get_upsells()
                                                
                                                if upsells:
                                                    logger.info(f"🎯 [UPSELLS VERIFY] Verificando upsells para produto: {payment.product_name}")
                                                    
                                                    # Filtrar upsells que fazem match com o produto comprado
                                                    matched_upsells = []
                                                    for upsell in upsells:
                                                        trigger_product = upsell.get('trigger_product', '')
                                                        
                                                        # Match: trigger vazio (todas compras) OU produto específico
                                                        if not trigger_product or trigger_product == payment.product_name:
                                                            matched_upsells.append(upsell)
                                                    
                                                    if matched_upsells:
                                                        logger.info(f"✅ [UPSELLS VERIFY] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")
                                                        
                                                        # ✅ CORREÇÃO: Usar função específica para upsells (não downsells)
                                                        self.schedule_upsells(
                                                            bot_id=payment.bot_id,
                                                            payment_id=payment.payment_id,
                                                            chat_id=int(payment.customer_user_id),
                                                            upsells=matched_upsells,
                                                            original_price=payment.amount,
                                                            original_button_index=payment.button_index if payment.button_index is not None else -1
                                                        )
                                                        
                                                        logger.info(f"📅 [UPSELLS VERIFY] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                    else:
                                                        logger.info(f"ℹ️ [UPSELLS VERIFY] Nenhum upsell configurado para '{payment.product_name}' (trigger_product não faz match)")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY] Lista de upsells vazia no config do bot")
                                            else:
                                                if not self.scheduler:
                                                    logger.error(f"❌ [UPSELLS VERIFY] Scheduler não disponível - upsells não serão agendados")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY] Upsells já foram agendados anteriormente para payment {payment.payment_id} (evitando duplicação)")
                                                
                                        except Exception as e:
                                            logger.error(f"❌ [UPSELLS VERIFY] Erro ao processar upsells: {e}", exc_info=True)
                                            import traceback
                                            traceback.print_exc()
                                else:
                                    logger.warning(f"⚠️ [VERIFY] send_payment_delivery retornou False para {payment.payment_id}")
                            else:
                                logger.error(
                                    f"❌ ERRO GRAVE: Tentativa de enviar entregável com status inválido "
                                    f"(status: {payment.status}, payment_id: {payment.payment_id})"
                                )
                        except Exception as e:
                            logger.error(f"❌ [VERIFY] Erro ao enviar entregável via send_payment_delivery: {e}", exc_info=True)
                            
                            # ✅ FALLBACK: Se send_payment_delivery falhar, usar método antigo (mas com validação)
                            logger.warning(f"⚠️ [VERIFY] Usando fallback para envio de mensagem (send_payment_delivery falhou)")
                            
                            bot = payment.bot
                            # ✅ REDIS BRAIN: Buscar config do Redis
                            bot_data = self.bot_state.get_bot_data(bot_id)
                            bot_config = bot_data.get('config', {}) if bot_data else {}
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
                    
                    # ============================================================================
                    # ✅ V∞: FLOW ENGINE - INTEGRAÇÃO COMPLETA COM PAGAMENTO PENDENTE
                    # ============================================================================
                    flow_processed = False
                    if payment.flow_step_id:
                        bot_flow = Bot.query.get(bot_id)
                        if bot_flow and bot_flow.config:
                            flow_config = bot_flow.config.to_dict()
                            flow_enabled = flow_config.get('flow_enabled', False)
                            
                            # Parsear flow_steps se necessário
                            import json
                            flow_steps_raw = flow_config.get('flow_steps', [])
                            if isinstance(flow_steps_raw, str):
                                try:
                                    flow_steps = json.loads(flow_steps_raw)
                                except:
                                    flow_steps = []
                            else:
                                flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []
                            
                            if flow_enabled and flow_steps:
                                # Buscar step atual do fluxo
                                current_step = self._find_step_by_id(flow_steps, payment.flow_step_id)
                                
                                if current_step:
                                    connections = current_step.get('connections', {})
                                    telegram_user_id = str(user_info.get('id', ''))
                                    
                                    # ✅ V∞: Se payment pendente, executar pending step
                                    if payment.status == 'pending':
                                        pending_step_id = connections.get('pending')
                                        
                                        if pending_step_id:
                                            logger.info(f"🚀 [FLOW V∞] Payment pendente - executando step: {pending_step_id}")
                                            
                                            # Buscar snapshot do Redis
                                            flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                            
                                            try:
                                                # Executar pending step diretamente
                                                self._execute_flow_recursive(
                                                    bot_id, token, flow_config,
                                                    chat_id, telegram_user_id,
                                                    pending_step_id,
                                                    recursion_depth=0,
                                                    visited_steps=set(),
                                                    flow_snapshot=flow_snapshot
                                                )
                                                flow_processed = True
                                                logger.info(f"✅ [FLOW V∞] Pending step executado: {pending_step_id}")
                                                return  # ✅ SAIR - fluxo processado, não executar código tradicional
                                            except Exception as e:
                                                logger.error(f"❌ [FLOW V∞] Erro ao executar pending step: {e}", exc_info=True)
                                                # Continuar para fallback tradicional
                    
                    # ✅ FALLBACK: Se fluxo não processou, usar comportamento tradicional
                    if not flow_processed:
                        bot = payment.bot
                        # ✅ REDIS BRAIN: Buscar config do Redis
                        bot_data = self.bot_state.get_bot_data(bot_id)
                        bot_config = bot_data.get('config', {}) if bot_data else {}
                        custom_pending_message = bot_config.get('pending_message', '').strip()
                    
                    # ✅ CORREÇÃO: Buscar PIX code do product_description (onde é salvo)
                    pix_code = payment.product_description or 'Aguardando...'
                    
                    # ✅ FALLBACK: Se PIX code não está salvo, tentar buscar do gateway (apenas para UmbrellaPay)
                    if (pix_code == 'Aguardando...' or not pix_code or len(pix_code) < 20) and payment.gateway_type == 'umbrellapag':
                        try:
                            # Buscar gateway e tentar obter PIX code novamente
                            gateway = Gateway.query.filter_by(
                                user_id=bot.user_id,
                                gateway_type='umbrellapag',
                                is_verified=True
                            ).first()
                            
                            if gateway and payment.gateway_transaction_id:
                                credentials = {
                                    'api_key': gateway.api_key,
                                    'product_hash': gateway.product_hash
                                }
                                payment_gateway = GatewayFactory.create_gateway(
                                    gateway_type='umbrellapag',
                                    credentials=credentials
                                )
                                
                                if payment_gateway:
                                    # ✅ Tentar buscar PIX code diretamente da API (GET /user/transactions/{id})
                                    # A resposta da API inclui o PIX code em data.pix.qrCode
                                    try:
                                        # Fazer requisição direta para obter PIX code
                                        response = payment_gateway._make_request('GET', f'/user/transactions/{payment.gateway_transaction_id}')
                                        if response and response.status_code == 200:
                                            api_data = response.json()
                                            
                                            # ✅ Tratar estrutura aninhada (data.data)
                                            inner_data = api_data
                                            if isinstance(api_data, dict) and 'data' in api_data:
                                                inner_data = api_data.get('data', {})
                                                if isinstance(inner_data, dict) and 'data' in inner_data:
                                                    inner_data = inner_data.get('data', {})
                                            
                                            # ✅ Extrair PIX code
                                            if isinstance(inner_data, dict):
                                                pix_obj = inner_data.get('pix', {})
                                                if isinstance(pix_obj, dict):
                                                    fallback_pix = (
                                                        pix_obj.get('qrCode') or
                                                        pix_obj.get('qr_code') or
                                                        pix_obj.get('code') or
                                                        None
                                                    )
                                                    if fallback_pix and len(fallback_pix) > 20:
                                                        pix_code = fallback_pix
                                                        logger.info(f"✅ [VERIFY] PIX code recuperado do gateway via API para {payment.payment_id}")
                                    except Exception as api_error:
                                        logger.debug(f"🔍 [VERIFY] Não foi possível buscar PIX code via API (não crítico): {api_error}")
                        except Exception as e:
                            logger.warning(f"⚠️ [VERIFY] Erro ao buscar PIX code do gateway (fallback): {e}")
                            # Continuar com pix_code atual (pode ser 'Aguardando...')
                    
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
                        elif payment.gateway_type == 'umbrellapag':
                            # ✅ CORREÇÃO: Mensagem específica para UmbrellaPay (similar ao Paradise)
                            pending_message = f"""⏳ <b>Aguardando confirmação</b>

Seu pagamento está sendo processado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

⏱️ <b>Confirmação automática:</b>
Se você já pagou, o sistema confirmará automaticamente em até 5 minutos via webhook ou job de sincronização.

💡 <b>Dica:</b> Você pode clicar novamente em "Verificar Pagamento" para consultar o status manualmente.

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
            logger.error(f"❌ Erro ao iniciar múltiplos order bumps: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_next_order_bump(self, bot_id: int, token: str, chat_id: int, user_key: str):
        """
        Exibe o próximo order bump na sequência - MIGRADO PARA REDIS (Multi-Worker)
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_key: Chave da sessão do usuário
        """
        try:
            # ✅ REDIS MIGRATION: Buscar sessão do Redis
            redis_key = f"gb:ob_session:{user_key}"
            redis_conn = get_redis_connection()
            session_json = redis_conn.get(redis_key)
            
            if not session_json:
                logger.error(f"❌ Sessão de order bump não encontrada no Redis: {redis_key}")
                return
            
            session = json.loads(session_json)
            
            # ✅ VALIDAÇÃO: Verificar se chat_id corresponde ao chat_id da sessão
            session_chat_id = session.get('chat_id')
            if session_chat_id and session_chat_id != chat_id:
                logger.warning(f"⚠️ Chat ID mismatch em _show_next_order_bump: recebido {chat_id}, mas sessão é do chat {session_chat_id}. Usando chat_id da sessão.")
                chat_id = session_chat_id  # ✅ Corrigir chat_id para o da sessão
            
            # ✅ VALIDAÇÃO: Usar bot_id da sessão se disponível (garante consistência)
            session_bot_id = session.get('bot_id', bot_id)
            if session_bot_id != bot_id:
                logger.warning(f"⚠️ Bot ID mismatch em _show_next_order_bump: recebido {bot_id}, mas sessão é do bot {session_bot_id}. Usando bot_id da sessão.")
                # Buscar token correto para o bot da sessão
                # ✅ REDIS BRAIN: Buscar do Redis
                session_bot_data = self.bot_state.get_bot_data(session_bot_id)
                if session_bot_data:
                    token = session_bot_data['token']
                    bot_id = session_bot_id  # ✅ Corrigir bot_id para o da sessão
                else:
                    logger.error(f"❌ Bot {session_bot_id} da sessão não está mais ativo no Redis!")
                    return
            
            current_index = session['current_index']
            order_bumps = session['order_bumps']
            
            if current_index >= len(order_bumps):
                # Todos os order bumps foram exibidos, gerar PIX final
                # ✅ Usar bot_id e token já corrigidos pela validação acima
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
            
            # ✅ CORREÇÃO: Botões com callback_data usando apenas chat_id (sem bot_id na chave)
            # Formato: multi_bump_yes_CHAT_ID_BUMP_INDEX_TOTAL_PRICE_CENTAVOS
            buttons = [
                {
                    'text': accept_button_text,
                    'callback_data': f'multi_bump_yes_{chat_id}_{current_index}_{int(total_with_this_bump*100)}'
                },
                {
                    'text': decline_button_text,
                    'callback_data': f'multi_bump_no_{chat_id}_{current_index}_{int(current_total*100)}'
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
        VERSÃO REDIS: Com idempotência multi-worker via Redis
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_key: Chave da sessão do usuário
        """
        try:
            import time
            current_time = time.time()
            
            # ✅ REDIS MIGRATION: Chaves para sessão e cache PIX
            redis_conn = get_redis_connection()
            session_key = f"gb:ob_session:{user_key}"
            pix_cache_key = f"gb:pix_cache:{user_key}"
            
            # ✅ IDEMPOTÊNCIA: Verificar se PIX já foi gerado recentemente (Redis)
            pix_cache_json = redis_conn.get(pix_cache_key)
            if pix_cache_json:
                cached = json.loads(pix_cache_json)
                pix_data = cached.get('pix_data')
                logger.info(f"🔄 PIX em cache Redis reutilizado (idempotência): {pix_data.get('payment_id')}")
                # Reenviar mensagem com PIX do cache
                self._send_pix_message(token, chat_id, pix_data, "🔄 Reenviando seu PIX:")
                return  # NÃO gerar novo PIX
            
            # ✅ REDIS MIGRATION: Buscar sessão do Redis
            session_json = redis_conn.get(session_key)
            if not session_json:
                logger.error(f"❌ Sessão de order bump não encontrada no Redis: {session_key}")
                return  # Realmente não temos dados - erro
            
            session = json.loads(session_json)
            
            # ✅ IDEMPOTÊNCIA: Verificar se sessão já gerou PIX
            if session.get('status') == 'pix_generated':
                payment_id = session.get('payment_id')
                logger.info(f"🔄 Sessão já gerou PIX anteriormente: {payment_id}")
                # Tentar recuperar do cache (já verificado acima, mas double-check)
                pix_cache_json = redis_conn.get(pix_cache_key)
                if pix_cache_json:
                    cached = json.loads(pix_cache_json)
                    self._send_pix_message(token, chat_id, cached['pix_data'], "🔄 Reenviando seu PIX:")
                    return
            
            # ✅ VALIDAÇÃO: Verificar se chat_id corresponde ao chat_id da sessão
            session_chat_id = session.get('chat_id')
            if session_chat_id and session_chat_id != chat_id:
                logger.warning(f"⚠️ Chat ID mismatch em _finalize_order_bump_session: recebido {chat_id}, mas sessão é do chat {session_chat_id}. Usando chat_id da sessão.")
                chat_id = session_chat_id  # ✅ Corrigir chat_id para o da sessão
            
            # ✅ VALIDAÇÃO: Usar bot_id da sessão se disponível (garante consistência)
            session_bot_id = session.get('bot_id', bot_id)
            if session_bot_id != bot_id:
                logger.warning(f"⚠️ Bot ID mismatch em _finalize_order_bump_session: recebido {bot_id}, mas sessão é do bot {session_bot_id}. Usando bot_id da sessão.")
                session_bot_data = self.bot_state.get_bot_data(session_bot_id)
                if session_bot_data:
                    token = session_bot_data['token']
                    bot_id = session_bot_id
                else:
                    logger.error(f"❌ Bot {session_bot_id} da sessão não está mais ativo no Redis!")
                    return
            
            original_price = session['original_price']
            original_description = session['original_description']
            button_index = session['button_index']
            accepted_bumps = session['accepted_bumps']
            total_bump_value = session['total_bump_value']
            
            final_price = original_price + total_bump_value
            
            logger.info(f"🎁 Finalizando sessão - Preço original: R$ {original_price:.2f}, Bumps aceitos: {len(accepted_bumps)}, Valor total: R$ {final_price:.2f}")
            
            # Buscar config do bot
            from internal_logic.core.models import Bot, BotUser
            from flask import current_app
            from internal_logic.core.extensions import db
            
            bot_config = None
            with current_app.app_context():
                bot_model = Bot.query.get(bot_id)
                if bot_model and bot_model.config:
                    bot_config = bot_model.config.to_dict()
            
            # Buscar BotUser para tracking
            customer_name = ""
            customer_username = ""
            with current_app.app_context():
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=str(chat_id)
                ).first()
                if bot_user:
                    customer_name = bot_user.first_name or ""
                    customer_username = bot_user.username or ""
            
            # Gerar PIX final
            pix_data = self._generate_pix_payment(
                bot_id=bot_id,
                amount=final_price,
                description=f"{original_description} + {len(accepted_bumps)} bônus" if accepted_bumps else original_description,
                customer_name=customer_name,
                customer_username=customer_username,
                customer_user_id=str(chat_id),
                order_bump_shown=True,
                order_bump_accepted=len(accepted_bumps) > 0,
                order_bump_value=total_bump_value
            )
            
            # ✅ UX FIX: Tratamento Amigável de Rate Limit
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                self.send_telegram_message(
                    chat_id=chat_id,
                    message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                    token=token
                )
                return
            
            if pix_data and pix_data.get('pix_code'):
                # Criar descrição detalhada
                bump_descriptions = [bump.get('description', 'Bônus') for bump in accepted_bumps]
                description_text = f"{original_description}"
                if bump_descriptions:
                    description_text += f" + {', '.join(bump_descriptions)}"
                
                # Adicionar amount ao pix_data para cache completo
                pix_data['amount'] = final_price
                pix_data['description'] = description_text
                
                self._send_pix_message(token, chat_id, pix_data, "🎁 Seu PIX com bônus:")
                
                logger.info(f"✅ PIX FINAL COM {len(accepted_bumps)} ORDER BUMPS ENVIADO! ID: {pix_data.get('payment_id')}")
                
                # ✅ REDIS MIGRATION: Salvar no cache PIX com TTL 5 minutos
                if pix_data.get('payment_id'):
                    cache_data = {
                        'pix_data': pix_data,
                        'timestamp': current_time,
                        'payment_id': pix_data.get('payment_id')
                    }
                    redis_conn.setex(pix_cache_key, 300, json.dumps(cache_data))
                    logger.info(f"💾 PIX salvo no cache Redis: {pix_cache_key} (TTL 5min)")
                
                # Agendar downsells
                if bot_config:
                    try:
                        if bot_config.get('downsells_enabled', False):
                            downsells = bot_config.get('downsells', [])
                            if downsells and len(downsells) > 0:
                                self.schedule_downsells(
                                    bot_id=bot_id,
                                    payment_id=pix_data.get('payment_id'),
                                    chat_id=chat_id,
                                    downsells=downsells,
                                    original_price=original_price,
                                    original_button_index=button_index
                                )
                    except Exception as e:
                        logger.error(f"❌ Erro ao agendar downsells: {e}", exc_info=True)
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
            
            # ✅ REDIS MIGRATION: Atualizar sessão com status 'pix_generated'
            session['status'] = 'pix_generated'
            session['pix_generated_at'] = current_time
            session['payment_id'] = pix_data.get('payment_id') if pix_data else None
            # ✅ Atualizar no Redis com TTL renovado de 10 minutos
            redis_conn.setex(session_key, 600, json.dumps(session))
            logger.info(f"🔄 Sessão marcada como 'pix_generated' no Redis: {session_key}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar sessão de order bumps: {e}")
            import traceback
            traceback.print_exc()
    
    def _send_pix_message(self, token: str, chat_id: int, pix_data: dict, header_msg: str):
        """
        Envia mensagem de PIX de forma idempotente.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            pix_data: Dados do PIX (pix_code, payment_id, amount, description)
            header_msg: Mensagem de cabeçalho
        """
        try:
            if not pix_data or not pix_data.get('pix_code'):
                logger.error(f"❌ _send_pix_message chamado sem pix_code válido")
                return False
            
            pix_code = pix_data.get('pix_code', '')
            payment_id = pix_data.get('payment_id', '')
            amount = pix_data.get('amount', 0)
            description = pix_data.get('description', 'Produto')
            
            payment_message = f"""{header_msg}

🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {amount:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo!</b>"""
            
            buttons = [{
                'text': '✅ Verificar Pagamento',
                'callback_data': f'verify_{payment_id}'
            }]
            
            result = self.send_telegram_message(
                token=token,
                chat_id=str(chat_id),
                message=payment_message.strip(),
                buttons=buttons
            )
            
            if result:
                logger.info(f"✅ Mensagem PIX enviada (idempotente): payment_id={payment_id}")
            else:
                logger.warning(f"⚠️ Falha ao enviar mensagem PIX: payment_id={payment_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro em _send_pix_message: {e}")
            return False
    
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
            
            # ✅ FIX SÊNIOR: Blindagem contra valores nulos e strings vazias no banco de dados
            raw_price = order_bump.get('price')
            try:
                if raw_price is None or str(raw_price).strip() == '':
                    bump_price = 0.0
                else:
                    bump_price = float(raw_price)
            except (ValueError, TypeError):
                logger.warning(f"⚠️ Valor de Order Bump inválido detectado ('{raw_price}'). Assumindo 0.0 para não interromper a venda.")
                bump_price = 0.0
                
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
            
            # ✅ FIX SÊNIOR: Blindagem contra valores nulos e strings vazias no banco de dados
            raw_price = order_bump.get('price')
            try:
                if raw_price is None or str(raw_price).strip() == '':
                    bump_price = 0.0
                else:
                    bump_price = float(raw_price)
            except (ValueError, TypeError):
                logger.warning(f"⚠️ Valor de Order Bump inválido detectado ('{raw_price}'). Assumindo 0.0 para não interromper a venda.")
                bump_price = 0.0
                
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
                             downsell_index: int = None,
                             is_upsell: bool = False,  # ✅ NOVO - UPSELLS
                             upsell_index: int = None,  # ✅ NOVO - UPSELLS
                             is_remarketing: bool = False,  # ✅ NOVO - REMARKETING
                             remarketing_campaign_id: int = None,  # ✅ NOVO - REMARKETING
                             button_index: int = None,  # ✅ NOVO - SISTEMA DE ASSINATURAS
                             button_config: dict = None) -> Optional[Dict[str, Any]]:  # ✅ NOVO - SISTEMA DE ASSINATURAS
        """Gera pagamento PIX via gateway configurado
        
        Args:
            bot_id: ID do bot
            amount: Valor do pagamento
            description: Descrição do produto
            customer_name: Nome do cliente
            customer_username: Username do Telegram
            customer_user_id: ID do usuário no Telegram
        """
        # ✅ INTEGRAÇÃO COM PAYMENTSERVICE (NOVA ARQUITETURA)
        try:
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot, Gateway
            
            # Buscar bot para obter gateway_id
            bot = Bot.query.get(bot_id)
            if not bot:
                logger.error(f"❌ Bot {bot_id} não encontrado para geração de PIX")
                return None
            
            # Buscar gateway ativo do usuário
            gateway = Gateway.query.filter_by(
                user_id=bot.user_id,
                is_active=True,
                is_verified=True
            ).first()
            
            if not gateway:
                logger.error(f"❌ Nenhum gateway ativo encontrado para usuário {bot.user_id}")
                return None
            
            # ✅ USAR PAYMENTSERVICE (NOVA ARQUITETURA)
            payment_service = get_payment_service(db.session)
            
            response = payment_service.generate_pix(
                bot_id=bot_id,
                gateway_id=gateway.id,
                amount=amount,
                description=description,
                customer_name=customer_name or 'Cliente',
                customer_email=f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
                customer_cpf=customer_user_id,  # Usar Telegram ID como identificador
                external_id=customer_user_id
            )
            
            if response.success:
                logger.info(f"✅ PIX gerado via PaymentService - Transaction ID: {response.transaction_id}")
                return {
                    'pix_code': response.qr_code,
                    'pix_code_base64': None,
                    'qr_code_url': response.qr_code_url,
                    'transaction_id': response.transaction_id,
                    'transaction_hash': None,
                    'payment_id': response.transaction_id,
                    'expires_at': None,
                    'status': response.status
                }
            else:
                logger.error(f"❌ Falha ao gerar PIX via PaymentService: {response.error_message}")
                # Se falhou, continuar com lógica legada (fallback)
                # Não retornar None ainda - deixa o código antigo tentar
        except Exception as e:
            logger.error(f"❌ Erro na integração PaymentService: {e}")
            logger.info("🔄 Fallback para lógica legada de PIX...")
        
        # 🔄 LÓGICA LEGADA (Fallback) - Executa se PaymentService falhar
        # (código original continua abaixo...)
            # ✅ VALIDAÇÃO CRÍTICA: customer_user_id não pode ser vazio (destrói tracking Meta Pixel)
            if not customer_user_id or customer_user_id.strip() == "":
                logger.error(f"❌ ERRO CRÍTICO: customer_user_id vazio ao gerar PIX! Bot: {bot_id}, Valor: R$ {amount:.2f}")
                logger.error(f"   Isso quebra tracking Meta Pixel - Purchase não será atribuído à campanha!")
                logger.error(f"   customer_name: {customer_name}, customer_username: {customer_username}")
                return None
            # ===== PATCH DEFENSIVO FINAL (OBRIGATÓRIO) =====
            fbc = None
            fbp = None
            fbclid = None
            pageview_event_id = None
            redirect_id = None
            meta_pixel_id = None
            tracking_token = None
            try:
                # Importar models dentro da função para evitar circular import
                from internal_logic.core.models import Bot, Gateway, Payment
                from internal_logic.core.extensions import db
                from flask import current_app
                from sqlalchemy.exc import IntegrityError
                
                with current_app.app_context():
                    # Buscar bot e gateway
                    bot = db.session.get(Bot, bot_id)
                    if not bot:
                        logger.error(f"Bot {bot_id} não encontrado")
                        return None
                    # ✅ FIX: Re-hidratar o objeto Bot AGORA que ele foi definido
                    bot = db.session.merge(bot)
                    
                    # Buscar gateway ativo e verificado do usuário
                    # ✅ CORREÇÃO: Filtrar também por gateway_type se necessário, mas permitir qualquer gateway ativo
                    gateway = Gateway.query.filter_by(
                        user_id=bot.user_id,
                        is_active=True,
                        is_verified=True
                    ).first()
                    
                    if not gateway:
                        logger.error(f"❌ Nenhum gateway ativo encontrado para usuário {bot.user_id} | Bot: {bot_id}")
                        logger.error(f"   Verifique se há um gateway configurado e ativo em /settings")
                        return None
                    
                    logger.info(f"💳 Gateway: {gateway.gateway_type.upper()} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")
                    
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
                            from internal_logic.core.models import get_brazil_time
                            age_seconds = (get_brazil_time() - pending_same_product.created_at).total_seconds() if pending_same_product.created_at else 999999
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
                        from internal_logic.core.models import get_brazil_time
                        time_since = (get_brazil_time() - last_pix.created_at).total_seconds()
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
                    # Prioridade: owner_commission (fresh) > gateway.split_percentage > 2.0 (padrão)
                    # ✅ FIX SÊNIOR: Bypass Lazy Load (DetachedInstance)
                    from internal_logic.core.models import User
                    owner_commission = None
                    if bot and getattr(bot, 'user_id', None):
                        current_owner = db.session.get(User, bot.user_id)
                        if current_owner:
                            owner_commission = current_owner.commission_percentage
                    user_commission = owner_commission or gateway.split_percentage or 2.0
                
                    # ✅ CRÍTICO: Extrair credenciais e validar ANTES de criar gateway
                    # Se descriptografia falhar, properties retornam None
                    # IMPORTANTE: Acessar properties explicitamente para forçar descriptografia e capturar exceções
                    try:
                        api_key = gateway.api_key
                        # ✅ LOG ESPECÍFICO PARA WIINPAY
                        if gateway.gateway_type == 'wiinpay':
                            if api_key:
                                logger.info(f"✅ [WiinPay] api_key descriptografada com sucesso (len={len(api_key)})")
                            else:
                                logger.warning(f"⚠️ [WiinPay] api_key retornou None (campo interno existe: {bool(gateway._api_key)})")
                    except Exception as decrypt_error:
                        logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.api_key (gateway {gateway.id}): {decrypt_error}")
                        logger.error(f"   Tipo do gateway: {gateway.gateway_type}")
                        logger.error(f"   Isso indica que a descriptografia está FALHANDO com exceção")
                        api_key = None
                        # ✅ LOG ESPECÍFICO PARA WIINPAY
                        if gateway.gateway_type == 'wiinpay':
                            logger.error(f"❌ [WiinPay] ERRO CRÍTICO na descriptografia da api_key!")
                            logger.error(f"   Gateway ID: {gateway.id} | User ID: {gateway.user_id}")
                            logger.error(f"   Campo interno existe: {bool(gateway._api_key)}")
                            logger.error(f"   Exceção: {decrypt_error}")
                            logger.error(f"   SOLUÇÃO: Reconfigure o gateway WiinPay com a api_key correta em /settings")
                
                    try:
                        client_secret = gateway.client_secret
                    except Exception as decrypt_error:
                        logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.client_secret (gateway {gateway.id}): {decrypt_error}")
                        client_secret = None
                
                    try:
                        product_hash = gateway.product_hash
                    except Exception as decrypt_error:
                        logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.product_hash (gateway {gateway.id}): {decrypt_error}")
                        product_hash = None
                
                    try:
                        split_user_id = gateway.split_user_id
                    except Exception as decrypt_error:
                        logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.split_user_id (gateway {gateway.id}): {decrypt_error}")
                        split_user_id = None
                
                    # ✅ CORREÇÃO CRÍTICA: WiinPay - SEMPRE usar ID da plataforma para split
                    # O split_user_id NUNCA deve ser o mesmo user_id da api_key (conta de recebimento)
                    # Isso causa erro 422: "A conta de split não pode ser a mesma conta de recebimento"
                    if gateway.gateway_type == 'wiinpay':
                        platform_split_id = '68ffcc91e23263e0a01fffa4'  # ID da plataforma
                        old_id = '6877edeba3c39f8451ba5bdd'  # ID antigo (também inválido)
                    
                        # ✅ Extrair user_id da api_key (JWT) para validar
                        try:
                            import jwt
                            import json
                            # Decodificar JWT sem verificar assinatura (apenas para ler payload)
                            decoded = jwt.decode(api_key, options={"verify_signature": False}) if api_key else {}
                            api_key_user_id = decoded.get('userId') or decoded.get('user_id') or ''
                            logger.info(f"🔍 [WiinPay] user_id da api_key (JWT): {api_key_user_id}")
                        except Exception as jwt_error:
                            api_key_user_id = None
                            logger.warning(f"⚠️ [WiinPay] Não foi possível extrair user_id do JWT: {jwt_error}")
                    
                        # ✅ FORÇAR: Sempre usar ID da plataforma, nunca o user_id do usuário
                        if not split_user_id or split_user_id == old_id or split_user_id.strip() == '':
                            logger.info(f"✅ [WiinPay] split_user_id vazio/antigo, usando ID da plataforma: {platform_split_id}")
                            split_user_id = platform_split_id
                        elif split_user_id == api_key_user_id:
                            logger.warning(f"⚠️ [WiinPay] split_user_id é o mesmo da conta de recebimento ({api_key_user_id})!")
                            logger.warning(f"   Isso causará erro 422. Forçando ID da plataforma: {platform_split_id}")
                            split_user_id = platform_split_id
                        elif split_user_id != platform_split_id:
                            logger.warning(f"⚠️ [WiinPay] split_user_id diferente do ID da plataforma: {split_user_id}")
                            logger.warning(f"   Esperado: {platform_split_id} | Usando: {split_user_id}")
                            logger.warning(f"   Forçando ID da plataforma para garantir split correto")
                            split_user_id = platform_split_id
                        else:
                            logger.info(f"✅ [WiinPay] split_user_id correto (ID da plataforma): {split_user_id}")
                
                    # ✅ VALIDAÇÃO: Verificar se credenciais foram descriptografadas corretamente
                    # Se alguma propriedade retornar None mas o campo interno existir, significa erro de descriptografia
                    encryption_error_detected = False
                
                    if gateway._api_key and not api_key:
                        logger.error(f"❌ CRÍTICO: Erro ao descriptografar api_key do gateway {gateway.id}")
                        logger.error(f"   Campo interno existe: {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                        logger.error(f"   Property retornou: {api_key}")
                        logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                        logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                        logger.error(f"   Gateway ID: {gateway.id} | Tipo: {gateway.gateway_type} | User: {gateway.user_id}")
                        encryption_error_detected = True
                
                    if gateway._client_secret and not client_secret:
                        logger.error(f"❌ CRÍTICO: Erro ao descriptografar client_secret do gateway {gateway.id}")
                        logger.error(f"   Campo interno existe: {gateway._client_secret[:30] if gateway._client_secret else 'None'}...")
                        logger.error(f"   Property retornou: {client_secret}")
                        logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                        logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                        encryption_error_detected = True
                
                    if gateway._product_hash and not product_hash:
                        logger.error(f"❌ CRÍTICO: Erro ao descriptografar product_hash do gateway {gateway.id}")
                        logger.error(f"   Campo interno existe: {gateway._product_hash[:30] if gateway._product_hash else 'None'}...")
                        logger.error(f"   Property retornou: {product_hash}")
                        logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                        logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                        encryption_error_detected = True
                
                    if gateway._split_user_id and not split_user_id and gateway.gateway_type == 'wiinpay':
                        logger.warning(f"⚠️ WiinPay: split_user_id não descriptografado (pode ser normal se não configurado)")
                
                    # ✅ Se detectou erro de descriptografia, retornar None imediatamente
                    if encryption_error_detected:
                        logger.error(f"❌ ERRO DE DESCRIPTOGRAFIA DETECTADO - Payment NÃO será criado")
                        logger.error(f"   ACÃO NECESSÁRIA: Reconfigure o gateway {gateway.gateway_type} (ID: {gateway.id}) em /settings")
                        return None
                
                    credentials = {
                        # SyncPay usa client_id/client_secret
                        'client_id': gateway.client_id,
                        'client_secret': client_secret,
                        # Outros gateways usam api_key
                        'api_key': api_key,
                        # ✅ Átomo Pay: api_token é salvo em api_key no banco, mas precisa ser passado como api_token
                        'api_token': api_key if gateway.gateway_type == 'atomopay' else None,
                        # ✅ Babylon: company_id é salvo em client_id no banco
                        'company_id': gateway.client_id if gateway.gateway_type == 'babylon' else None,
                        # Paradise
                        'product_hash': product_hash,
                        'offer_hash': gateway.offer_hash,
                        'store_id': gateway.store_id,
                        # WiinPay
                        'split_user_id': split_user_id,
                        # ✅ RANKING V2.0: Usar taxa do usuário (pode ser premium)
                        'split_percentage': user_commission
                    }
                
                    # ✅ VALIDAÇÃO ESPECÍFICA POR GATEWAY: Verificar credenciais obrigatórias
                    if gateway.gateway_type == 'paradise':
                        if not api_key:
                            logger.error(f"❌ Paradise: api_key ausente ou não descriptografado")
                            return None
                        if not product_hash:
                            logger.error(f"❌ Paradise: product_hash ausente ou não descriptografado")
                            return None
                    elif gateway.gateway_type == 'atomopay':
                        if not api_key:
                            logger.error(f"❌ Átomo Pay: api_token (api_key) ausente ou não descriptografado")
                            logger.error(f"   gateway.id: {gateway.id}")
                            return None
                        else:
                            logger.debug(f"🔑 Átomo Pay: api_token presente ({len(api_key)} caracteres)")
                    elif gateway.gateway_type == 'syncpay':
                        # ✅ SyncPay usa client_id/client_secret, NÃO api_key
                        if not client_secret:
                            logger.error(f"❌ SyncPay: client_secret ausente ou não descriptografado")
                            logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                            if gateway._client_secret:
                                logger.error(f"   Campo interno existe mas descriptografia falhou!")
                                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                            return None
                        if not gateway.client_id:
                            logger.error(f"❌ SyncPay: client_id ausente")
                            logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                            return None
                    elif gateway.gateway_type in ['pushynpay', 'wiinpay']:
                        if not api_key:
                            logger.error(f"❌ {gateway.gateway_type.upper()}: api_key ausente ou não descriptografado")
                            logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id} | Tipo: {gateway.gateway_type}")
                            if gateway._api_key:
                                logger.error(f"   ❌ Campo interno existe mas descriptografia falhou!")
                                logger.error(f"   Campo interno (primeiros 30 chars): {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                                logger.error(f"   SOLUÇÃO CRÍTICA: Reconfigure o gateway {gateway.gateway_type.upper()} (ID: {gateway.id}) em /settings")
                                logger.error(f"   Passo a passo:")
                                logger.error(f"   1. Acesse /settings")
                                logger.error(f"   2. Encontre o gateway {gateway.gateway_type.upper()} (ID: {gateway.id})")
                                logger.error(f"   3. Reinsira a api_key do gateway")
                                logger.error(f"   4. Salve as configurações")
                            else:
                                logger.error(f"   Campo interno (_api_key) também está vazio - gateway não foi configurado corretamente")
                                logger.error(f"   SOLUÇÃO: Configure o gateway {gateway.gateway_type.upper()} em /settings")
                            return None
                    elif gateway.gateway_type == 'babylon':
                        # ✅ BABYLON requer: api_key (Secret Key) + client_id (Company ID)
                        if not api_key:
                            logger.error(f"❌ BABYLON: api_key (Secret Key) ausente ou não descriptografado")
                            logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                            if gateway._api_key:
                                logger.error(f"   ❌ Campo interno existe mas descriptografia falhou!")
                                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                                logger.error(f"   SOLUÇÃO: Reconfigure o gateway Babylon (ID: {gateway.id}) em /settings")
                            return None
                        if not gateway.client_id:
                            logger.error(f"❌ BABYLON: client_id (Company ID) ausente")
                            logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                            logger.error(f"   SOLUÇÃO: Configure o Company ID no gateway Babylon em /settings")
                            return None
                
                    # Log para auditoria (apenas se for premium)
                    # ✅ FIX: Usar bot.user_id direto (evita DetachedInstanceError em bot.owner)
                    if user_commission < 2.0:
                        logger.info(f"🏆 TAXA PREMIUM aplicada: {user_commission}% (User ID {bot.user_id})")
                
                    # ✅ PATCH 2 QI 200: Garantir que product_hash existe antes de usar
                    # Se gateway não tem product_hash, será criado dinamicamente no generate_pix
                    # Mas precisamos garantir que será salvo no banco após criação
                    original_product_hash = gateway.product_hash
                
                    # Gerar PIX via gateway (usando Factory Pattern)
                    logger.info(f"🔧 Criando gateway {gateway.gateway_type} com credenciais...")
                
                    # ✅ LOG DETALHADO PARA WIINPAY
                    if gateway.gateway_type == 'wiinpay':
                        logger.info(f"🔍 [WiinPay Debug] Criando gateway com:")
                        logger.info(f"   - api_key presente: {bool(api_key)}")
                        logger.info(f"   - api_key length: {len(api_key) if api_key else 0}")
                        logger.info(f"   - split_user_id: {split_user_id}")
                        logger.info(f"   - split_percentage: {user_commission}%")
                        logger.info(f"   - credentials keys: {list(credentials.keys())}")
                
                    payment_gateway = GatewayFactory.create_gateway(
                        gateway_type=gateway.gateway_type,
                        credentials=credentials
                    )
                
                    if not payment_gateway:
                        logger.error(f"❌ Erro ao criar gateway {gateway.gateway_type}")
                        if gateway.gateway_type == 'wiinpay':
                            logger.error(f"   WIINPAY: Gateway não foi criado - verifique:")
                            logger.error(f"   1. api_key foi descriptografada corretamente: {bool(api_key)}")
                            logger.error(f"   2. Gateway está ativo e verificado: is_active={gateway.is_active}, is_verified={gateway.is_verified}")
                            logger.error(f"   3. Verifique logs anteriores para erros de descriptografia")
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
                    # ✅ CRÍTICO: Preparar customer_data ANTES de gerar PIX (para usar depois ao salvar Payment)
                    customer_data = {
                        'name': customer_name or 'Cliente',
                        'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
                        'phone': customer_user_id,  # ✅ User ID do Telegram como identificador único
                        'document': customer_user_id  # ✅ User ID do Telegram (gateways aceitam)
                    }
                    pix_result = payment_gateway.generate_pix(
                        amount=amount,
                        description=description,
                        payment_id=payment_id,
                        customer_data=customer_data
                    )
                
                    logger.info(f"📊 Resultado do PIX: {pix_result}")
                
                    # ✅ CORREÇÃO ROBUSTA: Se Payment foi criado mas gateway retornou None, marcar como 'pending_verification'
                    if not pix_result:
                        # ✅ Log detalhado para WiinPay especificamente
                        if gateway.gateway_type == 'wiinpay':
                            logger.error(f"❌ WIINPAY: generate_pix retornou None!")
                            logger.error(f"   Bot ID: {bot_id} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")
                            logger.error(f"   Valor: R$ {amount:.2f} | Descrição: {description}")
                            logger.error(f"   api_key presente: {bool(api_key)}")
                            logger.error(f"   split_user_id: {split_user_id}")
                            logger.error(f"   split_percentage: {user_commission}%")
                            logger.error(f"   Verifique os logs acima para ver se a API da WiinPay retornou algum erro")
                    
                        # ✅ Verificar se Payment foi criado antes de retornar None
                        if 'payment' in locals() and payment:
                            try:
                                logger.warning(f"⚠️ [GATEWAY RETORNOU NONE] Gateway {gateway.gateway_type} retornou None")
                                logger.warning(f"   Bot: {bot_id}, Valor: R$ {amount:.2f}, Payment ID: {payment.payment_id}")
                                logger.warning(f"   Payment será marcado como 'pending_verification' para não perder venda")
                            
                                payment.status = 'pending_verification'
                                payment.gateway_transaction_id = None
                                payment.product_description = None
                                db.session.commit()
                            
                                logger.warning(f"⚠️ Payment {payment.id} marcado como 'pending_verification' (gateway retornou None)")
                                return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway retornou None'}
                            except Exception as commit_error:
                                logger.error(f"❌ Erro ao commitar Payment após gateway retornar None: {commit_error}", exc_info=True)
                                db.session.rollback()
                                return None
                        else:
                            # ✅ Payment não foi criado - retornar None normalmente
                            logger.error(f"❌ Gateway retornou None e Payment não foi criado")
                            return None
                
                    if pix_result:
                        # ✅ CRÍTICO: Verificar se transação foi recusada
                        transaction_status = pix_result.get('status')
                        is_refused = transaction_status == 'refused' or pix_result.get('error')
                    
                        if is_refused:
                            logger.warning(f"⚠️ Transação RECUSADA pelo gateway - criando payment com status 'failed' para webhook")
                        else:
                            logger.info(f"✅ PIX gerado com sucesso pelo gateway!")
                    
                        # ✅ BUSCAR BOT_USER PARA COPIAR DADOS DEMOGRÁFICOS (robusto string/int)
                        from internal_logic.core.models import BotUser
                        bot_user = BotUser.query.filter_by(
                            bot_id=bot_id,
                            telegram_user_id=customer_user_id
                        ).first()
                        if not bot_user:
                            try:
                                bot_user_int = int(customer_user_id)
                            except (TypeError, ValueError):
                                bot_user_int = None
                            if bot_user_int is not None:
                                bot_user = BotUser.query.filter_by(
                                    bot_id=bot_id,
                                    telegram_user_id=str(bot_user_int)
                                ).first()
                    
                        # ✅ QI 500: GERAR/REUTILIZAR TRACKING_TOKEN V4 (mantém vínculo PageView → Purchase)
                        from utils.tracking_service import TrackingServiceV4
                        tracking_service = TrackingServiceV4()
                    
                        # Recuperar dados de tracking do bot_user
                        fbclid = getattr(bot_user, 'fbclid', None) if bot_user else None
                        utm_source = getattr(bot_user, 'utm_source', None) if bot_user else None
                        utm_medium = getattr(bot_user, 'utm_medium', None) if bot_user else None
                        utm_campaign = getattr(bot_user, 'utm_campaign', None) if bot_user else None
                        utm_content = getattr(bot_user, 'utm_content', None) if bot_user else None
                        utm_term = getattr(bot_user, 'utm_term', None) if bot_user else None
                    
                        redis_tracking_payload: Dict[str, Any] = {}
                        if not is_remarketing:
                            tracking_token = None

                        # ✅ CORREÇÃO CRÍTICA QI 1000+: PRIORIDADE MÁXIMA para bot_user.tracking_session_id
                        # Isso garante que o token do public_redirect seja SEMPRE usado (tem todos os dados: client_ip, client_user_agent, pageview_event_id)
                        # PROBLEMA IDENTIFICADO: Verificação estava DEPOIS de tracking:last_token e tracking:chat
                        # SOLUÇÃO: Verificar bot_user.tracking_session_id PRIMEIRO (antes de tudo)
                        # ✅ CORREÇÃO CRÍTICA V15: Se token gerado detectado, tentar recuperar token UUID correto via fbclid
                        if is_remarketing:
                            if bot_user and bot_user.tracking_session_id:
                                tracking_token = bot_user.tracking_session_id
                                token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                logger.info(f"✅ [REMARKETING] Forçando tracking_token do BotUser.tracking_session_id: {token_log}...")
                            else:
                                tracking_token = None
                                logger.error(f"❌ [REMARKETING] BotUser sem tracking_session_id - Payment será criado sem tracking_token (atribuição prejudicada)")
                        elif bot_user and bot_user.tracking_session_id and not is_remarketing:
                            tracking_token = bot_user.tracking_session_id
                            token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                            logger.info(f"✅ Tracking token recuperado de bot_user.tracking_session_id (PRIORIDADE MÁXIMA): {token_log}...")
                        
                            # ✅ CORREÇÃO CRÍTICA V15: Validar se token é gerado e tentar recuperar token UUID correto
                            is_generated_token = tracking_token.startswith('tracking_')
                            if is_generated_token:
                                token_log_30 = tracking_token[:30] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                logger.error(f"❌ [GENERATE PIX] bot_user.tracking_session_id contém token GERADO: {token_log_30}...")
                                logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                logger.error(f"   Tentando recuperar token UUID correto via fbclid...")
                            
                                # ✅ ESTRATÉGIA DE RECUPERAÇÃO: Tentar recuperar token UUID via fbclid
                                if bot_user and getattr(bot_user, 'fbclid', None):
                                    try:
                                        fbclid_from_botuser = bot_user.fbclid
                                        tracking_token_key = f"tracking:fbclid:{fbclid_from_botuser}"
                                        recovered_token_from_fbclid = tracking_service.redis.get(tracking_token_key)
                                        if recovered_token_from_fbclid:
                                            # ✅ Validar que token recuperado é UUID (não gerado)
                                            # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                            normalized_recovered = recovered_token_from_fbclid.replace('-', '').lower()
                                            is_recovered_uuid = len(normalized_recovered) == 32 and all(c in '0123456789abcdef' for c in normalized_recovered)
                                            if is_recovered_uuid:
                                                tracking_token = recovered_token_from_fbclid
                                                token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                logger.info(f"✅ [GENERATE PIX] Token UUID correto recuperado via fbclid: {token_log}...")
                                                logger.info(f"   Atualizando bot_user.tracking_session_id com token UUID correto")
                                                bot_user.tracking_session_id = tracking_token
                                            else:
                                                logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via fbclid tem formato inválido: {recovered_token_from_fbclid[:30]}... (len={len(recovered_token_from_fbclid)}) - IGNORANDO")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Erro ao recuperar token UUID via fbclid: {e}")
                                else:
                                    logger.warning(f"⚠️ [GENERATE PIX] bot_user.fbclid ausente - não é possível recuperar token UUID correto")
                        
                            # ✅ Tentar recuperar payload completo do Redis
                            try:
                                recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                                if recovered_payload:
                                    redis_tracking_payload = recovered_payload
                                    logger.info(f"✅ Tracking payload recuperado do bot_user.tracking_session_id: fbp={'✅' if recovered_payload.get('fbp') else '❌'}, fbc={'✅' if recovered_payload.get('fbc') else '❌'}, ip={'✅' if recovered_payload.get('client_ip') else '❌'}, ua={'✅' if recovered_payload.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload.get('pageview_event_id') else '❌'}")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao recuperar payload do bot_user.tracking_session_id: {e}")
                        elif bot_user:
                            logger.warning(f"⚠️ BotUser {bot_user.id} encontrado mas tracking_session_id está vazio (telegram_user_id: {customer_user_id})")

                        # ✅ FALLBACK 1: tracking:last_token (se bot_user.tracking_session_id não existir)
                        # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de usar
                        if not is_remarketing and not tracking_token and customer_user_id:
                            try:
                                cached_token = tracking_service.redis.get(f"tracking:last_token:user:{customer_user_id}")
                                if cached_token:
                                    # ✅ CORREÇÃO V16: Validar token antes de usar
                                    is_generated_token = cached_token.startswith('tracking_')
                                    # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                    normalized_cached = cached_token.replace('-', '').lower()
                                    is_uuid_token = len(normalized_cached) == 32 and all(c in '0123456789abcdef' for c in normalized_cached)
                                
                                    if is_generated_token:
                                        logger.error(f"❌ [GENERATE PIX] Token recuperado de tracking:last_token é GERADO: {cached_token[:30]}... - IGNORANDO")
                                        logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                        # ✅ NÃO usar token gerado
                                    elif is_uuid_token:
                                        tracking_token = cached_token
                                        token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                        logger.info(f"✅ Tracking token recuperado de tracking:last_token:user:{customer_user_id}: {token_log}...")
                                    else:
                                        logger.warning(f"⚠️ [GENERATE PIX] Token recuperado de tracking:last_token tem formato inválido: {cached_token[:30]}... (len={len(cached_token)}) - IGNORANDO")
                            except Exception:
                                logger.exception("Falha ao recuperar tracking:last_token do Redis")
                    
                        # ✅ FALLBACK 2: tracking:chat (se bot_user.tracking_session_id não existir)
                        # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de usar
                        # ✅ REGRA: Remarketing NÃO pode gerar/substituir tracking_token aqui
                        if not is_remarketing and not tracking_token and customer_user_id:
                            try:
                                cached_payload = tracking_service.redis.get(f"tracking:chat:{customer_user_id}")
                                if cached_payload:
                                    redis_tracking_payload = json.loads(cached_payload)
                                    recovered_token_from_chat = redis_tracking_payload.get("tracking_token")
                                    if recovered_token_from_chat:
                                        # ✅ CORREÇÃO V16: Validar token antes de usar
                                        is_generated_token = recovered_token_from_chat.startswith('tracking_')
                                        # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                        normalized_chat = recovered_token_from_chat.replace('-', '').lower()
                                        is_uuid_token = len(normalized_chat) == 32 and all(c in '0123456789abcdef' for c in normalized_chat)
                                    
                                        if is_generated_token:
                                            logger.error(f"❌ [GENERATE PIX] Token recuperado de tracking:chat é GERADO: {recovered_token_from_chat[:30]}... - IGNORANDO")
                                            logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                            # ✅ NÃO usar token gerado
                                        elif is_uuid_token:
                                            tracking_token = recovered_token_from_chat
                                            token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                            logger.info(f"✅ Tracking token recuperado de tracking:chat:{customer_user_id}: {token_log}...")
                                        else:
                                            logger.warning(f"⚠️ [GENERATE PIX] Token recuperado de tracking:chat tem formato inválido: {recovered_token_from_chat[:30]}... (len={len(recovered_token_from_chat)}) - IGNORANDO")
                            except Exception:
                                logger.exception("Falha ao recuperar tracking:chat do Redis")

                        tracking_data_v4: Dict[str, Any] = redis_tracking_payload if isinstance(redis_tracking_payload, dict) else {}

                        # HIDRATAR VARIÁVEIS A PARTIR DO REDIS (SE EXISTIR)
                        if tracking_data_v4:
                            fbc = tracking_data_v4.get("fbc")
                            fbp = tracking_data_v4.get("fbp")
                            fbclid = tracking_data_v4.get("fbclid")
                            pageview_event_id = tracking_data_v4.get("pageview_event_id")
                            redirect_id = tracking_data_v4.get("redirect_id")
                            meta_pixel_id = tracking_data_v4.get("pixel_id")
                            tracking_token = tracking_data_v4.get("tracking_token") or tracking_token

                        # CRÍTICO: Recuperar payload completo do Redis ANTES de gerar valores sintéticos
                        if tracking_token:
                            recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                            if recovered_payload:
                                tracking_data_v4 = recovered_payload
                                fbc = tracking_data_v4.get("fbc")
                                fbp = tracking_data_v4.get("fbp")
                                fbclid = tracking_data_v4.get("fbclid")
                                pageview_event_id = tracking_data_v4.get("pageview_event_id")
                                redirect_id = tracking_data_v4.get("redirect_id")
                                meta_pixel_id = tracking_data_v4.get("pixel_id")
                                tracking_token = tracking_data_v4.get("tracking_token") or tracking_token
                                token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                logger.info(f" Tracking payload recuperado do Redis para token {token_log}... | fbp={'ok' if fbp else 'missing'} | fbc={'ok' if fbc else 'missing'} | pageview_event_id={'ok' if pageview_event_id else 'missing'}")
                            elif not tracking_data_v4:
                                logger.warning(" Tracking token %s sem payload no Redis - tentando reconstruir via BotUser", tracking_token)
                            # CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                            # NUNCA atualizar com token gerado (deve ser UUID de 32 chars do redirect)
                            if bot_user and tracking_token:
                                is_generated_token = tracking_token.startswith('tracking_')
                                normalized_token_check = tracking_token.replace('-', '').lower()
                                is_uuid_token = len(normalized_token_check) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check)
                                if is_uuid_token and bot_user.tracking_session_id != tracking_token:
                                    bot_user.tracking_session_id = tracking_token
                                    token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                    logger.info(f" bot_user.tracking_session_id atualizado com token do redirect: {token_log}...")

                        # NOTA: bot_user.tracking_session_id já foi verificado no início (prioridade máxima)
                        # Não precisa verificar novamente aqui
                    
                        if not tracking_token:
                            # ESTRATÉGIA 1: Tentar recuperar tracking_token do Redis usando fbclid do BotUser
                            # ✅ ESTRATÉGIA 1: Tentar recuperar tracking_token do Redis usando fbclid do BotUser
                            # Isso recupera o token original do redirect mesmo se bot_user.tracking_session_id estiver vazio
                            recovered_token_from_fbclid = None
                            if bot_user and getattr(bot_user, 'fbclid', None):
                                try:
                                    # ✅ CRÍTICO: Buscar tracking_token no Redis via fbclid (chave: tracking:fbclid:{fbclid})
                                    fbclid_from_botuser = bot_user.fbclid
                                    tracking_token_key = f"tracking:fbclid:{fbclid_from_botuser}"
                                    recovered_token_from_fbclid = tracking_service.redis.get(tracking_token_key)
                                    if recovered_token_from_fbclid:
                                        # ✅ Token encontrado via fbclid - recuperar payload completo
                                        tracking_token = recovered_token_from_fbclid
                                        token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                        logger.info(f"✅ Tracking token recuperado do Redis via fbclid do BotUser: {token_log}...")
                                        recovered_payload_from_fbclid = tracking_service.recover_tracking_data(tracking_token) or {}
                                        if recovered_payload_from_fbclid:
                                            tracking_data_v4 = recovered_payload_from_fbclid
                                            logger.info(f"✅ Tracking payload recuperado via fbclid: fbp={'✅' if recovered_payload_from_fbclid.get('fbp') else '❌'}, fbc={'✅' if recovered_payload_from_fbclid.get('fbc') else '❌'}, ip={'✅' if recovered_payload_from_fbclid.get('client_ip') else '❌'}, ua={'✅' if recovered_payload_from_fbclid.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload_from_fbclid.get('pageview_event_id') else '❌'}")
                                            # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                                            # Token recuperado via fbclid deve ser UUID (vem do redirect)
                                            if bot_user and tracking_token:
                                                is_generated_token = tracking_token.startswith('tracking_')
                                                # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                                normalized_token_check2 = tracking_token.replace('-', '').lower()
                                                is_uuid_token = len(normalized_token_check2) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check2)
                                            
                                                if is_generated_token:
                                                    token_log_30 = tracking_token[:30] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                    logger.error(f"❌ [GENERATE PIX] Token recuperado via fbclid é GERADO: {token_log_30}... - NÃO atualizar bot_user.tracking_session_id")
                                                elif is_uuid_token:
                                                    if bot_user.tracking_session_id != tracking_token:
                                                        bot_user.tracking_session_id = tracking_token
                                                        token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                        logger.info(f"✅ bot_user.tracking_session_id atualizado com token recuperado via fbclid: {token_log}...")
                                                else:
                                                    token_log_30 = tracking_token[:30] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                    len_log = len(tracking_token) if tracking_token else 'N/A'
                                                    logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via fbclid tem formato inválido: {token_log_30}... (len={len_log})")
                                except Exception as e:
                                    logger.warning(f"⚠️ Erro ao recuperar tracking_token via fbclid do BotUser: {e}")
                        
                            # ✅ ESTRATÉGIA 2: Tentar recuperar de tracking:chat:{customer_user_id}
                            if not tracking_token and bot_user:
                                try:
                                    chat_key = f"tracking:chat:{customer_user_id}"
                                    chat_payload_raw = tracking_service.redis.get(chat_key)
                                    if chat_payload_raw:
                                        try:
                                            chat_payload = json.loads(chat_payload_raw)
                                            recovered_token_from_chat = chat_payload.get('tracking_token')
                                            if recovered_token_from_chat:
                                                tracking_token = recovered_token_from_chat
                                                token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                logger.info(f"✅ Tracking token recuperado de tracking:chat:{customer_user_id}: {token_log}...")
                                                recovered_payload_from_chat = tracking_service.recover_tracking_data(tracking_token) or {}
                                                if recovered_payload_from_chat:
                                                    tracking_data_v4 = recovered_payload_from_chat
                                                    logger.info(f"✅ Tracking payload recuperado via chat: fbp={'✅' if recovered_payload_from_chat.get('fbp') else '❌'}, fbc={'✅' if recovered_payload_from_chat.get('fbc') else '❌'}, ip={'✅' if recovered_payload_from_chat.get('client_ip') else '❌'}, ua={'✅' if recovered_payload_from_chat.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload_from_chat.get('pageview_event_id') else '❌'}")
                                                    # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                                                    # Token recuperado via chat deve ser UUID (vem do redirect)
                                                    if bot_user and tracking_token:
                                                        is_generated_token = tracking_token.startswith('tracking_')
                                                        # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                                        normalized_token_check3 = tracking_token.replace('-', '').lower()
                                                        is_uuid_token = len(normalized_token_check3) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check3)
                                                    
                                                        if is_generated_token:
                                                            token_log_30 = tracking_token[:30] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                            logger.error(f"❌ [GENERATE PIX] Token recuperado via chat é GERADO: {token_log_30}... - NÃO atualizar bot_user.tracking_session_id")
                                                        elif is_uuid_token:
                                                            if bot_user.tracking_session_id != tracking_token:
                                                                bot_user.tracking_session_id = tracking_token
                                                                token_log = tracking_token[:20] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                                logger.info(f"✅ bot_user.tracking_session_id atualizado com token recuperado via chat: {token_log}...")
                                                        else:
                                                            token_log_30 = tracking_token[:30] if tracking_token and isinstance(tracking_token, str) else 'N/A'
                                                            len_log = len(tracking_token) if tracking_token else 'N/A'
                                                            logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via chat tem formato inválido: {token_log_30}... (len={len_log})")
                                        except Exception as e:
                                            logger.warning(f"⚠️ Erro ao parsear chat_payload: {e}")
                                except Exception as e:
                                    logger.warning(f"⚠️ Erro ao recuperar tracking_token de tracking:chat: {e}")
                        
                            # ✅ CORREÇÃO CRÍTICA V17: Se PIX foi gerado com sucesso, SEMPRE criar Payment
                            # tracking_token ausente não deve bloquear criação de Payment se PIX já foi gerado
                            # Isso evita perder vendas quando gateway gera PIX mas tracking_token não está disponível
                            if not tracking_token:
                                # ✅ Verificar se PIX foi gerado com sucesso (pix_result existe e tem transaction_id)
                                if pix_result and pix_result.get('transaction_id'):
                                    gateway_transaction_id_temp = pix_result.get('transaction_id')
                                    logger.warning(f"⚠️ [TOKEN AUSENTE] tracking_token AUSENTE - PIX já foi gerado (transaction_id: {gateway_transaction_id_temp})")
                                    logger.warning(f"   Isso indica que o usuário NÃO passou pelo redirect ou tracking_session_id não foi salvo")
                                    logger.warning(f"   bot_user.tracking_session_id: {getattr(bot_user, 'tracking_session_id', None) if bot_user else 'N/A'}")
                                    logger.warning(f"   bot_user.fbclid: {getattr(bot_user, 'fbclid', None) if bot_user else 'N/A'}")
                                    logger.warning(f"   Payment será criado mesmo sem tracking_token para evitar perder venda")
                                    logger.warning(f"   Meta Pixel Purchase terá atribuição reduzida (sem pageview_event_id)")
                                    # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                                    # tracking_token será None no Payment
                                else:
                                    # ✅ PIX não foi gerado - pode falhar normalmente
                                    error_msg = f"❌ [TOKEN AUSENTE] tracking_token AUSENTE e PIX não foi gerado para BotUser {bot_user.id if bot_user else 'N/A'} (customer_user_id: {customer_user_id})"
                                    logger.error(error_msg)
                                    logger.error(f"   Isso indica que o usuário NÃO passou pelo redirect ou tracking_session_id não foi salvo")
                                    logger.error(f"   bot_user.tracking_session_id: {getattr(bot_user, 'tracking_session_id', None) if bot_user else 'N/A'}")
                                    logger.error(f"   bot_user.fbclid: {getattr(bot_user, 'fbclid', None) if bot_user else 'N/A'}")
                                    logger.error(f"   SOLUÇÃO: Usuário deve acessar link de redirect primeiro: /go/{{slug}}?grim=...&fbclid=...")
                                    logger.error(f"   Payment NÃO será criado sem tracking_token válido e sem PIX gerado")
                                
                                    # ✅ FALHAR: Não gerar token, não criar Payment sem tracking_token válido E sem PIX
                                    raise ValueError(
                                        f"tracking_token ausente e PIX não gerado - usuário deve acessar link de redirect primeiro. "
                                        f"BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id. "
                                        f"SOLUÇÃO: Acessar /go/{{slug}}?grim=...&fbclid=... antes de gerar PIX"
                                    )
                        if not tracking_data_v4:
                            tracking_data_v4 = tracking_service.recover_tracking_data(tracking_token) or {}
                    
                        # Enriquecer com dados do BotUser quando faltarem no payload
                        enrichment_source = {
                            "fbclid": fbclid,
                            "utm_source": utm_source,
                            "utm_medium": utm_medium,
                            "utm_campaign": utm_campaign,
                            "utm_content": utm_content,
                            "utm_term": utm_term,
                            "grim": getattr(bot_user, 'campaign_code', None) if bot_user else None,
                        }
                        for key, value in enrichment_source.items():
                            if value and key not in tracking_data_v4:
                                tracking_data_v4[key] = value
                    
                        if tracking_data_v4.get('fbclid'):
                            fbclid = tracking_data_v4['fbclid']
                        if tracking_data_v4.get('utm_source'):
                            utm_source = tracking_data_v4['utm_source']
                        if tracking_data_v4.get('utm_medium'):
                            utm_medium = tracking_data_v4['utm_medium']
                        if tracking_data_v4.get('utm_campaign'):
                            utm_campaign = tracking_data_v4['utm_campaign']
                        if tracking_data_v4.get('utm_content'):
                            fbp_log = fbp[:30] if fbp and isinstance(fbp, str) else 'N/A'
                            logger.info(f"✅ fbp recuperado do tracking_data_v4: {fbp_log}...")
                    
                        # ✅ CRÍTICO: NUNCA gerar fbc sintético em generate_pix_payment
                        # O fbc deve vir EXATAMENTE do redirect (cookie do browser)
                        # Gerar sintético aqui quebra a atribuição porque o timestamp não corresponde ao clique original
                        if fbc is not None:
                            fbc_log = fbc[:30] if fbc and isinstance(fbc, str) else 'N/A'
                            logger.info(f"✅ fbc recuperado do tracking_data_v4: {fbc_log}...")
                        else:
                            logger.warning(f"⚠️ fbc não encontrado no tracking_data_v4 - NÃO gerando sintético (preservando atribuição)")
                            # ✅ NÃO gerar fbc sintético - deixar None e confiar no fallback do Purchase
                    
                        if pageview_event_id:
                            logger.info(f"✅ pageview_event_id recuperado do tracking_data_v4: {pageview_event_id}")
                        else:
                            # ✅ FALLBACK: Tentar recuperar do bot_user (se houver tracking_session_id)
                            if bot_user and bot_user.tracking_session_id:
                                try:
                                    # ✅ CORREÇÃO: Usar tracking_service (já instanciado acima) ao invés de tracking_service_v4
                                    fallback_tracking = tracking_service.recover_tracking_data(bot_user.tracking_session_id)
                                    pageview_event_id = fallback_tracking.get('pageview_event_id')
                                    if pageview_event_id:
                                        logger.info(f"✅ pageview_event_id recuperado do bot_user.tracking_session_id: {pageview_event_id}")
                                except Exception as e:
                                    logger.warning(f"⚠️ Erro ao recuperar pageview_event_id do bot_user: {e}")
                        
                            if not pageview_event_id:
                                logger.warning(f"⚠️ pageview_event_id não encontrado no tracking_data_v4 nem no bot_user - Purchase pode não fazer dedup perfeito")
                    
                        # Gerar external_ids com dados reais recuperados
                        external_ids = tracking_service.build_external_id_array(
                            fbclid=fbclid,
                            telegram_user_id=str(customer_user_id),
                            email=getattr(bot_user, 'email', None) if bot_user else None,
                            phone=getattr(bot_user, 'phone', None) if bot_user else None
                        )
                    
                        tracking_update_payload = {
                            "tracking_token": tracking_token,
                            "bot_id": bot_id,
                            "customer_user_id": customer_user_id,
                            "fbclid": fbclid,
                            "fbp": fbp,
                            # ✅ CRÍTICO: Só incluir fbc se for válido (não None)
                            # Não sobrescrever fbc válido do Redis com None
                            **({"fbc": fbc} if fbc is not None else {}),
                            "pageview_event_id": pageview_event_id,
                            "pageview_ts": tracking_data_v4.get('pageview_ts'),
                            "grim": tracking_data_v4.get('grim'),
                            "utm_source": utm_source,
                            "utm_medium": utm_medium,
                            "utm_campaign": utm_campaign,
                            "utm_content": utm_content,
                            "utm_term": utm_term,
                            "external_ids": external_ids,
                            "updated_from": "generate_pix_payment",
                        }
                        # ✅ CRÍTICO: Filtrar None/vazios para não sobrescrever dados válidos no Redis
                        tracking_service.save_tracking_token(tracking_token, {k: v for k, v in tracking_update_payload.items() if v})
                    
                        logger.info("Tracking token pronto: %s | fbp=%s | fbc=%s | pageview=%s", tracking_token, 'ok' if fbp else 'missing', 'ok' if fbc else 'missing', 'ok' if pageview_event_id else 'missing')
                    
                        # ✅ CRÍTICO: Determinar status do payment
                        # Se recusado, usar 'failed' para que webhook possa atualizar
                        # Se não recusado, usar 'pending' normalmente
                        payment_status = 'failed' if is_refused else 'pending'
                    
                        # ✅ CRÍTICO: Extrair transaction_id/hash (prioridade: transaction_id > transaction_hash)
                        gateway_transaction_id = (
                            pix_result.get('transaction_id') or 
                            pix_result.get('transaction_hash') or 
                            None
                        )
                    
                        # ✅ CRÍTICO: Extrair gateway_hash (campo 'hash' da resposta) para webhook matching
                        gateway_hash = pix_result.get('gateway_hash') or pix_result.get('transaction_hash')
                    
                        # ✅ CRÍTICO: Extrair reference para matching no webhook
                        reference = pix_result.get('reference')
                    
                        # ✅ PATCH 2 QI 200: Salvar product_hash se foi criado dinamicamente
                        if gateway.gateway_type in ['atomopay', 'umbrellapag'] and payment_gateway:
                            # Verificar se product_hash foi criado dinamicamente
                            current_product_hash = getattr(payment_gateway, 'product_hash', None)
                            if current_product_hash and current_product_hash != original_product_hash:
                                gateway.product_hash = current_product_hash
                                logger.info(f"💾 Product Hash criado dinamicamente e salvo no Gateway: {current_product_hash[:12]}...")
                    
                        # ✅ CRÍTICO: Extrair producer_hash para identificar conta do usuário (multi-tenant)
                        # Salvar no Gateway para que webhook possa identificar qual usuário enviou
                        producer_hash = pix_result.get('producer_hash')
                        if producer_hash and gateway.gateway_type == 'atomopay':
                            # ✅ Salvar producer_hash no Gateway (se ainda não tiver)
                            if not gateway.producer_hash:
                                gateway.producer_hash = producer_hash
                                logger.info(f"💾 Producer Hash salvo no Gateway: {producer_hash[:12]}...")
                    
                        # ✅ PATCH 2 & 3 QI 200: Commit de todas as alterações do Gateway
                        if gateway.gateway_type in ['atomopay', 'umbrellapag']:
                            db.session.commit()
                            if gateway.gateway_type == 'atomopay':
                                logger.info(f"💾 Gateway atualizado (product_hash, producer_hash)")
                            else:
                                logger.info(f"💾 Gateway atualizado (product_hash)")
                    
                        logger.info(f"💾 Salvando Payment com dados do gateway:")
                        logger.info(f"   payment_id: {payment_id}")
                        logger.info(f"   gateway_transaction_id: {gateway_transaction_id}")
                        logger.info(f"   gateway_hash: {gateway_hash}")
                        logger.info(f"   producer_hash: {producer_hash}")  # ✅ Para identificar conta do usuário
                        logger.info(f"   reference: {reference}")
                    
                        # ✅ CORREÇÃO CRÍTICA V17: VALIDAR tracking_token antes de criar Payment
                        # Se PIX foi gerado com sucesso, SEMPRE criar Payment (mesmo sem tracking_token)
                        # Isso evita perder vendas quando gateway gera PIX mas tracking_token não está disponível
                        if not tracking_token:
                            # ✅ Verificar se PIX foi gerado com sucesso (pix_result existe e tem transaction_id)
                            transaction_id_from_result = pix_result.get('transaction_id') if pix_result else None
                            if pix_result and transaction_id_from_result:
                                logger.warning(f"⚠️ [TOKEN AUSENTE] tracking_token AUSENTE - PIX já foi gerado (transaction_id: {transaction_id_from_result})")
                                logger.warning(f"   BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id")
                                logger.warning(f"   Payment será criado mesmo sem tracking_token para evitar perder venda")
                                logger.warning(f"   Meta Pixel Purchase terá atribuição reduzida (sem pageview_event_id)")
                                # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                                # tracking_token será None no Payment
                            else:
                                # ✅ PIX não foi gerado - pode falhar normalmente
                                error_msg = f"❌ [TOKEN AUSENTE] tracking_token AUSENTE e PIX não foi gerado - Payment NÃO será criado"
                                logger.error(error_msg)
                                logger.error(f"   BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id")
                                logger.error(f"   SOLUÇÃO: Usuário deve acessar link de redirect primeiro: /go/{{slug}}?grim=...&fbclid=...")
                                raise ValueError("tracking_token ausente e PIX não gerado - Payment não pode ser criado sem tracking_token válido e sem PIX")
                    
                        # ✅ CORREÇÃO V17: Validar tracking_token apenas se não for None
                        # ✅ CORREÇÃO CRÍTICA: Aceitar UUID com hífens (36 chars) OU sem hífens (32 chars)
                        is_generated_token = False
                        is_uuid_token = False
                    
                        if tracking_token:
                            is_generated_token = tracking_token.startswith('tracking_')
                        
                            # ✅ CORREÇÃO: Normalizar UUID removendo hífens para validação
                            # UUIDs podem vir em dois formatos:
                            # 1. Com hífens: faeac7b2-d4eb-4968-bf3b-87cad1b2bd5a (36 chars)
                            # 2. Sem hífens: faeac7b2d4eb4968bf3b87cad1b2bd5a (32 chars)
                            normalized_token = tracking_token.replace('-', '').lower()
                            is_uuid_token = len(normalized_token) == 32 and all(c in '0123456789abcdef' for c in normalized_token)
                        
                            # ✅ CORREÇÃO V14: Se PIX foi gerado com sucesso, permitir criar Payment mesmo com token gerado
                            # Isso evita perder vendas quando o gateway gera PIX mas o tracking_token não é ideal
                            # O warning será logado mas o Payment será criado para que o webhook possa processar
                            if is_generated_token:
                                logger.warning(f"⚠️ [TOKEN LEGADO] tracking_token LEGADO detectado: {tracking_token[:30]}...")
                                logger.warning(f"   PIX foi gerado com sucesso (transaction_id: {gateway_transaction_id})")
                                logger.warning(f"   Payment será criado mesmo com token legado para evitar perder venda")
                                logger.warning(f"   Meta Pixel Purchase pode ter atribuição reduzida (sem pageview_event_id)")
                                # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                        
                            if not is_uuid_token and not is_generated_token:
                                error_msg = f"❌ [GENERATE PIX] tracking_token com formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})"
                                logger.error(error_msg)
                                logger.error(f"   Payment NÃO será criado com token inválido")
                                logger.error(f"   tracking_token deve ser UUID (32 ou 36 chars, com ou sem hífens) ou gerado (tracking_*)")
                                raise ValueError(f"tracking_token com formato inválido - deve ser UUID (32 ou 36 chars) ou gerado (tracking_*)")
                        
                            # ✅ VALIDAÇÃO PASSOU - criar Payment
                            if is_uuid_token:
                                logger.info(f"✅ [TOKEN UUID] tracking_token validado: {tracking_token[:20]}... (UUID do redirect, len={len(tracking_token)})")
                            else:
                                logger.info(f"⚠️ [TOKEN LEGADO] tracking_token legado: {tracking_token[:20]}... (será usado mesmo assim)")
                        else:
                            # ✅ tracking_token é None - já foi logado como warning acima
                            logger.info(f"⚠️ [TOKEN AUSENTE] Payment será criado sem tracking_token (PIX já foi gerado)")
                    
                        # ✅ SISTEMA DE ASSINATURAS - Preparar dados de subscription
                        button_data_for_subscription = None
                        has_subscription_flag = False
                    
                        if button_config:
                            # Se button_config foi fornecido diretamente, usar
                            button_data_for_subscription = button_config.copy()
                            has_subscription_flag = button_config.get('subscription', {}).get('enabled', False)
                        elif button_index is not None:
                            # Se button_index foi fornecido, buscar do config do bot
                            if bot and bot.config:
                                config_dict = bot.config.to_dict()
                                main_buttons = config_dict.get('main_buttons', [])
                                if button_index < len(main_buttons):
                                    button_data_for_subscription = main_buttons[button_index].copy()
                                    has_subscription_flag = button_data_for_subscription.get('subscription', {}).get('enabled', False)
                    
                        # ✅ CORREÇÃO: Importar json localmente para evitar UnboundLocalError
                        import json as json_module
                    
                        # Salvar pagamento no banco (incluindo código PIX para reenvio + analytics)
                        # ✅ CRÍTICO: Preparar dados para Payment
                        # Determinar se é downsell, upsell ou normal
                        is_downsell_final = is_downsell or False
                        is_upsell_final = is_upsell or False
                    
                        payment = Payment(
                            bot_id=bot_id,  # ✅ OBRIGATÓRIO: ID do bot
                            payment_id=payment_id,  # ✅ OBRIGATÓRIO: ID único do pagamento
                            gateway_type=gateway.gateway_type if gateway else None,  # ✅ OBRIGATÓRIO: tipo do gateway
                            gateway_transaction_id=gateway_transaction_id,  # ✅ OBRIGATÓRIO: ID da transação
                            gateway_transaction_hash=gateway_hash,  # ✅ CRÍTICO: gateway_hash (campo 'hash' da resposta) para webhook matching
                            payment_method=str(pix_result.get('payment_method') or pix_result.get('paymentMethod') or 'PIX')[:20] if pix_result else 'PIX',
                            amount=amount,
                            customer_name=customer_name,
                            customer_username=customer_username,
                            customer_user_id=customer_user_id,
                            # ✅ CRÍTICO: Salvar email, phone e document do customer_data (para Meta Pixel Purchase)
                            customer_email=customer_data.get('email'),
                            customer_phone=customer_data.get('phone'),
                            customer_document=customer_data.get('document'),
                            product_name=description,
                            product_description=pix_result.get('pix_code'),  # Salvar código PIX para reenvio (None se recusado)
                            status=payment_status,  # ✅ 'failed' se recusado, 'pending' se não
                            # ✅ CRÍTICO: tracking_token do redirect para matching PageView → Purchase
                            tracking_token=tracking_token if tracking_token else None,
                            # Analytics tracking
                            order_bump_shown=order_bump_shown,
                            order_bump_accepted=order_bump_accepted,
                            order_bump_value=order_bump_value,
                            is_downsell=is_downsell,
                            downsell_index=downsell_index,
                            is_upsell=is_upsell_final,  # ✅ NOVO - UPSELLS
                            upsell_index=upsell_index,  # ✅ NOVO - UPSELLS
                            is_remarketing=is_remarketing,  # ✅ NOVO - REMARKETING
                            remarketing_campaign_id=remarketing_campaign_id,  # ✅ NOVO - REMARKETING
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
                            # ✅ CRÍTICO: UTM TRACKING E CAMPAIGN CODE (grim) - PRIORIDADE: tracking_data_v4 > bot_user
                            # ✅ CORREÇÃO CRÍTICA: Usar UTMs do tracking_data_v4 (mais atualizados do redirect) ao invés de bot_user
                            utm_source=utm_source if utm_source is not None else (getattr(bot_user, 'utm_source', None) if bot_user else None),
                            utm_campaign=utm_campaign if utm_campaign is not None else (getattr(bot_user, 'utm_campaign', None) if bot_user else None),
                            utm_content=utm_content if utm_content is not None else (getattr(bot_user, 'utm_content', None) if bot_user else None),
                            utm_medium=utm_medium if utm_medium is not None else (getattr(bot_user, 'utm_medium', None) if bot_user else None),
                            utm_term=utm_term if utm_term is not None else (getattr(bot_user, 'utm_term', None) if bot_user else None),
                            # ✅ CRÍTICO QI 600+: campaign_code (grim) para atribuição de campanha
                            # PRIORIDADE: tracking_data_v4.grim > bot_user.campaign_code
                            campaign_code=tracking_data_v4.get('grim') if tracking_data_v4.get('grim') else (getattr(bot_user, 'campaign_code', None) if bot_user else None),
                            # ✅ CONTEXTO ORIGINAL DO CLIQUE (persistente para remarketing)
                            click_context_url=(
                                tracking_data_v4.get('event_source_url')
                                or getattr(bot_user, 'last_click_context_url', None)
                                or None
                            ),
                            # ✅ SISTEMA DE ASSINATURAS - Campos de subscription
                            button_index=button_index,
                            button_config=json_module.dumps(button_data_for_subscription, ensure_ascii=False) if button_data_for_subscription else None,
                            has_subscription=has_subscription_flag
                        )
                        db.session.add(payment)
                        db.session.flush()  # ✅ Flush para obter payment.id antes do commit
                    
                        # ✅ QI 500: Salvar tracking data no Redis (após criar payment para ter payment.id)
                        # ✅ CORREÇÃO V17: Só salvar se tracking_token não for None
                        # ✅ CORREÇÃO ROBUSTA: Não bloquear se Redis falhar
                        if tracking_token:
                            try:
                                tracking_service.save_tracking_data(
                                    tracking_token=tracking_token,
                                    bot_id=bot_id,
                                    customer_user_id=customer_user_id,
                                    payment_id=payment.id,
                                    fbclid=fbclid,
                                    fbp=fbp,
                                    fbc=fbc,
                                    utm_source=utm_source,
                                    utm_medium=utm_medium,
                                    utm_campaign=utm_campaign,
                                    external_ids=external_ids
                                )
                                logger.info(f"✅ Tracking data salvo no Redis para payment {payment.id}")
                            except Exception as redis_error:
                                logger.warning(f"⚠️ [REDIS INDISPONÍVEL] Erro ao salvar tracking data no Redis: {redis_error}")
                                logger.warning(f"   Payment {payment.id} foi criado mesmo assim (tracking data é opcional)")
                                # ✅ NÃO bloquear - continuar mesmo se Redis falhar
                        else:
                            logger.warning(f"⚠️ [TOKEN AUSENTE] Não salvando tracking data no Redis (tracking_token é None)")
                    
                        # ✅ ATUALIZAR CONTADOR DE TRANSAÇÕES DO GATEWAY
                        gateway.total_transactions += 1
                    
                        # ✅ CORREÇÃO ROBUSTA: Validação de integridade antes de commit
                        try:
                            db.session.commit()
                            logger.info(f"✅ Payment {payment.id} commitado com sucesso")
                        except IntegrityError as integrity_error:
                            db.session.rollback()
                            logger.error(f"❌ [ERRO DE INTEGRIDADE] Erro ao commitar Payment: {integrity_error}", exc_info=True)
                            logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                            logger.error(f"   Gateway Transaction ID: {gateway_transaction_id}")
                            return None
                        except Exception as commit_error:
                            db.session.rollback()
                            logger.error(f"❌ [ERRO AO COMMITAR] Erro ao commitar Payment: {commit_error}", exc_info=True)
                            logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                            return None

                        # ✅ QI 500: PAGEVIEW ENRICHMENT NO MOMENTO DO PIX (FONTE DE VERDADE = PAYMENT)
                        # Re-enviar o MESMO PageView (mesmo event_id) com em/ph quando houver alta confiança.
                        # Meta fará merge por event_id (não duplica PageView).
                        try:
                            resolved_pageview_event_id = (
                                pageview_event_id
                                or getattr(payment, 'pageview_event_id', None)
                                or getattr(bot_user, 'pageview_event_id', None)
                            )
                            logger.info(
                                "🔎 ENRICHMENT CHECK | PIX",
                                extra={
                                    "payment_db_id": getattr(payment, 'id', None),
                                    "payment_id": getattr(payment, 'payment_id', None),
                                    "pageview_event_id": pageview_event_id,
                                    "resolved_pageview_event_id": resolved_pageview_event_id,
                                    "tracking_token": tracking_token,
                                    "has_customer_email": bool(getattr(payment, 'customer_email', None)),
                                    "has_customer_phone": bool(getattr(payment, 'customer_phone', None)),
                                    "pool_bot": bool(pool_bot),
                                    "meta_enabled": bool(pool_bot and pool_bot.pool and pool_bot.pool.meta_tracking_enabled),
                                    "meta_pageview_enabled": bool(pool_bot and pool_bot.pool and pool_bot.pool.meta_events_pageview)
                                }
                            )
                            if resolved_pageview_event_id and pool_bot and pool_bot.pool and pool_bot.pool.meta_tracking_enabled and pool_bot.pool.meta_events_pageview:
                                pool_for_meta = pool_bot.pool

                                customer_email = getattr(payment, 'customer_email', None)
                                customer_phone = getattr(payment, 'customer_phone', None)

                                def _is_high_confidence_email(email_value: str) -> bool:
                                    if not email_value or not isinstance(email_value, str):
                                        return False
                                    email_clean = email_value.strip().lower()
                                    if '@' not in email_clean:
                                        return False
                                    if email_clean.endswith('@telegram.local'):
                                        return False
                                    if email_clean.startswith('user_') and email_clean.endswith('@telegram.local'):
                                        return False
                                    return len(email_clean) >= 6

                                def _is_high_confidence_phone(phone_value: str) -> bool:
                                    if not phone_value or not isinstance(phone_value, str):
                                        return False
                                    digits = ''.join(filter(str.isdigit, phone_value))
                                    if len(digits) < 10:
                                        return False
                                    if digits in ('11999999999', '00000000000'):
                                        return False
                                    return True

                                should_enrich = _is_high_confidence_email(customer_email) or _is_high_confidence_phone(customer_phone)
                                if should_enrich:
                                    if not resolved_pageview_event_id:
                                        logger.warning(
                                            "🚨 PAGEVIEW_EVENT_ID AUSENTE | Enrichment impossível",
                                            extra={
                                                "payment_db_id": getattr(payment, 'id', None),
                                                "payment_id": getattr(payment, 'payment_id', None),
                                                "tracking_token": tracking_token,
                                                "bot_user_id": getattr(bot_user, 'id', None),
                                                "is_remarketing": bool(is_remarketing)
                                            }
                                        )
                                        return

                                    enrichment_lock_key = f"meta:pageview_enriched:{resolved_pageview_event_id}"
                                    lock_ttl_seconds = 60 * 60 * 24 * 30  # 30 dias

                                    lock_acquired = False
                                    try:
                                        lock_acquired = bool(tracking_service.redis.set(enrichment_lock_key, '1', nx=True, ex=lock_ttl_seconds))
                                    except Exception as lock_error:
                                        logger.warning(f"⚠️ [META PAGEVIEW ENRICH] Falha ao criar lock Redis: {lock_error}")

                                    logger.info(
                                        "🔎 ENRICHMENT LOCK RESULT",
                                        extra={
                                            "enrichment_lock_key": enrichment_lock_key,
                                            "lock_ttl_seconds": lock_ttl_seconds,
                                            "lock_acquired": bool(lock_acquired)
                                        }
                                    )

                                    if lock_acquired:
                                        from celery_app import send_meta_event
                                        from utils.encryption import decrypt
                                        from utils.meta_pixel import MetaPixelAPI

                                        try:
                                            access_token = decrypt(pool_for_meta.meta_access_token)
                                        except Exception as decrypt_error:
                                            logger.error(f"❌ [META PAGEVIEW ENRICH] Erro ao descriptografar access_token do pool {pool_for_meta.id}: {decrypt_error}")
                                            access_token = None

                                        if access_token:
                                            # IP/UA/FBP/FBC: pegar do tracking_data_v4, com fallback em Payment
                                            ip_value_for_enrich = tracking_data_v4.get('client_ip') or tracking_data_v4.get('ip') or tracking_data_v4.get('client_ip_address')
                                            if ip_value_for_enrich and isinstance(ip_value_for_enrich, str) and '.AQYBAQIA' in ip_value_for_enrich:
                                                ip_value_for_enrich = ip_value_for_enrich.split('.AQYBAQIA')[0]

                                            ua_value_for_enrich = tracking_data_v4.get('client_user_agent') or tracking_data_v4.get('ua') or tracking_data_v4.get('client_ua')
                                            fbp_value_for_enrich = tracking_data_v4.get('fbp') or getattr(payment, 'fbp', None)
                                            fbc_value_for_enrich = tracking_data_v4.get('fbc') or getattr(payment, 'fbc', None)

                                            fbclid_for_enrich = tracking_data_v4.get('fbclid') or getattr(payment, 'fbclid', None)

                                            telegram_user_id_for_enrich = None
                                            if bot_user and getattr(bot_user, 'telegram_user_id', None):
                                                telegram_user_id_for_enrich = str(bot_user.telegram_user_id)
                                            elif customer_user_id:
                                                telegram_user_id_for_enrich = str(customer_user_id).replace('user_', '')

                                            external_id_list = []
                                            if fbclid_for_enrich and isinstance(fbclid_for_enrich, str) and fbclid_for_enrich.strip():
                                                external_id_list.append(fbclid_for_enrich.strip())
                                            if telegram_user_id_for_enrich and telegram_user_id_for_enrich.strip():
                                                external_id_list.append(telegram_user_id_for_enrich.strip())

                                            user_data_enriched = MetaPixelAPI._build_user_data(
                                                customer_user_id=telegram_user_id_for_enrich,
                                                external_id=external_id_list,
                                                email=customer_email if _is_high_confidence_email(customer_email) else None,
                                                phone=customer_phone if _is_high_confidence_phone(customer_phone) else None,
                                                client_ip=ip_value_for_enrich,
                                                client_user_agent=ua_value_for_enrich,
                                                fbp=fbp_value_for_enrich,
                                                fbc=fbc_value_for_enrich
                                            )

                                            event_source_url_enrich = tracking_data_v4.get('event_source_url') or tracking_data_v4.get('first_page')

                                            pageview_enriched_event = {
                                                'event_name': 'PageView',
                                                'event_time': int(time.time()),
                                                'event_id': resolved_pageview_event_id,
                                                'action_source': 'website',
                                                'event_source_url': event_source_url_enrich,
                                                'user_data': user_data_enriched,
                                                'custom_data': {
                                                    'source': 'pageview_enrichment',
                                                    'payment_id': getattr(payment, 'payment_id', None),
                                                    'payment_db_id': getattr(payment, 'id', None),
                                                    'gateway_type': getattr(payment, 'gateway_type', None)
                                                }
                                            }

                                            send_meta_event.delay(
                                                pixel_id=pool_for_meta.meta_pixel_id,
                                                access_token=access_token,
                                                event_data=pageview_enriched_event,
                                                test_code=pool_for_meta.meta_test_event_code
                                            )

                                            logger.info(
                                                f"✅ [META PAGEVIEW ENRICH] Enfileirado após PIX | event_id={resolved_pageview_event_id} | "
                                                f"em={'✅' if user_data_enriched.get('em') else '❌'} | ph={'✅' if user_data_enriched.get('ph') else '❌'}"
                                            )
                                    else:
                                        logger.info(f"ℹ️ [META PAGEVIEW ENRICH] Lock já existe (não reenviar) | key={enrichment_lock_key} | ttl={lock_ttl_seconds}s | event_id={resolved_pageview_event_id}")
                        except Exception as enrich_error:
                            logger.warning(f"⚠️ [META PAGEVIEW ENRICH] Falha ao enriquecer PageView após PIX (não bloqueia PIX): {enrich_error}")
                    
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
                    
                        if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                            logger.error(f"⚠️ WIINPAY: Valor mínimo é R$ 3,00! Valor enviado: R$ {amount:.2f}")
                    
                        return None
            
            except requests.exceptions.Timeout as timeout_error:
                logger.warning(f"⚠️ [GATEWAY TIMEOUT] Gateway timeout ao gerar PIX: {timeout_error}")
                # Tentar encontrar Payment criado antes do timeout para marcar como pendente de verificação
                try:
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Payment
                    from flask import current_app
                    with current_app.app_context():
                        payment = Payment.query.filter_by(
                            bot_id=bot_id,
                            customer_user_id=customer_user_id,
                            amount=amount,
                            status='pending'
                        ).order_by(Payment.id.desc()).first()
                    
                        if payment:
                            payment.status = 'pending_verification'
                            db.session.commit()
                            return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway timeout'}
                except Exception as db_err:
                    logger.error(f"Erro ao tratar timeout no DB: {db_err}")
                return None

        finally:
            # Liberar lock distribuído
            try:
                if lock_acquired and lock_key and redis_conn:
                    redis_conn.delete(lock_key)
            except Exception as unlock_error:
                logger.warning(f"⚠️ Erro ao liberar lock PIX: {unlock_error}")
    
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
            elif gateway_type == 'atomopay':
                # ✅ ÁTOMO PAY: Credenciais dummy para webhook (não precisa de credenciais reais)
                dummy_credentials = {
                    'api_token': 'dummy_token',
                    'offer_hash': 'dummy_offer',
                    'product_hash': 'dummy_product'
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

            # ✅ Robustez: normalizar media_type (evita 'VIDEO'/'Video'/None quebrando envio de mídia)
            if media_url and (media_type is None or (isinstance(media_type, str) and not media_type.strip())):
                media_type = 'video'
            if isinstance(media_type, str):
                media_type = media_type.strip().lower()
            
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
            if media_type == 'video':
                response = self.send_video_safe(
                    token=token,
                    chat_id=chat_id,
                    caption=message,
                    reply_markup=reply_markup,
                    file_path=file_path
                )
                if response is None:
                    return False
            else:
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
                    
                    with self.messenger.telegram_http_semaphore:
                        response = requests.post(url, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result_data = response.json()
                if result_data.get('ok'):
                    logger.info(f"✅ Arquivo {media_type} enviado para chat {chat_id}")
                    
                    # ✅ CHAT: Salvar mensagem enviada pelo bot no banco
                    try:
                        from flask import current_app
                        from internal_logic.core.extensions import db
                        from internal_logic.core.models import BotUser, BotMessage, Bot
                        import json as json_lib
                        import uuid as uuid_lib
                        
                        with current_app.app_context():
                            # ✅ REDIS BRAIN: Buscar bot pelo token
                            # Como não temos índice reverso no Redis, buscar direto no banco
                            bot_id = None
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
    
    # Taxonomia de Erros do Telegram - 3 Buckets
    USER_FATAL_KEYWORDS = [
        'bot was blocked by the user', 'user is deactivated', 'have no rights to send a message',
        'not enough rights', 'chat not found', 'user not found', 'chat_id is empty',
        'peer_id_invalid', 'input_user_deactivated', 'bot was kicked', 'bot is not a member',
        'need administrator rights', 'group chat was upgraded', 'blocked by the user', 'user blocked'
    ]
    
    BOT_FATAL_KEYWORDS = [
        'unauthorized', 'token is invalid', 'bot token is invalid', '401',
        'bot was banned', 'this bot has been blocked', 'terminated by other getupdates request'
    ]
    
    RETRYABLE_KEYWORDS = [
        'too many requests', 'retry_after', 'flood', '500', '502', '503', '504',
        'bad gateway', 'service unavailable', 'gateway timeout', 'internal server error',
        'connection', 'timeout', 'timed out', 'network', 'remotedisconnected',
        'connectionreset', 'connectionrefused', 'migrate_to_chat_id', 'retry'
    ]

    def _classify_telegram_error(self, error_str: str) -> str:
        """
        Classifica erro da API Telegram em 3 buckets:
        - USER_FATAL: Erro do usuário (não punir bot)
        - BOT_FATAL: Erro do bot (desativar imediatamente)
        - RETRYABLE: Erro transitório (tentar novamente)
        
        Args:
            error_str: String do erro em lowercase
            
        Returns:
            'USER_FATAL', 'BOT_FATAL', ou 'RETRYABLE'
        """
        error_lower = error_str.lower()
        
        # Verificar BOT_FATAL primeiro (prioridade máxima)
        for keyword in self.BOT_FATAL_KEYWORDS:
            if keyword in error_lower:
                return 'BOT_FATAL'
        
        # Verificar USER_FATAL
        for keyword in self.USER_FATAL_KEYWORDS:
            if keyword in error_lower:
                return 'USER_FATAL'
        
        # Verificar RETRYABLE
        for keyword in self.RETRYABLE_KEYWORDS:
            if keyword in error_lower:
                return 'RETRYABLE'
        
        # Por padrão, considerar RETRYABLE (fail-safe)
        return 'RETRYABLE'

    def _apply_circuit_breaker(self, token: str, error_bucket: str, error_description: str):
        """
        🔴 DESATIVADO: Circuit Breaker removido (colunas não existem no banco legado)
        
        Mantido para compatibilidade - apenas loga, não modifica banco.
        """
        # ✅ COLUNAS REMOVIDAS: health_status, circuit_breaker_until, 
        # error_count, consecutive_failures, last_health_check
        # Usar apenas logging, sem writes no banco
        if error_bucket == 'BOT_FATAL':
            logger.critical(f"🔴 BOT_FATAL detectado: {error_description[:200]}")
        elif error_bucket == 'RETRYABLE':
            logger.warning(f"⚠️ RETRYABLE detectado: {error_description[:200]}")
        # NÃO faz nenhuma operação no banco - colunas não existem
        return

    def _reset_circuit_breaker_on_success(self, token: str):
        """
        🔴 DESATIVADO: Circuit Breaker reset removido (colunas não existem no banco legado)
        
        Mantido para compatibilidade - apenas loga, não modifica banco.
        """
        # ✅ COLUNAS REMOVIDAS: consecutive_failures, health_status, circuit_breaker_until, last_health_check
        # Não faz nada - as colunas não existem no banco legado
        return 

    def send_telegram_message(self, token: str, chat_id: str, message: str, 
                             media_url: Optional[str] = None, 
                             media_type: str = 'video',
                             buttons: Optional[list] = None):
        """
        Envia mensagem pelo Telegram (delegado ao BotMessenger)
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message: Mensagem de texto
            media_url: URL da mídia (opcional)
            media_type: Tipo da mídia (video, photo ou audio)
            buttons: Lista de botões inline
            
        Returns:
            bool: True se enviado com sucesso
        """
        try:
            # ✅ DELEGAÇÃO: Usar BotMessenger para envio
            return self.messenger.send_message_with_media(
                token=token,
                chat_id=chat_id,
                message=message,
                media_type=media_type,
                media_url=media_url,
                reply_markup=self.messenger.build_keyboard(buttons) if buttons else None
            )
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            return False
    
    def get_bot_status(self, bot_id: int, verify_telegram: bool = False) -> Dict[str, Any]:
        """
        Obtém status de um bot via Redis (única fonte de verdade)
        
        Args:
            bot_id: ID do bot
            verify_telegram: Se True, verifica REALMENTE se bot responde no Telegram
        
        Returns:
            Informações de status
        """
        # ✅ REDIS BRAIN: Buscar dados do bot no Redis
        bot_info = self.bot_state.get_bot_data(bot_id)
        if not bot_info:
            return {
                'is_running': False,
                'status': 'stopped'
            }
        
        token = bot_info.get('token')
        
        # ✅ VERIFICAÇÃO REAL: Se solicitado, verificar se bot responde no Telegram
        if verify_telegram and token:
            try:
                url = f"https://api.telegram.org/bot{token}/getMe"
                with self.messenger.telegram_http_semaphore:
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
        
        # Bot está ativo no Redis e (se verificado) responde no Telegram
        from internal_logic.core.models import get_brazil_time
        from datetime import datetime
        started_at = bot_info.get('started_at')
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        return {
            'is_running': True,
            'status': bot_info.get('status', 'running'),
            'started_at': started_at.isoformat() if started_at else None,
            'uptime': (get_brazil_time() - started_at).total_seconds() if started_at else 0
        }
    
    def schedule_downsells(self, bot_id: int, payment_id: str, chat_id: int, downsells: list, original_price: float = 0, original_button_index: int = -1):
        """
        # ✅ MIGRAÇÃO RQ: Agenda downsells usando RQ (Redis Queue) em vez de APScheduler
        
        Args:
            bot_id: ID do bot
            payment_id: ID do pagamento
            chat_id: ID do chat
            downsells: Lista de downsells configurados
            original_price: Preço do botão original (para cálculo percentual)
            original_button_index: Índice do botão original clicado
        """
        from datetime import timedelta
        
        logger.info(f"🚨 ===== SCHEDULE_DOWNSELLS (RQ) =====")
        logger.info(f"   bot_id: {bot_id}")
        logger.info(f"   payment_id: {payment_id}")
        logger.info(f"   chat_id: {chat_id}")
        logger.info(f"   downsells count: {len(downsells) if downsells else 0}")
        
        try:
            if not downsells:
                logger.warning(f"⚠️ Lista de downsells está vazia!")
                return
            
            # ✅ Importar fila RQ e função de job
            from tasks_async import marathon_queue, send_downsell_job
            
            if not marathon_queue:
                logger.error(f"❌ CRÍTICO: Fila RQ 'marathon' não disponível!")
                return
            
            logger.info(f"📅 Agendando {len(downsells)} downsell(s) via RQ para payment {payment_id}")
            
            jobs_agendados = []
            for i, downsell in enumerate(downsells):
                delay_minutes = int(downsell.get('delay_minutes', 5))
                
                logger.info(f"📅 Downsell {i+1}: delay={delay_minutes}min")
                
                try:
                    # ✅ ISOLAMENTO: Agendar downsell com user_id no payload
                    from internal_logic.workers import enqueue_with_user_and_bot
                    from tasks_async import marathon_queue
                    
                    if marathon_queue and self.user_id:
                        job = enqueue_with_user_and_bot(
                            queue=marathon_queue,
                            user_id=self.user_id,  # ✅ Namespace isolado
                            bot_id=bot_id,
                            func=send_downsell_job,
                            payment_id=payment_id,
                            chat_id=chat_id,
                            downsell=downsell,
                            index=i,
                            original_price=original_price,
                            original_button_index=original_button_index,
                            job_id=f"downsell_{bot_id}_{payment_id}_{i}",
                            job_timeout=300
                        )
                    elif marathon_queue:
                        # Fallback legacy
                        job = marathon_queue.enqueue_in(
                            timedelta(minutes=delay_minutes),
                            send_downsell_job,
                            bot_id=bot_id,
                            payment_id=payment_id,
                            chat_id=chat_id,
                            downsell=downsell,
                            index=i,
                            original_price=original_price,
                            original_button_index=original_button_index,
                            job_id=f"downsell_{bot_id}_{payment_id}_{i}",
                            job_timeout=300
                        )
                    
                    logger.info(f"✅ Downsell {i+1} AGENDADO via RQ: job_id={job.id if job else 'N/A'}")
                    if job:
                        jobs_agendados.append(job.id)
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao agendar downsell {i+1} no RQ: {e}", exc_info=True)
            
            logger.info(f"✅ Total de {len(jobs_agendados)} downsell(s) agendado(s) via RQ")
            logger.info(f"🚨 ===== FIM SCHEDULE_DOWNSELLS (RQ) =====")
                
        except Exception as e:
            logger.error(f"❌ Erro ao agendar downsells via RQ: {e}", exc_info=True)
    
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
        import traceback
        logger.info(f"🚨 ===== _SEND_DOWNSELL EXECUTADO ===== [ENTRADA DA FUNÇÃO]")
        logger.info(f"   ⏰ Timestamp: {datetime.now()}")
        logger.info(f"   bot_id: {bot_id}")
        logger.info(f"   payment_id: {payment_id}")
        logger.info(f"   chat_id: {chat_id}")
        logger.info(f"   index: {index}")
        logger.info(f"   original_price: {original_price}")
        logger.info(f"   original_button_index: {original_button_index}")
        logger.info(f"   downsell config: {downsell}")
        
        try:
            # ✅ DIAGNÓSTICO CRÍTICO: Log imediato no início da função
            logger.info(f"🔍 [DIAGNÓSTICO] Função _send_downsell chamada pelo scheduler")
            logger.info(f"   Stack trace (primeiras 5 linhas):")
            for line in traceback.format_stack()[-5:]:
                logger.info(f"      {line.strip()}")
            # ✅ DIAGNÓSTICO CRÍTICO: Verificar pagamento ANTES de enviar
            logger.info(f"🔍 Verificando status do pagamento...")
            payment_status = None
            try:
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Payment
                with current_app.app_context():
                    payment = Payment.query.filter_by(payment_id=payment_id).first()
                    if payment:
                        payment_status = payment.status
                        logger.info(f"   Status do pagamento: {payment_status}")
                    else:
                        logger.error(f"   ❌ Pagamento {payment_id} não encontrado no banco!")
                        return  # Cancelar envio se pagamento não existe
            except Exception as e:
                logger.error(f"   ❌ Erro ao verificar pagamento: {e}")
                return  # Cancelar envio se não conseguir verificar se pagamento ainda está pendente
            if payment_status != 'pending':
                logger.warning(f"💰 Pagamento {payment_id} já foi {payment_status}, cancelando downsell {index+1}")
                logger.warning(f"   Isso é normal se o cliente pagou antes do delay configurado")
                return
            
            logger.info(f"✅ Pagamento ainda está pendente - prosseguindo com downsell")
            
            # ✅ REDIS BRAIN: Verificar se bot está ativo no Redis (única fonte de verdade)
            logger.info(f"🔍 DEBUG _send_downsell - Verificando bot no Redis...")
            bot_info = self.bot_state.get_bot_data(bot_id)
            if not bot_info:
                logger.warning(f"🤖 Bot {bot_id} não está mais ativo no Redis, cancelando downsell {index+1}")
                return False  # Retorna False para matar o job silenciosamente
            logger.info(f"✅ Bot está ativo no Redis")
            
            token = bot_info['token']
            
            # ✅ CRÍTICO: Buscar config atualizada do BANCO (não usar cache da memória)
            # Isso garante que mudanças recentes na configuração sejam refletidas
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel
            
            with current_app.app_context():
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
                        
                        # Extrair apenas o nome do produto (remover valor se existir)
                        original_btn_text = btn.get('text', 'Produto')
                        # Verificar se tem "por" no texto original para manter no resultado
                        has_por = 'por' in original_btn_text.lower()
                        # Remover padrões como "R$X.XX", "por X.XX", "X,XX", "por 19,97", etc.
                        # Remove valores com R$ e também valores soltos (19,97, por 19,97, etc)
                        product_name = re.sub(r'\s*(por\s+)?(R\$\s*)?\d+[.,]\d+', '', original_btn_text, flags=re.IGNORECASE).strip()
                        # Limpar espaços extras e "por" solto no final (mas vamos adicionar depois se tinha)
                        product_name = re.sub(r'\s+por\s*$', '', product_name, flags=re.IGNORECASE).strip()
                        if not product_name:
                            product_name = 'Produto'
                        
                        # Texto do botão: Nome + "por" (se tinha) + Valor com desconto + Percentual
                        if has_por:
                            btn_text = f"{product_name} por R${discounted_price:.2f} ({int(discount_percentage)}% OFF)"
                        else:
                            btn_text = f"{product_name} R${discounted_price:.2f} ({int(discount_percentage)}% OFF)"
                        
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
                    
                    # No modo percentual, sempre usar apenas o valor com desconto
                    # Extrair nome do produto (remover valor se existir no button_text customizado)
                    custom_button_text = downsell.get('button_text', '').strip()
                    has_por = False
                    if custom_button_text:
                        # Verificar se tem "por" no texto original para manter no resultado
                        has_por = 'por' in custom_button_text.lower()
                        # Remover padrões como "R$X.XX", "por X.XX", "X,XX", etc.
                        product_name = re.sub(r'\s*(por\s+)?(R\$\s*)?\d+[.,]\d+', '', custom_button_text, flags=re.IGNORECASE).strip()
                        # Limpar espaços extras e "por" solto no final (mas vamos adicionar depois se tinha)
                        product_name = re.sub(r'\s+por\s*$', '', product_name, flags=re.IGNORECASE).strip()
                        if not product_name:
                            product_name = downsell.get('product_name', 'Produto') or 'Produto'
                    else:
                        product_name = downsell.get('product_name', 'Produto') or 'Produto'
                    
                    # Texto do botão: Nome + "por" (se tinha) + Valor com desconto + Percentual
                    if has_por:
                        button_text = f'{product_name} por R${price:.2f} ({int(discount_percentage)}% OFF)'
                    else:
                        button_text = f'{product_name} R${price:.2f} ({int(discount_percentage)}% OFF)'
                    
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
            logger.info(f"   - Mensagem: {message[:50]}..." if message else "   - Mensagem: (vazia)")
            logger.info(f"   - Mídia: {media_url[:50] if media_url else 'Nenhuma'}...")
            logger.info(f"   - Botões: {len(buttons)} botão(ões)")
            
            # Enviar mensagem com ou sem mídia
            try:
                if media_url and '/c/' not in media_url and media_url.startswith('http'):
                    logger.info(f"📤 Enviando downsell com mídia...")
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        media_url=media_url,
                        media_type=media_type,
                        buttons=buttons
                    )
                    if not result:
                        logger.warning(f"⚠️ Falha ao enviar com mídia, tentando sem mídia...")
                        # Fallback sem mídia se falhar
                        result = self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=message,
                            buttons=buttons
                        )
                else:
                    logger.info(f"📤 Enviando downsell sem mídia...")
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        buttons=buttons
                    )
                
                if result:
                    logger.info(f"✅ Downsell {index+1} ENVIADO COM SUCESSO para chat {chat_id}")
                else:
                    logger.error(f"❌ Falha ao enviar downsell {index+1} para chat {chat_id}")
            except Exception as send_error:
                logger.error(f"❌ Erro ao enviar mensagem do downsell {index+1}: {send_error}", exc_info=True)
            
            # ✅ Enviar áudio adicional se habilitado
            if audio_enabled and audio_url:
                logger.info(f"🎤 Enviando áudio complementar do Downsell {index+1}...")
                try:
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
                except Exception as audio_error:
                    logger.error(f"❌ Erro ao enviar áudio complementar: {audio_error}")
            
            logger.info(f"🚨 ===== FIM _SEND_DOWNSELL =====")
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Erro CRÍTICO ao enviar downsell {index+1}: {e}")
            logger.error(f"   Tipo do erro: {type(e).__name__}")
            logger.error(f"   Stack trace completo:")
            logger.error(traceback.format_exc())
            logger.error(f"🚨 ===== FIM _SEND_DOWNSELL (COM ERRO) =====")
    
    def schedule_upsells(self, bot_id: int, payment_id: str, chat_id: int, upsells: list, original_price: float = 0, original_button_index: int = -1):
        """
        Agenda upsells para um pagamento aprovado
        
        # ✅ DIFERENÇA CRÍTICA vs downsells:
        - Upsells são enviados quando payment.status == 'paid'
        - Downsells são enviados quando payment.status == 'pending'
        
        Args:
            bot_id: ID do bot
            payment_id: ID do pagamento
            chat_id: ID do chat
            upsells: Lista de upsells configurados
            original_price: Preço do botão original (para cálculo percentual)
            original_button_index: Índice do botão original clicado
        """
        logger.info(f"🚨 ===== SCHEDULE_UPSELLS CHAMADO =====")
        logger.info(f"   bot_id: {bot_id}")
        logger.info(f"   payment_id: {payment_id}")
        logger.info(f"   chat_id: {chat_id}")
        logger.info(f"   original_price: {original_price}")
        logger.info(f"   original_button_index: {original_button_index}")
        logger.info(f"   upsells count: {len(upsells) if upsells else 0}")
        
        try:
            # ✅ DIAGNÓSTICO CRÍTICO: Verificar scheduler
            if not self.scheduler:
                logger.error(f"❌ CRÍTICO: Scheduler não está disponível no bot_manager!")
                logger.error(f"   Isso significa que upsells NÃO serão agendados!")
                logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                logger.error(f"   Payment ID: {payment_id} | Bot ID: {bot_id}")
                # ✅ CORREÇÃO CRÍTICA QI 500: Tentar recuperar scheduler do app
                # TODO: Implementar importação alternativa para o scheduler
                logger.warning(f"⚠️ Scheduler não disponível no bot_manager...")
                return
            
            if not upsells:
                logger.warning(f"⚠️ Lista de upsells está vazia!")
                return
            
            # ✅ Importar fila RQ e função de job
            from tasks_async import marathon_queue, send_upsell_job
            
            if not marathon_queue:
                logger.error(f"❌ CRÍTICO: Fila RQ 'marathon' não disponível!")
                return
            
            logger.info(f"📅 Agendando {len(upsells)} upsell(s) via RQ para payment {payment_id}")
            
            jobs_agendados = []
            for i, upsell in enumerate(upsells):
                delay_minutes = int(upsell.get('delay_minutes', 5))
                
                logger.info(f"📅 Upsell {i+1}: delay={delay_minutes}min")
                
                try:
                    # ✅ AGENDAR VIA RQ: enqueue_in() agenda para executar após o delay
                    job = marathon_queue.enqueue_in(
                        timedelta(minutes=delay_minutes),
                        send_upsell_job,
                        bot_id=bot_id,
                        payment_id=payment_id,
                        chat_id=chat_id,
                        upsell=upsell,
                        index=i,
                        original_price=original_price,
                        original_button_index=original_button_index,
                        job_id=f"upsell_{bot_id}_{payment_id}_{i}",  # ID único para anti-duplicação
                        job_timeout=300  # 5 minutos timeout
                    )
                    
                    logger.info(f"✅ Upsell {i+1} AGENDADO via RQ: job_id={job.id}")
                    jobs_agendados.append(job.id)
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao agendar upsell {i+1}: {e}", exc_info=True)
            
            logger.info(f"✅ Total de {len(jobs_agendados)} upsell(s) agendado(s) com sucesso")
            logger.info(f"🚨 ===== FIM SCHEDULE_UPSELLS =====")
                
        except Exception as e:
            logger.error(f"❌ Erro ao agendar upsells: {e}", exc_info=True)
    
    def _send_upsell(self, bot_id: int, payment_id: str, chat_id: int, upsell: dict, index: int, original_price: float = 0, original_button_index: int = -1):
        """
        Envia upsell agendado
        
        # ✅ DIFERENÇA CRÍTICA vs downsell:
        - Upsells são enviados quando payment.status == 'paid'
        - Downsells são enviados quando payment.status == 'pending'
        
        Args:
            bot_id: ID do bot
            payment_id: ID do pagamento
            chat_id: ID do chat
            upsell: Configuração do upsell
            index: Índice do upsell
            original_price: Preço do botão original (para cálculo percentual)
            original_button_index: Índice do botão original clicado
        """
        import traceback
        logger.info(f"🚨 ===== _SEND_UPSELL EXECUTADO ===== [ENTRADA DA FUNÇÃO]")
        logger.info(f"   ⏰ Timestamp: {datetime.now()}")
        logger.info(f"   bot_id: {bot_id}")
        logger.info(f"   payment_id: {payment_id}")
        logger.info(f"   chat_id: {chat_id}")
        logger.info(f"   index: {index}")
        logger.info(f"   original_price: {original_price}")
        logger.info(f"   original_button_index: {original_button_index}")
        logger.info(f"   upsell config: {upsell}")
        
        try:
            # ✅ DIAGNÓSTICO CRÍTICO: Log imediato no início da função
            logger.info(f"🔍 [DIAGNÓSTICO] Função _send_upsell chamada pelo scheduler")
            logger.info(f"   Stack trace (primeiras 5 linhas):")
            for line in traceback.format_stack()[-5:]:
                logger.info(f"      {line.strip()}")
            # ✅ DIAGNÓSTICO CRÍTICO: Verificar pagamento ANTES de enviar
            logger.info(f"🔍 Verificando status do pagamento...")
            payment_status = None
            try:
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Payment
                with current_app.app_context():
                    payment = Payment.query.filter_by(payment_id=payment_id).first()
                    if payment:
                        payment_status = payment.status
                        logger.info(f"✅ Pagamento encontrado: status={payment_status}")
                    else:
                        logger.error(f"❌ Pagamento {payment_id} NÃO encontrado no banco!")
                        logger.error(f"   Upsell NÃO será enviado")
                        return
            except Exception as e:
                logger.error(f"❌ Erro ao verificar pagamento: {e}", exc_info=True)
                return
            
            # ✅ CRÍTICO: Verificar se pagamento está pago (upsells só para pagamentos aprovados)
            if payment_status != 'paid':
                logger.warning(f"💰 Pagamento {payment_id} não está pago (status={payment_status}), cancelando upsell {index+1}")
                logger.warning(f"   Upsells devem ser enviados apenas para pagamentos aprovados")
                return
            
            logger.info(f"✅ Pagamento está pago - prosseguindo com upsell")
            
            # ✅ REDIS BRAIN: Verificar se bot está ativo no Redis (única fonte de verdade)
            logger.info(f"🔍 DEBUG _send_upsell - Verificando bot no Redis...")
            bot_info = self.bot_state.get_bot_data(bot_id)
            if not bot_info:
                logger.warning(f"🤖 Bot {bot_id} não está mais ativo no Redis, cancelando upsell {index+1}")
                return False  # Retorna False para matar o job silenciosamente
            logger.info(f"✅ Bot está ativo no Redis")
            
            token = bot_info['token']
            
            # ✅ CRÍTICO: Buscar config atualizada do BANCO (não usar cache da memória)
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel
            
            with current_app.app_context():
                bot = BotModel.query.get(bot_id)
                if bot and bot.config:
                    config = bot.config.to_dict()
                    logger.info(f"🔄 Config recarregada do banco para upsell")
                else:
                    # Fallback: usar config da memória se não encontrar no banco
                    config = bot_info.get('config', {})
                    logger.warning(f"⚠️ Usando config da memória para upsell")
            
            # Verificar se upsells ainda estão habilitados
            logger.info(f"🔍 DEBUG _send_upsell - Verificando se upsells estão habilitados...")
            if not config.get('upsells_enabled', False):
                logger.info(f"📵 Upsells desabilitados, cancelando upsell {index+1}")
                return
            logger.info(f"✅ Upsells estão habilitados")
            
            message = upsell.get('message', '')
            media_url = upsell.get('media_url', '')
            media_type = upsell.get('media_type', 'video')
            audio_enabled = upsell.get('audio_enabled', False)
            audio_url = upsell.get('audio_url', '')
            
            # ✅ NOVO: Calcular preço baseado no modo (fixo ou percentual)
            pricing_mode = upsell.get('pricing_mode', 'fixed')
            logger.info(f"🔍 DEBUG pricing_mode: {pricing_mode}")
            
            # 🎯 ESTRATÉGIA DE CONVERSÃO: MODO PERCENTUAL = TODOS OS BOTÕES COM DESCONTO
            if pricing_mode == 'percentage':
                discount_percentage = float(upsell.get('discount_percentage', 50))
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
                        
                        # Extrair apenas o nome do produto (remover valor se existir)
                        original_btn_text = btn.get('text', 'Produto')
                        # Verificar se tem "por" no texto original para manter no resultado
                        has_por = 'por' in original_btn_text.lower()
                        # Remover padrões como "R$X.XX", "por X.XX", "X,XX", "por 19,97", etc.
                        # Remove valores com R$ e também valores soltos (19,97, por 19,97, etc)
                        product_name = re.sub(r'\s*(por\s+)?(R\$\s*)?\d+[.,]\d+', '', original_btn_text, flags=re.IGNORECASE).strip()
                        # Limpar espaços extras e "por" solto no final (mas vamos adicionar depois se tinha)
                        product_name = re.sub(r'\s+por\s*$', '', product_name, flags=re.IGNORECASE).strip()
                        if not product_name:
                            product_name = 'Produto'
                        
                        # Texto do botão: Nome + "por" (se tinha) + Valor com desconto + Percentual
                        if has_por:
                            btn_text = f"{product_name} por R${discounted_price:.2f} ({int(discount_percentage)}% OFF)"
                        else:
                            btn_text = f"{product_name} R${discounted_price:.2f} ({int(discount_percentage)}% OFF)"
                        
                        buttons.append({
                            'text': btn_text,
                            'callback_data': f'upsell_{index}_{int(discounted_price*100)}_{btn_index}'  # ✅ Formato: upsell_INDEX_PRICE_ORIGINAL_BTN
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
                        # ✅ CORREÇÃO CRÍTICA: Se original_price for 0, usar preço padrão de upsell
                        logger.warning(f"⚠️ original_price é 0! Usando preço padrão para upsell")
                        price = 97.00  # Preço padrão para upsells
                        logger.info(f"💜 MODO PERCENTUAL (corrigido): Usando preço padrão R$ {price:.2f}")
                    
                    if price < 0.50:
                        logger.error(f"❌ Preço muito baixo (R$ {price:.2f}), mínimo R$ 0,50")
                        return
                    
                    button_text = upsell.get('button_text', '').strip()
                    if not button_text:
                        button_text = f'🛒 Comprar por R$ {price:.2f} ({int(discount_percentage)}% OFF)'
                    
                    buttons = [{
                        'text': button_text,
                        'callback_data': f'upsell_{index}_{int(price*100)}_{original_button_index if original_button_index >= 0 else 0}'  # ✅ Formato: upsell_INDEX_PRICE_ORIGINAL_BTN
                    }]
            
            else:
                # 💙 MODO FIXO: Um único botão com preço fixo (comportamento original)
                price = float(upsell.get('price', 0))
                logger.info(f"💙 MODO FIXO: R$ {price:.2f}")
                
                if price < 0.50:
                    logger.error(f"❌ Preço muito baixo (R$ {price:.2f}), mínimo R$ 0,50")
                    return
                
                button_text = upsell.get('button_text', '').strip()
                if not button_text:
                    button_text = f'🛒 Comprar por R$ {price:.2f}'
                
                buttons = [{
                    'text': button_text,
                    'callback_data': f'upsell_{index}_{int(price*100)}_{original_button_index}'  # ✅ Formato: upsell_INDEX_PRICE_ORIGINAL_BTN
                }]
            
            # ✅ VERIFICAR SE TEM ORDER BUMP PARA ESTE UPSELL
            order_bump = upsell.get('order_bump', {})
            
            logger.info(f"🔍 DEBUG _send_upsell - Botões criados: {len(buttons)}")
            logger.info(f"  - message: {message}")
            logger.info(f"  - media_url: {media_url}")
            logger.info(f"  - order_bump_enabled: {order_bump.get('enabled', False)}")
            
            logger.info(f"📨 Enviando upsell {index+1} para chat {chat_id}")
            logger.info(f"   - Mensagem: {message[:50]}..." if message else "   - Mensagem: (vazia)")
            logger.info(f"   - Mídia: {media_url[:50] if media_url else 'Nenhuma'}...")
            logger.info(f"   - Botões: {len(buttons)} botão(ões)")
            
            # Enviar mensagem com ou sem mídia
            try:
                if media_url and '/c/' not in media_url and media_url.startswith('http'):
                    logger.info(f"📤 Enviando upsell com mídia...")
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        media_url=media_url,
                        media_type=media_type,
                        buttons=buttons
                    )
                    if not result:
                        logger.warning(f"⚠️ Falha ao enviar com mídia, tentando sem mídia...")
                        # Fallback sem mídia se falhar
                        result = self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=message,
                            buttons=buttons
                        )
                else:
                    logger.info(f"📤 Enviando upsell sem mídia...")
                    result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        buttons=buttons
                    )
                
                if result:
                    logger.info(f"✅ Upsell {index+1} ENVIADO COM SUCESSO para chat {chat_id}")
                else:
                    logger.error(f"❌ Falha ao enviar upsell {index+1} para chat {chat_id}")
            except Exception as send_error:
                logger.error(f"❌ Erro ao enviar mensagem do upsell {index+1}: {send_error}", exc_info=True)
            
            # ✅ Enviar áudio adicional se habilitado
            if audio_enabled and audio_url:
                logger.info(f"🎤 Enviando áudio complementar do Upsell {index+1}...")
                try:
                    audio_result = self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="",
                        media_url=audio_url,
                        media_type='audio',
                        buttons=None
                    )
                    if audio_result:
                        logger.info(f"✅ Áudio complementar do Upsell {index+1} enviado")
                except Exception as audio_error:
                    logger.error(f"❌ Erro ao enviar áudio complementar: {audio_error}")
            
            logger.info(f"🚨 ===== FIM _SEND_UPSELL =====")
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Erro CRÍTICO ao enviar upsell {index+1}: {e}")
            logger.error(f"   Tipo do erro: {type(e).__name__}")
            logger.error(f"   Stack trace completo:")
            logger.error(traceback.format_exc())
            logger.error(f"🚨 ===== FIM _SEND_UPSELL (COM ERRO) =====")
    
    def _is_payment_pending(self, payment_id: str) -> bool:
        """
        Verifica se pagamento ainda está pendente
        
        Args:
            payment_id: ID do pagamento
            
        Returns:
            True se ainda está pendente
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Payment
            
            with current_app.app_context():
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
                            days_since_last_contact: int = 3, exclude_buyers: bool = True,
                            audience_segment: str = None) -> int:
        """
        Conta quantos leads são elegíveis para remarketing
        
        Args:
            bot_id: ID do bot
            target_audience: Tipo de público (all, non_buyers, abandoned_cart, inactive) - LEGADO
            days_since_last_contact: Dias mínimos sem contato
            exclude_buyers: Excluir quem já comprou - LEGADO
            audience_segment: ✅ V2.0 - Nova segmentação avançada:
                - 'all_users': Todos os usuários
                - 'buyers': Todos que compraram
                - 'pix_generated': Todos que geraram PIX
                - 'downsell_buyers': Todos que compraram via downsell
                - 'order_bump_buyers': Todos que compraram com order bump
                - 'upsell_buyers': Todos que compraram via upsell
                - 'remarketing_buyers': Todos que compraram via remarketing
            
        Returns:
            Quantidade de leads elegíveis
        """
        from flask import current_app
        from internal_logic.core.extensions import db
        from internal_logic.core.models import BotUser, Payment, RemarketingBlacklist
        from datetime import datetime, timedelta
        
        with current_app.app_context():
            # Data limite de último contato
            from internal_logic.core.models import get_brazil_time
            contact_limit = get_brazil_time() - timedelta(days=days_since_last_contact)
            
            # Query base: usuários do bot (apenas ativos, não arquivados)
            query = BotUser.query.filter_by(bot_id=bot_id, archived=False)
            
            # Filtro: último contato há X dias
            if days_since_last_contact > 0:
                query = query.filter(BotUser.last_interaction <= contact_limit)
            
            # ✅ MELHORIA: Filtro: excluir blacklist (usuários que bloquearam este bot específico)
            blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                bot_id=bot_id
            ).all()
            blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
            if blacklist_ids:
                query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                logger.debug(f"🚫 Blacklist para bot {bot_id}: {len(blacklist_ids)} usuários excluídos")
            
            # ✅ V2.0: NOVA SEGMENTAÇÃO AVANÇADA
            if audience_segment:
                if audience_segment == 'all_users':
                    # Todos os usuários (sem filtro adicional de compra)
                    pass  # Usa query base
                
                elif audience_segment == 'buyers':
                    # Todos que compraram (status = 'paid')
                    buyer_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == bot_id,
                        Payment.status == 'paid'
                    ).distinct().all()
                    buyer_ids = [b[0] for b in buyer_ids if b[0]]
                    if buyer_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(buyer_ids))
                    else:
                        return 0
                
                elif audience_segment == 'pix_generated':
                    # Todos que geraram PIX (status = 'pending')
                    pix_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == bot_id,
                        Payment.status == 'pending'
                    ).distinct().all()
                    pix_ids = [b[0] for b in pix_ids if b[0]]
                    if pix_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(pix_ids))
                    else:
                        return 0
                
                elif audience_segment == 'downsell_buyers':
                    # Todos que compraram via downsell
                    downsell_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == bot_id,
                        Payment.status == 'paid',
                        Payment.is_downsell == True
                    ).distinct().all()
                    downsell_ids = [b[0] for b in downsell_ids if b[0]]
                    if downsell_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(downsell_ids))
                    else:
                        return 0
                
                elif audience_segment == 'order_bump_buyers':
                    # Todos que compraram com order bump
                    orderbump_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == bot_id,
                        Payment.status == 'paid',
                        Payment.order_bump_accepted == True
                    ).distinct().all()
                    orderbump_ids = [b[0] for b in orderbump_ids if b[0]]
                    if orderbump_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(orderbump_ids))
                    else:
                        return 0
                
                elif audience_segment == 'upsell_buyers':
                    # Todos que compraram via upsell
                    upsell_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == bot_id,
                        Payment.status == 'paid',
                        Payment.is_upsell == True
                    ).distinct().all()
                    upsell_ids = [b[0] for b in upsell_ids if b[0]]
                    if upsell_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(upsell_ids))
                    else:
                        return 0
                
                elif audience_segment == 'remarketing_buyers':
                    # Todos que compraram via remarketing
                    remarketing_ids = db.session.query(Payment.customer_user_id).filter(
                        Payment.bot_id == bot_id,
                        Payment.status == 'paid',
                        Payment.is_remarketing == True
                    ).distinct().all()
                    remarketing_ids = [b[0] for b in remarketing_ids if b[0]]
                    if remarketing_ids:
                        query = query.filter(BotUser.telegram_user_id.in_(remarketing_ids))
                    else:
                        return 0
                
                else:
                    # Segmento desconhecido - retorna 0
                    logger.warning(f"⚠️ Segmento desconhecido: {audience_segment}")
                    return 0
            
            else:
                # ✅ COMPATIBILIDADE: Lógica antiga (legado)
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
                    from internal_logic.core.models import get_brazil_time
                    inactive_limit = get_brazil_time() - timedelta(days=7)
                    query = query.filter(BotUser.last_interaction <= inactive_limit)
            
            return query.count()
    
    def send_remarketing_campaign(self, campaign_id: int, bot_token: str):
        """
        Envia campanha de remarketing em background
        
        Args:
            campaign_id: ID da campanha
            bot_token: Token do bot
        """
        try:
            from redis_manager import get_redis_connection
            import json
            from flask import current_app
            from internal_logic.core.extensions import db, socketio
            from internal_logic.core.models import RemarketingCampaign, BotUser, Payment, RemarketingBlacklist, get_brazil_time, Bot
            from datetime import timedelta

            def enqueue_jobs():
                with current_app.app_context():
                    campaign = db.session.get(RemarketingCampaign, campaign_id)
                    if not campaign:
                        logger.warning(f"❌ Remarketing enqueue abortado: campaign_id={campaign_id} não encontrada")
                        return

                    campaign.status = 'sending'
                    campaign.started_at = get_brazil_time()
                    db.session.commit()

                    redis_conn = get_redis_connection()
                    queue_key = f"gb:{self.user_id}:remarketing:queue:{campaign.bot_id}"
                    sent_set_key = f"remarketing:sent:{campaign.id}"
                    stats_key = f"remarketing:stats:{campaign.id}"

                    contact_limit = get_brazil_time() - timedelta(days=campaign.days_since_last_contact)
                    query = BotUser.query.filter_by(bot_id=campaign.bot_id, archived=False)
                    if campaign.days_since_last_contact > 0:
                        query = query.filter(BotUser.last_interaction <= contact_limit)

                    blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                        bot_id=campaign.bot_id
                    ).all()
                    blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
                    if blacklist_ids:
                        query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))

                    target_audience = campaign.target_audience
                    if target_audience == 'all':
                        pass
                    elif target_audience == 'buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(buyer_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'downsell_buyers':
                        downsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_downsell == True
                        ).distinct().all()
                        downsell_ids = [b[0] for b in downsell_ids if b[0]]
                        if downsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(downsell_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'order_bump_buyers':
                        orderbump_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.order_bump_accepted == True
                        ).distinct().all()
                        orderbump_ids = [b[0] for b in orderbump_ids if b[0]]
                        if orderbump_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(orderbump_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'upsell_buyers':
                        upsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_upsell == True
                        ).distinct().all()
                        upsell_ids = [b[0] for b in upsell_ids if b[0]]
                        if upsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(upsell_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'remarketing_buyers':
                        remarketing_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_remarketing == True
                        ).distinct().all()
                        remarketing_ids = [b[0] for b in remarketing_ids if b[0]]
                        if remarketing_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(remarketing_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'abandoned_cart':
                        abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'pending'
                        ).distinct().all()
                        abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                        if abandoned_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'inactive':
                        inactive_limit = get_brazil_time() - timedelta(days=7)
                        query = query.filter(BotUser.last_interaction <= inactive_limit)
                    elif target_audience == 'non_buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                    else:
                        if campaign.exclude_buyers:
                            buyer_ids = db.session.query(Payment.customer_user_id).filter(
                                Payment.bot_id == campaign.bot_id,
                                Payment.status == 'paid'
                            ).distinct().all()
                            buyer_ids = [b[0] for b in buyer_ids if b[0]]
                            if buyer_ids:
                                query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))

                    total_leads = query.count()
                    if total_leads == 0:
                        campaign.total_targets = 0
                        campaign.status = 'completed'
                        campaign.completed_at = get_brazil_time()
                        db.session.commit()
                        return

                    enqueued = 0
                    skipped_blacklist = 0
                    skipped_sent = 0
                    skipped_invalid = 0
                    skipped_not_eligible = 0
                    debug_logged = 0
                    debug_mode = False

                    def _is_valid_chat_id(chat_id):
                        try:
                            if chat_id is None:
                                return False
                            chat_int = int(str(chat_id))
                            return chat_int != 0
                        except Exception:
                            return False
                    batch_size = 200
                    offset = 0

                    while offset < total_leads:
                        batch = query.offset(offset).limit(batch_size).all()
                        if not batch:
                            break

                        for lead in batch:
                            if not getattr(lead, 'telegram_user_id', None):
                                skipped_invalid += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"🚫 SKIP_ENQUEUE reason=invalid_chat_id campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={getattr(lead, 'telegram_user_id', None)}")
                                    debug_logged += 1
                                continue
                            if not _is_valid_chat_id(lead.telegram_user_id):
                                skipped_invalid += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"🚫 SKIP_ENQUEUE reason=invalid_chat_id campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            blk_key = f"remarketing:blacklist:{campaign.bot_id}"
                            if redis_conn.sismember(blk_key, str(lead.telegram_user_id)):
                                skipped_blacklist += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"🚫 SKIP_ENQUEUE reason=blacklist campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            if redis_conn.sismember(sent_set_key, str(lead.telegram_user_id)):
                                skipped_sent += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"🚫 SKIP_ENQUEUE reason=already_received campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            if getattr(lead, 'opt_out', False) or getattr(lead, 'unsubscribed', False) or getattr(lead, 'inactive', False):
                                skipped_not_eligible += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"🚫 SKIP_ENQUEUE reason=not_eligible campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            # Bot token sempre resolvido por bot_id do clone (evita reuse de token inválido/None)
                            bot_obj = Bot.query.get(campaign.bot_id)
                            current_bot_token = bot_obj.telegram_token if bot_obj else None
                            if not current_bot_token:
                                logger.error(f"❌ Bot sem token no enqueue | bot_id={campaign.bot_id} campaign_id={campaign.id} chat_id={lead.telegram_user_id}")
                                skipped_not_eligible += 1
                                continue

                            message = campaign.message.replace('{nome}', lead.first_name or 'Cliente')
                            message = message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])

                            remarketing_buttons = []
                            if campaign.buttons:
                                buttons_list = campaign.buttons
                                if isinstance(campaign.buttons, str):
                                    try:
                                        buttons_list = json.loads(campaign.buttons)
                                    except Exception:
                                        buttons_list = []
                                for btn_idx, btn in enumerate(buttons_list):
                                    if btn.get('price') and btn.get('description'):
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Comprar'),
                                            'callback_data': f"rmkt_{campaign.id}_{btn_idx}"
                                        })
                                    elif btn.get('url'):
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Link'),
                                            'url': btn.get('url')
                                        })

                            job = {
                                'type': 'send',
                                'campaign_id': campaign.id,
                                'bot_id': campaign.bot_id,
                                'telegram_user_id': str(lead.telegram_user_id),
                                'message': message,
                                'media_url': campaign.media_url,
                                'media_type': campaign.media_type,
                                'buttons': remarketing_buttons,
                                'audio_enabled': bool(campaign.audio_enabled),
                                'audio_url': campaign.audio_url or '',
                                'bot_token': current_bot_token
                            }
                            try:
                                redis_conn.rpush(queue_key, json.dumps(job))
                                redis_conn.hincrby(stats_key, 'enqueued', 1)
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"📦 ENQUEUE OK campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                enqueued += 1
                            except Exception as enqueue_error:
                                logger.warning(f"⚠️ Falha ao enfileirar job remarketing: campaign_id={campaign.id} chat_id={lead.telegram_user_id} err={enqueue_error}")

                        offset += batch_size

                    if skipped_blacklist:
                        redis_conn.hincrby(stats_key, 'skipped_blacklist', skipped_blacklist)
                    if skipped_sent:
                        redis_conn.hincrby(stats_key, 'skipped_already_received', skipped_sent)
                    if skipped_invalid:
                        redis_conn.hincrby(stats_key, 'skipped_invalid_chat', skipped_invalid)
                    if skipped_not_eligible:
                        redis_conn.hincrby(stats_key, 'skipped_not_eligible', skipped_not_eligible)

                    campaign.total_targets = enqueued
                    db.session.commit()

                    try:
                        socketio.emit('remarketing_progress', {
                            'campaign_id': campaign.id,
                            'sent': campaign.total_sent,
                            'failed': campaign.total_failed,
                            'blocked': campaign.total_blocked,
                            'total': campaign.total_targets,
                            'percentage': 0
                        })
                    except Exception:
                        pass

                    try:
                        redis_conn.rpush(queue_key, json.dumps({'type': 'campaign_done', 'campaign_id': campaign.id}))
                    except Exception:
                        pass

                    logger.info(f"📦 Remarketing jobs enfileirados: campaign_id={campaign.id} bot_id={campaign.bot_id} total={enqueued} queue={queue_key}")

            thread = threading.Thread(target=enqueue_jobs, name=f"remarketing-enqueue-{campaign_id}")
            thread.daemon = True
            thread.start()
            logger.info(f"🚀 Remarketing enqueue thread disparada: campaign_id={campaign_id} thread_name={thread.name}")
            return
        except Exception as orchestration_error:
            logger.error(f"❌ Falha no remarketing orchestration (fallback para modo legado): {orchestration_error}", exc_info=True)

        from flask import current_app
        from internal_logic.core.extensions import db, socketio
        from internal_logic.core.models import RemarketingCampaign, BotUser, Payment, RemarketingBlacklist
        from datetime import datetime, timedelta
        import time
        
        def send_campaign():
            import time  # ✅ CRÍTICO: Importar time no início da função para evitar UnboundLocalError
            with current_app.app_context():
                try:
                    campaign = db.session.get(RemarketingCampaign, campaign_id)
                    if not campaign:
                        logger.warning(f"❌ Remarketing abortado: campaign_id={campaign_id} não encontrada (db.session.get retornou None)")
                        return
                    
                    # Atualizar status
                    campaign.status = 'sending'
                    from internal_logic.core.models import get_brazil_time
                    campaign.started_at = get_brazil_time()
                    db.session.commit()
                    
                    logger.info(f"📢 Iniciando envio de remarketing: {campaign.name}")
                    
                    # Buscar leads elegíveis (apenas usuários ativos, não arquivados)
                    from internal_logic.core.models import get_brazil_time
                    contact_limit = get_brazil_time() - timedelta(days=campaign.days_since_last_contact)
                    
                    query = BotUser.query.filter_by(bot_id=campaign.bot_id, archived=False)
                    
                    # Filtro de último contato
                    if campaign.days_since_last_contact > 0:
                        query = query.filter(BotUser.last_interaction <= contact_limit)
                    
                    # ✅ MELHORIA: Excluir blacklist (usuários que bloquearam este bot específico)
                    blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                        bot_id=campaign.bot_id
                    ).all()
                    blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
                    if blacklist_ids:
                        query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                        logger.info(f"🚫 Blacklist para bot {campaign.bot_id}: {len(blacklist_ids)} usuários excluídos da campanha")
                    
                    # ✅ V2.0: NOVA SEGMENTAÇÃO AVANÇADA
                    # Verificar se é segmentação nova (valores mapeados do app.py) ou legado
                    target_audience = campaign.target_audience
                    
                    # Mapeamento reverso: target_audience → audience_segment
                    # Valores novos: buyers, downsell_buyers, order_bump_buyers, upsell_buyers, remarketing_buyers
                    # Valores legado: all, non_buyers, abandoned_cart, inactive
                    
                    if target_audience == 'all':
                        # Todos os usuários (sem filtro adicional de compra)
                        pass  # Usa query base
                    
                    elif target_audience == 'buyers':
                        # Todos que compraram (status = 'paid')
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(buyer_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"🎯 0 leads elegíveis (nenhum comprador encontrado)")
                            return
                    
                    elif target_audience == 'downsell_buyers':
                        # Todos que compraram via downsell
                        downsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_downsell == True
                        ).distinct().all()
                        downsell_ids = [b[0] for b in downsell_ids if b[0]]
                        if downsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(downsell_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"🎯 0 leads elegíveis (nenhum comprador via downsell encontrado)")
                            return
                    
                    elif target_audience == 'order_bump_buyers':
                        # Todos que compraram com order bump
                        orderbump_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.order_bump_accepted == True
                        ).distinct().all()
                        orderbump_ids = [b[0] for b in orderbump_ids if b[0]]
                        if orderbump_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(orderbump_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"🎯 0 leads elegíveis (nenhum comprador com order bump encontrado)")
                            return
                    
                    elif target_audience == 'upsell_buyers':
                        # Todos que compraram via upsell
                        upsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_upsell == True
                        ).distinct().all()
                        upsell_ids = [b[0] for b in upsell_ids if b[0]]
                        if upsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(upsell_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"🎯 0 leads elegíveis (nenhum comprador via upsell encontrado)")
                            return
                    
                    elif target_audience == 'remarketing_buyers':
                        # Todos que compraram via remarketing
                        remarketing_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_remarketing == True
                        ).distinct().all()
                        remarketing_ids = [b[0] for b in remarketing_ids if b[0]]
                        if remarketing_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(remarketing_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"🎯 0 leads elegíveis (nenhum comprador via remarketing encontrado)")
                            return
                    
                    elif target_audience == 'abandoned_cart':
                        # ✅ COMPATIBILIDADE LEGADO: Usuários que geraram PIX mas não pagaram
                        abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'pending'
                        ).distinct().all()
                        abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                        if abandoned_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"🎯 0 leads elegíveis (nenhum PIX gerado encontrado)")
                            return
                    
                    elif target_audience == 'inactive':
                        # ✅ COMPATIBILIDADE LEGADO: Inativos há 7+ dias
                        from internal_logic.core.models import get_brazil_time
                        inactive_limit = get_brazil_time() - timedelta(days=7)
                        query = query.filter(BotUser.last_interaction <= inactive_limit)
                    
                    elif target_audience == 'non_buyers':
                        # ✅ COMPATIBILIDADE LEGADO: Excluir compradores
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                    
                    else:
                        # ✅ COMPATIBILIDADE: Se exclude_buyers estiver marcado, aplicar filtro antigo
                        if campaign.exclude_buyers:
                            buyer_ids = db.session.query(Payment.customer_user_id).filter(
                                Payment.bot_id == campaign.bot_id,
                                Payment.status == 'paid'
                            ).distinct().all()
                            buyer_ids = [b[0] for b in buyer_ids if b[0]]
                            if buyer_ids:
                                query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                    
                    # ✅ CORREÇÃO CRÍTICA: Contar leads sem carregar todos na memória (evita sobrecarga)
                    total_leads = query.count()
                    campaign.total_targets = total_leads
                    try:
                        db.session.commit()
                        db.session.refresh(campaign)  # ✅ CRÍTICO: Refresh após commit
                    except Exception as commit_error:
                        logger.error(f"❌ Erro ao salvar total_targets: {commit_error}")
                        db.session.rollback()
                    
                    logger.info(f"🎯 {campaign.total_targets} leads elegíveis")
                    
                    if total_leads == 0:
                        logger.warning(f"⚠️ Nenhum lead elegível para campanha {campaign_id}")
                        campaign.status = 'completed'
                        from internal_logic.core.models import get_brazil_time
                        campaign.completed_at = get_brazil_time()
                        db.session.commit()
                        return
                    
                    # ✅ CORREÇÃO CRÍTICA: Processar em batches com paginação (evita sobrecarga de memória)
                    # ✅ OTIMIZAÇÃO MULTI-USUÁRIO: Batch maior quando sistema não está sobrecarregado
                    # Ajusta dinamicamente baseado no número de campanhas ativas
                    active_count = len(self.active_remarketing_campaigns)
                    if active_count <= 5:
                        batch_size = 30  # Batch maior quando poucas campanhas ativas
                    elif active_count <= 10:
                        batch_size = 25  # Batch médio
                    else:
                        batch_size = 20  # Batch menor quando muitas campanhas ativas
                    
                    offset = 0
                    batch_number = 0
                    
                    logger.info(f"🚀 Iniciando processamento de {total_leads} leads em batches de {batch_size} (campanhas ativas: {active_count})")
                    
                    while offset < total_leads:
                        batch_number += 1
                        remaining = total_leads - offset
                        batch_expected = min(batch_size, remaining)
                        logger.info(f"📦 [Batch {batch_number}/{((total_leads + batch_size - 1) // batch_size)}] Processando offset {offset}-{offset + batch_expected - 1} de {total_leads} leads")

                        # ✅ Diagnóstico objetivo (1x por batch, sem spam por lead)
                        logger.info(
                            f"🧩 Remarketing campaign media: campaign_id={campaign.id} "
                            f"media_type={campaign.media_type!r} media_url={campaign.media_url!r}"
                        )
                        
                        # ✅ Buscar apenas o batch atual (paginação)
                        try:
                            batch = query.offset(offset).limit(batch_size).all()
                        except Exception as query_error:
                            logger.error(f"❌ Erro ao buscar batch {batch_number} (offset {offset}): {query_error}", exc_info=True)
                            # Tentar pular para próximo batch
                            offset += batch_size
                            continue
                        
                        if not batch:
                            logger.warning(f"⚠️ Batch {batch_number} vazio (offset: {offset}), finalizando processamento")
                            break
                        
                        logger.info(f"✅ Batch {batch_number} carregado: {len(batch)} leads encontrados")
                        
                        batch_sent = 0
                        batch_failed = 0
                        batch_blocked = 0
                        consecutive_401_errors = 0  # ✅ Contador de erros 401 consecutivos
                        max_401_errors = 20  # ✅ Parar se 20 erros 401 consecutivos (token claramente inválido) - limite aumentado por segurança
                        first_lead_logged = False
                        
                        for lead in batch:
                            try:
                                if not first_lead_logged:
                                    logger.warning(
                                        f"🔎 LOOP ATIVO: entrando no envio por lead | campaign_id={campaign.id} bot_id={campaign.bot_id} "
                                        f"batch={batch_number} batch_size={len(batch)}"
                                    )
                                    first_lead_logged = True

                                # ✅ Diagnóstico/proteção: lead sem telegram_user_id não pode receber envio
                                if not getattr(lead, 'telegram_user_id', None):
                                    batch_failed += 1
                                    logger.warning(
                                        f"❌ FALHA: bot={campaign.bot_id} lead_id={getattr(lead, 'id', None)} "
                                        f"motivo=missing_telegram_user_id batch={batch_number}"
                                    )
                                    continue

                                # ✅ CRÍTICO: Se muitos erros 401 consecutivos, token está inválido - pular batch
                                if consecutive_401_errors >= max_401_errors:
                                    logger.error(f"🛑 Token do bot {campaign.bot_id} está INVÁLIDO ({consecutive_401_errors} erros 401 consecutivos) - PARANDO envio para este bot")
                                    logger.error(f"🛑 Ação necessária: Verificar/atualizar token do bot {campaign.bot_id} no painel")
                                    # Marcar todos os leads restantes como falha
                                    batch_failed += len(batch) - (batch_sent + batch_failed + batch_blocked)
                                    break  # Sair do loop de leads
                                
                                # ✅ MELHORIA: Verificar se usuário está na blacklist ANTES de tentar enviar
                                # Isso evita tentativas desnecessárias e melhora performance
                                is_blocked = db.session.query(RemarketingBlacklist).filter_by(
                                    bot_id=campaign.bot_id,
                                    telegram_user_id=lead.telegram_user_id
                                ).first()
                                
                                if is_blocked:
                                    batch_blocked += 1
                                    logger.info(
                                        f"🚫 BLOQUEADO: bot={campaign.bot_id} chat_id={lead.telegram_user_id} "
                                        f"batch={batch_number}"
                                    )
                                    continue  # Pular este lead e ir para o próximo
                                
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
                                
                                # Enviar mensagem
                                logger.warning(
                                    f"🚀 TENTATIVA_ENVIO: bot={campaign.bot_id} campaign_id={campaign.id} "
                                    f"chat_id={lead.telegram_user_id} lead_id={getattr(lead, 'id', None)} "
                                    f"media_type={campaign.media_type!r} batch={batch_number}"
                                )
                                result = self.send_telegram_message(
                                    token=bot_token,
                                    chat_id=lead.telegram_user_id,
                                    message=message,
                                    media_url=campaign.media_url,
                                    media_type=campaign.media_type,
                                    buttons=remarketing_buttons
                                )

                                if not first_lead_logged:
                                    # redundante por segurança (não deve acontecer)
                                    first_lead_logged = True
                                
                                # Log pós-envio apenas para a primeira tentativa do batch (reduz spam)
                                if first_lead_logged is True and batch_sent == 0 and batch_failed == 0 and batch_blocked == 0:
                                    logger.warning(
                                        f"🧾 RETORNO_ENVIO (1º lead do batch): bot={campaign.bot_id} campaign_id={campaign.id} "
                                        f"chat_id={lead.telegram_user_id} result_type={type(result).__name__}"
                                    )
                                
                                # ✅ CRÍTICO: Verificar se result é dict com erro (novo formato) ou bool/True (formato antigo)
                                if isinstance(result, dict) and result.get('error'):
                                    # ✅ Novo formato: result contém informações do erro
                                    error_code = result.get('error_code', 0)
                                    error_description = result.get('description', '').lower()
                                    
                                    if error_code == 401:
                                        # ✅ Erro 401 - token inválido
                                        consecutive_401_errors += 1
                                        batch_failed += 1
                                        logger.error(f"🔑 Token INVÁLIDO para bot {campaign.bot_id} (erro 401 #{consecutive_401_errors}/{max_401_errors}) - lead {lead.telegram_user_id}")
                                        if consecutive_401_errors >= max_401_errors:
                                            logger.error(f"🛑 Token do bot {campaign.bot_id} está claramente INVÁLIDO - PARANDO envio para evitar desperdício de recursos")
                                            logger.error(f"🛑 Ação necessária: Verificar/atualizar token do bot {campaign.bot_id} no painel de configuração")
                                            # Marcar todos os leads restantes como falha
                                            remaining_leads = len(batch) - (batch_sent + batch_failed + batch_blocked)
                                            batch_failed += remaining_leads
                                            break  # Sair do loop de leads
                                    elif error_code == 403 and ("bot was blocked" in error_description or "forbidden: bot was blocked" in error_description):
                                        # ✅ MELHORIA: Erro 403 - bot bloqueado pelo usuário - adicionar à blacklist
                                        batch_blocked += 1
                                        consecutive_401_errors = 0  # Reset (não é erro de token)
                                        logger.warning(f"🚫 Bot bloqueado pelo usuário {lead.telegram_user_id} (erro 403)")
                                        
                                        # ✅ CRÍTICO: Adicionar na blacklist IMEDIATAMENTE
                                        try:
                                            # Verificar se já está na blacklist (evitar duplicatas)
                                            existing = db.session.query(RemarketingBlacklist).filter_by(
                                                bot_id=campaign.bot_id,
                                                telegram_user_id=lead.telegram_user_id
                                            ).first()
                                            
                                            if not existing:
                                                blacklist = RemarketingBlacklist(
                                                    bot_id=campaign.bot_id,
                                                    telegram_user_id=lead.telegram_user_id,
                                                    reason='bot_blocked'
                                                )
                                                db.session.add(blacklist)
                                                # ✅ CRÍTICO: Commit imediato para garantir que blacklist seja salva
                                                try:
                                                    db.session.commit()
                                                    logger.info(f"🚫 Usuário {lead.telegram_user_id} adicionado à blacklist do bot {campaign.bot_id} (bloqueado via erro 403)")
                                                except Exception as commit_error:
                                                    logger.error(f"❌ Erro ao commitar blacklist: {commit_error}")
                                                    db.session.rollback()
                                            else:
                                                logger.debug(f"ℹ️ Usuário {lead.telegram_user_id} já está na blacklist do bot {campaign.bot_id}")
                                        except Exception as blacklist_error:
                                            logger.warning(f"⚠️ Erro ao adicionar blacklist: {blacklist_error}")
                                            db.session.rollback()
                                    else:
                                        # Outro erro - reset contador 401
                                        consecutive_401_errors = 0
                                        batch_failed += 1
                                        logger.warning(
                                            f"❌ FALHA: bot={campaign.bot_id} chat_id={lead.telegram_user_id} "
                                            f"error_code={error_code} desc={error_description[:120]} batch={batch_number}"
                                        )
                                elif result:
                                    # ✅ Sucesso (result é True ou dict com dados)
                                    logger.debug(f"✅ Remarketing enviado com sucesso para {lead.telegram_user_id}")
                                    logger.info(
                                        f"📨 ENVIADO: bot={campaign.bot_id} chat_id={lead.telegram_user_id} "
                                        f"type={campaign.media_type} batch={batch_number}"
                                    )
                                    batch_sent += 1
                                    consecutive_401_errors = 0  # ✅ Reset contador se sucesso
                                    
                                    # ✅ Enviar áudio adicional se habilitado
                                    if campaign.audio_enabled and campaign.audio_url:
                                        try:
                                            audio_result = self.send_telegram_message(
                                                token=bot_token,
                                                chat_id=lead.telegram_user_id,
                                                message="",
                                                media_url=campaign.audio_url,
                                                media_type='audio',
                                                buttons=None
                                            )
                                            if isinstance(audio_result, dict) and audio_result.get('error'):
                                                logger.warning(f"⚠️ Áudio não foi enviado para {lead.telegram_user_id} (erro {audio_result.get('error_code', 'desconhecido')})")
                                            elif not audio_result:
                                                logger.warning(f"⚠️ Áudio não foi enviado para {lead.telegram_user_id} (result=False)")
                                        except Exception as audio_error:
                                            logger.warning(f"⚠️ Erro ao enviar áudio para {lead.telegram_user_id}: {audio_error}")
                                else:
                                    # ✅ Result é False (formato antigo - compatibilidade)
                                    logger.warning(
                                        f"❌ FALHA: bot={campaign.bot_id} chat_id={lead.telegram_user_id} "
                                        f"result=False batch={batch_number}"
                                    )
                                    batch_failed += 1
                                    
                            except Exception as e:
                                error_msg = str(e).lower()
                                logger.warning(f"⚠️ Erro ao enviar para {lead.telegram_user_id}: {e}")
                                
                                # ✅ Tratamento específico de erros comuns
                                if "bot was blocked" in error_msg or "forbidden: bot was blocked" in error_msg:
                                    batch_blocked += 1
                                    consecutive_401_errors = 0  # Reset (não é erro de token)
                                    # ✅ MELHORIA: Adicionar na blacklist IMEDIATAMENTE para evitar tentativas futuras
                                    try:
                                        # Verificar se já está na blacklist (evitar duplicatas)
                                        existing = db.session.query(RemarketingBlacklist).filter_by(
                                            bot_id=campaign.bot_id,
                                            telegram_user_id=lead.telegram_user_id
                                        ).first()
                                        
                                        if not existing:
                                            blacklist = RemarketingBlacklist(
                                                bot_id=campaign.bot_id,
                                                telegram_user_id=lead.telegram_user_id,
                                                reason='bot_blocked'
                                            )
                                            db.session.add(blacklist)
                                            # ✅ CRÍTICO: Commit imediato para garantir que blacklist seja salva
                                            try:
                                                db.session.commit()
                                                logger.info(f"🚫 Usuário {lead.telegram_user_id} adicionado à blacklist do bot {campaign.bot_id} (bloqueado)")
                                            except Exception as commit_error:
                                                logger.error(f"❌ Erro ao commitar blacklist: {commit_error}")
                                                db.session.rollback()
                                        else:
                                            logger.debug(f"ℹ️ Usuário {lead.telegram_user_id} já está na blacklist do bot {campaign.bot_id}")
                                    except Exception as blacklist_error:
                                        logger.warning(f"⚠️ Erro ao adicionar blacklist: {blacklist_error}")
                                        db.session.rollback()
                                elif "rate limit" in error_msg or "too many requests" in error_msg or "error_code\":429" in error_msg:
                                    # ✅ Rate limiting do Telegram - aguardar e tentar novamente
                                    batch_failed += 1
                                    consecutive_401_errors = 0  # Reset (não é erro de token)
                                    logger.warning(f"⏱️ Rate limit do Telegram atingido para {lead.telegram_user_id} - aguardando 1 segundo...")
                                    time.sleep(1)  # Aguardar 1 segundo antes de continuar
                                elif "unauthorized" in error_msg or "error_code\":401" in error_msg:
                                    # ✅ Token inválido - incrementar contador e parar se muitos consecutivos
                                    batch_failed += 1
                                    consecutive_401_errors += 1
                                    logger.error(f"🔑 Token INVÁLIDO para bot {campaign.bot_id} (erro 401 #{consecutive_401_errors}/{max_401_errors}) - lead {lead.telegram_user_id}")
                                    if consecutive_401_errors >= max_401_errors:
                                        logger.error(f"🛑 Token do bot {campaign.bot_id} está claramente INVÁLIDO - PARANDO envio para evitar desperdício de recursos")
                                        logger.error(f"🛑 Ação necessária: Verificar/atualizar token do bot {campaign.bot_id} no painel de configuração")
                                elif "chat not found" in error_msg or "error_code\":400" in error_msg:
                                    # ✅ Chat não existe mais - contar como falha mas continuar
                                    batch_failed += 1
                                    consecutive_401_errors = 0  # Reset (não é erro de token)
                                    logger.warning(f"💬 Chat não encontrado para lead {lead.telegram_user_id}")
                                elif "user is deactivated" in error_msg:
                                    # ✅ Usuário desativado - contar como falha mas continuar
                                    batch_failed += 1
                                    consecutive_401_errors = 0  # Reset (não é erro de token)
                                    logger.warning(f"🚫 Usuário desativado: {lead.telegram_user_id}")
                                else:
                                    # ✅ Outros erros - contar como falha mas continuar processamento
                                    batch_failed += 1
                                    consecutive_401_errors = 0  # Reset (não é erro de token)
                                    logger.warning(f"❓ Erro desconhecido para lead {lead.telegram_user_id}: {e}")
                        
                        # ✅ CRÍTICO: Atualizar contadores e fazer commit com tratamento de erro
                        try:
                            # ✅ CRÍTICO: Recarregar campaign do banco para garantir dados atualizados
                            db.session.refresh(campaign)
                            campaign.total_sent += batch_sent
                            campaign.total_failed += batch_failed
                            campaign.total_blocked += batch_blocked
                            
                            # ✅ NOVO: Verificar se sistema está sobrecarregado (muitos erros consecutivos)
                            # Se mais de 80% dos leads falharem em um batch, pausar por mais tempo
                            total_in_batch = batch_sent + batch_failed + batch_blocked
                            if total_in_batch > 0:
                                failure_rate = (batch_failed + batch_blocked) / total_in_batch
                                if failure_rate > 0.8:
                                    # ✅ Pausa maior quando muitas falhas (mas não avisar usuário)
                                    logger.debug(f"⚠️ Taxa de falha alta ({failure_rate*100:.1f}%) - pausando por mais tempo...")
                                    time.sleep(2.5)  # Pausa moderada quando muitas falhas
                                else:
                                    # ✅ Pausa otimizada para throughput maior (sistema multi-usuário)
                                    time.sleep(0.8)  # Reduzido para processar mais rápido
                            else:
                                time.sleep(0.8)  # Pausa padrão otimizada
                            
                            db.session.commit()
                            db.session.refresh(campaign)  # ✅ Refresh após commit
                            
                            progress_pct = round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                            logger.info(f"✅✅ Batch {batch_number} concluído: ✅{batch_sent} enviados | ❌{batch_failed} falhas | 🚫{batch_blocked} bloqueados | 📊 Total geral: {campaign.total_sent}/{campaign.total_targets} ({progress_pct}%)")
                            
                        except Exception as commit_error:
                            logger.error(f"❌ Erro ao commitar batch {batch_number}: {commit_error}", exc_info=True)
                            try:
                                db.session.rollback()
                                # Tentar novamente com refresh
                                db.session.refresh(campaign)
                                campaign.total_sent += batch_sent
                                campaign.total_failed += batch_failed
                                campaign.total_blocked += batch_blocked
                                db.session.commit()
                                db.session.refresh(campaign)
                                logger.info(f"✅ Batch {batch_number} recuperado após rollback: Total {campaign.total_sent}/{campaign.total_targets}")
                            except Exception as retry_error:
                                logger.error(f"❌ Erro crítico ao recuperar batch {batch_number}: {retry_error}", exc_info=True)
                                # ✅ IMPORTANTE: Continuar mesmo com erro para não perder progresso
                                # Salvar contadores em memória para tentar commitar no próximo batch
                                logger.warning(f"⚠️ Batch {batch_number} não foi salvo no banco, mas processamento continuará")
                        
                        # ✅ Emitir progresso via WebSocket com tratamento de erro
                        try:
                            socketio.emit('remarketing_progress', {
                                'campaign_id': campaign.id,
                                'sent': campaign.total_sent,
                                'failed': campaign.total_failed,
                                'blocked': campaign.total_blocked,
                                'total': campaign.total_targets,
                                'percentage': round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                            })
                        except Exception as socket_error:
                            logger.warning(f"⚠️ Erro ao emitir progresso WebSocket: {socket_error}")
                        
                        # ✅ Rate limiting otimizado: sleep condicional já aplicado acima
                        # Sistema multi-usuário: processamento mais rápido quando possível
                        
                        # ✅ Atualizar offset para próximo batch
                        offset += batch_size
                        progress_pct = round((offset / total_leads) * 100, 1) if total_leads > 0 else 0
                        logger.info(f"📊 Progresso geral: {offset}/{total_leads} leads processados ({progress_pct}%)")
                    
                    # ✅ Finalizar campanha com tratamento robusto
                    logger.info(f"🏁 Finalizando campanha {campaign_id} após processar todos os batches")
                    try:
                        db.session.refresh(campaign)  # ✅ CRÍTICO: Refresh antes de finalizar
                        campaign.status = 'completed'
                        from internal_logic.core.models import get_brazil_time
                        campaign.completed_at = get_brazil_time()
                        db.session.commit()
                        db.session.refresh(campaign)  # ✅ Refresh após commit final
                        
                        total_processed = campaign.total_sent + campaign.total_failed + campaign.total_blocked
                        success_rate = round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                        
                        logger.info(f"✅✅✅ CAMPANHA {campaign_id} CONCLUÍDA: {campaign.total_sent}/{campaign.total_targets} enviados ({success_rate}%) | Falhas: {campaign.total_failed} | Bloqueados: {campaign.total_blocked} | Total processado: {total_processed}")
                        
                    except Exception as final_error:
                        logger.error(f"❌ Erro ao finalizar campanha: {final_error}", exc_info=True)
                        try:
                            db.session.rollback()
                            db.session.refresh(campaign)
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            logger.info(f"✅ Campanha finalizada após rollback")
                        except Exception as retry_error:
                            logger.error(f"❌ Erro crítico ao finalizar campanha: {retry_error}", exc_info=True)
                    
                    # ✅ Emitir conclusão com tratamento de erro
                    try:
                        socketio.emit('remarketing_completed', {
                            'campaign_id': campaign.id,
                            'total_sent': campaign.total_sent,
                            'total_failed': campaign.total_failed,
                            'total_blocked': campaign.total_blocked
                        })
                    except Exception as socket_error:
                        logger.warning(f"⚠️ Erro ao emitir conclusão WebSocket: {socket_error}")
                except KeyboardInterrupt:
                    # ✅ Tratar interrupção graciosamente sem crashar
                    logger.warning(f"⚠️ Campanha {campaign_id} interrompida pelo usuário")
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'paused'
                            db.session.commit()
                    except:
                        pass
                    raise  # Re-raise para permitir shutdown gracioso
                except SystemExit:
                    # ✅ Tratar SystemExit graciosamente
                    logger.warning(f"⚠️ Campanha {campaign_id} interrompida por SystemExit")
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'failed'
                            campaign.error_message = 'Sistema reiniciando'
                            db.session.commit()
                    except:
                        pass
                    raise  # Re-raise para permitir shutdown gracioso
                except MemoryError:
                    # ✅ CRÍTICO: Tratar falta de memória sem crashar o sistema
                    logger.error(f"❌ MEMÓRIA INSUFICIENTE na campanha {campaign_id} - pausando")
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'failed'
                            campaign.error_message = 'Memória insuficiente - sistema sobrecarregado'
                            db.session.commit()
                    except:
                        pass
                    # Não re-raise MemoryError para evitar crash
                    return
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar campanha de remarketing {campaign_id}: {e}", exc_info=True)
                    # ✅ GARANTIR: Atualizar status mesmo em caso de erro
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign and campaign.status == 'sending':
                            # Se já enviou alguma mensagem, marcar como concluída
                            if campaign.total_sent and campaign.total_sent > 0:
                                campaign.status = 'completed'
                                from internal_logic.core.models import get_brazil_time
                                if not campaign.completed_at:
                                    campaign.completed_at = get_brazil_time()
                                db.session.commit()
                                logger.info(f"✅ Status atualizado para 'completed' após erro (campanha {campaign_id}: {campaign.total_sent} enviados)")
                            else:
                                # Se não enviou nada, marcar como falha
                                campaign.status = 'failed'
                                db.session.commit()
                                logger.info(f"✅ Status atualizado para 'failed' após erro (campanha {campaign_id})")
                    except Exception as update_error:
                        logger.error(f"❌ Erro ao atualizar status após falha: {update_error}", exc_info=True)
                        db.session.rollback()
        
        # ✅ CONTROLE DE CONCORRÊNCIA: Usar semáforo para limitar threads simultâneas
        def send_campaign_with_limit():
            """Wrapper que controla concorrência de remarketing"""
            # Adicionar campanha à lista de ativas
            self.active_remarketing_campaigns.add(campaign_id)
            logger.info(f"🧵 Remarketing worker iniciado: campaign_id={campaign_id} (aguardando slot do semáforo)")
            
            # ✅ LOOP INFINITO: Tentar adquirir slot até conseguir (transparente para usuário)
            # Sistema multi-usuário: todas as campanhas serão processadas, mesmo que aguardem
            max_retries = 360  # Máximo 6 horas de tentativas (360 * 60s = 6 horas)
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # ✅ Tentar adquirir slot (timeout de 60 segundos por tentativa)
                    acquired = self.remarketing_semaphore.acquire(timeout=60)
                    
                    if acquired:
                        # ✅ Slot adquirido - iniciar processamento
                        logger.info(f"✅ Slot adquirido: campaign_id={campaign_id} (tentativa {retry_count + 1})")
                        break
                    else:
                        # ✅ Slot não disponível - aguardar e tentar novamente
                        retry_count += 1
                        if retry_count % 10 == 0:  # Log a cada 10 tentativas (10 minutos)
                            logger.info(f"⏳ Campanha {campaign_id} aguardando slot... (tentativa {retry_count}/{max_retries})")
                        time.sleep(5)  # Aguardar 5 segundos antes de tentar novamente
                        continue
                        
                except Exception as acquire_error:
                    logger.warning(f"⚠️ Erro ao adquirir slot para campanha {campaign_id}: {acquire_error}")
                    time.sleep(10)  # Aguardar mais tempo em caso de erro
                    retry_count += 1
                    continue
            
            if retry_count >= max_retries:
                # ✅ Timeout muito longo - apenas logar (não falhar)
                logger.error(f"❌ Campanha {campaign_id} não conseguiu slot após {max_retries} tentativas")
                try:
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    with current_app.app_context():
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign and campaign.status == 'sending':
                            # Manter como 'sending' mas adicionar nota no erro
                            campaign.error_message = f'Sistema muito ocupado - aguardando processamento'
                            db.session.commit()
                except:
                    pass
                return
            
            try:
                
                # Executar campanha (já tem app_context interno)
                logger.info(f"🔥 Iniciando send_campaign(): campaign_id={campaign_id}")
                send_campaign()
                logger.info(f"✅ send_campaign() retornou: campaign_id={campaign_id}")
                
            except Exception as outer_error:
                logger.error(f"❌ Erro crítico na campanha {campaign_id}: {outer_error}", exc_info=True)
                try:
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    with current_app.app_context():
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'failed'
                            campaign.error_message = f'Erro crítico: {str(outer_error)[:200]}'
                            db.session.commit()
                except:
                    pass
            finally:
                # Liberar semáforo e remover da lista de ativas
                self.remarketing_semaphore.release()
                self.active_remarketing_campaigns.discard(campaign_id)
                logger.info(f"✅ Slot liberado - Campanha {campaign_id} concluída")
                
                # ✅ Se há campanhas na fila, processar próxima automaticamente
                # (transparente para o usuário - não precisa fazer nada)
        
        # Executar em thread separada
        thread = threading.Thread(target=send_campaign_with_limit)
        thread.daemon = True
        thread.start()
        logger.info(f"🚀 Thread disparada para remarketing: campaign_id={campaign_id} thread_name={thread.name}")
    
    # ============================================================================
    # ✅ SISTEMA DE ASSINATURAS - Ativação e Gerenciamento
    # ============================================================================
    
    def _activate_subscription(self, subscription_id: int) -> bool:
        """
        Ativa subscription quando usuário entra no grupo VIP
        
        # ✅ LOCK PESSIMISTA para evitar race condition
        # ✅ Calcula expires_at usando dateutil.relativedelta para meses
        
        Retorna: True se ativada com sucesso, False caso contrário
        """
        from flask import current_app
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Subscription
        from datetime import datetime, timezone
        from dateutil.relativedelta import relativedelta
        from sqlalchemy import select
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            with current_app.app_context():
                # ✅ LOCK PESSIMISTA: Selecionar subscription com lock
                subscription = db.session.execute(
                    select(Subscription)
                    .where(Subscription.id == subscription_id)
                    .where(Subscription.status == 'pending')
                    .with_for_update()
                ).scalar_one_or_none()
                
                if not subscription:
                    # Subscription não existe ou já foi ativada
                    logger.debug(f"Subscription {subscription_id} não encontrada ou já ativada")
                    return False
                
                # ✅ CORREÇÃO 3 (ROBUSTA): Validação explícita de status após lock (defensive programming)
                # Verificação redundante garante que status não foi alterado entre lock e update
                # Previne race conditions e garante consistência mesmo em cenários edge case
                if subscription.status != 'pending':
                    logger.warning(
                        f"⚠️ Subscription {subscription_id} não está em status 'pending' "
                        f"(status atual: {subscription.status}) - abortando ativação"
                    )
                    return False
                
                # ✅ Validação adicional: Verificar se started_at já está definido (segunda camada de proteção)
                if subscription.started_at is not None:
                    logger.warning(
                        f"⚠️ Subscription {subscription_id} já possui started_at definido "
                        f"({subscription.started_at}) - subscription já foi ativada anteriormente"
                    )
                    return False
                
                # ✅ Calcular expires_at
                now_utc = datetime.now(timezone.utc)
                
                duration_type = subscription.duration_type
                duration_value = subscription.duration_value
                
                if duration_type == 'hours':
                    expires_at = now_utc + relativedelta(hours=duration_value)
                elif duration_type == 'days':
                    expires_at = now_utc + relativedelta(days=duration_value)
                elif duration_type == 'weeks':
                    expires_at = now_utc + relativedelta(weeks=duration_value)
                elif duration_type == 'months':
                    # ✅ USAR relativedelta para meses corretos (30 dias ≠ 1 mês)
                    expires_at = now_utc + relativedelta(months=duration_value)
                else:
                    logger.error(f"❌ Duration type inválido: {duration_type}")
                    subscription.status = 'error'
                    subscription.last_error = f"Duration type inválido: {duration_type}"
                    db.session.commit()
                    return False
                
                # ✅ Atualizar subscription
                subscription.status = 'active'
                subscription.started_at = now_utc
                subscription.expires_at = expires_at
                
                db.session.commit()
                
                logger.info(f"✅ Subscription {subscription_id} ativada | Expira em: {expires_at} UTC ({duration_value} {duration_type})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao ativar subscription {subscription_id}: {e}", exc_info=True)
            db.session.rollback()
            return False
    
    def _handle_new_chat_member(self, bot_id: int, chat_id: int, telegram_user_id: str):
        """
        Processa quando novo membro entra no grupo
        
        # ✅ Ativa subscriptions pendentes para este usuário neste grupo
        """
        from flask import current_app
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Subscription
        from utils.subscriptions import normalize_vip_chat_id
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            with current_app.app_context():
                # ✅ Buscar subscriptions pendentes para este usuário neste grupo
                pending_subscriptions = Subscription.query.filter(
                    Subscription.bot_id == bot_id,
                    Subscription.telegram_user_id == telegram_user_id,
                    # ✅ CORREÇÃO 4 (ROBUSTA): Usar função centralizada de normalização
                    Subscription.vip_chat_id == normalize_vip_chat_id(str(chat_id)),
                    Subscription.status == 'pending'
                ).all()
                
                if not pending_subscriptions:
                    logger.debug(f"Nenhuma subscription pendente para user {telegram_user_id} no grupo {chat_id}")
                    return
                
                logger.info(f"🎉 Usuário {telegram_user_id} entrou no grupo VIP {chat_id} | {len(pending_subscriptions)} subscription(s) pendente(s)")
                
                # ✅ Ativar cada subscription
                for subscription in pending_subscriptions:
                    try:
                        success = self._activate_subscription(subscription.id)
                        if success:
                            logger.info(f"✅ Subscription {subscription.id} ativada quando usuário entrou no grupo")
                        else:
                            logger.warning(f"⚠️ Falha ao ativar subscription {subscription.id}")
                    except Exception as e:
                        logger.error(f"❌ Erro ao ativar subscription {subscription.id}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"❌ Erro ao processar new_chat_member: {e}", exc_info=True)
    
    def cancel_downsells(self, payment_id: str):
        """
        Cancela downsells agendados para um pagamento
        
        Args:
            payment_id: ID do pagamento
        """
        logger.info(f"🚫 ===== CANCEL_DOWNSELLS CHAMADO =====")
        logger.info(f"   payment_id: {payment_id}")
        
        try:
            if not self.scheduler:
                logger.warning(f"⚠️ Scheduler não disponível - não é possível cancelar downsells")
                return
            
            # Encontrar e remover jobs de downsell para este pagamento
            jobs_to_remove = []
            try:
                all_jobs = self.scheduler.get_jobs()
                logger.info(f"🔍 Total de jobs no scheduler: {len(all_jobs)}")
                
                for job in all_jobs:
                    if job.id.startswith(f"downsell_") and payment_id in job.id:
                        jobs_to_remove.append(job.id)
                        logger.info(f"   - Job encontrado: {job.id} (próxima execução: {job.next_run_time})")
            except Exception as e:
                logger.error(f"❌ Erro ao listar jobs: {e}")
                return
            
            if not jobs_to_remove:
                logger.info(f"ℹ️ Nenhum downsell agendado encontrado para payment {payment_id}")
                return
            
            logger.info(f"🚫 Cancelando {len(jobs_to_remove)} downsell(s)...")
            for job_id in jobs_to_remove:
                try:
                    self.scheduler.remove_job(job_id)
                    logger.info(f"✅ Downsell cancelado: {job_id}")
                except Exception as e:
                    logger.error(f"❌ Erro ao cancelar job {job_id}: {e}")
            
            logger.info(f"🚫 ===== FIM CANCEL_DOWNSELLS =====")
                
        except Exception as e:
            logger.error(f"❌ Erro ao cancelar downsells para pagamento {payment_id}: {e}", exc_info=True)


