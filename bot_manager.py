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
from internal_logic.core.redis_manager import get_redis_connection
import hashlib
import hmac
from internal_logic.services.flow_engine_router_v8 import get_message_router
from internal_logic.services.bot_messenger import BotMessenger, checkActiveFlow
from internal_logic.services.bot_runner import BotRunner
from internal_logic.services.flow_engine import FlowEngine
from internal_logic.services.payment_service import PaymentService, get_payment_service
from internal_logic.services.payment_verifier import verify_payment
from internal_logic.services.subscription_service import activate_subscription, handle_new_chat_member
from internal_logic.services.offer_sender import cancel_downsells as cancel_scheduled_downsells
from internal_logic.services import remarketing_sender
from internal_logic.services.start_command_handler import handle_start_command as handle_start_cmd
from internal_logic.services.callback_handler import handle_callback_query as handle_callback

logger = logging.getLogger(__name__)

# Configurar logging para este módulo
logger.setLevel(logging.INFO)


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

from gateways import GatewayFactory
from internal_logic.core.redis_manager import get_redis_connection
from internal_logic.core.redis_bot_state import redis_bot_state, get_namespaced_bot_state  # ✅ ISOLAMENTO: Importar factory V2
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
        
        # ✅ REMARKETING SENDER: Serviço de remarketing extraído
        from internal_logic.services.remarketing_sender import RemarketingSender
        self.remarketing_sender = RemarketingSender(
            user_id=user_id,
            send_message_func=self.send_telegram_message,
        )

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
        """Inicia worker de remarketing (delega para RemarketingSender)"""
        self.remarketing_sender.start_remarketing_worker(bot_id=bot_id, bot_token=bot_token)

    def _get_remarketing_worker_token(self, bot_id: int) -> Optional[str]:
        """Retorna token do worker (delega para RemarketingSender)"""
        return self.remarketing_sender.get_remarketing_worker_token(bot_id)

    def _remarketing_worker_loop(self, *, bot_id: int, stop_event: threading.Event) -> None:
        """Loop do worker (delega para RemarketingSender)"""
        self.remarketing_sender._remarketing_worker_loop(bot_id=bot_id, stop_event=stop_event)

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
                            self._process_telegram_update(bot_id, None, update)
                        
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
                                self._process_telegram_update(bot_id, None, update)
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

                # Detectar mídia na mensagem (foto, vídeo, documento, áudio)
                media_type = 'text'
                media_url = None
                caption = ''
                if 'photo' in message:
                    media_type = 'photo'
                    photos = message['photo']
                    media_url = photos[-1]['file_id']
                    caption = message.get('caption', '') or ''
                elif 'video' in message:
                    media_type = 'video'
                    media_url = message['video']['file_id']
                    caption = message.get('caption', '') or ''
                elif 'document' in message:
                    media_type = 'document'
                    media_url = message['document']['file_id']
                    caption = message.get('caption', '') or ''
                elif 'audio' in message:
                    media_type = 'audio'
                    media_url = message['audio']['file_id']
                    caption = message.get('caption', '') or ''
                if not text:
                    text = caption
                
                logger.info(f"💬 De: {user.get('first_name', 'Usuário')} | Tipo: {media_type} | Texto: '{text[:50] if text else '(vazio)'}'")
                
                # ✅ CHAT: Salvar mensagem recebida no banco (SEMPRE, independente do comando)
                if text and text.strip() or media_type != 'text':
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
                                        message_text=text or caption,
                                        message_type=media_type,
                                        direction='incoming',
                                        is_read=False,
                                        media_url=media_url,
                                        raw_data=json.dumps(message)
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
                    from internal_logic.services.flow_engine_router_v8 import get_message_router
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
                            current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
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
                    current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
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
        handle_start_cmd(self, bot_id, token, config, chat_id, message, start_param)
    
    def _handle_callback_query(self, bot_id: int, token: str, config: Dict[str, Any], 
                               callback: Dict[str, Any]):
        handle_callback(self, bot_id, token, config, callback)
    
    def _handle_verify_payment(self, bot_id: int, token: str, chat_id: int, 
                               payment_id: str, user_info: Dict[str, Any]):
        verify_payment(self, bot_id, token, chat_id, payment_id, user_info)
    
    def _show_multiple_order_bumps(self, bot_id: int, token: str, chat_id: int, user_info: Dict[str, Any],
                                   original_price: float, original_description: str, button_index: int,
                                   order_bumps: List[Dict[str, Any]]):
        """
        Exibe múltiplos Order Bumps SEQUENCIAIS - VERSÃO REDIS (Multi-Worker)
        
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
            import json as json_lib  # ✅ Proteção contra shadowing do módulo json
            
            # ✅ REDIS MIGRATION: user_key e chave Redis
            user_key = f"orderbump_{chat_id}"
            redis_key = f"gb:ob_session:{user_key}"
            
            # ✅ REDIS MIGRATION: Verificar se já existe sessão
            redis_conn = get_redis_connection()
            existing_session_json = redis_conn.get(redis_key)
            
            if existing_session_json:
                existing_session = json_lib.loads(existing_session_json)
                existing_button = existing_session.get('button_index', 'N/A')
                logger.info(f"🔄 Substituindo sessão anterior (botão {existing_button}) por nova (botão {button_index})")
                # Redis delete + setex vai substituir
                redis_conn.delete(redis_key)
            
            # ✅ IMPLEMENTAÇÃO QI 600+: Copiar tracking do Redis para sessão
            session_tracking = None
            try:
                chat_tracking_key = f'tracking:chat:{chat_id}'
                chat_tracking_json = redis_conn.get(chat_tracking_key)
                if chat_tracking_json:
                    session_tracking = json_lib.loads(chat_tracking_json)
                    logger.info(f"🔑 Tracking copiado para sessão via tracking:chat:{chat_id}")
                
                if not session_tracking:
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import BotUser
                    with current_app.app_context():
                        bot_user = BotUser.query.filter_by(
                            bot_id=bot_id,
                            telegram_user_id=str(chat_id)
                        ).first()
                        if bot_user and bot_user.fbclid:
                            fbclid_key = f'tracking:fbclid:{bot_user.fbclid}'
                            fbclid_tracking_json = redis_conn.get(fbclid_key)
                            if fbclid_tracking_json:
                                session_tracking = json_lib.loads(fbclid_tracking_json)
                                logger.info(f"🔑 Tracking copiado via tracking:fbclid:{bot_user.fbclid[:20]}...")
            except Exception as tracking_error:
                logger.warning(f"⚠️ Erro ao copiar tracking para sessão: {tracking_error}")
            
            # ✅ REDIS MIGRATION: Criar sessão e salvar no Redis
            session_data = {
                'bot_id': bot_id,
                'chat_id': chat_id,
                'original_price': original_price,
                'original_description': original_description,
                'button_index': button_index,
                'order_bumps': order_bumps,
                'current_index': 0,
                'accepted_bumps': [],
                'total_bump_value': 0.0,
                'created_at': time.time(),
                'fbclid': session_tracking.get('fbclid') if session_tracking else None,
                'tracking': session_tracking,
                'status': 'active'
            }
            
            # ✅ REDIS MIGRATION: Persistir no Redis com TTL 10 minutos
            redis_conn.setex(redis_key, 600, json_lib.dumps(session_data))
            logger.info(f"💾 Sessão de order bump salva no Redis: {redis_key} (TTL 10min)")
            
            # Exibir primeiro order bump
            self._show_next_order_bump(bot_id, token, chat_id, user_key)
            
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
            import json as json_lib  # ✅ Proteção contra shadowing do módulo json
            
            # ✅ REDIS MIGRATION: Buscar sessão do Redis
            redis_key = f"gb:ob_session:{user_key}"
            redis_conn = get_redis_connection()
            session_json = redis_conn.get(redis_key)
            
            if not session_json:
                logger.error(f"❌ Sessão de order bump não encontrada no Redis: {redis_key}")
                return
            
            session = json_lib.loads(session_json)
            
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
            import json as json_lib  # ✅ Proteção contra shadowing do módulo json
            current_time = time.time()
            
            # ✅ REDIS MIGRATION: Chaves para sessão e cache PIX
            redis_conn = get_redis_connection()
            session_key = f"gb:ob_session:{user_key}"
            pix_cache_key = f"gb:pix_cache:{user_key}"
            
            # ✅ IDEMPOTÊNCIA: Verificar se PIX já foi gerado recentemente (Redis)
            pix_cache_json = redis_conn.get(pix_cache_key)
            if pix_cache_json:
                cached = json_lib.loads(pix_cache_json)
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
            
            session = json_lib.loads(session_json)
            
            # ✅ IDEMPOTÊNCIA: Verificar se sessão já gerou PIX
            if session.get('status') == 'pix_generated':
                payment_id = session.get('payment_id')
                logger.info(f"🔄 Sessão já gerou PIX anteriormente: {payment_id}")
                # Tentar recuperar do cache (já verificado acima, mas double-check)
                pix_cache_json = redis_conn.get(pix_cache_key)
                if pix_cache_json:
                    cached = json_lib.loads(pix_cache_json)
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
                    redis_conn.setex(pix_cache_key, 300, json_lib.dumps(cache_data))
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
            redis_conn.setex(session_key, 600, json_lib.dumps(session))
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
                             is_upsell: bool = False,
                             upsell_index: int = None,
                             is_remarketing: bool = False,
                             remarketing_campaign_id: int = None,
                             button_index: int = None,
                             button_config: dict = None) -> Optional[Dict[str, Any]]:
        from internal_logic.services.payment_generator import generate_pix_payment
        return generate_pix_payment(
            bot_id=bot_id, amount=amount, description=description,
            customer_name=customer_name, customer_username=customer_username,
            customer_user_id=customer_user_id,
            order_bump_shown=order_bump_shown,
            order_bump_accepted=order_bump_accepted,
            order_bump_value=order_bump_value,
            is_downsell=is_downsell, downsell_index=downsell_index,
            is_upsell=is_upsell, upsell_index=upsell_index,
            is_remarketing=is_remarketing,
            remarketing_campaign_id=remarketing_campaign_id,
            button_index=button_index, button_config=button_config
        )
    
    def verify_gateway(self, gateway_type: str, credentials: Dict[str, Any]) -> bool:
        """Verifica credenciais de gateway (delega para payment_gateway)"""
        from internal_logic.services.payment_gateway import verify_gateway as _verify_gateway
        return _verify_gateway(gateway_type, credentials)

    def process_payment_webhook(self, gateway_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processa webhook de pagamento (delega para payment_gateway)"""
        from internal_logic.services.payment_gateway import process_payment_webhook as _process_webhook
        return _process_webhook(gateway_type, data)

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
                             audio_url: Optional[str] = None,
                             buttons: Optional[list] = None):
        """
        Envia mensagem pelo Telegram (delegado ao BotMessenger)
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message: Mensagem de texto
            media_url: URL da mídia (opcional)
            media_type: Tipo da mídia (video, photo ou audio)
            audio_url: URL do áudio (opcional)
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
                audio_url=audio_url,
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
        """Agenda downsells via RQ (delega para offer_sender)"""
        from internal_logic.services.offer_sender import schedule_offers
        from tasks_async import marathon_queue
        return schedule_offers(
            mode='downsell',
            marathon_queue=marathon_queue,
            bot_id=bot_id,
            payment_id=payment_id,
            chat_id=chat_id,
            offers=downsells,
            original_price=original_price,
            original_button_index=original_button_index,
            user_id=self.user_id,
        )

    def _send_downsell(self, bot_id: int, payment_id: str, chat_id: int, downsell: dict, index: int, original_price: float = 0, original_button_index: int = -1):
        """Envia downsell agendado (delega para offer_sender)"""
        from internal_logic.services.offer_sender import send_offer
        return send_offer(
            mode='downsell',
            bot_state=self.bot_state,
            send_message_func=self.send_telegram_message,
            bot_id=bot_id,
            payment_id=payment_id,
            chat_id=chat_id,
            offer_config=downsell,
            index=index,
            original_price=original_price,
            original_button_index=original_button_index,
        )

    def schedule_upsells(self, bot_id: int, payment_id: str, chat_id: int, upsells: list, original_price: float = 0, original_button_index: int = -1):
        """Agenda upsells via RQ (delega para offer_sender)"""
        from internal_logic.services.offer_sender import schedule_offers
        from tasks_async import marathon_queue
        return schedule_offers(
            mode='upsell',
            marathon_queue=marathon_queue,
            bot_id=bot_id,
            payment_id=payment_id,
            chat_id=chat_id,
            offers=upsells,
            original_price=original_price,
            original_button_index=original_button_index,
        )

    def _send_upsell(self, bot_id: int, payment_id: str, chat_id: int, upsell: dict, index: int, original_price: float = 0, original_button_index: int = -1):
        """Envia upsell agendado (delega para offer_sender)"""
        from internal_logic.services.offer_sender import send_offer
        return send_offer(
            mode='upsell',
            bot_state=self.bot_state,
            send_message_func=self.send_telegram_message,
            bot_id=bot_id,
            payment_id=payment_id,
            chat_id=chat_id,
            offer_config=upsell,
            index=index,
            original_price=original_price,
            original_button_index=original_button_index,
        )

    def count_eligible_leads(self, bot_id: int, target_audience: str = 'non_buyers', 
                            days_since_last_contact: int = 3, exclude_buyers: bool = True,
                            audience_segment: str = None) -> int:
        return remarketing_sender.count_eligible_leads(
            bot_id, target_audience, days_since_last_contact, exclude_buyers, audience_segment
        )
    
    def send_remarketing_campaign(self, campaign_id: int, bot_token: str):
        """Envia campanha de remarketing (delega para RemarketingSender)"""
        self.remarketing_sender.send_remarketing_campaign(campaign_id, bot_token)
    
    # ============================================================================
    # ✅ SISTEMA DE ASSINATURAS - Ativação e Gerenciamento
    # ============================================================================
    
    def _activate_subscription(self, subscription_id: int) -> bool:
        return activate_subscription(subscription_id)
    
    def _handle_new_chat_member(self, bot_id: int, chat_id: int, telegram_user_id: str):
        handle_new_chat_member(bot_id, chat_id, telegram_user_id, activate_func=activate_subscription)
    
    def cancel_downsells(self, payment_id: str):
        cancel_scheduled_downsells(payment_id)
