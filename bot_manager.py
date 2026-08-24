"""
Bot Manager - Gerenciador de Bots do Telegram
Respons├ível por validar tokens, iniciar/parar bots e processar webhooks
"""

import eventlet
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

# Configurar logging para este m├│dulo
logger.setLevel(logging.INFO)


# For├ºar urllib3/requests a ignorar IPv6 (evita NameResolutionError com IPv6 inst├ível)
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

# Compatibilidade com eventlet: create_connection do socket verde n├úo aceita "family"
try:
    import eventlet.green.socket as eventlet_socket  # type: ignore[import]

    _green_create_connection = eventlet_socket.create_connection

    def _create_connection_ipv4(address, timeout=None, source_address=None, **kwargs):
        """
        Compat layer para eventlet >=0.33 com urllib3>=2, removendo kwargs n├úo suportados.
        """
        kwargs.pop("family", None)
        return _green_create_connection(address, timeout, source_address, **kwargs)

    eventlet_socket.create_connection = _create_connection_ipv4
    socket.create_connection = _create_connection_ipv4
except ImportError:
    # eventlet n├úo dispon├¡vel (execu├º├úo s├¡ncrona/local)
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
    Envia evento ViewContent para Meta Pixel quando usu├írio inicia conversa com bot
    
    ARQUITETURA V3.0 (QI 540 - CORRE├ç├âO CR├ìTICA):
    - Busca pixel do POOL ESPEC├ìFICO (passado via pool_id)
    - Se pool_id n├úo fornecido, busca primeiro pool do bot (fallback)
    - Usa UTM e external_id salvos no BotUser
    - Alta disponibilidade: dados consolidados no pool
    - Tracking preciso mesmo com m├║ltiplos bots
    
    CR├ìTICO: Anti-duplica├º├úo via meta_viewcontent_sent flag
    
    Args:
        bot: Inst├óncia do Bot
        bot_user: Inst├óncia do BotUser
        message: Mensagem do Telegram
        pool_id: ID do pool espec├¡fico (extra├¡do do start param)
    """
    try:
        # Ô£à VERIFICA├ç├âO 1: Buscar pool associado ao bot
        from internal_logic.core.models import PoolBot, RedirectPool
        
        # Se pool_id foi passado, buscar pool espec├¡fico
        if pool_id:
            pool_bot = PoolBot.query.filter_by(bot_id=bot.id, pool_id=pool_id).first()
            if not pool_bot:
                logger.warning(f"Bot {bot.id} n├úo est├í no pool {pool_id} especificado - tentando fallback")
                pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        else:
            # Fallback: buscar primeiro pool do bot
            pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        
        if not pool_bot:
            logger.info(f"Bot {bot.id} n├úo est├í associado a nenhum pool - Meta Pixel ignorado")
            return
        
        pool = pool_bot.pool
        
        logger.info(f"­ƒôè Pool selecionado para ViewContent: {pool.id} ({pool.name}) | " +
                   f"pool_id_param={pool_id} | bot_id={bot.id}")
        
        # Ô£à VERIFICA├ç├âO 2: Pool tem Meta Pixel configurado?
        if not pool.meta_tracking_enabled:
            return
        
        if not pool.meta_pixel_id or not pool.meta_access_token:
            logger.warning(f"Pool {pool.id} tem tracking ativo mas sem pixel_id ou access_token")
            return
        
        # Ô£à VERIFICA├ç├âO 3: Evento ViewContent est├í habilitado?
        if not pool.meta_events_viewcontent:
            logger.info(f"Evento ViewContent desabilitado para pool {pool.id}")
            return
        
        # Ô£à VERIFICA├ç├âO 4: J├í enviou ViewContent para este usu├írio? (ANTI-DUPLICA├ç├âO)
        if bot_user.meta_viewcontent_sent:
            logger.info(f"ÔÜá´©Å ViewContent j├í enviado ao Meta, ignorando: BotUser {bot_user.id}")
            return
        
        logger.info(f"­ƒôè Preparando envio Meta ViewContent: Pool {pool.name} | User {bot_user.telegram_user_id}")
        
        # Importar Meta Pixel API
        from utils.meta_pixel import MetaPixelAPI
        from utils.encryption import decrypt
        
        # Gerar event_id ├║nico para deduplica├º├úo
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
        
        # Ô£à CR├ìTICO V4.1: RECUPERAR DADOS COMPLETOS DO REDIS (MESMO DO PAGEVIEW!)
        # ViewContent DEVE usar os MESMOS dados do PageView para garantir matching perfeito!
        from utils.tracking_service import TrackingServiceV4
        from utils.meta_pixel import MetaPixelAPI
        from utils.encryption import decrypt
        
        tracking_service_v4 = TrackingServiceV4()
        tracking_data = {}
        
        # Ô£à PRIORIDADE 1: Recuperar do tracking_token (se dispon├¡vel)
        if hasattr(bot_user, 'tracking_session_id') and bot_user.tracking_session_id:
            tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
            logger.info(f"Ô£à ViewContent - tracking_data recuperado do Redis: {len(tracking_data)} campos")
        
        # Ô£à PRIORIDADE 2: Se n├úo tem tracking_token, usar dados do BotUser (fallback)
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
            logger.info(f"Ô£à ViewContent - usando dados do BotUser (fallback)")
        
        # Ô£à CR├ìTICO: Construir user_data usando MetaPixelAPI._build_user_data() (MESMO DO PAGEVIEW!)
        # Isso garante que external_id seja hashado corretamente e fbp/fbc sejam inclu├¡dos
        
        # Ô£à CORRE├ç├âO CR├ìTICA: Normalizar external_id para garantir matching consistente com PageView/Purchase
        # Se fbclid > 80 chars, normalizar para hash MD5 (32 chars) - MESMO algoritmo usado em todos os eventos
        from utils.meta_pixel import normalize_external_id
        external_id_raw = tracking_data.get('fbclid') or getattr(bot_user, 'fbclid', None)
        external_id_value = normalize_external_id(external_id_raw) if external_id_raw else None
        if external_id_value != external_id_raw and external_id_raw:
            logger.info(f"Ô£à ViewContent - external_id normalizado: {external_id_value} (original len={len(external_id_raw)})")
            logger.info(f"Ô£à ViewContent - MATCH GARANTIDO com PageView/Purchase (mesmo algoritmo de normaliza├º├úo)")
        elif external_id_value:
            logger.info(f"Ô£à ViewContent - external_id usado original: {external_id_value[:30]}... (len={len(external_id_value)})")
        
        fbp_value = tracking_data.get('fbp') or getattr(bot_user, 'fbp', None)
        
        # Ô£à CORRE├ç├âO CR├ìTICA: Verificar fbc_origin para garantir que s├│ enviamos fbc real (cookie)
        # Ô£à CR├ìTICO: Aceitar fbc se veio do cookie OU foi gerado conforme documenta├º├úo Meta
        # Meta aceita _fbc gerado quando fbclid est├í presente na URL (conforme documenta├º├úo oficial)
        fbc_value = None
        fbc_origin = tracking_data.get('fbc_origin')
        
        # Ô£à PRIORIDADE 1: tracking_data com fbc (cookie OU generated_from_fbclid)
        # Meta aceita ambos conforme documenta├º├úo oficial
        if tracking_data.get('fbc') and fbc_origin in ('cookie', 'generated_from_fbclid'):
            fbc_value = tracking_data.get('fbc')
            logger.info(f"[META VIEWCONTENT] ViewContent - fbc recuperado do tracking_data (origem: {fbc_origin}): {fbc_value[:50]}...")
        # Ô£à PRIORIDADE 2: BotUser (assumir que veio de cookie se foi salvo via process_start_async)
        elif bot_user and getattr(bot_user, 'fbc', None):
            fbc_value = bot_user.fbc
            logger.info(f"[META VIEWCONTENT] ViewContent - fbc recuperado do BotUser (assumido como real): {fbc_value[:50]}...")
        else:
            logger.warning(f"[META VIEWCONTENT] ViewContent - fbc ausente ou ignorado (origem: {fbc_origin or 'ausente'}) - Meta ter├í atribui├º├úo reduzida")
        
        ip_value = tracking_data.get('client_ip') or getattr(bot_user, 'ip_address', None)
        ua_value = tracking_data.get('client_user_agent') or getattr(bot_user, 'user_agent', None)
        
        # Ô£à Usar _build_user_data para garantir formato correto (hash SHA256, array external_id, etc)
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=str(bot_user.telegram_user_id),  # Ô£à Telegram ID
            external_id=external_id_value,  # Ô£à fbclid normalizado (ser├í hashado)
            email=None,  # BotUser n├úo tem email
            phone=None,  # BotUser n├úo tem phone
            client_ip=ip_value,
            client_user_agent=ua_value,
            fbp=fbp_value,  # Ô£à CR├ìTICO: FBP do PageView
            fbc=fbc_value  # Ô£à CR├ìTICO: FBC do PageView (apenas se real/cookie)
        )
        
        # Ô£à Construir custom_data (filtrar None/vazios)
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
        
        # Ô£à CR├ìTICO: event_source_url (mesmo do PageView)
        event_source_url = tracking_data.get('event_source_url') or tracking_data.get('first_page')
        if not event_source_url and pool.slug:
            event_source_url = f'https://app.grimbots.online/go/{pool.slug}'
        
        # ============================================================================
        # Ô£à ENFILEIRAR EVENTO VIEWCONTENT (ASS├ìNCRONO - RQ)
        # ============================================================================
        from tasks_async import enqueue_meta_event
        import time
        
        event_data = {
            'event_name': 'ViewContent',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'event_source_url': event_source_url,  # Ô£à ADICIONAR
            'user_data': user_data,  # Ô£à AGORA COMPLETO (fbp, fbc, external_id hashado, ip, ua)
            'custom_data': custom_data  # Ô£à Sempre dict (nunca None)
        }
        
        # Ô£à LOG: Verificar dados enviados
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
                   f"external_id={'Ô£à' if external_ids else 'ÔØî'} | " +
                   f"fbp={'Ô£à' if user_data.get('fbp') else 'ÔØî'} | " +
                   f"fbc={'Ô£à' if user_data.get('fbc') else 'ÔØî'} | " +
                   f"ip={'Ô£à' if user_data.get('client_ip_address') else 'ÔØî'} | " +
                   f"ua={'Ô£à' if user_data.get('client_user_agent') else 'ÔØî'}")
        
        # Ô£à ENFILEIRAR NA RQ (tracking real, n├úo fantasma)
        enqueue_meta_event(
            pixel_id=pool.meta_pixel_id,
            access_token=access_token,
            event_data=event_data,
            test_code=pool.meta_test_event_code
        )
        
        # Marcar como enviado IMEDIATAMENTE (flag otimista)
        bot_user.meta_viewcontent_sent = True
        from internal_logic.core.models import get_brazil_time
        bot_user.meta_viewcontent_sent_at = get_brazil_time()
        
        # Commit da flag
        from internal_logic.core.extensions import db
        db.session.commit()
        
        logger.info(f"­ƒôñ ViewContent enfileirado: Pool {pool.name} | " +
                   f"User {bot_user.telegram_user_id} | " +
                   f"Event ID: {event_id} | " +
                   f"UTM: {bot_user.utm_source}/{bot_user.utm_campaign}")
    
    except Exception as e:
        logger.error(f"­ƒÆÑ Erro ao enviar Meta ViewContent: {e}")
        # N├úo impedir o funcionamento do bot se Meta falhar

# Configura├º├úo de Split Payment da Plataforma
import os
PLATFORM_SPLIT_USER_ID = os.environ.get('PLATFORM_SPLIT_USER_ID', '')  # Client ID para receber comiss├Áes (SyncPay)
PLATFORM_SPLIT_PERCENTAGE = 2  # 2% PADR├âO PARA TODOS OS GATEWAYS

# Configura├º├úo de Split Payment para PushynPay (LEGADO - n├úo mais usado)
# ÔÜá´©Å SPLIT DESABILITADO - Account ID fornecido n├úo existe no PushynPay
PUSHYN_SPLIT_ACCOUNT_ID = os.environ.get('PUSHYN_SPLIT_ACCOUNT_ID', None)
PUSHYN_SPLIT_PERCENTAGE = 2  # 2% (quando habilitado)


# ============================================================================
# Helpers de tempo (hor├írio do Brasil, mesmo em servidores fora do fuso)
# ============================================================================
try:
    _pytz = pytz.timezone('America/Sao_Paulo') if pytz else None
except Exception:
    _pytz = None


def get_brazil_time():
    """Retorna datetime no fuso de S├úo Paulo.

    - Tenta usar pytz (mais preciso para DST).
    - Fallback: UTC-3 manual.
    - ├Ültimo fallback: datetime.now() se algo der errado.
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
from internal_logic.core.redis_bot_state import redis_bot_state, get_namespaced_bot_state  # Ô£à ISOLAMENTO: Importar factory V2
import json
import random
import time

class BotManager:
    """Gerenciador de bots Telegram - Com estado centralizado em Redis (Namespace Isolado V2)"""
    
    def __init__(self, socketio=None, scheduler=None, user_id=None, **kwargs):
        """
        Inicializa o BotManager com namespace isolado.
        
        ÔÜá´©Å Compatibilidade legada: Todos os par├ómetros s├úo opcionais.
        
        Args:
            socketio: Inst├óncia do SocketIO (opcional)
            scheduler: Agendador (opcional, compatibilidade legacy)
            user_id: ID do usu├írio para namespace isolado (opcional, fallback=1)
            **kwargs: Argumentos adicionais
        """
        # ­ƒøæ BLINDAGEM REMOVIDA: user_id ├® opcional para compatibilidade com webhooks legados
        if not user_id:
            user_id = kwargs.get('user_id', None) or 1  # Fallback seguro
        
        self.socketio = socketio
        self.user_id = user_id
        
        # Ô£à ISOLAMENTO NAMESPACE V2: Sempre usar estado isolado
        self.bot_state = get_namespaced_bot_state(user_id)
        logger.info(f"Ô£à BotManager inicializado com namespace isolado: gb:{user_id}:*")
        
        self.bot_threads: Dict[int, threading.Thread] = {}
        
        # Ô£à CACHE DE RATE LIMITING MIGRADO PARA REDIS (multi-worker, TTL autom├ítico)
        # Chaves: gb:rate_limit:{user_key} (TTL 300s)
        # Redis TTL faz cleanup autom├ítico - sem threads necess├írias
        
        # Ô£à REMARKETING SENDER: Servi├ºo de remarketing extra├¡do
        from internal_logic.services.remarketing_sender import RemarketingSender
        self.remarketing_sender = RemarketingSender(
            user_id=user_id,
            send_message_func=self.send_telegram_message,
        )

        # Ô£à MESSENGER SERVICE: Delega├º├úo de envio de mensagens
        self.messenger = BotMessenger(max_concurrent=10)
        logger.info("Ô£à BotMessenger injetado no BotManager")

        # Ô£à RUNNER SERVICE: Ciclo de vida dos bots (start, stop, polling)
        self.runner = BotRunner(
            bot_state=self.bot_state,
            on_update_received=self._process_telegram_update
        )
        logger.info("Ô£à BotRunner injetado no BotManager")

        # Ô£à FLOW ENGINE: Processamento de mensagens e funil
        self.flow_engine = FlowEngine(
            messenger=self.messenger,
            bot_state=self.bot_state
        )
        logger.info("Ô£à FlowEngine injetado no BotManager")

        # Ô£à PATCH: Session reutiliz├ível + Retry/Backoff para envios pesados (sendVideo)
        # Regra: manter impacto ZERO em outros tipos de mensagem; Session ser├í usada somente em send_video_safe.
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

        # Ô£à PATCH: Rate limit POR TOKEN (thread-safe)
        self._telegram_rate_lock = threading.Lock()
        self._telegram_last_send_ts: Dict[str, float] = {}
        self._telegram_min_interval_seconds = 1.2
        logger.info("BotManager inicializado")

    # =============================================================
    # Helpers de formata├º├úo
    # =============================================================
    def _format_button_text(self, text: str, price: float, price_position: str = None) -> str:
        """Formata texto do bot├úo com pre├ºo antes ou depois."""
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
        """Rate limit thread-safe por token. N├úo muda fluxo, apenas evita flood de conex├Áes."""
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
        """Blacklist definitiva para 'user is deactivated' (best-effort; n├úo quebra execu├º├úo se falhar)."""
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import RemarketingBlacklist, Bot

            with current_app.app_context():
                bot_id = None
                # Ô£à REDIS BRAIN: Buscar bot pelo token no Redis
                # Como n├úo temos ├¡ndice reverso no Redis, buscar no banco
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
                logger.info(f"­ƒÜ½ Usu├írio {chat_id} adicionado ├á blacklist do bot {bot_id} (user is deactivated)")
        except Exception as e:
            logger.warning(f"ÔÜá´©Å Falha ao adicionar blacklist (user is deactivated) para chat {chat_id}: {e}")

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

            # Ô£à Validar HTTP 5xx sem quebrar fluxo (retry j├í ocorreu no adapter)
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
            logger.error(f"ÔØî Arquivo n├úo encontrado: {file_path}")
            return None
        except (requests.exceptions.Timeout, requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            logger.error(f"ÔØî Erro de rede ao enviar v├¡deo para chat {chat_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"ÔØî Erro inesperado em send_video_safe para chat {chat_id}: {e}", exc_info=True)
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
                            error = Exception('Bot bloqueado pelo usu├írio')
                            error.error_type = 'blocked'
                            raise error
                        elif 'bot token is invalid' in desc:
                            error = Exception('Token inv├ílido ou banido pelo Telegram')
                            error.error_type = 'invalid_token'
                            raise error
                        else:
                            error = Exception('Token inv├ílido ou expirado')
                            error.error_type = 'invalid_token'
                            raise error
                    else:
                        error = Exception(data.get('description', 'Token inv├ílido'))
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
                    logger.warning(f"Falha de DNS/Conex├úo ao validar token (tentativa {attempt}/{max_attempts}): {message}. Retentativa em {wait}s")
                    time.sleep(wait)
                    continue
                if any(keyword in message for keyword in keywords):
                    logger.error(f"Erro ao validar token ap├│s {attempt} tentativas: {message}")
                    break  # sair do loop e acionar fallback
                
                logger.error(f"Erro ao validar token: {e}")
                error = Exception(f"Erro de conex├úo com API do Telegram: {message}")
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
        logger.warning(f"├Ültima exce├º├úo registrada: {message}")

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
                error = Exception(data.get('description', 'Token inv├ílido'))
                error.error_type = 'invalid_token'
                raise error

            bot_info = data.get('result', {})
            logger.info(f"Token validado via fallback curl: @{bot_info.get('username')}")
            return {
                'bot_info': bot_info,
                'error_type': None
            }
        except Exception as curl_exc:
            logger.error(f"Fallback curl tamb├®m falhou: {curl_exc}")
            if isinstance(curl_exc, subprocess.CalledProcessError):
                logger.error(f"curl stdout: {curl_exc.stdout}")
                logger.error(f"curl stderr: {curl_exc.stderr}")

        error = Exception('Erro de conex├úo com API do Telegram ap├│s m├║ltiplas tentativas')
        error.error_type = 'connection_error'
        raise error
    
    def start_bot(self, bot_id: int, token: str, config: Dict[str, Any]):
        """
        Inicia um bot Telegram - Delegado ao BotRunner
        
        Ô£à REFATORADO: Ciclo de vida delegado ao servi├ºo BotRunner
        
        Args:
            bot_id: ID do bot no banco
            token: Token do bot
            config: Configura├º├úo do bot
        """
        return self.runner.start_bot(bot_id, token, config)
    
    def stop_bot(self, bot_id: int):
        """
        Para um bot Telegram - Delegado ao BotRunner
        
        Ô£à REFATORADO: Ciclo de vida delegado ao servi├ºo BotRunner
        
        Args:
            bot_id: ID do bot no banco
        """
        return self.runner.stop_bot(bot_id)
    
    def update_bot_config(self, bot_id: int, config: Dict[str, Any]):
        """
        Atualiza configura├º├úo de um bot em tempo real via Redis
        
        Args:
            bot_id: ID do bot
            config: Nova configura├º├úo
        """
        # Ô£à REDIS BRAIN: Atualizar config no Redis (vis├¡vel para todos os workers)
        if self.bot_state.update_bot_config(bot_id, config):
            logger.info(f"­ƒöº Configura├º├úo do bot {bot_id} atualizada no Redis")
            logger.info(f"­ƒöì DEBUG Config - downsells_enabled: {config.get('downsells_enabled', False)}")
            logger.info(f"­ƒöì DEBUG Config - downsells: {config.get('downsells', [])}")
        else:
            logger.warning(f"ÔÜá´©Å Bot {bot_id} n├úo est├í ativo no Redis para atualizar configura├º├úo")
    
    def _bot_monitor_thread(self, bot_id: int):
        """
        Thread de monitoramento de um bot (simula├º├úo de atividade)
        
        Args:
            bot_id: ID do bot
        """
        logger.info(f"Monitor do bot {bot_id} iniciado")

        # Watchdog com retry/backoff: nunca encerrar por exce├º├Áes transit├│rias
        error_count = 0
        max_backoff_seconds = 60
        cycle = 0
        
        while True:
            # Ô£à REDIS BRAIN: Verificar se bot est├í ativo no Redis
            bot_info = self.bot_state.get_bot_data(bot_id)
            if not bot_info or bot_info.get('status') != 'running':
                logger.info(f"Monitor do bot {bot_id} encerrado (status n├úo-running ou removido)")
                break

            try:
                # Heartbeat (mant├®m conex├Áes em tempo real e sinaliza vivacidade)
                from internal_logic.core.models import get_brazil_time
                # ­ƒöÑ CR├ìTICO: Blindagem UI - n├úo deixar WebSocket afetar processamento core
                try:
                    if self.socketio:
                        self.socketio.emit('bot_heartbeat', {
                            'bot_id': bot_id,
                            'timestamp': get_brazil_time().isoformat(),
                            'status': 'online'
                        }, room=f'bot_{bot_id}')
                except Exception as ws_error:
                    logger.debug(f"Falha n├úo-cr├¡tica na UI (WebSocket ignorado): {ws_error}")
                    pass  # O processamento da mensagem DEVE continuar!

                # Registrar heartbeat compartilhado (Redis) para ambientes multi-worker
                try:
                    import redis, time as _t
                    r = get_redis_connection()
                    r.setex(f'bot_heartbeat:{bot_id}', 180, int(_t.time()))
                except Exception:
                    # N├úo interromper o monitor se Redis indispon├¡vel
                    pass

                # Reset de erros ap├│s sucesso
                error_count = 0

                # Intervalo padr├úo de monitoramento
                time.sleep(30)

                # Auto-verifica├º├úo peri├│dica do webhook (a cada ~5 min)
                cycle += 1
                if cycle % 10 == 0:
                    try:
                        # Ô£à REDIS BRAIN: Buscar token do Redis
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
                                        logger.warning(f"­ƒöü Auto-fix webhook bot {bot_id}: cfg='{configured}', expected='{expected_url}', last_error='{last_error}'")
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
                                    logger.warning(f"ÔÜá´©Å getWebhookInfo {resp.status_code}: {resp.text}")
                    except Exception as ie:
                        logger.debug(f"Webhook auto-check falhou: {ie}")

            except Exception as e:
                error_count += 1
                backoff = min(2 ** min(error_count, 5), max_backoff_seconds)
                logger.error(f"Erro no monitor do bot {bot_id} (tentativa {error_count}): {e}. Backoff {backoff}s")
                time.sleep(backoff)
                # Continua tentando at├® que o status seja alterado para n├úo-running
    
    def _setup_webhook(self, token: str, bot_id: int):
        """
        Configura webhook do Telegram
        
        Args:
            token: Token do bot
            bot_id: ID do bot
        """
        try:
            # Para desenvolvimento local, usar ngrok ou similar
            # Para produ├º├úo, usar dom├¡nio real com HTTPS
            
            # IMPORTANTE: Configure WEBHOOK_URL nas vari├íveis de ambiente
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
                                logger.warning(f"ÔÜá´©Å Webhook n├úo corresponde (cfg='{url_cfg}') ao esperado ('{webhook_url}')")
                            if last_error_message:
                                logger.error(f"ÔØî getWebhookInfo: last_error='{last_error_message}' date={last_error_date}")
                            if isinstance(pending, int) and pending > 100:
                                logger.warning(f"ÔÜá´©Å pending_update_count alto: {pending}")

                            # Failover autom├ítico para polling se o webhook estiver retornando 502
                            if last_error_message and '502 Bad Gateway' in str(last_error_message):
                                try:
                                    # Remover webhook e habilitar polling para n├úo perder vendas
                                    del_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
                                    with self.messenger.telegram_http_semaphore:
                                        del_resp = requests.post(del_url, timeout=10)
                                    logger.warning(f"­ƒöü Failover para polling (deleteWebhook status={del_resp.status_code}) para bot {bot_id}")
                                except Exception as de:
                                    logger.warning(f"ÔÜá´©Å Falha ao deletar webhook para failover: {de}")
                                
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
                                    logger.info(f"Ô£à Polling job (failover) criado: {job_id}")
                                else:
                                    polling_thread = threading.Thread(
                                        target=self._polling_mode,
                                        args=(bot_id, token),
                                        daemon=True
                                    )
                                    polling_thread.start()
                                    logger.info(f"Ô£à Polling thread (failover) iniciada para bot {bot_id}")
                        else:
                            logger.warning(f"ÔÜá´©Å Falha ao consultar getWebhookInfo: {info_resp.status_code} {info_resp.text}")
                    except Exception as ie:
                        logger.warning(f"ÔÜá´©Å Erro ao verificar getWebhookInfo: {ie}")
                else:
                    logger.error(f"Erro ao configurar webhook: {response.text}")
            else:
                # Modo polling para desenvolvimento local
                logger.warning(f"WEBHOOK_URL n├úo configurado. Bot {bot_id} em modo polling.")
                
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
                    logger.info(f"Ô£à Polling job criado: {job_id}")
                else:
                    # Fallback para thread manual
                    polling_thread = threading.Thread(
                        target=self._polling_mode,
                        args=(bot_id, token),
                        daemon=True
                    )
                    polling_thread.start()
                    logger.info(f"Ô£à Polling thread iniciada para bot {bot_id}")
                
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
            # Ô£à REDIS BRAIN: Verificar se bot est├í ativo no Redis
            bot_data = self.bot_state.get_bot_data(bot_id)
            if not bot_data or bot_data.get('status') != 'running':
                logger.warning(f"ÔÜá´©Å Bot {bot_id} n├úo est├í ativo no Redis, n├úo enviando mensagem")
                return
            
            # Ô£à REDIS BRAIN: Buscar offset/poll_count do Redis (transientes)
            config = bot_data.get('config', {})
            offset = config.get('_polling_offset', 0)
            poll_count = config.get('_polling_count', 0)
            poll_count += 1
            
            # Atualizar m├®tricas no Redis (n├úo cr├¡tico se falhar)
            try:
                new_config = config.copy()
                new_config['_polling_offset'] = offset
                new_config['_polling_count'] = poll_count
                self.bot_state.update_bot_config(bot_id, new_config)
            except:
                pass
            
            # Log apenas a cada 30 polls (30 segundos)
            if poll_count % 30 == 0:
                logger.info(f"Ô£à Bot {bot_id} online e aguardando mensagens...")
            
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            with self.telegram_http_semaphore:
                response = requests.get(url, params={'offset': offset, 'timeout': 25}, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('ok'):
                    updates = data.get('result', [])
                    
                    if updates:
                        logger.info(f"\n{'='*60}")
                        logger.info(f"­ƒô¿ NOVA MENSAGEM RECEBIDA! ({len(updates)} update(s))")
                        logger.info(f"{'='*60}")
                        
                        max_update_id = offset
                        for update in updates:
                            if update.get('update_id', 0) > max_update_id:
                                max_update_id = update['update_id']
                            self._process_telegram_update(bot_id, None, update)
                        
                        # Ô£à OTIMIZA├ç├âO: Atualizar offset uma ├║nica vez ap├│s processar todos
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
            pass  # Timeout ├® esperado
        except Exception as e:
            logger.error(f"ÔØî Erro no polling bot {bot_id}: {e}")
            import time
            time.sleep(5)  # Ô£à DEFESA: Evitar loop infinito de CPU em caso de erro cont├¡nuo
    
    def _polling_mode(self, bot_id: int, token: str):
        """
        Modo polling para receber atualiza├º├Áes (desenvolvimento local)
        
        Args:
            bot_id: ID do bot
            token: Token do bot
        """
        logger.info(f"­ƒöä Iniciando polling para bot {bot_id}")
        offset = 0
        poll_count = 0
        
        # Ô£à CORRE├ç├âO: Loop com verifica├º├úo no Redis
        while True:
            bot_data = self.bot_state.get_bot_data(bot_id)
            if not bot_data or bot_data.get('status') != 'running':
                break
            try:
                poll_count += 1
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                
                # Log a cada 5 polls para mostrar que est├í funcionando
                if poll_count % 5 == 0:
                    logger.info(f"­ƒôí Bot {bot_id} polling ativo (ciclo {poll_count}) - Thread: {threading.current_thread().name}")
                
                with self.messenger.telegram_http_semaphore:
                    response = requests.get(url, params={'offset': offset, 'timeout': 30}, timeout=35)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok'):
                        updates = data.get('result', [])
                        
                        if updates:
                            logger.info(f"­ƒô¿ Bot {bot_id} recebeu {len(updates)} update(s)")
                            
                            for update in updates:
                                offset = update['update_id'] + 1
                                logger.info(f"­ƒöì Processando update {update['update_id']}")
                                # Processar update
                                self._process_telegram_update(bot_id, None, update)
                    else:
                        logger.error(f"ÔØî Resposta n├úo OK do Telegram: {data}")
                else:
                    logger.error(f"ÔØî Status code {response.status_code}: {response.text}")
                
                time.sleep(1)
                
            except requests.exceptions.Timeout:
                # Timeout ├® normal, continuar polling
                logger.debug(f"ÔÅ▒´©Å Timeout no polling bot {bot_id} (normal)")
                continue
            except Exception as e:
                logger.error(f"ÔØî Erro no polling do bot {bot_id}: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
        
        logger.info(f"­ƒøæ Polling do bot {bot_id} encerrado")
    
    def _process_telegram_update(self, bot_id: int, user_id: int, update: Dict[str, Any], isolated_state=None):
        """
        Processa update recebido do Telegram
        
        # Ô£à ISOLAMENTO NAMESPACE V2: Agora recebe user_id e usa estado isolado
        - user_id: ID do dono do bot (para namespace gb:{user_id}:*)
        - isolated_state: Opcional - estado Redis j├í isolado (se None, usa self.bot_state)
        
        # Ô£à QI 500: ANTI-DUPLICA├ç├âO ABSOLUTO
        - Lock por update_id para evitar processamento duplicado
        - Garante que cada update ├® processado apenas 1 vez
        - Previne reset m├║ltiplo, pixel duplicado, mensagens duplicadas
        
        Args:
            bot_id: ID do bot
            user_id: ID do dono do bot (para isolamento de namespace)
            update: Dados do update
            isolated_state: Estado Redis isolado (opcional, para performance)
        """
        # Ô£à ISOLAMENTO: Usar estado isolado se fornecido, sen├úo usar self.bot_state
        bot_state = isolated_state if isolated_state else self.bot_state
        
        # Ô£à ISOLAMENTO: Lock de update com namespace do usu├írio
        import redis
        redis_conn = get_redis_connection()
        lock_key = f"gb:{user_id}:lock:update:{update.get('update_id')}"
        
        try:
            # Ô£à QI 500: ANTI-DUPLICA├ç├âO - Lock por update_id (PRIMEIRA COISA)
            update_id = update.get('update_id')
            if update_id is None:
                logger.warning(f"ÔÜá´©Å Update sem update_id - ignorando")
                return
            
            try:
                # Ô£à ISOLAMENTO: Lock com namespace do usu├írio
                if redis_conn.get(lock_key):
                    logger.warning(f"ÔÜá´©Å Update {update_id} j├í processado ÔÇö ignorando duplicado (anti-duplica├º├úo)")
                    return
                
                # Adquirir lock (expira em 120 segundos)
                acquired = redis_conn.set(lock_key, "1", ex=120, nx=True)
                if not acquired:
                    logger.warning(f"ÔÜá´©Å Update {update_id} j├í est├í sendo processado ÔÇö ignorando duplicado")
                    return
                
                logger.debug(f"­ƒöÆ Lock adquirido para update {update_id} (user_id={user_id})")
            except Exception as e:
                logger.error(f"ÔØî Erro ao verificar lock update: {e}")
                # Fail-open: se Redis falhar, permitir processar
                pass
            
            # Ô£à ISOLAMENTO: Verificar se bot est├í ativo no Redis ISOLADO
            if not bot_state.is_bot_active(bot_id):
                logger.warning(f"ÔÜá´©Å Bot {bot_id} n├úo est├í ativo no Redis (namespace gb:{user_id}:), tentando auto-start")
                
                # Ô£à ISOLAMENTO: Verificar se outro worker est├í tentando auto-start (namespace isolado)
                if bot_state.is_autostart_locked(bot_id):
                    logger.info(f"­ƒöÆ Outro worker est├í iniciando bot {bot_id} (user_id={user_id}) - aguardando")
                    import eventlet as _eventlet
                    for _ in range(10):
                        _eventlet.sleep(0.5)
                        if bot_state.is_bot_active(bot_id):
                            logger.info(f"Ô£à Bot {bot_id} foi iniciado por outro worker")
                            break
                    else:
                        logger.warning(f"ÔÜá´©Å Timeout aguardando bot {bot_id}")
                        return
                else:
                    # Tentar auto-start com lock (namespace isolado)
                    try:
                        from flask import current_app
                        from internal_logic.core.extensions import db
                        from internal_logic.core.models import Bot, BotConfig
                        with current_app.app_context():
                            from sqlalchemy.orm import joinedload
                            bot = db.session.query(Bot).options(joinedload(Bot.config)).get(bot_id)
                            if bot and bot.is_active:  # ­ƒöÑ CR├ìTICO: Removida verifica├º├úo de user_id - webhook ├® stateless
                                config_obj = bot.config or BotConfig.query.filter_by(bot_id=bot.id).first()
                                config_dict = config_obj.to_dict() if config_obj else {}
                                # Ô£à Usar o m├®todo de registro do bot_state isolado
                                bot_state.register_bot(bot.id, bot.token, config_dict)
                    except Exception as autostart_error:
                        logger.error(f"ÔØî Falha ao auto-start bot {bot_id} durante webhook: {autostart_error}")
                
                # Verificar novamente
                if not bot_state.is_bot_active(bot_id):
                    logger.warning(f"ÔÜá´©Å Bot {bot_id} ainda indispon├¡vel ap├│s auto-start. Acionando FALLBACK para banco de dados...")
                    # N├âO retornar - vamos tentar fallback no banco
                    bot_info = None  # Marcar para fallback
                else:
                    # Bot est├í ativo, obter dados do Redis
                    bot_info = bot_state.get_bot_data(bot_id)
            else:
                # Bot j├í estava ativo, obter dados do Redis
                bot_info = bot_state.get_bot_data(bot_id)
            
            # Ô£à FALLBACK CR├ìTICO: Se Redis falhou, buscar direto do banco
            if not bot_info:
                logger.warning(f"­ƒñû Bot {bot_id} n├úo encontrado no Redis. Acionando FALLBACK LEGADO (Via Expressa)!")
                try:
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    from internal_logic.core.models import Bot, BotConfig
                    
                    with current_app.app_context():
                        # ­ƒöÑ CR├ìTICO: Limpar transa├º├úo pendente antes de come├ºar
                        db.session.rollback()
                        
                        from sqlalchemy.orm import joinedload
                        db_bot = db.session.query(Bot).options(joinedload(Bot.config)).get(bot_id)
                        if not db_bot:
                            logger.error(f"ÔØî Bot {bot_id} n├úo existe no banco de dados!")
                            return  # Bot realmente n├úo existe
                            
                        # Buscar config
                        try:
                            db_config = db_bot.config or BotConfig.query.filter_by(bot_id=bot_id).first()
                            config_dict = db_config.to_dict() if db_config else {}
                        except Exception as config_err:
                            db.session.rollback()  # Limpa erro de transa├º├úo
                            logger.error(f"ÔÜá´©Å Erro ao buscar config: {config_err}")
                            config_dict = {}  # Continua sem config
                        
                        # Criar bot_info manualmente do banco
                        bot_info = {
                            'token': db_bot.token,
                            'config': config_dict
                        }
                        logger.info(f"Ô£à FALLBACK: Bot {bot_id} carregado direto do banco!")
                        
                except Exception as fallback_error:
                    logger.error(f"ÔØî FALLBACK falhou para bot {bot_id}: {fallback_error}")
                    # ­ƒöÑ CR├ìTICO: Limpar transa├º├úo suja antes de retornar
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    return  # Se fallback falhou, realmente n├úo podemos processar
            
            token = bot_info['token']
            config = bot_info['config']
            
            logger.info(f"­ƒÆ¼ Processando update {update_id} para bot {bot_id} (user_id={user_id})")
            
            # Processar mensagem
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                user = message.get('from', {})
                telegram_user_id = str(user.get('id', ''))

                # Detectar m├¡dia na mensagem (foto, v├¡deo, documento, ├íudio)
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
                
                logger.info(f"­ƒÆ¼ De: {user.get('first_name', 'Usu├írio')} | Tipo: {media_type} | Texto: '{text[:50] if text else '(vazio)'}'")
                
                # Ô£à CHAT: Salvar mensagem recebida no banco (SEMPRE, independente do comando)
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
                            
                            # Se n├úo existe, criar (ser├í atualizado depois no /start se necess├írio)
                            # Ô£à CORRE├ç├âO CR├ìTICA: Tratamento de race condition
                            if not bot_user:
                                try:
                                    bot_user = BotUser(
                                        bot_id=bot_id,
                                        telegram_user_id=telegram_user_id,
                                        first_name=user.get('first_name', 'Usu├írio'),
                                        username=user.get('username', ''),
                                        archived=False
                                    )
                                    db.session.add(bot_user)
                                    db.session.flush()  # Obter ID sem commit (detecta duplica├º├úo)
                                except Exception as e:
                                    # Ô£à RACE CONDITION: Outro processo criou entre a busca e o add
                                    db.session.rollback()
                                    logger.debug(f"ÔÜá´©Å Race condition ao criar BotUser (esperado em /start), buscando: {e}")
                                    # Buscar novamente (pode ter sido criado pelo outro processo ou no /start)
                                    bot_user = BotUser.query.filter_by(
                                        bot_id=bot_id,
                                        telegram_user_id=telegram_user_id,
                                        archived=False
                                    ).first()
                                    if not bot_user:
                                        # Se ainda n├úo encontrou, buscar sem filtro archived
                                        bot_user = BotUser.query.filter_by(
                                            bot_id=bot_id,
                                            telegram_user_id=telegram_user_id
                                        ).first()
                            
                            # Ô£à CR├ìTICO: Gerar message_id ├║nico se n├úo existir
                            telegram_msg_id = message.get('message_id')
                            if not telegram_msg_id:
                                # Se n├úo tem message_id, gerar um baseado no timestamp + texto
                                import hashlib
                                from internal_logic.core.models import get_brazil_time
                                unique_id = f"{telegram_user_id}_{get_brazil_time().timestamp()}_{text[:20]}"
                                telegram_msg_id = hashlib.md5(unique_id.encode()).hexdigest()[:16]
                                logger.warning(f"ÔÜá´©Å Mensagem sem message_id do Telegram, gerando ID ├║nico: {telegram_msg_id}")
                            
                            telegram_msg_id_str = str(telegram_msg_id)
                            
                            # ============================================================================
                            # Ô£à QI 10000: ANTI-DUPLICA├ç├âO ROBUSTA - Lock por chat+comando
                            # ============================================================================
                            # Lock adicional por chat_id+texto para prevenir race conditions
                            lock_acquired = False
                            try:
                                import redis
                                redis_conn_msg = get_redis_connection()
                                # Lock espec├¡fico para esta mensagem (chat_id + message_id, n├úo hash do texto)
                                import hashlib
                                msg_lock_key = f"gb:{self.user_id}:lock:msg:{bot_id}:{telegram_user_id}:{telegram_msg_id_str}"
                                
                                # Tentar adquirir lock (expira em 3 segundos)
                                lock_acquired = redis_conn_msg.set(msg_lock_key, "1", ex=10, nx=True)
                                if not lock_acquired:
                                    logger.warning(f"Ôøö Mensagem j├í est├í sendo processada: {text[:30]}... (lock: {msg_lock_key})")
                                    return  # Sair sem processar
                            except Exception as e:
                                logger.warning(f"ÔÜá´©Å Erro ao verificar lock de mensagem: {e} - continuando")
                                # Fail-open: se Redis falhar, continuar (melhor que bloquear tudo)
                            
                            # Ô£à CR├ìTICO: Verificar se mensagem j├í foi salva (evitar duplica├º├úo)
                            # Verificar por message_id E por texto + timestamp (fallback)
                            existing_message = BotMessage.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id,
                                message_id=telegram_msg_id_str,
                                direction='incoming'
                            ).first()
                            
                            # Fallback: verificar por texto similar nos ├║ltimos 5 segundos
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
                                    logger.warning(f"Ôøö Mensagem similar encontrada nos ├║ltimos 5s, pulando duplica├º├úo: {text[:30]}...")
                            
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
                                    logger.info(f"Ô£à Mensagem recebida salva no banco: '{text[:50]}...' (message_id: {telegram_msg_id_str})")
                                except Exception as db_error:
                                    # Ô£à QI 10000: Tratar erro de constraint ├║nica (se existir)
                                    db.session.rollback()
                                    # Verificar novamente se foi salva por outro processo
                                    existing_check = BotMessage.query.filter_by(
                                        bot_id=bot_id,
                                        telegram_user_id=telegram_user_id,
                                        message_id=telegram_msg_id_str,
                                        direction='incoming'
                                    ).first()
                                    if existing_check:
                                        logger.warning(f"Ôøö Mensagem j├í foi salva por outro processo: {telegram_msg_id_str}")
                                    else:
                                        logger.error(f"ÔØî Erro ao salvar mensagem: {db_error}")
                            else:
                                logger.warning(f"Ôøö Mensagem j├í existe no banco, pulando: {telegram_msg_id_str}")
                    except Exception as e:
                        logger.error(f"ÔØî Erro ao salvar mensagem recebida: {e}", exc_info=True)
                        # N├úo interromper o fluxo se falhar ao salvar
                
                # ­ƒöÑ V8 ULTRA: Usar MessageRouter V8 como ├║nico ponto de entrada
                # Garante atomicidade e previne race conditions
                try:
                    router = get_message_router(self)
                    
                    # Extrair par├ómetro do deep link (se houver)
                    start_param = None
                    message_type = "text"
                    
                    if text.startswith('/start'):
                        message_type = "start"
                        if len(text) > 6 and text[6] == ' ':  # "/start " tem 7 caracteres
                            start_param = text[7:].strip()  # Tudo ap├│s "/start "
                    
                    # Ô£à VÔê×: MessageRouter V8 - ├ÜNICO PONTO DE ENTRADA (sem fallback)
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
                    logger.error(f"ÔØî Erro no MessageRouter V8: {router_error}", exc_info=True)
                    # N├úo interromper o fluxo, apenas logar o erro
                
                # Ô£à SISTEMA DE ASSINATURAS - Processar new_chat_member e left_chat_member
                if 'new_chat_members' in message:
                    # Lista de novos membros
                    new_members = message['new_chat_members']
                    chat_info = message.get('chat', {})
                    chat_type = chat_info.get('type', '')
                    
                    # Ô£à Processar apenas em grupos/supergrupos
                    if chat_type in ['group', 'supergroup']:
                        logger.info(f"­ƒæÑ Novo(s) membro(s) adicionado(s) ao grupo {chat_info.get('id')} (tipo: {chat_type})")
                        
                        for new_member in new_members:
                            member_id = str(new_member.get('id', ''))
                            member_name = new_member.get('first_name', 'Usu├írio')
                            
                            # Ô£à Verificar se n├úo ├® o pr├│prio bot
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
                            
                            logger.info(f"   ÔåÆ Novo membro: {member_name} (ID: {member_id})")
                            
                            # Ô£à CORRE├ç├âO 5: Detectar migrate_to_chat_id (grupo convertido)
                            migrate_to_chat_id = message.get('migrate_to_chat_id')
                            if migrate_to_chat_id:
                                logger.info(f"­ƒöä CORRE├ç├âO 5: Grupo convertido! Chat ID antigo: {chat_info.get('id')} ÔåÆ Novo: {migrate_to_chat_id}")
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
                                            logger.info(f"Ô£à CORRE├ç├âO 5: {updated} subscription(s) atualizada(s) com novo chat_id: {new_chat_id_str}")
                                except Exception as migrate_error:
                                    logger.error(f"ÔØî CORRE├ç├âO 5: Erro ao atualizar chat_id ap├│s migra├º├úo: {migrate_error}")
                            
                            # Ô£à Processar subscription (usar chat_id correto)
                            final_chat_id = migrate_to_chat_id if migrate_to_chat_id else chat_info.get('id')
                            self._handle_new_chat_member(
                                bot_id=bot_id,
                                chat_id=final_chat_id,
                                telegram_user_id=member_id
                            )
                
                if 'left_chat_member' in message:
                    # Usu├írio saiu do grupo
                    left_member = message['left_chat_member']
                    chat_info = message.get('chat', {})
                    chat_type = chat_info.get('type', '')
                    
                    if chat_type in ['group', 'supergroup']:
                        member_id = str(left_member.get('id', ''))
                        member_name = left_member.get('first_name', 'Usu├írio')
                        
                        logger.info(f"­ƒæï Usu├írio {member_name} (ID: {member_id}) saiu do grupo {chat_info.get('id')}")
                        # Ô£à CORRE├ç├âO 12: Cancelar subscriptions ativas quando usu├írio sai do grupo
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
                                    logger.info(f"­ƒö┤ Cancelando subscription {sub.id} - usu├írio {member_id} saiu do grupo {chat_id_str}")
                                    sub.status = 'cancelled'
                                    sub.removed_at = datetime.now(timezone.utc)
                                    sub.removed_by = 'system_user_left'
                                    db.session.commit()
                                    logger.info(f"Ô£à Subscription {sub.id} cancelada")
                        except Exception as cancel_error:
                            logger.error(f"ÔØî Erro ao cancelar subscriptions quando usu├írio saiu: {cancel_error}")
            
            # ­ƒöÑ V8 ULTRA: Processar callback via MessageRouter V8
            elif 'callback_query' in update:
                callback = update['callback_query']
                callback_data = callback.get('data', '')
                logger.info(f"­ƒöÿ BOT├âO CLICADO: {callback_data}")
                
                try:
                    router = get_message_router(self)
                    
                    # Obter chat_id e telegram_user_id do callback
                    message_from_callback = callback.get('message', {})
                    chat_id = message_from_callback.get('chat', {}).get('id')
                    user = callback.get('from', {})
                    telegram_user_id = str(user.get('id', ''))
                    
                    if not chat_id:
                        logger.warning("ÔÜá´©Å Callback sem chat_id, usando m├®todo tradicional")
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
                        logger.warning(f"ÔÜá´©Å Callback n├úo processado pelo router: {result.get('reason', 'unknown')}")
                        # Fallback: processar via m├®todo tradicional
                        self._handle_callback_query(bot_id, token, config, callback)
                    
                except Exception as router_error:
                    logger.error(f"ÔØî Erro no MessageRouter V8 para callback: {router_error}", exc_info=True)
                    # Fallback: processar via m├®todo tradicional
                    self._handle_callback_query(bot_id, token, config, callback)
                
        except Exception as e:
            import traceback
            logger.error(f"ÔØî Erro ao processar update do bot {bot_id}: {e}\n{traceback.format_exc()}")
    
    def _process_telegram_update_direct(self, bot_id: int, token: str, config: Dict[str, Any], 
                                         update: Dict[str, Any]) -> None:
        """
        ­ƒöÑ FALLBACK LEGADO: Processa update SEM verificar Redis/state
        
        Usado quando o bot n├úo est├í registrado no Redis ou quando
        o caminho normal falha. Implementa├º├úo direta similar ao c├│digo legado.
        
        Args:
            bot_id: ID do bot
            token: Token do bot Telegram
            config: Configura├º├úo do bot
            update: Update do Telegram
        """
        try:
            logger.info(f"­ƒÜÇ [FALLBACK DIRECT] Processando update para bot {bot_id}")
            
            # ­ƒöÑ CR├ìTICO: Limpar transa├º├úo pendente no in├¡cio
            try:
                from flask import current_app
                from internal_logic.core.extensions import db
                db.session.rollback()
            except Exception:
                pass  # Ignora se n├úo conseguir
            
            update_id = update.get('update_id')
            
            # Processar mensagem diretamente (sem Redis locks/state)
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')
                user = message.get('from', {})
                telegram_user_id = str(user.get('id', ''))
                
                logger.info(f"­ƒÆ¼ [FALLBACK] De: {user.get('first_name', 'Usu├írio')} | Msg: '{text[:50]}...'")
                
                # Verificar se ├® comando /start
                if text and text.strip() == '/start':
                    logger.info(f"Ô¡É [FALLBACK] Comando /start detectado")
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
                    
                    logger.info(f"Ô£à [FALLBACK] Mensagem processada via Router: {result}")
                    
                except Exception as router_error:
                    logger.error(f"ÔØî [FALLBACK] Erro no Router: {router_error}")
                    # Fallback ├║ltimo recurso: processar direto
                    self._handle_text_message(bot_id, token, config, chat_id, message)
                    
            elif 'callback_query' in update:
                # Callback query - processar diretamente
                callback = update['callback_query']
                message = callback.get('message', {})
                chat_id = message.get('chat', {}).get('id')
                callback_data = callback.get('data', '')
                
                if chat_id and callback_data:
                    logger.info(f"­ƒöÿ [FALLBACK] Callback: {callback_data}")
                    self._handle_callback_query(bot_id, token, config, callback)
                    
            logger.info(f"Ô£à [FALLBACK DIRECT] Update {update_id} processado com sucesso")
            
        except Exception as e:
            import traceback
            logger.error(f"ÔØî [FALLBACK DIRECT] Erro ao processar: {e}\n{traceback.format_exc()}")
            # ­ƒöÑ CR├ìTICO: Limpar transa├º├úo suja antes de propagar erro
            try:
                from internal_logic.core.extensions import db
                db.session.rollback()
            except Exception:
                pass
            raise  # Propagar erro para que o caller saiba que falhou
    
    def _handle_text_message(self, bot_id: int, token: str, config: Dict[str, Any], 
                            chat_id: int, message: Dict[str, Any]):
        """
        Processa mensagens de texto (n├úo comandos)
        
        # Lock variables - MUST be declared at function start to avoid scope issues
        lock_acquired = False
        lock_key = None
        
        # Ô£à CORRE├ç├âO CR├ìTICA QI 600+:
        - Verifica se h├í conversa ativa (mensagens do bot nos ├║ltimos 30 min)
        - Se houver conversa ativa, N├âO reinicia funil (apenas salva mensagem)
        - Se N├âO houver conversa ativa, reinicia funil (usu├írio retornando)
        
        PROTE├ç├òES IMPLEMENTADAS:
        - Verifica├º├úo de conversa ativa (30 minutos)
        - Rate limiting (m├íximo 1 mensagem por minuto para reiniciar funil)
        - N├úo envia Meta Pixel ViewContent (evita duplica├º├úo)
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser, Bot, BotMessage
            from datetime import datetime, timedelta
            
            with current_app.app_context():
                # Buscar usu├írio
                user_from = message.get('from', {})
                telegram_user_id = str(user_from.get('id', ''))
                first_name = user_from.get('first_name', 'Usu├írio')
                
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).first()
                
                if not bot_user:
                    # Usu├írio n├úo existe - tratar como /start
                    logger.info(f"­ƒæñ Usu├írio n├úo encontrado, tratando como /start")
                    self._handle_start_command(bot_id, token, config, chat_id, message, None)
                    return
                
                from internal_logic.core.models import get_brazil_time
                now = get_brazil_time()
                
                # Ô£à VERIFICA├ç├âO CR├ìTICA QI 600+: H├í conversa ativa?
                # Estrat├®gia robusta: verificar ├║ltima mensagem do bot + last_interaction
                conversation_window = now - timedelta(minutes=30)
                
                # 1. Verificar ├║ltima mensagem do bot enviada
                last_bot_message = BotMessage.query.filter(
                    BotMessage.bot_id == bot_id,
                    BotMessage.telegram_user_id == telegram_user_id,
                    BotMessage.direction == 'outgoing'
                ).order_by(BotMessage.created_at.desc()).first()
                
                # 2. Verificar se bot_user teve intera├º├úo recente (fallback se mensagens n├úo salvas ainda)
                recent_interaction = bot_user.last_interaction and (now - bot_user.last_interaction).total_seconds() < 1800  # 30 minutos
                
                # 3. Verificar se ├║ltima mensagem do bot foi recente (dentro da janela)
                recent_bot_message = last_bot_message and (now - last_bot_message.created_at).total_seconds() < 1800
                
                # Ô£à CONVERSA ATIVA: Se bot enviou mensagem recente OU teve intera├º├úo recente
                has_active_conversation = recent_bot_message or (recent_interaction and bot_user.welcome_sent)
                
                if has_active_conversation:
                    # Ô£à CONVERSA ATIVA: Verificar se h├í step com condi├º├Áes aguardando resposta
                    text = message.get('text', '').strip()
                    
                    # Ô£à NOVO: Buscar step atual com fun├º├úo at├┤mica
                    try:
                        current_step_id = self._get_current_step_atomic(bot_id, telegram_user_id)
                        
                        if current_step_id:
                            logger.info(f"­ƒöì Step ativo encontrado: {current_step_id} - processando condi├º├Áes")
                            
                            # Buscar step no fluxo
                            flow_steps = config.get('flow_steps', [])
                            current_step = self._find_step_by_id(flow_steps, current_step_id)
                            
                            if current_step:
                                # Ô£à QI 500: Avaliar condi├º├Áes do step com par├ómetros completos
                                next_step_id = self._evaluate_conditions(
                                    current_step, 
                                    user_input=text, 
                                    context={},
                                    bot_id=bot_id,
                                    telegram_user_id=telegram_user_id,
                                    step_id=current_step_id
                                )
                                
                                if next_step_id:
                                    logger.info(f"Ô£à Condi├º├úo matchou! Continuando para step: {next_step_id}")
                                    # Ô£à NOVO: Limpar step atual e tentativas globais
                                    try:
                                        redis_conn = get_redis_connection()
                                        if redis_conn:
                                            current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                            redis_conn.delete(current_step_key)
                                            
                                            # Ô£à NOVO: Limpar tentativas globais quando condi├º├úo matcha
                                            global_attempts_key = f"flow_global_attempts:{bot_id}:{telegram_user_id}:{current_step_id}"
                                            redis_conn.delete(global_attempts_key)
                                    except:
                                        pass
                                    # Ô£à NOVO: Buscar snapshot do Redis se dispon├¡vel
                                    flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                    
                                    # Continuar fluxo no pr├│ximo step
                                    self._execute_flow_recursive(
                                        bot_id, token, config, chat_id, telegram_user_id, next_step_id,
                                        recursion_depth=0,
                                        visited_steps=set(),
                                        flow_snapshot=flow_snapshot
                                    )
                                    return
                                else:
                                    logger.info(f"ÔÜá´©Å Nenhuma condi├º├úo matchou para texto: '{text[:50]}...'")
                                    
                                    # Ô£à QI 500: Verificar se h├í step de erro definido
                                    error_step_id = current_step.get('error_step_id')
                                    if error_step_id:
                                        logger.info(f"­ƒöä Usando step de erro: {error_step_id}")
                                        try:
                                            redis_conn = get_redis_connection()
                                            if redis_conn:
                                                current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                                redis_conn.delete(current_step_key)
                                        except:
                                            pass
                                        # Ô£à NOVO: Buscar snapshot do Redis
                                        flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                        self._execute_flow_recursive(
                                            bot_id, token, config, chat_id, telegram_user_id, error_step_id,
                                            recursion_depth=0, visited_steps=set(), flow_snapshot=flow_snapshot
                                        )
                                        return
                                    
                                    # Ô£à QI 500: Verificar se h├í conex├úo retry (comportamento antigo)
                                    connections = current_step.get('connections', {})
                                    retry_step_id = connections.get('retry')
                                    if retry_step_id:
                                        logger.info(f"­ƒöä Usando conex├úo retry: {retry_step_id}")
                                        try:
                                            redis_conn = get_redis_connection()
                                            if redis_conn:
                                                current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                                redis_conn.delete(current_step_key)
                                        except:
                                            pass
                                        # Ô£à NOVO: Buscar snapshot do Redis
                                        flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                        self._execute_flow_recursive(
                                            bot_id, token, config, chat_id, telegram_user_id, retry_step_id,
                                            recursion_depth=0, visited_steps=set(), flow_snapshot=flow_snapshot
                                        )
                                        return
                                    
                                    # Ô£à QI 500: Fallback padr├úo - enviar mensagem de erro com limite de tentativas
                                    error_message = current_step.get('config', {}).get('error_message') or "ÔÜá´©Å Resposta n├úo reconhecida. Por favor, tente novamente."
                                    
                                    # Ô£à NOVO: Limite global de tentativas por usu├írio (evita loop infinito)
                                    try:
                                        redis_conn = get_redis_connection()
                                        if redis_conn:
                                            global_attempts_key = f"flow_global_attempts:{bot_id}:{telegram_user_id}:{current_step_id}"
                                            global_attempts = redis_conn.get(global_attempts_key)
                                            global_attempts = int(global_attempts) if global_attempts else 0
                                            
                                            # Limite global: 10 tentativas por step
                                            max_global_attempts = 10
                                            if global_attempts >= max_global_attempts:
                                                logger.warning(f"ÔÜá´©Å Limite global de tentativas ({max_global_attempts}) atingido para step {current_step_id}")
                                                # Limpar step ativo e enviar mensagem final
                                                current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                                redis_conn.delete(current_step_key)
                                                final_message = "ÔÜá´©Å Muitas tentativas incorretas. Por favor, reinicie o bot com /start."
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
                                    logger.info(f"­ƒÆ¼ Mensagem de erro enviada - mantendo step ativo para retry")
                                    # N├úo limpar Redis - permite nova tentativa
                                    return
                        else:
                            logger.debug(f"­ƒÆ¼ Nenhum step ativo - mensagem ser├í apenas salva")
                    except Exception as e:
                        logger.error(f"ÔØî Erro ao processar condi├º├Áes: {e}", exc_info=True)
                    
                    # Atualizar ├║ltima intera├º├úo
                    bot_user.last_interaction = now
                    db.session.commit()
                    
                    # Mensagem j├í foi salva em _process_telegram_update antes desta fun├º├úo ser chamada
                    # N├úo fazer mais nada - apenas deixar a mensagem salva
                    return
                
                # Ô£à SEM CONVERSA ATIVA: Usu├írio retornando ap├│s muito tempo
                # Verificar rate limiting para evitar spam de reinicializa├º├úo (Redis, multi-worker)
                user_key = f"gb:rate_limit:{bot_id}_{telegram_user_id}"
                
                try:
                    redis_rl = get_redis_connection()
                    if redis_rl:
                        last_time_ts = redis_rl.get(user_key)
                        if last_time_ts is not None:
                            last_time_ts = float(last_time_ts)
                            time_diff = time.time() - last_time_ts
                            if time_diff < 300:  # 5 minutos entre reinicializa├º├Áes
                                logger.info(f"ÔÅ▒´©Å Rate limiting: Usu├írio {first_name} tentou reiniciar funil muito recente ({time_diff:.1f}s atr├ís)")
                                bot_user.last_interaction = now
                                db.session.commit()
                                return
                except Exception:
                    pass  # Redis indispon├¡vel ÔÇö fail-open
                
                # Ô£à REINICIAR FUNIL: Usu├írio retornou ap├│s muito tempo sem conversa
                logger.info(f"­ƒÆ¼ Reiniciando funil para usu├írio retornado: {first_name} (sem conversa ativa h├í 30+ min)")
                
                # Atualizar cache de rate limiting no Redis com TTL autom├ítico
                try:
                    redis_rl = get_redis_connection()
                    if redis_rl:
                        redis_rl.setex(user_key, 300, time.time())
                except Exception:
                    pass
                
                # Atualizar ├║ltima intera├º├úo no banco
                bot_user.last_interaction = now
                db.session.commit()
                
                # Enviar mensagem de boas-vindas (sem Meta Pixel)
                self._send_welcome_message_only(bot_id, token, config, chat_id, message)
                
        except Exception as e:
            logger.error(f"ÔØî Erro ao processar mensagem de texto: {e}")
            import traceback
            traceback.print_exc()
    
    def _send_welcome_message_only(self, bot_id: int, token: str, config: Dict[str, Any], 
                                  chat_id: int, message: Dict[str, Any]):
        """
        Envia apenas a mensagem de boas-vindas (sem Meta Pixel)
        Usado para mensagens de texto que reiniciam o funil
        
        # Ô£à CR├ìTICO: Respeita flow_enabled - se fluxo visual est├í ativo, n├úo envia welcome_message
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser
            from datetime import datetime
            import json
            
            # Ô£à V8 ULTRA: Verifica├º├úo centralizada de modo ativo
            is_flow_active = checkActiveFlow(config)
            
            logger.info(f"­ƒöì _send_welcome_message_only: is_flow_active={is_flow_active}")
            
            # Ô£à Se fluxo visual est├í ativo, N├âO enviar welcome_message
            if is_flow_active:
                logger.info(f"­ƒÜ½ _send_welcome_message_only: Fluxo visual ativo - BLOQUEANDO welcome_message")
                logger.info(f"­ƒÜ½ Usu├írio retornou mas fluxo visual est├í ativo - executando fluxo em vez de welcome")
                
                # Executar fluxo visual em vez de enviar welcome_message
                try:
                    user_from = message.get('from', {})
                    telegram_user_id = str(user_from.get('id', ''))
                    self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
                    logger.info(f"Ô£à Fluxo visual executado em _send_welcome_message_only")
                except Exception as e:
                    logger.error(f"ÔØî Erro ao executar fluxo em _send_welcome_message_only: {e}", exc_info=True)
                    # Mesmo com erro, n├úo enviar welcome_message quando fluxo est├í ativo
                
                return  # Ô£à SAIR SEM ENVIAR welcome_message
            
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser
            
            with current_app.app_context():
                # Buscar usu├írio para atualizar welcome_sent
                user_from = message.get('from', {})
                telegram_user_id = str(user_from.get('id', ''))
                
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).first()
                
                # Preparar mensagem de boas-vindas
                welcome_message = config.get('welcome_message', 'Ol├í! Bem-vindo!')
                welcome_media_url = config.get('welcome_media_url')
                welcome_media_type = config.get('welcome_media_type', 'video')
                welcome_audio_enabled = config.get('welcome_audio_enabled', False)
                welcome_audio_url = config.get('welcome_audio_url', '')
                main_buttons = config.get('main_buttons', [])
                redirect_buttons = config.get('redirect_buttons', [])
                
                # Preparar bot├Áes
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
                
                # Verificar m├¡dia v├ílida
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
                    logger.info(f"Ô£à Mensagem de texto reiniciou funil com {len(buttons)} bot├úo(├Áes)")
                    
                    # Marcar como enviado (sem afetar Meta Pixel)
                    if bot_user:
                        bot_user.welcome_sent = True
                        from internal_logic.core.models import get_brazil_time
                        bot_user.welcome_sent_at = get_brazil_time()
                        db.session.commit()
                    
                    # Enviar ├íudio se habilitado
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
                    logger.error(f"ÔØî Falha ao enviar mensagem de boas-vindas")
                    
        except Exception as e:
            logger.error(f"ÔØî Erro ao enviar mensagem de boas-vindas: {e}")
    
    def _check_start_lock(self, chat_id: int) -> bool:
        """
        # Ô£à QI 500: Lock para evitar /start duplicado
        
        Retorna True se pode processar (lock adquirido)
        Retorna False se j├í est├í processando (lock j├í existe)
        """
        try:
            import redis
            redis_conn = get_redis_connection()
            lock_key = f"gb:{self.user_id}:lock:start:{chat_id}"
            
            # Tentar adquirir lock (expira em 3 segundos)
            acquired = redis_conn.set(lock_key, "1", ex=3, nx=True)
            
            if acquired:
                logger.info(f"­ƒöÆ Lock adquirido para /start: chat_id={chat_id}")
                return True
            else:
                logger.warning(f"ÔÜá´©Å /start duplicado bloqueado: chat_id={chat_id} (j├í processando)")
                return False
        except Exception as e:
            logger.error(f"ÔØî Erro ao verificar lock /start: {e}")
            # Em caso de erro, permitir processar (fail open)
            return True
    
    def send_funnel_step_sequential(self, token: str, chat_id: str, 
                                   text: str = None,
                                   media_url: str = None,
                                   media_type: str = None,
                                   buttons: list = None,
                                   delay_between: float = 0.2,
                                   bot_id: Optional[int] = None):
        """
        # Ô£à QI 500: Envia step do funil SEQUENCIALMENTE (garante ordem)
        
        # Ô£à QI 10000: ANTI-DUPLICA├ç├âO - Lock por chat+hash(texto) antes de enviar
        
        # Ô£à NOVA L├ôGICA: Se texto > 1024 caracteres (limite do Telegram para caption) E tem m├¡dia:
           1. M├¡dia PRIMEIRO (sem caption)
           2. Texto completo COM bot├Áes (depois da m├¡dia)
        
        # Ô£à L├ôGICA PADR├âO: Se texto <= 1024 caracteres E tem m├¡dia:
           1. M├¡dia COM caption e bot├Áes
        
        # Ô£à L├ôGICA SEM M├ìDIA: Se n├úo tem m├¡dia:
           1. Texto com bot├Áes (se houver texto)
           2. OU Bot├Áes separados (se n├úo houver texto)
        
        Tudo na mesma thread, com delay entre envios.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            text: Texto da mensagem
            media_url: URL da m├¡dia
            media_type: Tipo da m├¡dia (photo, video, audio)
            buttons: Lista de bot├Áes
            delay_between: Delay em segundos entre envios (padr├úo 0.2s)
            bot_id: ID do bot (se None, resolvido do token)
        
        Returns:
            bool: True se todos os envios foram bem-sucedidos
        """
        import time
        import hashlib
        
        if not bot_id:
            try:
                from internal_logic.core.models import Bot
                bot = Bot.query.filter_by(token=token).first()
                if bot:
                    bot_id = bot.id
            except Exception:
                pass
        
        # ============================================================================
        # Ô£à QI 10000: ANTI-DUPLICA├ç├âO ROBUSTA - Lock ├║nico sincronizado para m├¡dia + texto
        # ============================================================================
        # Gerar hash do conte├║do (texto + m├¡dia + bot├Áes) para garantir consist├¬ncia
        content_hash = hashlib.md5(
            f"{text or ''}{media_url or ''}{str(buttons or [])}".encode('utf-8')
        ).hexdigest()[:12]  # 12 caracteres para maior unicidade
        
        # Lock ├║nico e sincronizado para m├¡dia + texto completo
        media_text_lock_key = f"gb:{self.user_id}:lock:send_media_and_text:{chat_id}:{content_hash}"
        redis_conn_send = None
        lock_acquired = False
        
        # Vari├íveis para finally (garantir que est├úo no escopo)
        lock_to_release = None
        
        try:
            import redis
            redis_conn_send = get_redis_connection()
            
            # Tentar adquirir lock (expira em 15 segundos - tempo suficiente para m├¡dia + texto completo)
            lock_acquired = redis_conn_send.set(media_text_lock_key, "1", ex=15, nx=True)
            if not lock_acquired:
                logger.warning(f"Ôøö Lock de envio j├í adquirido: chat_id={chat_id}, hash={content_hash} - BLOQUEANDO DUPLICA├ç├âO")
                return False  # Sair sem enviar (duplica├º├úo detectada)
            else:
                logger.debug(f"­ƒöÆ Lock de envio adquirido: {media_text_lock_key} (expira em 15s)")
                lock_to_release = media_text_lock_key  # Marcar para liberar no finally
        except Exception as e:
            logger.warning(f"ÔÜá´©Å Erro ao verificar lock de envio: {e} - continuando")
            # Fail-open: se Redis falhar, continuar (melhor que bloquear tudo)
        
        try:
            # Ô£à QI 10000: Log para rastrear envios
            logger.info(f"­ƒôñ Enviando mensagem do funil: chat_id={chat_id}, texto_len={len(text) if text else 0}, tem_midia={bool(media_url)}")
            
            base_url = f"https://api.telegram.org/bot{token}"
            all_success = True
            
            # 1´©ÅÔâú ENVIAR TEXTO (se houver e N├âO houver m├¡dia - se houver m├¡dia, texto ser├í caption)
            if text and text.strip() and not media_url:
                logger.info(f"­ƒôØ Enviando texto sequencial...")
                url = f"{base_url}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200 and response.json().get('ok'):
                    logger.info(f"Ô£à Texto enviado")
                    if bot_id:
                        result_data = response.json()
                        msg_id = str(result_data.get('result', {}).get('message_id', ''))
                        self._save_outgoing_message(
                            bot_id=bot_id, chat_id=chat_id, message_text=text,
                            message_type='text', message_id=msg_id
                        )
                else:
                    logger.error(f"ÔØî Falha ao enviar texto: {response.text}")
                    all_success = False
                
                time.sleep(delay_between)  # Ô£à QI 500: Delay entre envios
            
            # 2´©ÅÔâú ENVIAR M├ìDIA (se houver)
            if media_url:
                logger.info(f"­ƒû╝´©Å Enviando m├¡dia sequencial ({media_type})...")
                CAPTION_LIMIT = 1024  # Ô£à Limite real do Telegram para caption
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

                # Ô£à NOVA L├ôGICA: Se texto > 1024, enviar m├¡dia PRIMEIRO (sem caption), depois texto completo com bot├Áes
                text_exceeds_caption = text and len(text or '') > CAPTION_LIMIT
                
                if text_exceeds_caption:
                    logger.info(f"­ƒôè Texto excede limite de caption ({len(text)} > {CAPTION_LIMIT}). Enviando m├¡dia PRIMEIRO (sem caption), depois texto completo com bot├Áes...")
                    text_sent_separately = True  # Marcar que texto ser├í enviado separadamente
                else:
                    # Texto <= 1024: pode usar como caption
                    logger.info(f"­ƒôè Texto dentro do limite de caption ({len(text) if text else 0} <= {CAPTION_LIMIT}). Usando como caption da m├¡dia.")

                # Preparar caption (apenas se texto <= 1024)
                caption_text = ''
                if text and text.strip() and not text_sent_separately:
                    caption_text = text[:CAPTION_LIMIT] if len(text) > CAPTION_LIMIT else text

                # Ô£à PASSO 1: ENVIAR M├ìDIA (SEM caption se texto > 1024, COM caption se texto <= 1024)
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
                    logger.warning(f"ÔÜá´©Å Tipo de m├¡dia desconhecido: {media_type}")
                    all_success = False
                    media_url = None  # N├úo enviar m├¡dia inv├ílida

                if media_url:
                    # Ô£à Adicionar bot├Áes ├á m├¡dia APENAS se texto <= 1024 (texto ser├í caption)
                    # Se texto > 1024, bot├Áes v├úo no texto separado
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
                        logger.info(f"Ô£à M├¡dia enviada{' com caption' if caption_text else ' sem caption'} {'e bot├Áes' if inline_keyboard and not text_sent_separately else ''}")
                        if bot_id:
                            result_data = response.json()
                            msg_id = str(result_data.get('result', {}).get('message_id', ''))
                            self._save_outgoing_message(
                                bot_id=bot_id, chat_id=chat_id,
                                message_text=caption_text or None,
                                message_type=media_type or 'photo',
                                media_url=media_url,
                                message_id=msg_id
                            )
                    else:
                        logger.error(f"ÔØî Falha ao enviar m├¡dia: {response.text}")
                        all_success = False

                    time.sleep(delay_between)  # Ô£à Delay entre envios

                    # Ô£à PASSO 2: Se texto > 1024, enviar texto completo COM BOT├òES ap├│s m├¡dia
                    if text_exceeds_caption:
                        # ========================================================================
                        # Ô£à LOCK ESPEC├ìFICO PARA TEXTO COMPLETO (ANTI-DUPLICA├ç├âO)
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
                                logger.warning(f"Ôøö TEXTO COMPLETO j├í est├í sendo enviado: chat_id={chat_id}, hash={text_only_hash} - BLOQUEANDO DUPLICA├ç├âO")
                                return all_success  # Retornar sucesso parcial (m├¡dia j├í foi enviada)
                            else:
                                logger.info(f"­ƒöÆ Lock de texto completo adquirido: {text_complete_lock_key} (expira em 10s)")
                        except Exception as e:
                            logger.warning(f"ÔÜá´©Å Erro ao verificar lock de texto completo: {e} - continuando")

                        try:
                            # Ô£à Verifica├º├úo adicional no banco (anti-duplica├º├úo)
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
                                        logger.warning(f"Ôøö Texto completo j├í foi enviado recentemente (├║ltimos 5s): chat_id={chat_id} - BLOQUEANDO DUPLICA├ç├âO")
                                        if text_lock_acquired and redis_conn_text:
                                            try:
                                                redis_conn_text.delete(text_complete_lock_key)
                                                logger.debug(f"­ƒöô Lock liberado ap├│s detec├º├úo de duplica├º├úo no banco")
                                            except:
                                                pass
                                        return all_success  # Retornar sucesso parcial (m├¡dia j├í foi enviada)
                            except Exception as e:
                                logger.warning(f"ÔÜá´©Å Erro ao verificar duplica├º├úo no banco: {e} - continuando")

                            # Ô£à ENVIAR TEXTO COMPLETO COM BOT├òES (ap├│s m├¡dia)
                            logger.info(f"­ƒôØ Enviando texto completo ap├│s m├¡dia (len={len(text)}, hash={text_only_hash})...")
                            url_msg = f"{base_url}/sendMessage"
                            payload_msg = {
                                'chat_id': chat_id,
                                'text': text,  # Ô£à Texto completo
                                'parse_mode': 'HTML'
                            }
                            
                            # Ô£à Adicionar bot├Áes ao texto completo
                            if inline_keyboard:
                                payload_msg['reply_markup'] = {'inline_keyboard': inline_keyboard}

                            logger.info(f"­ƒÜÇ Enviando texto completo com bot├Áes ap├│s m├¡dia: chat_id={chat_id}, hash={text_only_hash}")

                            response_msg = requests.post(url_msg, json=payload_msg, timeout=10)

                            # Ô£à Log ap├│s enviar para confirmar
                            if response_msg.status_code == 200:
                                result_data = response_msg.json()
                                if result_data.get('ok'):
                                    message_id_sent = result_data.get('result', {}).get('message_id')
                                    logger.info(f"Ô£à Texto completo com bot├Áes enviado ap├│s m├¡dia (message_id={message_id_sent}, hash={text_only_hash})")
                                    
                                    # Ô£à Salvar mensagem enviada no banco para verifica├º├úo futura (anti-duplica├º├úo)
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

                                                # Verificar se j├í existe antes de salvar
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
                                                        message_text=text,  # Ô£à Texto completo (n├úo apenas restante)
                                                        message_type='text',
                                                        direction='outgoing',
                                                        is_read=True
                                                    )
                                                    db.session.add(bot_message)
                                                    db.session.commit()
                                                    logger.debug(f"Ô£à Texto completo salvo no banco para verifica├º├úo futura")
                                    except Exception as e:
                                        logger.debug(f"ÔÜá´©Å Erro ao salvar texto completo no banco (n├úo cr├¡tico): {e}")
                                else:
                                    logger.error(f"ÔØî Telegram API retornou erro: {result_data.get('description', 'Erro desconhecido')}")
                                    all_success = False
                            else:
                                logger.error(f"ÔØî HTTP {response_msg.status_code}: {response_msg.text[:200]}")
                                all_success = False
                        finally:
                            # Ô£à SEMPRE liberar lock de texto completo ap├│s envio (ou erro)
                            if text_lock_acquired and redis_conn_text:
                                try:
                                    redis_conn_text.delete(text_complete_lock_key)
                                    logger.debug(f"­ƒöô Lock de texto completo liberado: {text_complete_lock_key}")
                                except Exception as e:
                                    logger.debug(f"ÔÜá´©Å Erro ao liberar lock de texto completo (n├úo cr├¡tico): {e}")

                        time.sleep(delay_between)  # Ô£à Delay entre envios

            # 3´©ÅÔâú ENVIAR BOT├òES (se houver e N├âO foram enviados com m├¡dia)
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
                
                logger.info(f"­ƒöÿ Enviando bot├Áes sequencial...")
                url = f"{base_url}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': text[:100] if text else "Ô¼ç´©Å Escolha uma op├º├úo",
                    'parse_mode': 'HTML',
                    'reply_markup': reply_markup
                }
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200 and response.json().get('ok'):
                    logger.info(f"Ô£à Bot├Áes enviados")
                    if bot_id:
                        result_data = response.json()
                        msg_id = str(result_data.get('result', {}).get('message_id', ''))
                        self._save_outgoing_message(
                            bot_id=bot_id, chat_id=chat_id,
                            message_text=text[:100] if text else "Escolha uma op├º├úo",
                            message_type='text', message_id=msg_id
                        )
                else:
                    logger.error(f"ÔØî Falha ao enviar bot├Áes: {response.text}")
                    all_success = False
            
            return all_success
            
        except Exception as e:
            logger.error(f"ÔØî Erro ao enviar step sequencial: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Ô£à QI 10000: Liberar lock ap├│s envio completo (ou erro)
            # Nota: Lock expira automaticamente em 15s, mas liberar manualmente ├® melhor pr├ítica
            if lock_acquired and redis_conn_send and lock_to_release:
                try:
                    redis_conn_send.delete(lock_to_release)
                    logger.debug(f"­ƒöô Lock liberado: {lock_to_release}")
                except Exception as e:
                    logger.debug(f"ÔÜá´©Å Erro ao liberar lock (n├úo cr├¡tico, expira automaticamente em 15s): {e}")
    
    def _find_step_by_id(self, flow_steps: list, step_id: str) -> Dict[str, Any]:
        """
        Busca step por ID no fluxo
        
        # Ô£à VALIDA├ç├âO: Sanitiza step_id antes de buscar
        # Ô£à CR├ìTICO: Compara IDs como strings (pode vir como n├║mero ou string)
        """
        if not step_id:
            return None
        
        # Converter step_id para string para compara├º├úo
        step_id_str = str(step_id).strip()
        
        if not step_id_str:
            return None
        
        if not flow_steps or not isinstance(flow_steps, list):
            logger.warning(f"ÔÜá´©Å _find_step_by_id: flow_steps inv├ílido (tipo: {type(flow_steps)})")
            return None
        
        for step in flow_steps:
            if not isinstance(step, dict):
                continue
            
            step_id_candidate = step.get('id')
            if step_id_candidate is None:
                continue
            
            # Ô£à CR├ìTICO: Comparar como strings (pode ser n├║mero ou string)
            if str(step_id_candidate).strip() == step_id_str:
                logger.info(f"Ô£à Step encontrado: id={step_id_candidate} (tipo: {type(step_id_candidate)})")
                return step
        
        logger.warning(f"ÔÜá´©Å Step {step_id_str} n├úo encontrado em {len(flow_steps)} steps")
        return None
    
    def _validate_condition(self, condition: Dict[str, Any]) -> tuple:
        """
        # Ô£à QI 500: Valida estrutura de uma condi├º├úo
        
        Returns:
            (is_valid: bool, error_message: str)
        """
        if not isinstance(condition, dict):
            return False, "Condi├º├úo deve ser um objeto"
        
        condition_type = condition.get('type')
        if not condition_type or not isinstance(condition_type, str):
            return False, "Condi├º├úo deve ter 'type' (string)"
        
        valid_types = ['text_validation', 'button_click', 'payment_status', 'time_elapsed']
        if condition_type not in valid_types:
            return False, f"Tipo de condi├º├úo inv├ílido: {condition_type}. V├ílidos: {valid_types}"
        
        target_step = condition.get('target_step')
        if not target_step or not isinstance(target_step, str) or not target_step.strip():
            return False, "Condi├º├úo deve ter 'target_step' (string n├úo vazia)"
        
        # Valida├º├Áes espec├¡ficas por tipo
        if condition_type == 'text_validation':
            validation = condition.get('validation', 'any')
            valid_validations = ['email', 'phone', 'cpf', 'contains', 'equals', 'any']
            if validation not in valid_validations:
                return False, f"Valida├º├úo de texto inv├ílida: {validation}"
            
            if validation in ('contains', 'equals'):
                value = condition.get('value')
                if not value or not isinstance(value, str):
                    return False, f"Valida├º├úo '{validation}' requer 'value' (string)"
        
        elif condition_type == 'button_click':
            button_text = condition.get('button_text')
            if not button_text or not isinstance(button_text, str):
                return False, "Condi├º├úo 'button_click' requer 'button_text' (string)"
        
        elif condition_type == 'payment_status':
            status = condition.get('status', 'paid')
            valid_statuses = ['paid', 'pending', 'failed', 'expired']
            if status not in valid_statuses:
                return False, f"Status de pagamento inv├ílido: {status}"
        
        elif condition_type == 'time_elapsed':
            minutes = condition.get('minutes', 5)
            seconds = condition.get('seconds', 0)
            if not isinstance(minutes, (int, float)) or minutes < 0:
                return False, "Condi├º├úo 'time_elapsed' requer 'minutes' (n├║mero >= 0)"
            if not isinstance(seconds, (int, float)) or seconds < 0 or seconds > 59:
                return False, "Condi├º├úo 'time_elapsed' requer 'seconds' (0-59)"
            if minutes == 0 and seconds == 0:
                return False, "Condi├º├úo 'time_elapsed' requer pelo menos 1 minuto ou 1 segundo"
        
        # Validar max_attempts se presente
        max_attempts = condition.get('max_attempts')
        if max_attempts is not None:
            if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 100:
                return False, "max_attempts deve ser um inteiro entre 1 e 100"
        
        # Validar fallback_step se presente
        fallback_step = condition.get('fallback_step')
        if fallback_step is not None:
            if not isinstance(fallback_step, str) or not fallback_step.strip():
                return False, "fallback_step deve ser uma string n├úo vazia"
        
        return True, ""
    
    def _evaluate_conditions(self, step: Dict[str, Any], user_input: str = None, 
                            context: Dict[str, Any] = None, bot_id: int = None, 
                            telegram_user_id: str = None, step_id: str = None) -> Optional[str]:
        """
        # Ô£à QI 500: Avalia condi├º├Áes do step e retorna pr├│ximo step_id
        
        # Ô£à NOVO: Valida├º├úo completa de condi├º├Áes antes de avaliar
        # Ô£à NOVO: Valida├º├úo de max_attempts com fallback
        # Ô£à NOVO: Suporte a step de erro padr├úo
        
        Args:
            step: Step atual com condi├º├Áes
            user_input: Input do usu├írio (texto, callback_data, etc.)
            context: Contexto adicional (payment_status, etc.)
            bot_id: ID do bot (para Redis)
            telegram_user_id: ID do usu├írio (para Redis)
            step_id: ID do step atual (para Redis)
        
        Returns:
            step_id do pr├│ximo step ou None se nenhuma condi├º├úo matchou
        """
        if not step or not isinstance(step, dict):
            return None
        
        conditions = step.get('conditions', [])
        if not conditions or not isinstance(conditions, list) or len(conditions) == 0:
            return None
        
        # Ô£à VALIDA├ç├âO: Filtrar condi├º├Áes inv├ílidas
        valid_conditions = []
        for idx, condition in enumerate(conditions):
            is_valid, error_msg = self._validate_condition(condition)
            if not is_valid:
                logger.error(f"ÔØî Condi├º├úo {idx} do step {step_id} inv├ílida: {error_msg}")
                logger.error(f"   Condi├º├úo: {condition}")
                continue
            valid_conditions.append(condition)
        
        if not valid_conditions:
            logger.warning(f"ÔÜá´©Å Nenhuma condi├º├úo v├ílida no step {step_id}")
            return None
        
        # Ordenar por ordem (order)
        sorted_conditions = sorted(valid_conditions, key=lambda c: c.get('order', 0))
        
        # Ô£à NOVO: Verificar max_attempts antes de avaliar
        try:
            import redis
            redis_conn = get_redis_connection()
        except:
            redis_conn = None
        
        for condition in sorted_conditions:
            condition_type = condition.get('type')
            condition_id = condition.get('id', f"cond_{sorted_conditions.index(condition)}")
            
            # Ô£à NOVO: Verificar max_attempts (apenas para condi├º├Áes de texto/button)
            if condition_type in ('text_validation', 'button_click') and redis_conn and bot_id and telegram_user_id and step_id:
                max_attempts = condition.get('max_attempts')
                if max_attempts and max_attempts > 0:
                    attempt_key = f"flow_attempts:{bot_id}:{telegram_user_id}:{step_id}:{condition_id}"
                    try:
                        attempts = redis_conn.get(attempt_key)
                        attempts = int(attempts) if attempts else 0
                        
                        if attempts >= max_attempts:
                            logger.warning(f"ÔÜá´©Å M├íximo de tentativas ({max_attempts}) atingido para condi├º├úo {condition_id}")
                            # Retornar fallback_step se definido
                            fallback_step = condition.get('fallback_step')
                            if fallback_step:
                                logger.info(f"­ƒöä Usando fallback_step: {fallback_step}")
                                return fallback_step
                            # Se n├úo tem fallback, continuar para pr├│xima condi├º├úo
                            continue
                    except Exception as e:
                        logger.warning(f"ÔÜá´©Å Erro ao verificar max_attempts: {e}")
            
            # Avaliar condi├º├úo
            matched = False
            
            if condition_type == 'text_validation':
                if user_input and self._match_text_validation(condition, user_input):
                    matched = True
                    # Ô£à NOVO: Resetar tentativas quando matcha
                    if redis_conn and bot_id and telegram_user_id and step_id:
                        attempt_key = f"flow_attempts:{bot_id}:{telegram_user_id}:{step_id}:{condition_id}"
                        try:
                            redis_conn.delete(attempt_key)
                        except:
                            pass
            
            elif condition_type == 'button_click':
                # Ô£à NOVO: Passar step completo para match correto
                if user_input and self._match_button_click(condition, user_input, step=step):
                    matched = True
                    # Ô£à NOVO: Resetar tentativas quando matcha
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
                # Ô£à NOVO: Passar par├ómetros adicionais para calcular tempo decorrido
                if self._match_time_elapsed(condition, context or {}, bot_id, telegram_user_id, step_id):
                    matched = True
            
            if matched:
                return condition.get('target_step')
            
            # Ô£à NOVO: Incrementar tentativas se n├úo matchou (apenas para condi├º├Áes de texto/button)
            if condition_type in ('text_validation', 'button_click') and redis_conn and bot_id and telegram_user_id and step_id:
                max_attempts = condition.get('max_attempts')
                if max_attempts and max_attempts > 0:
                    attempt_key = f"flow_attempts:{bot_id}:{telegram_user_id}:{step_id}:{condition_id}"
                    try:
                        redis_conn.incr(attempt_key)
                        redis_conn.expire(attempt_key, 3600)  # Expira em 1 hora
                    except:
                        pass
        
        return None  # Nenhuma condi├º├úo matchou
    
    def _match_text_validation(self, condition: Dict[str, Any], user_input: str) -> bool:
        """Valida texto do usu├írio baseado na condi├º├úo"""
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
        # Ô£à QI 500: Verifica se callback_data corresponde ao bot├úo da condi├º├úo
        
        # Ô£à CORRE├ç├âO: Match exato usando ├¡ndice do bot├úo quando dispon├¡vel
        """
        if not callback_data or not isinstance(callback_data, str):
            return False
        
        button_text = condition.get('button_text', '').strip()
        if not button_text:
            return False
        
        # Ô£à NOVO: Se callback_data ├® do formato flow_step_{step_id}_btn_{idx}
        # E temos acesso ao step, fazer match exato por ├¡ndice
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
                        
                        # Verificar se ├¡ndice ├® v├ílido e texto corresponde
                        if btn_idx < len(custom_buttons):
                            actual_button = custom_buttons[btn_idx]
                            expected_text = button_text.lower().strip()
                            actual_text = actual_button.get('text', '').strip().lower()
                            
                            # Ô£à MATCH EXATO: Comparar texto do bot├úo
                            if expected_text == actual_text:
                                logger.debug(f"Ô£à Button click match exato: '{expected_text}' == '{actual_text}' (├¡ndice {btn_idx})")
                                return True
                            else:
                                logger.debug(f"ÔØî Button click n├úo matchou: '{expected_text}' != '{actual_text}' (├¡ndice {btn_idx})")
                                return False
            except (ValueError, IndexError, TypeError) as e:
                logger.debug(f"ÔÜá´©Å Erro ao extrair ├¡ndice do bot├úo: {e} - usando fallback")
        
        # Ô£à FALLBACK: Match por texto (case insensitive) para outros formatos
        # Mas apenas se callback_data cont├®m button_text como substring completa
        callback_lower = callback_data.lower()
        button_lower = button_text.lower()
        
        # Match exato (preferencial)
        if button_lower == callback_lower:
            return True
        
        # Match por substring (menos confi├ível, mas necess├írio para compatibilidade)
        if button_lower in callback_lower:
            logger.debug(f"ÔÜá´©Å Button click match por substring: '{button_lower}' in '{callback_lower}'")
            return True
        
        return False
    
    def _match_payment_status(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Verifica se status de pagamento corresponde ├á condi├º├úo"""
        expected_status = condition.get('status', 'paid')
        actual_status = context.get('payment_status')
        
        return actual_status == expected_status
    
    def _match_time_elapsed(self, condition: Dict[str, Any], context: Dict[str, Any], 
                           bot_id: int = None, telegram_user_id: str = None, step_id: str = None) -> bool:
        """
        # Ô£à QI 500: Verifica se tempo decorrido corresponde ├á condi├º├úo
        
        # Ô£à NOVO: Implementa├º├úo funcional usando Redis para rastrear timestamp
        """
        # FIX FALSY: 0 minutos valido
        _rm = condition.get('minutes')
        required_minutes = int(_rm) if _rm not in (None, '') else 5
        required_seconds = condition.get('seconds', 0)
        required_total_seconds = required_minutes * 60 + required_seconds
        
        # Ô£à NOVO: Buscar timestamp do step do Redis
        if bot_id and telegram_user_id and step_id:
            try:
                redis_conn = get_redis_connection()
                if redis_conn:
                    timestamp_key = f"flow_step_timestamp:{bot_id}:{telegram_user_id}:{step_id}"
                    step_timestamp = redis_conn.get(timestamp_key)
                    
                    if step_timestamp:
                        step_timestamp = int(step_timestamp) if isinstance(step_timestamp, (str, bytes)) else step_timestamp
                        import time
                        elapsed_seconds = int(time.time()) - step_timestamp
                        
                        logger.debug(f"ÔÅ▒´©Å Tempo decorrido: {elapsed_seconds}s (requerido: {required_total_seconds}s = {required_minutes}min {required_seconds}s)")
                        return elapsed_seconds >= required_total_seconds
            except Exception as e:
                logger.warning(f"ÔÜá´©Å Erro ao calcular tempo decorrido: {e}")
        
        # ­ƒöÑ FALLBACK ROBUSTO: Redis indispon├¡vel -> usa ├║ltima mensagem do BOT
        # para o chat como refer├¬ncia de tempo (o step anterior foi enviado pelo bot)
        try:
            from internal_logic.core.models import BotMessage
            last = BotMessage.query.filter_by(
                bot_id=bot_id, chat_id=str(telegram_user_id)
            ).order_by(BotMessage.created_at.desc()).first() if (bot_id and telegram_user_id) else None
            if last is None and bot_id and telegram_user_id:
                from sqlalchemy import desc as _desc
                last = BotMessage.query.filter(
                    BotMessage.bot_id == bot_id
                ).order_by(BotMessage.created_at.desc()).first()
            if last is not None:
                ref_time = getattr(last, 'created_at', None) or getattr(last, 'sent_at', None)
                if ref_time is not None:
                    import time as _t2, datetime as _dt2
                    now_utc = _dt2.datetime.now(_dt2.timezone.utc)
                    ref = ref_time if ref_time.tzinfo else ref_time.replace(tzinfo=_dt2.timezone.utc)
                    elapsed_seconds = int((now_utc - ref).total_seconds())
                    logger.warning(f"ÔÅ▒´©Å [FALLBACK DB] tempo decorrido: {elapsed_seconds}s >= {required_total_seconds}s?")
                    return elapsed_seconds >= required_total_seconds
        except Exception as fb_err:
            logger.error(f"ÔØî Fallback DB do time_elapsed falhou: {fb_err}")

        # ├Ültimo recurso: context se dispon├¡vel
        elapsed_minutes = context.get('elapsed_minutes', 0)
        return elapsed_minutes * 60 >= required_total_seconds
    
    def _validate_cpf(self, cpf: str) -> bool:
        """
        # Ô£à QI 500: Valida CPF com d├¡gitos verificadores
        
        # Ô£à NOVO: Valida├º├úo robusta de edge cases
        
        Args:
            cpf: CPF a ser validado (pode conter formata├º├úo)
        
        Returns:
            True se CPF ├® v├ílido, False caso contr├írio
        """
        import re
        
        # Ô£à VALIDA├ç├âO: Verificar se cpf ├® string v├ílida
        if not cpf or not isinstance(cpf, str):
            return False
        
        # Remover formata├º├úo
        cpf_clean = re.sub(r'\D', '', cpf)
        
        # Ô£à VALIDA├ç├âO: Verificar se tem apenas n├║meros ap├│s limpeza
        if not cpf_clean.isdigit():
            return False
        
        # Verificar tamanho
        if len(cpf_clean) != 11:
            return False
        
        cpf = cpf_clean
        
        # CPFs conhecidos como inv├ílidos (todos d├¡gitos iguais)
        if cpf == cpf[0] * 11:
            return False
        
        # Validar d├¡gitos verificadores
        def calculate_digit(cpf: str, weights: list) -> int:
            """Calcula d├¡gito verificador"""
            total = sum(int(cpf[i]) * weights[i] for i in range(len(weights)))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        # Validar primeiro d├¡gito
        weights_1 = [10, 9, 8, 7, 6, 5, 4, 3, 2]
        digit_1 = calculate_digit(cpf, weights_1)
        if int(cpf[9]) != digit_1:
            return False
        
        # Validar segundo d├¡gito
        weights_2 = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
        digit_2 = calculate_digit(cpf, weights_2)
        if int(cpf[10]) != digit_2:
            return False
        
        return True
    
    def _save_payment_flow_step_id(self, payment_id: str, step_id: str) -> bool:
        """
        # Ô£à QI 500: Salva flow_step_id no payment de forma at├┤mica
        
        Returns:
            bool: True se salvou com sucesso
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Payment
            
            with current_app.app_context():
                # Ô£à Buscar payment com lock (SELECT FOR UPDATE)
                payment = db.session.query(Payment).filter_by(payment_id=payment_id).with_for_update().first()
                
                if not payment:
                    logger.error(f"ÔØî Payment n├úo encontrado: {payment_id}")
                    return False
                
                # Ô£à Validar que payment ainda est├í pending (evita sobrescrever se j├í foi processado)
                if payment.status != 'pending':
                    logger.warning(f"ÔÜá´©Å Payment {payment_id} j├í est├í {payment.status} - n├úo atualizando flow_step_id")
                    return False
                
                # Salvar flow_step_id
                payment.flow_step_id = step_id
                
                # Ô£à Commit at├┤mico
                db.session.commit()
                
                # Ô£à Verificar se foi salvo corretamente
                db.session.refresh(payment)
                if payment.flow_step_id == step_id:
                    logger.info(f"Ô£à flow_step_id salvo atomicamente: {step_id} para payment {payment_id}")
                    return True
                else:
                    logger.error(f"ÔØî flow_step_id n├úo foi salvo corretamente!")
                    return False
        
        except Exception as e:
            logger.error(f"ÔØî Erro ao salvar flow_step_id: {e}", exc_info=True)
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    def _build_step_buttons(self, step: Dict[str, Any], config: Dict[str, Any] = None) -> list:
        """
        # Ô£à QI 500: Constr├│i lista de bot├Áes para um step (customizados + cadastrados)
        
        Returns:
            list: Lista de bot├Áes no formato Telegram API
        """
        buttons = []
        step_config = step.get('config', {})
        step_id = step.get('id', '')
        
        if config is None:
            config = {}
        
        # Ô£à 1. Processar bot├Áes customizados primeiro
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
                    logger.info(f"­ƒöÿ Bot├úo customizado criado: '{btn_text}' ÔåÆ {target_step if target_step else 'nenhum'} (callback: {callback_data})")
        
        # Ô£à 2. Processar bot├Áes cadastrados (se n├úo houver customizados ou adicionar junto)
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

    # Ô£à PERSONALIZA├ç├âO DE FUNIL ÔÇö delega para util compartilhado
    def _personalize_text(self, text: str, bot_id: Optional[int], chat_id: int) -> str:
        try:
            from internal_logic.services.flow_personalization import personalize
            return personalize(text, bot_id, str(chat_id))
        except Exception:
            return text
    def _execute_step(self, step: Dict[str, Any], token: str, chat_id: int, delay: float = 0, config: Dict[str, Any] = None, bot_id: Optional[int] = None, telegram_user_id: str = None):
        """
        # Ô£à QI 500: Executa um step do fluxo com tratamento de erro robusto
        """
        import time
        
        logger.info(f"­ƒÄ¼ _execute_step chamado: step_id={step.get('id')}, step_type={step.get('type')}")
        
        # Ô£à VALIDA├ç├âO: Verificar se step ├® v├ílido
        if not step or not isinstance(step, dict):
            logger.error(f"ÔØî Step inv├ílido: {step}")
            return
        
        step_type = step.get('type')
        if not step_type or not isinstance(step_type, str):
            logger.error(f"ÔØî Step sem tipo v├ílido: {step}")
            return
        
        step_config = step.get('config', {})
        if config is None:
            config = {}
        
        logger.info(f"­ƒÄ¼ Executando step tipo '{step_type}' com config: {step_config}")
        
        # Ô£à TRATAMENTO DE ERRO: Try/except para cada tipo de step
        try:
            if step_type == 'content':
                # Ô£à Processar bot├Áes (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                message_text = self._personalize_text(step_config.get('message', ''), bot_id, chat_id)
                media_url = step_config.get('media_url')
                media_type = step_config.get('media_type', 'video')
                
                logger.info(f"­ƒôñ Enviando step 'content': mensagem_len={len(message_text) if message_text else 0}, media_url={bool(media_url)}, media_type={media_type}, buttons={len(buttons)}")
                
                # ­ƒöÑ V8 ULTRA: Verificar se step tem conte├║do antes de enviar
                if not message_text and not media_url:
                    logger.error(f"ÔØî Step 'content' n├úo tem mensagem nem m├¡dia configurada! step_id={step.get('id')}")
                    # Enviar mensagem de aviso ao usu├írio
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="ÔÜá´©Å Esta etapa n├úo tem conte├║do configurado. Entre em contato com o suporte.",
                        bot_id=bot_id,
                        save_message=True
                    )
                    return  # N├úo continuar se n├úo tem conte├║do
                
                result = self.send_funnel_step_sequential(
                    token=token,
                    chat_id=str(chat_id),
                    text=message_text or '',  # Garantir string vazia se None
                    media_url=media_url,
                    media_type=media_type,
                    buttons=buttons,
                    delay_between=delay,
                    bot_id=bot_id
                )
                
                if result:
                    logger.info(f"Ô£à Step 'content' enviado com sucesso: resultado={result}")
                else:
                    logger.error(f"ÔØî Falha ao enviar step 'content': resultado={result}")
            elif step_type == 'message':
                # Ô£à Processar bot├Áes (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                message_text = self._personalize_text(step_config.get('message', ''), bot_id, chat_id)
                if not message_text or not message_text.strip():
                    logger.error(f"ÔØî Step 'message' n├úo tem mensagem configurada! step_id={step.get('id')}")
                    # Enviar mensagem de aviso ao usu├írio
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="ÔÜá´©Å Esta etapa n├úo tem mensagem configurada. Entre em contato com o suporte.",
                        bot_id=bot_id,
                        save_message=True
                    )
                    return  # N├úo continuar se n├úo tem mensagem
                
                logger.info(f"­ƒôñ Enviando step 'message' com mensagem: {message_text[:50]}...")
                logger.info(f"­ƒôñ Bot├Áes: {len(buttons)} bot├Áes configurados")
                
                result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message_text,
                    buttons=buttons if buttons else None,
                    bot_id=bot_id,
                    save_message=True
                )
                
                if result:
                    logger.info(f"Ô£à Step 'message' enviado com sucesso: resultado={result}")
                else:
                    logger.error(f"ÔØî Falha ao enviar step 'message': resultado={result}")
            elif step_type == 'audio':
                # Ô£à Processar bot├Áes (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message='',
                    media_url=step_config.get('audio_url'),
                    media_type='audio',
                    buttons=buttons if buttons else None,
                    bot_id=bot_id,
                    save_message=True
                )
            elif step_type == 'video':
                # Ô£à Processar bot├Áes (customizados + cadastrados)
                buttons = self._build_step_buttons(step, config)
                
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=self._personalize_text(step_config.get('message', ''), bot_id, chat_id),
                    media_url=step_config.get('media_url'),
                    media_type='video',
                    buttons=buttons,
                    bot_id=bot_id,
                    save_message=True
                )
            elif step_type == 'buttons':
                # Ô£à NOVO: Verificar se usa bot├Áes contextuais ou globais
                use_custom_buttons = step_config.get('use_custom_buttons', False)
                buttons = []
                
                if use_custom_buttons:
                    # Ô£à Bot├Áes contextuais (espec├¡ficos do step)
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
                            logger.info(f"­ƒöÿ Bot├úo contextual criado: '{btn_text}' ÔåÆ {target_step} (callback: {callback_data})")
                else:
                    # Ô£à Bot├Áes globais (comportamento antigo)
                    selected_buttons = step_config.get('selected_buttons', [])
                    
                    # Buscar bot├Áes do config completo (main_buttons e redirect_buttons)
                    main_buttons = config.get('main_buttons', []) if config else []
                    redirect_buttons = config.get('redirect_buttons', []) if config else []
                    
                    # Construir lista de bot├Áes baseada nos selecionados
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
                        message=step_config.get('message', 'Ô¼ç´©Å Escolha uma op├º├úo'),
                        buttons=buttons
                    )

            elif step_type == 'condition':
                conditions = step.get('conditions', [])
                if not conditions:
                    logger.warning(f"ÔÜá´©Å Step condition sem conditions[]: {step.get('id')}")
                    return

                condition = conditions[0]
                ctype = condition.get('condition_type', 'payment_status')

                if ctype in ('payment_status', 'time_elapsed'):
                    context = {}
                    if ctype == 'payment_status':
                        from internal_logic.core.models import Payment
                        last_payment = Payment.query.filter_by(
                            bot_id=bot_id,
                            customer_user_id=str(telegram_user_id)
                        ).order_by(Payment.created_at.desc()).first()
                        if last_payment:
                            context = {'payment_status': last_payment.status}

                    next_step_id = self._evaluate_conditions(
                        step, user_input=None, context=context,
                        bot_id=bot_id, telegram_user_id=telegram_user_id,
                        step_id=step.get('id')
                    )
                    if next_step_id:
                        self._execute_flow_recursive(
                            bot_id, token, config, chat_id,
                            telegram_user_id, next_step_id
                        )
                    else:
                        fallback = condition.get('fallback_step')
                        if fallback:
                            self._execute_flow_recursive(
                                bot_id, token, config, chat_id,
                                telegram_user_id, fallback
                            )
                    step['conditions'] = []
                    return

                elif ctype in ('text_validation', 'button_click'):
                    self._save_current_step_atomic(bot_id, telegram_user_id, step.get('id'))
                    msg = step.get('config', {}).get('message', '')
                    if msg:
                        self.send_telegram_message(
                            token=token, chat_id=str(chat_id),
                            message=msg, bot_id=bot_id
                        )
                    return

            elif step_type == 'redirect':
                step_config = step.get('config', {})
                msg = step_config.get('message', '')
                btn_text = step_config.get('button_text', 'Acessar')
                url = step_config.get('redirect_url', '')

                if msg:
                    self.send_telegram_message(
                        token=token, chat_id=str(chat_id),
                        message=msg, bot_id=bot_id
                    )

                if url:
                    buttons = [{'text': btn_text, 'url': url}]
                    self.send_telegram_message(
                        token=token, chat_id=str(chat_id),
                        message='', buttons=buttons, bot_id=bot_id
                    )
                return

            elif step_type in ('downsell', 'upsell'):
                step_config = step.get('config', {})
                mode = step_type

                from internal_logic.core.models import Payment
                last_payment = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=str(telegram_user_id)
                ).order_by(Payment.created_at.desc()).first()

                if not last_payment:
                    logger.warning(f"ÔÜá´©Å {mode} sem pagamento: bot={bot_id}, user={telegram_user_id}")
                    return

                offer_config = {
                    'message': step_config.get('message', ''),
                    'media_url': step_config.get('media_url', ''),
                    'media_type': step_config.get('media_type', 'video'),
                    'audio_enabled': step_config.get('audio_enabled', False),
                    'audio_url': step_config.get('audio_url', ''),
                    'pricing_mode': step_config.get('pricing_mode', 'fixed'),
                    'price': step_config.get('price', 0),
                    'discount_percentage': step_config.get('discount_percentage', 50),
                    'product_name': step_config.get('product_name', ''),
                    'button_text': step_config.get('button_text', ''),
                    'subscription': step_config.get('subscription', {}),
                    'trigger_product': step_config.get('trigger_product', ''),
                    'delay_minutes': step_config.get('delay_minutes', 5),
                }

                try:
                    from internal_logic.services.offer_sender import schedule_offers
                    from tasks_async import marathon_queue
                    schedule_offers(
                        mode=mode,
                        marathon_queue=marathon_queue,
                        bot_id=bot_id,
                        payment_id=str(last_payment.payment_id),
                        chat_id=chat_id,
                        offers=[offer_config],
                        original_price=float(last_payment.amount or 0),
                        user_id=self.user_id
                    )
                    logger.info(f"Ô£à {mode} agendado: payment_id={last_payment.payment_id}")
                except Exception as e:
                    logger.error(f"ÔØî Erro ao agendar {mode}: {e}")
                return

            elif step_type == 'settings':
                logger.info(f"ÔÜÖ´©Å Step settings: processado pelo frontend (syncToConfig)")
                return

            # Delay antes do pr├│ximo step
            if delay > 0:
                time.sleep(delay)
        
        except Exception as e:
            logger.error(f"ÔØî Erro ao executar step tipo '{step_type}': {e}", exc_info=True)
            # Ô£à FALLBACK: Enviar mensagem de erro gen├®rica
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="ÔÜá´©Å Erro ao processar esta etapa. Tente novamente."
                )
            except:
                pass
            raise  # Re-raise para caller decidir o que fazer
        
        # Delay antes do pr├│ximo step
        if delay > 0:
            time.sleep(delay)
    
    def _save_current_step_atomic(self, bot_id: int, telegram_user_id: str, step_id: str, ttl: int = 7200) -> bool:
        """
        # Ô£à QI 500: Salva step atual com lock at├┤mico (evita race conditions)
        
        # Ô£à NOVO: TTL aumentado para 2 horas (evita perda de estado em sess├Áes longas)
        # Ô£à NOVO: Timeout em opera├º├Áes Redis
        
        Returns:
            bool: True se salvou com sucesso, False se falhou
        """
        try:
            import time
            redis_conn = get_redis_connection()
            if not redis_conn:
                logger.warning("ÔÜá´©Å Redis n├úo dispon├¡vel - usando fallback")
                return False
            
            # Ô£à VALIDA├ç├âO: Sanitizar telegram_user_id
            if not telegram_user_id or not isinstance(telegram_user_id, str) or not telegram_user_id.strip():
                logger.error(f"ÔØî telegram_user_id inv├ílido: {telegram_user_id}")
                return False
            
            telegram_user_id = telegram_user_id.strip()
            
            lock_key = f"lock:flow_step:{bot_id}:{telegram_user_id}"
            step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
            
            # Ô£à NOVO: Timeout de 2 segundos para opera├º├Áes Redis
            try:
                # Tentar adquirir lock (expira em 5 segundos)
                lock_acquired = redis_conn.set(lock_key, "1", ex=5, nx=True)
            except Exception as e:
                logger.warning(f"ÔÜá´©Å Erro ao adquirir lock (timeout?): {e}")
                return False
            
            if not lock_acquired:
                logger.warning(f"Ôøö Lock j├í adquirido para {step_key} - aguardando...")
                # Aguardar at├® 2 segundos para lock ser liberado
                for _ in range(20):  # 20 tentativas de 0.1s = 2s total
                    time.sleep(0.1)
                    try:
                        if redis_conn.set(lock_key, "1", ex=5, nx=True):
                            lock_acquired = True
                            break
                    except:
                        pass
                
                if not lock_acquired:
                    logger.error(f"ÔØî N├úo foi poss├¡vel adquirir lock ap├│s 2s - abortando")
                    return False
            
            try:
                # Ô£à NOVO: TTL aumentado para 2 horas (7200 segundos)
                redis_conn.set(step_key, step_id, ex=ttl)
                
                # Ô£à NOVO: Salvar timestamp para time_elapsed (per-step key)
                timestamp_key = f"flow_step_timestamp:{bot_id}:{telegram_user_id}:{step_id}"
                try:
                    redis_conn.set(timestamp_key, int(time.time()), ex=ttl)
                    logger.debug(f"ÔÅ▒´©Å Timestamp salvo para time_elapsed: {timestamp_key}")
                except Exception as e:
                    logger.warning(f"ÔÜá´©Å Erro ao salvar timestamp (n├úo cr├¡tico): {e}")
                
                logger.info(f"Ô£à Step atual salvo atomicamente: {step_id} (TTL: {ttl}s)")
                return True
            except Exception as e:
                logger.error(f"ÔØî Erro ao salvar step atual (timeout?): {e}")
                return False
            finally:
                # Sempre liberar lock
                try:
                    redis_conn.delete(lock_key)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"ÔØî Erro ao salvar step atual: {e}", exc_info=True)
            return False
    
    def _get_current_step_atomic(self, bot_id: int, telegram_user_id: str) -> Optional[str]:
        """
        # Ô£à QI 500: Busca step atual com valida├º├úo e timeout
        
        Returns:
            str: step_id ou None se n├úo encontrado
        """
        try:
            redis_conn = get_redis_connection()
            if not redis_conn:
                return None
            
            # Ô£à NOVO: Timeout de 2 segundos para opera├º├Áes Redis
            step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
            try:
                step_id = redis_conn.get(step_key)
            except Exception as e:
                logger.warning(f"ÔÜá´©Å Erro ao buscar step atual (timeout?): {e}")
                return None
            
            if step_id:
                step_id = step_id.decode('utf-8') if isinstance(step_id, bytes) else step_id
                # Validar que step_id n├úo est├í vazio
                if step_id and step_id.strip():
                    return step_id.strip()
            
            return None
        except Exception as e:
            logger.error(f"ÔØî Erro ao buscar step atual: {e}", exc_info=True)
            return None
    
    def _get_flow_snapshot_from_redis(self, bot_id: int, telegram_user_id: str) -> Optional[Dict[str, Any]]:
        """
        # Ô£à QI 500: Busca snapshot de config do Redis
        
        Returns:
            Dict com snapshot ou None se n├úo encontrado
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
                logger.warning(f"ÔÜá´©Å Erro ao buscar snapshot (timeout?): {e}")
                return None
            
            if snapshot_json:
                snapshot_json = snapshot_json.decode('utf-8') if isinstance(snapshot_json, bytes) else snapshot_json
                snapshot = json.loads(snapshot_json)
                logger.info(f"Ô£à Snapshot recuperado do Redis: {snapshot_key}")
                return snapshot
            
            return None
        except Exception as e:
            logger.error(f"ÔØî Erro ao buscar snapshot: {e}", exc_info=True)
            return None
    
    def _execute_flow(self, bot_id: int, token: str, config: Dict[str, Any], 
                      chat_id: int, telegram_user_id: str):
        """
        # Ô£à QI 500: Executa fluxo visual configurado - com snapshot de config
        
        # Ô£à SEGURO: Fallback para welcome_message se fluxo inv├ílido
        # Ô£à H├ìBRIDO: S├¡ncrono at├® payment, ass├¡ncrono ap├│s callback
        # Ô£à INTELIGENTE: Usa flow_start_step_id ou fallback autom├ítico (order=1 ou primeiro step)
        # Ô£à SNAPSHOT: Cria snapshot da config no in├¡cio (evita mudan├ºas durante execu├º├úo)
        """
        try:
            import json
            import time
            
            # Ô£à CR├ìTICO: Parsear flow_steps se for string JSON
            flow_steps_raw = config.get('flow_steps', [])
            flow_steps = []
            
            if flow_steps_raw:
                if isinstance(flow_steps_raw, str):
                    try:
                        flow_steps = json.loads(flow_steps_raw)
                        logger.info(f"Ô£à flow_steps parseado de JSON em _execute_flow: {len(flow_steps)} steps")
                    except Exception as e:
                        logger.error(f"ÔØî Erro ao parsear flow_steps em _execute_flow: {e}")
                        raise ValueError(f"Fluxo inv├ílido (JSON malformado): {e}")
                elif isinstance(flow_steps_raw, list):
                    flow_steps = flow_steps_raw
                else:
                    logger.error(f"ÔØî flow_steps tem tipo inv├ílido em _execute_flow: {type(flow_steps_raw)}")
                    raise ValueError("Fluxo inv├ílido (tipo incorreto)")
            
            if not flow_steps or len(flow_steps) == 0:
                logger.warning("ÔÜá´©Å Fluxo vazio - usando welcome_message")
                raise ValueError("Fluxo vazio")
            
            # Ô£à NOVO: Criar snapshot da config no in├¡cio
            flow_snapshot = {
                'flow_steps': json.dumps(flow_steps),
                'flow_start_step_id': config.get('flow_start_step_id'),
                'flow_enabled': config.get('flow_enabled', False),
                'main_buttons': json.dumps(config.get('main_buttons', [])),
                'redirect_buttons': json.dumps(config.get('redirect_buttons', [])),
                'snapshot_timestamp': int(time.time())
            }
            
            # Ô£à Salvar snapshot no Redis (expira em 24h)
            try:
                redis_conn = get_redis_connection()
                if redis_conn:
                    snapshot_key = f"flow_snapshot:{bot_id}:{telegram_user_id}"
                    redis_conn.set(snapshot_key, json.dumps(flow_snapshot), ex=86400)
                    logger.info(f"Ô£à Snapshot de config salvo: {snapshot_key}")
            except Exception as e:
                logger.warning(f"ÔÜá´©Å Erro ao salvar snapshot: {e} - continuando sem snapshot")
                flow_snapshot = None
            
            # Ô£à IDENTIFICAR STEP INICIAL (QI 500: Prioridade inteligente)
            start_step_id = config.get('flow_start_step_id')
            start_step = None
            
            logger.info(f"­ƒöì Buscando step inicial: flow_start_step_id={start_step_id} (tipo: {type(start_step_id)})")
            logger.info(f"­ƒöì Total de steps no fluxo: {len(flow_steps)}")
            logger.debug(f"IDs dos steps: {[str(s.get('id')) for s in flow_steps if isinstance(s, dict)]}")
            
            if start_step_id:
                # Buscar step espec├¡fico marcado como inicial
                logger.info(f"­ƒöì Tentando encontrar step inicial com ID: {start_step_id}")
                start_step = self._find_step_by_id(flow_steps, start_step_id)
                if start_step:
                    logger.info(f"Ô£à Step inicial encontrado: {start_step_id} (tipo: {start_step.get('type')}, order: {start_step.get('order', 0)})")
                else:
                    logger.warning(f"ÔÜá´©Å Step inicial {start_step_id} n├úo encontrado - usando fallback")
                    logger.warning(f"ÔÜá´©Å IDs dispon├¡veis: {[str(s.get('id')) for s in flow_steps if isinstance(s, dict)]}")
                    start_step_id = None
            
            if not start_step:
                # FALLBACK 1: Buscar step com order=1
                sorted_steps = sorted(flow_steps, key=lambda x: x.get('order', 0))
                for step in sorted_steps:
                    if step.get('order') == 1:
                        start_step = step
                        start_step_id = step.get('id')
                        logger.info(f"­ƒÄ» Usando step com order=1: {start_step_id}")
                        break
                
                # FALLBACK 2: Se n├úo encontrou order=1, usar primeiro step (menor order)
                if not start_step:
                    if sorted_steps:
                        start_step = sorted_steps[0]
                        start_step_id = start_step.get('id')
                        logger.info(f"­ƒÄ» Usando primeiro step (order={start_step.get('order', 0)}): {start_step_id}")
                    else:
                        logger.error(f"ÔØî Nenhum step encontrado no fluxo")
                        raise ValueError("Nenhum step dispon├¡vel")
            
            # Ô£à V8 ULTRA: Prote├º├úo contra loops j├í existe em _execute_flow_recursive via visited_steps
            # N├úo precisa validar ciclos aqui - visited_steps vai detectar e parar loops automaticamente
            
            # Executar recursivamente a partir do step inicial
            logger.info(f"­ƒÜÇ Iniciando fluxo a partir do step inicial: {start_step_id} (tipo: {type(start_step_id)}, order={start_step.get('order', 0)})")
            logger.info(f"­ƒÜÇ Step inicial completo: {start_step}")
            logger.info(f"­ƒÜÇ Step inicial tipo: {start_step.get('type')}")
            logger.info(f"­ƒÜÇ Step inicial config: {start_step.get('config', {})}")
            logger.info(f"­ƒÜÇ Step inicial mensagem: {start_step.get('config', {}).get('message', '')[:100] if start_step.get('config', {}).get('message') else 'VAZIA'}")
            logger.info(f"­ƒÜÇ Chamando _execute_flow_recursive com step_id={start_step_id}")
            
            self._execute_flow_recursive(
                bot_id, token, config, chat_id, telegram_user_id, str(start_step_id),  # Ô£à Garantir string
                recursion_depth=0,
                visited_steps=set(),
                flow_snapshot=flow_snapshot
            )
            
            logger.info(f"Ô£à _execute_flow_recursive conclu├¡do para step {start_step_id}")
            
        except ValueError as e:
            # Erro de valida├º├úo (fluxo vazio, step n├úo encontrado, etc)
            logger.error(f"ÔØî Erro de valida├º├úo ao executar fluxo: {e}", exc_info=True)
            # ­ƒöÑ V8 ULTRA: Enviar mensagem de erro ao usu├írio em vez de apenas fazer raise
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="ÔÜá´©Å Erro na configura├º├úo do fluxo. Entre em contato com o suporte."
                )
            except Exception as e2:
                logger.error(f"ÔØî Erro ao enviar mensagem de erro: {e2}")
            raise  # Re-raise para caller decidir fallback
        except Exception as e:
            logger.error(f"ÔØî Erro ao executar fluxo: {e}", exc_info=True)
            # ­ƒöÑ V8 ULTRA: Enviar mensagem de erro ao usu├írio em vez de apenas fazer raise
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="ÔÜá´©Å Erro ao processar fluxo. Tente novamente ou entre em contato com o suporte."
                )
            except Exception as e2:
                logger.error(f"ÔØî Erro ao enviar mensagem de erro: {e2}")
            raise  # Re-raise para caller decidir fallback
    
    def _execute_flow_recursive(self, bot_id: int, token: str, config: Dict[str, Any],
                                chat_id: int, telegram_user_id: str, step_id: str,
                                recursion_depth: int = 0, visited_steps: set = None,
                                flow_snapshot: Dict[str, Any] = None):
        """
        # Ô£à QI 500: Executa step recursivamente - THREAD-SAFE e ROBUSTO
        
        # Ô£à RECURS├âO LIMITADA: M├íximo 50 steps (prote├º├úo contra loops infinitos)
        # Ô£à DETEC├ç├âO DE LOOPS: Usa visited_steps para detectar ciclos
        # Ô£à SNAPSHOT DE CONFIG: Usa snapshot se dispon├¡vel (evita mudan├ºas durante execu├º├úo)
        
        Args:
            recursion_depth: Profundidade atual (passado como par├ómetro, n├úo atributo)
            visited_steps: Set de steps j├í visitados (detecta loops)
            flow_snapshot: Snapshot da config no in├¡cio do fluxo
        """
        import time
        from flask import current_app
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Payment
        
        if visited_steps is None:
            visited_steps = set()
        
        # Ô£à Prote├º├úo contra loops infinitos
        if recursion_depth >= 50:
            logger.error(f"ÔØî Profundidade m├íxima atingida (50) para step {step_id}")
            self.send_telegram_message(
                token=token,
                chat_id=str(chat_id),
                message="ÔÜá´©Å Fluxo muito longo detectado. Entre em contato com o suporte."
            )
            return
        
        # Ô£à Detectar loops circulares
        if step_id in visited_steps:
            logger.error(f"ÔØî Loop circular detectado: step {step_id} j├í foi visitado")
            logger.error(f"   Steps visitados: {list(visited_steps)}")
            self.send_telegram_message(
                token=token,
                chat_id=str(chat_id),
                message="ÔÜá´©Å Erro no fluxo detectado. Entre em contato com o suporte."
            )
            return
        
        # Adicionar step atual aos visitados
        visited_steps.add(step_id)
        
        try:
            # Ô£à NOVO: Usar snapshot se dispon├¡vel
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
                # Ô£à CR├ìTICO: Parsear flow_steps se necess├írio (pode vir como string JSON)
                flow_steps_raw = config.get('flow_steps', [])
                flow_steps = []
                if flow_steps_raw:
                    if isinstance(flow_steps_raw, str):
                        try:
                            import json
                            flow_steps = json.loads(flow_steps_raw)
                            logger.info(f"Ô£à flow_steps parseado de JSON em _execute_flow_recursive: {len(flow_steps)} steps")
                        except Exception as e:
                            logger.error(f"ÔØî Erro ao parsear flow_steps em _execute_flow_recursive: {e}")
                            flow_steps = []
                    elif isinstance(flow_steps_raw, list):
                        flow_steps = flow_steps_raw
                    else:
                        logger.error(f"ÔØî flow_steps tem tipo inv├ílido em _execute_flow_recursive: {type(flow_steps_raw)}")
                        flow_steps = []
            
            logger.info(f"­ƒöì Buscando step {step_id} em {len(flow_steps)} steps dispon├¡veis")
            logger.debug(f"IDs dos steps dispon├¡veis: {[s.get('id') for s in flow_steps if isinstance(s, dict)]}")
            
            step = self._find_step_by_id(flow_steps, step_id)
            
            if not step:
                logger.error(f"ÔØî Step {step_id} n├úo encontrado no fluxo")
                logger.error(f"ÔØî flow_steps tem {len(flow_steps)} steps")
                logger.error(f"ÔØî Tipos dos steps: {[type(s) for s in flow_steps]}")
                # Ô£à FALLBACK: Tentar encontrar step inicial ou enviar mensagem de erro
                self._handle_missing_step(bot_id, token, config, chat_id, telegram_user_id)
                return
            
            step_type = step.get('type')
            step_config = step.get('config', {})
            delay = step.get('delay_seconds', 0)
            connections = step.get('connections', {})
            
            logger.debug(f"Step encontrado")
            logger.info(f"­ƒÄ» Executando step {step_id} (tipo: {step_type}, ordem: {step.get('order', 0)})")
            logger.debug(f"Config do step")
            logger.debug(f"Connections")
            logger.info(f"­ƒÄ» Mensagem do step: {step_config.get('message', '')[:100] if step_config.get('message') else 'VAZIA'}")
            logger.info(f"­ƒÄ» Media URL: {step_config.get('media_url', 'N├âO CONFIGURADA')}")
            logger.info(f"­ƒÄ» Custom buttons: {len(step_config.get('custom_buttons', []))} bot├Áes")
            logger.info(f"­ƒÄ» Media URL: {step_config.get('media_url', 'N├âO CONFIGURADA')}")
            logger.info(f"­ƒÄ» Custom buttons: {len(step_config.get('custom_buttons', []))} bot├Áes")
            
            # Ô£à Payment para aqui (aguarda callback verify_)
            if step_type == 'payment':
                logger.info(f"­ƒÆ░ Step payment detectado - gerando PIX e parando fluxo")
                
                # Ô£à VALIDA├ç├âO CR├ìTICA: Verificar conex├Áes obrigat├│rias ANTES de gerar PIX
                has_next = bool(connections.get('next'))
                has_pending = bool(connections.get('pending'))
                
                if not has_next and not has_pending:
                    logger.error(f"ÔØî Step payment {step_id} n├úo tem conex├Áes obrigat├│rias (next ou pending)")
                    error_message = "ÔÜá´©Å Erro de configura├º├úo: Step de pagamento sem conex├Áes definidas. Entre em contato com o suporte."
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=error_message
                    )
                    return  # N├úo gerar PIX se n├úo tem conex├Áes
                
                # Validar que conex├Áes apontam para steps existentes
                if has_next:
                    next_step_id = connections.get('next')
                    if not self._find_step_by_id(flow_steps, next_step_id):
                        logger.error(f"ÔØî Step payment {step_id} tem conex├úo 'next' apontando para step inexistente: {next_step_id}")
                        error_message = "ÔÜá´©Å Erro de configura├º├úo: Conex├úo inv├ílida no step de pagamento. Entre em contato com o suporte."
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=error_message
                        )
                        return
                
                if has_pending:
                    pending_step_id = connections.get('pending')
                    if not self._find_step_by_id(flow_steps, pending_step_id):
                        logger.error(f"ÔØî Step payment {step_id} tem conex├úo 'pending' apontando para step inexistente: {pending_step_id}")
                        error_message = "ÔÜá´©Å Erro de configura├º├úo: Conex├úo inv├ílida no step de pagamento. Entre em contato com o suporte."
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=error_message
                        )
                        return
                
                # Ô£à NOVO: Buscar contexto do bot├úo clicado (se dispon├¡vel)
                # Isso ser├í implementado quando rastrearmos bot├úo at├® payment step
                context = visited_steps  # Por enquanto, usar visited_steps como contexto
                button_context = getattr(self, f'_button_context_{bot_id}_{telegram_user_id}', None)
                
                # Buscar dados do bot├úo principal (primeiro main_button) para gerar PIX
                main_buttons = config.get('main_buttons', [])
                amount = 0.0
                description = 'Produto'
                button_index = 0
                
                # Ô£à NOVO: Usar contexto do bot├úo se dispon├¡vel
                if button_context and isinstance(button_context, dict):
                    button_index = button_context.get('button_index')
                    if button_index is not None and button_index < len(main_buttons):
                        selected_button = main_buttons[button_index]
                        amount = float(selected_button.get('price', 0))
                        description = selected_button.get('description', 'Produto') or selected_button.get('text', 'Produto')
                        logger.info(f"­ƒÆ░ Usando bot├úo do contexto: ├¡ndice={button_index}, valor=R$ {amount:.2f}")
                    # Limpar contexto ap├│s usar
                    if hasattr(self, f'_button_context_{bot_id}_{telegram_user_id}'):
                        delattr(self, f'_button_context_{bot_id}_{telegram_user_id}')
                elif main_buttons and len(main_buttons) > 0:
                    # Fallback: primeiro bot├úo
                    first_button = main_buttons[0]
                    amount = float(first_button.get('price', 0))
                    description = first_button.get('description', 'Produto') or first_button.get('text', 'Produto')
                    button_index = 0
                    logger.warning(f"ÔÜá´©Å Usando primeiro bot├úo (contexto n├úo dispon├¡vel)")
                
                # Usar valores do step se especificados (sobrescreve bot├úo)
                if step_config.get('amount'):
                    amount = float(step_config.get('amount'))
                    logger.info(f"­ƒÆ░ Usando valor do step: R$ {amount:.2f}")
                if step_config.get('description'):
                    description = step_config.get('description')
                # ­ƒöÑ FLOW: aliases do bloco canvas (price/product_name)
                elif step_config.get('product_name'):
                    description = step_config.get('product_name')
                if step_config.get('price') and not step_config.get('amount'):
                    amount = float(step_config.get('price'))
                
                # ­ƒöÑ FLOW: assinatura anexada ao pagamento (lida por
                # create_subscription_for_payment via payment.button_config)
                _sub_cfg = step_config.get('subscription') or {}
                button_config = None
                if isinstance(_sub_cfg, dict) and _sub_cfg.get('enabled') and _sub_cfg.get('vip_chat_id'):
                    button_config = {'subscription': {
                        'enabled': True,
                        'duration_type': _sub_cfg.get('duration_type', 'days'),
                        'duration_value': int(_sub_cfg.get('duration_value') or 30),
                        'vip_chat_id': _sub_cfg.get('vip_chat_id'),
                        'vip_group_link': _sub_cfg.get('vip_group_link', ''),
                    }}
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
                    order_bump_value=0.0,
                    button_config=button_config,
                )
                # Ô£à UX FIX: Tratamento Amig├ível de Rate Limit
                if pix_data and pix_data.get('rate_limit'):
                    wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                    self.send_telegram_message(
                        chat_id=chat_id,
                        message=f"ÔÅ│ <b>Aguarde {wait_time_msg}...</b>\n\nVoc├¬ j├í gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                        token=token
                    )
                    return
                
                if pix_data and pix_data.get('pix_code'):
                    # Ô£à NOVO: Salvar flow_step_id atomicamente
                    payment_id = pix_data.get('payment_id')
                    if payment_id:
                        success = self._save_payment_flow_step_id(payment_id, step_id)
                        if not success:
                            logger.error(f"ÔØî Falha ao salvar flow_step_id - fluxo pode n├úo continuar ap├│s pagamento")
                    
                    # Enviar mensagem de PIX
                    payment_message = f"""­ƒÄ» <b>Produto:</b> {description}
­ƒÆ░ <b>Valor:</b> R$ {amount:.2f}

­ƒô▒ <b>PIX Copia e Cola:</b>
<code>{pix_data.get('pix_code')}</code>

<i>­ƒæå Toque no c├│digo acima para copiar</i>

ÔÅ░ <b>V├ílido por:</b> 30 minutos

­ƒÆí <b>Ap├│s pagar, clique no bot├úo abaixo para verificar e receber seu acesso!</b>"""
                    
                    buttons = [{
                        'text': 'Ô£à Verificar Pagamento',
                        'callback_data': f'verify_{pix_data.get("payment_id")}'
                    }]
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                    
                    logger.info(f"Ô£à PIX gerado - fluxo pausado aguardando callback verify_")
                else:
                    logger.error(f"ÔØî Erro ao gerar PIX no fluxo")
                
                return  # Para aqui, aguarda callback
            
            # Ô£à Access finaliza fluxo
            # ­ƒöÑ FLOW V9: Condition ÔÇö roteador
            elif step_type == 'condition':
                cond_list = step.get('conditions') or []
                c0 = cond_list[0] if cond_list else {}
                ctype = c0.get('condition_type', 'payment_status')

                if ctype == 'payment_status':
                    expected = c0.get('status', 'paid')
                    matched = False
                    try:
                        from internal_logic.core.models import Payment
                        last_payment = Payment.query.filter_by(
                            bot_id=bot_id,
                            customer_user_id=str(telegram_user_id)
                        ).order_by(Payment.created_at.desc()).first()
                        matched = bool(last_payment and last_payment.status == expected)
                    except Exception:
                        pass
                    nxt = (c0.get('target_step') or '') if matched else (c0.get('fallback_step') or '')
                    logger.info(f"­ƒöÇ Condition payment_status matched={matched} -> {nxt}")
                    if nxt:
                        snap = None
                        try:
                            snap = self._get_flow_snapshot_from_redis(bot_id, str(chat_id))
                        except Exception:
                            pass
                        self._execute_flow_recursive(bot_id, token, config, chat_id, telegram_user_id, str(nxt), recursion_depth=recursion_depth + 1, visited_steps=visited_steps | {str(step_id)}, flow_snapshot=snap)
                        return
                elif ctype == 'time_elapsed':
                    # ÔÅ▒´©Å TIMER REAL: agenda disparo via native queue
                    _raw_min = c0.get('minutes')
                    required_minutes = int(_raw_min) if _raw_min not in (None, '') else 5
                    _raw_sec = c0.get('seconds')
                    required_seconds = required_minutes * 60 + (int(_raw_sec) if _raw_sec not in (None, '') else 0)
                    nxt = c0.get('target_step') or ''

                    # [DEBUG] Confirma no Telegram que o nó foi atingido
                    try:
                        self.send_telegram_message(token=token, chat_id=str(chat_id),
                            message='[DEBUG] Condicao! Timer={}s Target={}'.format(required_seconds, nxt),
                            bot_id=bot_id)
                    except Exception:
                        pass
                    # Salvar current_step = condition step (timer guard precisa disso)
                    try:
                        redis_conn = get_redis_connection()
                        if redis_conn:
                            k = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                            redis_conn.setex(k, required_seconds + 3600, str(step.get('id')))
                    except Exception:
                        pass
                    try:
                        redis_conn = get_redis_connection()
                        if redis_conn:
                            ts_key = f"flow_step_timestamp:{bot_id}:{telegram_user_id}:{step.get('id')}"
                            import time as _t
                            redis_conn.setex(ts_key, required_seconds + 3600, int(_t.time()))
                    except Exception:
                        pass
                    if nxt:
                        _fired = False
                        try:
                            from tasks_async import marathon_queue, flow_time_elapsed_fire
                            _cfg_json = json.dumps(config, default=str)
                            _job_id = f"gb:timer:{bot_id}:{telegram_user_id}:{str(step.get('id'))}"
                            _job = marathon_queue.enqueue_in(
                                timedelta(seconds=max(1, required_seconds)),
                                flow_time_elapsed_fire,
                                self.user_id, bot_id, token, int(chat_id), str(telegram_user_id),
                                _cfg_json, str(step.get('id')), str(nxt),
                                job_id=_job_id
                            )
                            logger.info(f"[TIMER] job={_job.id} dispara em {required_seconds}s -> {nxt}")
                            _fired = True
                        except Exception as sched_err:
                            logger.error(f"ÔØî Falha ao agendar timer: {sched_err}")
                        if not _fired:
                            # ­ƒöÑ FALLBACK: timer em-thread no pr├│prio processo
                            # (sem depender do servi├ºo rqscheduler na VPS)
                            import threading as _th
                            # ­ƒöÑ FIX 5: current_app pode n├úo existir (chamado via RQ worker)
                            _app = None
                            try:
                                from flask import has_app_context
                                if has_app_context():
                                    from flask import current_app as _ca
                                    _app = _ca._get_current_object()
                            except Exception:
                                _app = None
                            _cfg_json2 = json.dumps(config, default=str)
                            def _fire_inline():
                                import time as _t2
                                _t2.sleep(max(1, required_seconds))
                                try:
                                    if _app is not None:
                                        with _app.app_context():
                                            from tasks_async import flow_time_elapsed_fire
                                            flow_time_elapsed_fire(self.user_id, bot_id, token, int(chat_id), str(telegram_user_id), _cfg_json2, str(step.get('id')), str(nxt))
                                    else:
                                        # Sem contexto Flask (RQ worker): cria app pr├│prio
                                        from internal_logic.core.extensions import create_app as _create
                                        with _create(skip_sync_thread=True).app_context():
                                            from tasks_async import flow_time_elapsed_fire
                                            flow_time_elapsed_fire(self.user_id, bot_id, token, int(chat_id), str(telegram_user_id), _cfg_json2, str(step.get('id')), str(nxt))
                                except Exception as e2:
                                    logger.error(f"[TIMER][thread] falha: {e2}", exc_info=True)
                            _th.Thread(target=_fire_inline, daemon=True).start()
                            logger.info(f"[TIMER][thread] {required_seconds}s -> {nxt}")

                    return  # fluxo pausa; continua├º├úo ├® feita pelo timer
                else:
                    # text_validation / button_click: aguarda resposta do usu├írio
                    try:
                        redis_conn = get_redis_connection()
                        if redis_conn:
                            k = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                            redis_conn.setex(k, 86400, str(step.get('id')))
                    except Exception:
                        pass
                    msg_txt = self._personalize_text(step_config.get('message', ''), bot_id, chat_id)
                    if msg_txt:
                        buttons_c = self._build_step_buttons(step, config)
                        self.send_telegram_message(token=token, chat_id=str(chat_id), message=msg_txt, buttons=buttons_c if buttons_c else None, bot_id=bot_id, save_message=True)
                    return  # resposta do usu├írio cai no avaliador existente (L~1795)

            # ­ƒöÑ FLOW V9: Redirect ÔÇö mensagem com bot├úo de URL (n├úo-terminal)
            elif step_type == 'redirect':
                url_r = step_config.get('redirect_url', '')
                btn_txt = step_config.get('button_text') or 'Acessar'
                msg_txt = self._personalize_text(step_config.get('message', ''), bot_id, chat_id)
                buttons_r = [{'text': btn_txt, 'url': url_r}] if url_r else None
                self.send_telegram_message(token=token, chat_id=str(chat_id), message=msg_txt or '', buttons=buttons_r, bot_id=bot_id, save_message=True)
                nxt_r = (step.get('connections') or {}).get('next')
                if nxt_r:
                    snap = None
                    try:
                        snap = self._get_flow_snapshot_from_redis(bot_id, str(chat_id))
                    except Exception:
                        pass
                    self._execute_flow_recursive(bot_id, token, config, chat_id, telegram_user_id, str(nxt_r), recursion_depth=0, visited_steps=set(), flow_snapshot=snap)
                return


            elif step_type == 'access':
                logger.info(f"Ô£à Step access detectado - finalizando fluxo")
                
                link = step_config.get('link') or config.get('access_link', '')
                message = self._personalize_text(step_config.get('message', 'Acesso liberado!'), bot_id, chat_id)
                
                buttons = []
                if link:
                    buttons.append({
                        'text': 'Ô£à Acessar',
                        'url': link
                    })
                
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    buttons=buttons if buttons else None
                )
                
                return  # Fim do fluxo
            
            # Ô£à Executar step normalmente (content, message, audio, video, buttons)
            else:
                logger.info(f"­ƒÄ¼ Executando step tipo '{step_type}' (id={step_id})")
                logger.info(f"­ƒÄ¼ Config do step: {step_config}")
                logger.info(f"­ƒÄ¼ Mensagem do step: {step_config.get('message', '')[:100] if step_config.get('message') else 'VAZIA'}")
                
                # ­ƒöÑ V8 ULTRA: Verificar se step tem mensagem antes de executar
                if step_type == 'message' and not step_config.get('message'):
                    logger.warning(f"ÔÜá´©Å Step {step_id} tipo 'message' n├úo tem mensagem configurada!")
                    # Enviar mensagem de aviso ao usu├írio
                    try:
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="ÔÜá´©Å Esta etapa n├úo tem mensagem configurada. Entre em contato com o suporte.",
                            bot_id=bot_id,
                            save_message=True
                        )
                    except Exception as e:
                        logger.error(f"ÔØî Erro ao enviar mensagem de aviso: {e}")
                
                # ­ƒöÑ V8 ULTRA: Executar step com tratamento de erro robusto
                try:
                    self._execute_step(step, token, chat_id, delay, config=config, bot_id=bot_id, telegram_user_id=str(telegram_user_id))
                    logger.info(f"Ô£à Step {step_id} executado com sucesso")
                except Exception as e:
                    logger.error(f"ÔØî Erro ao executar step {step_id}: {e}", exc_info=True)
                    # Enviar mensagem de erro ao usu├írio
                    try:
                        self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="ÔÜá´©Å Erro ao processar esta etapa. Tente novamente ou entre em contato com o suporte.",
                            bot_id=bot_id,
                            save_message=True
                        )
                    except Exception as e2:
                        logger.error(f"ÔØî Erro ao enviar mensagem de erro: {e2}")
                    # Continuar para pr├│ximo step mesmo com erro (n├úo quebrar fluxo completo)
                
                # Ô£à NOVO: Priorizar condi├º├Áes sobre conex├Áes diretas
                # Se step tem condi├º├Áes, aguardar input do usu├írio (n├úo continuar automaticamente)
                conditions = step.get('conditions', [])
                # 🔥 CRÍTICO: só pausa para condições que ESPERAM input do usuário.
                # time_elapsed tem timer próprio; payment_status é avaliado imediatamente.
                # Sem este guard, QUALQUER condition[] no step causava pausa indevida
                # e o funil travava no primeiro bloco.
                INPUT_WAITING_TYPES = ('text_validation', 'button_click')
                _needs_input = any(
                    isinstance(c, dict) and c.get('condition_type') in INPUT_WAITING_TYPES
                    for c in conditions if isinstance(c, dict)
                )
                if _needs_input:
                    logger.info(f"ÔÅ©´©Å Step {step_id} tem {len(conditions)} condi├º├úo(├Áes) - aguardando input do usu├írio")
                    # Ô£à NOVO: Salvar step atual com lock at├┤mico (TTL aumentado para 2 horas)
                    success = self._save_current_step_atomic(bot_id, telegram_user_id, step_id, ttl=7200)
                    if not success:
                        logger.error(f"ÔØî Falha ao salvar step atual atomicamente - condi├º├Áes podem n├úo funcionar")
                    # Fluxo pausa aqui - ser├í continuado quando usu├írio enviar mensagem/clicar bot├úo
                    return
                
                # Fallback: usar conex├Áes diretas (comportamento antigo)
                next_step_id = connections.get('next')
                logger.info(f"­ƒöì Verificando conex├Áes: next_step_id={next_step_id}, connections={connections}")
                
                if next_step_id:
                    logger.info(f"Ô×í´©Å Continuando para pr├│ximo step: {next_step_id}")
                    self._execute_flow_recursive(
                        bot_id, token, config, chat_id, telegram_user_id, next_step_id,
                        recursion_depth=recursion_depth + 1,
                        visited_steps=visited_steps.copy(),  # C├│pia para n├úo compartilhar entre branches
                        flow_snapshot=flow_snapshot
                    )
                else:
                    # Sem pr├│ximo step - fim do fluxo
                    logger.info(f"Ô£à Fluxo finalizado - sem pr├│ximo step (step {step_id} n├úo tem conex├úo 'next')")
                    # Ô£à VÔê×: Limpar estado do Redis quando fluxo termina
                    try:
                        redis_conn = get_redis_connection()
                        if redis_conn:
                            current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                            redis_conn.delete(current_step_key)
                            logger.info(f"Ô£à [FLOW VÔê×] Estado do fluxo limpo do Redis (fluxo finalizado)")
                    except Exception as e:
                        logger.warning(f"ÔÜá´©Å [FLOW VÔê×] Erro ao limpar estado do Redis: {e}")
        
        except Exception as e:
            logger.error(f"ÔØî Erro ao executar step {step_id}: {e}", exc_info=True)
            # Ô£à FALLBACK: Enviar mensagem de erro ao usu├írio
            try:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="ÔÜá´©Å Erro ao processar fluxo. Tente novamente ou entre em contato com o suporte."
                )
            except:
                pass
        finally:
            pass  # Estado ├® salvo apenas em pontos intencionais (_save_current_step_atomic, time_elapsed)
    
    def continue_flow_if_active(self, bot, chat_id, telegram_user_id):
        """
        # Ô£à VÔê×: Se o usu├írio estiver no meio do flow, continuar automaticamente.
        
        Args:
            bot: Objeto Bot
            chat_id: ID do chat
            telegram_user_id: ID do usu├írio no Telegram
            
        Returns:
            bool: True se flow foi continuado, False caso contr├írio
        """
        try:
            redis_conn = get_redis_connection()
            if not redis_conn:
                return False
            
            key = f"gb:{self.user_id}:flow_current_step:{bot.id}:{telegram_user_id}"
            step_id = redis_conn.get(key)
            
            if step_id:
                step_id = step_id.decode() if isinstance(step_id, bytes) else step_id
                logger.info(f"­ƒöä [FLOW VÔê×] Continuando fluxo ativo: step={step_id}")
                
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
            logger.error(f"ÔØî [FLOW VÔê×] Erro ao continuar fluxo: {e}", exc_info=True)
            return False
    
    def _handle_missing_step(self, bot_id: int, token: str, config: Dict[str, Any],
                             chat_id: int, telegram_user_id: str):
        """
        # Ô£à QI 500: Fallback quando step n├úo ├® encontrado
        """
        try:
            # Limpar step atual do Redis
            redis_conn = get_redis_connection()
            if redis_conn:
                current_step_key = f"gb:{self.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                redis_conn.delete(current_step_key)
            
            # Tentar reiniciar fluxo do in├¡cio
            flow_enabled = config.get('flow_enabled', False)
            if flow_enabled:
                logger.info(f"­ƒöä Tentando reiniciar fluxo do in├¡cio...")
                self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
            else:
                # Fallback para welcome_message
                logger.info(f"­ƒöä Usando welcome_message como fallback...")
                welcome_message = config.get('welcome_message', 'Ol├í! Bem-vindo!')
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=welcome_message
                )
        except Exception as e:
            logger.error(f"ÔØî Erro no fallback de missing step: {e}", exc_info=True)
    
    def _execute_flow_step_async(self, bot_id: int, token: str, config: Dict[str, Any],
                                  chat_id: int, telegram_user_id: str, step_id: str):
        """
        # Ô£à QI 500: Executa step do fluxo de forma ass├¡ncrona (via RQ)
        
        # Ô£à ASS├ìNCRONO: Pode ser pesado (access pode enviar m├║ltiplas mensagens)
        # Ô£à SNAPSHOT: Busca snapshot do Redis para manter consist├¬ncia
        # Ô£à IDEMPOT├èNCIA: Verifica se step j├í foi executado (evita duplica├º├úo)
        """
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            
            with current_app.app_context():
                # Ô£à NOVO: Buscar snapshot do Redis primeiro (prioridade sobre config atual)
                telegram_user_id_str = str(telegram_user_id) if telegram_user_id else ''
                flow_snapshot = self._get_flow_snapshot_from_redis(bot_id, telegram_user_id_str)
                
                if flow_snapshot:
                    # Usar snapshot se dispon├¡vel
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
                    logger.info(f"Ô£à Usando snapshot de config para step {step_id}")
                else:
                    # Fallback: buscar config atual do banco
                    from internal_logic.core.models import Bot
                    from sqlalchemy.orm import joinedload
                    bot = Bot.query.options(joinedload(Bot.config)).get(bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                        logger.info(f"ÔÜá´©Å Snapshot n├úo encontrado, usando config atual do banco")
                
                # Ô£à NOVO: Idempot├¬ncia - verificar se step j├í foi executado recentemente
                try:
                    redis_conn = get_redis_connection()
                    if redis_conn:
                        execution_key = f"flow_step_executed:{bot_id}:{telegram_user_id_str}:{step_id}"
                        already_executed = redis_conn.get(execution_key)
                        if already_executed:
                            logger.warning(f"Ôøö Step {step_id} j├í foi executado recentemente - pulando (idempot├¬ncia)")
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
                
                logger.info(f"Ô£à Step {step_id} executado com sucesso (ass├¡ncrono)")
        
        except Exception as e:
            logger.error(f"ÔØî Erro ao executar step {step_id} (ass├¡ncrono): {e}", exc_info=True)
    
    def _reset_user_funnel(self, bot_id: int, chat_id: int, telegram_user_id: str, db_session=None):
        """
        # Ô£à QI 500: RESET ABSOLUTO DO FUNIL
        
        Limpa TODOS os estados e sess├Áes do funil:
        - Sess├Áes de order bump (Redis)
        - Cache de rate limiting (mem├│ria)
        - welcome_sent = False (ESSENCIAL - permite novo welcome)
        - last_interaction = agora
        - Qualquer estado relacionado ao funil
        
        Esta fun├º├úo ├® chamada SEMPRE que /start ├® recebido,
        independente de conversa ativa ou hist├│rico.
        """
        try:
            # Ô£à REDIS MIGRATION: Limpar sess├Áes de order bump no Redis
            user_key_orderbump = f"orderbump_{bot_id}_{chat_id}"
            session_key = f"gb:ob_session:{user_key_orderbump}"
            pix_cache_key = f"gb:pix_cache:{user_key_orderbump}"
            
            redis_conn = get_redis_connection()
            deleted_session = redis_conn.delete(session_key)
            deleted_cache = redis_conn.delete(pix_cache_key)
            
            if deleted_session or deleted_cache:
                logger.info(f"­ƒº╣ Sess├úo de order bump limpa no Redis: {user_key_orderbump} (session={deleted_session}, cache={deleted_cache})")
            
            # Limpar cache de rate limiting (Redis)
            try:
                user_key_rate = f"gb:rate_limit:{bot_id}_{telegram_user_id}"
                redis_rl = get_redis_connection()
                if redis_rl and redis_rl.delete(user_key_rate):
                    logger.info(f"­ƒº╣ Rate limit cache limpo (Redis): {user_key_rate}")
            except Exception:
                pass
            
            # Ô£à QI 500: RESET COMPLETO NO BANCO (ESSENCIAL)
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser, get_brazil_time
            
            # Usar sess├úo fornecida ou criar nova
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
                    # Ô£à QI 500: RESET COMPLETO - ESSENCIAL para permitir novo welcome
                    bot_user.welcome_sent = False  # Ô£à ESSENCIAL - sem isso, funil nunca recome├ºa
                    bot_user.welcome_sent_at = None
                    bot_user.last_interaction = get_brazil_time()  # Atualizar ├║ltima intera├º├úo
                    # Usar sess├úo correta
                    current_session = session if session else db.session
                    current_session.commit()
                    logger.info(f"­ƒº╣ Estado do funil resetado no banco: welcome_sent=False, last_interaction=agora")
                else:
                    logger.warning(f"ÔÜá´©Å BotUser n├úo encontrado para reset: bot_id={bot_id}, telegram_user_id={telegram_user_id}")
            
            if in_context:
                # J├í estamos em app_context, fazer reset direto
                do_reset()
            else:
                # Criar novo app_context
                from flask import current_app
                with current_app.app_context():
                    do_reset()
            
            logger.info(f"Ô£à Funil completamente resetado para bot_id={bot_id}, chat_id={chat_id}")
            
        except Exception as e:
            logger.error(f"ÔØî Erro ao resetar funil: {e}")
            import traceback
            traceback.print_exc()
            # N├úo interromper o fluxo se falhar
    
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
        Exibe m├║ltiplos Order Bumps SEQUENCIAIS - VERS├âO REDIS (Multi-Worker)
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_info: Dados do usu├írio
            original_price: Pre├ºo original
            original_description: Descri├º├úo original
            button_index: ├ìndice do bot├úo
            order_bumps: Lista de order bumps habilitados
        """
        try:
            import json as json_lib  # Ô£à Prote├º├úo contra shadowing do m├│dulo json
            
            # Ô£à REDIS MIGRATION: user_key e chave Redis
            user_key = f"orderbump_{bot_id}_{chat_id}"
            redis_key = f"gb:ob_session:{user_key}"
            
            # Ô£à REDIS MIGRATION: Verificar se j├í existe sess├úo
            redis_conn = get_redis_connection()
            existing_session_json = redis_conn.get(redis_key)
            
            if existing_session_json:
                existing_session = json_lib.loads(existing_session_json)
                existing_button = existing_session.get('button_index', 'N/A')
                logger.info(f"­ƒöä Substituindo sess├úo anterior (bot├úo {existing_button}) por nova (bot├úo {button_index})")
                # Redis delete + setex vai substituir
                redis_conn.delete(redis_key)
            
            # Ô£à IMPLEMENTA├ç├âO QI 600+: Copiar tracking do Redis para sess├úo
            session_tracking = None
            try:
                chat_tracking_key = f'tracking:chat:{chat_id}'
                chat_tracking_json = redis_conn.get(chat_tracking_key)
                if chat_tracking_json:
                    session_tracking = json_lib.loads(chat_tracking_json)
                    logger.info(f"­ƒöæ Tracking copiado para sess├úo via tracking:chat:{chat_id}")
                
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
                                logger.info(f"­ƒöæ Tracking copiado via tracking:fbclid:{bot_user.fbclid[:20]}...")
            except Exception as tracking_error:
                logger.warning(f"ÔÜá´©Å Erro ao copiar tracking para sess├úo: {tracking_error}")
            
            # Ô£à REDIS MIGRATION: Criar sess├úo e salvar no Redis
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
            
            # Ô£à REDIS MIGRATION: Persistir no Redis com TTL 10 minutos
            redis_conn.setex(redis_key, 600, json_lib.dumps(session_data))
            logger.info(f"­ƒÆ¥ Sess├úo de order bump salva no Redis: {redis_key} (TTL 10min)")
            
            # Exibir primeiro order bump
            self._show_next_order_bump(bot_id, token, chat_id, user_key)
            
        except Exception as e:
            logger.error(f"ÔØî Erro ao iniciar m├║ltiplos order bumps: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_next_order_bump(self, bot_id: int, token: str, chat_id: int, user_key: str):
        """
        Exibe o pr├│ximo order bump na sequ├¬ncia - MIGRADO PARA REDIS (Multi-Worker)
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_key: Chave da sess├úo do usu├írio
        """
        try:
            import json as json_lib  # Ô£à Prote├º├úo contra shadowing do m├│dulo json
            
            # Ô£à REDIS MIGRATION: Buscar sess├úo do Redis
            redis_key = f"gb:ob_session:{user_key}"
            redis_conn = get_redis_connection()
            session_json = redis_conn.get(redis_key)
            
            if not session_json:
                logger.error(f"ÔØî Sess├úo de order bump n├úo encontrada no Redis: {redis_key}")
                return
            
            session = json_lib.loads(session_json)
            
            # Ô£à VALIDA├ç├âO: Verificar se chat_id corresponde ao chat_id da sess├úo
            session_chat_id = session.get('chat_id')
            if session_chat_id and session_chat_id != chat_id:
                logger.warning(f"ÔÜá´©Å Chat ID mismatch em _show_next_order_bump: recebido {chat_id}, mas sess├úo ├® do chat {session_chat_id}. Usando chat_id da sess├úo.")
                chat_id = session_chat_id  # Ô£à Corrigir chat_id para o da sess├úo
            
            # Ô£à VALIDA├ç├âO: Usar bot_id da sess├úo se dispon├¡vel (garante consist├¬ncia)
            session_bot_id = session.get('bot_id', bot_id)
            if session_bot_id != bot_id:
                logger.warning(f"ÔÜá´©Å Bot ID mismatch em _show_next_order_bump: recebido {bot_id}, mas sess├úo ├® do bot {session_bot_id}. Usando bot_id da sess├úo.")
                # Buscar token correto para o bot da sess├úo
                # Ô£à REDIS BRAIN: Buscar do Redis
                session_bot_data = self.bot_state.get_bot_data(session_bot_id)
                if session_bot_data:
                    token = session_bot_data['token']
                    bot_id = session_bot_id  # Ô£à Corrigir bot_id para o da sess├úo
                else:
                    logger.error(f"ÔØî Bot {session_bot_id} da sess├úo n├úo est├í mais ativo no Redis!")
                    return
            
            current_index = session['current_index']
            order_bumps = session['order_bumps']
            
            if current_index >= len(order_bumps):
                # Todos os order bumps foram exibidos, gerar PIX final
                # Ô£à Usar bot_id e token j├í corrigidos pela valida├º├úo acima
                self._finalize_order_bump_session(bot_id, token, chat_id, user_key)
                return
            
            order_bump = order_bumps[current_index]
            bump_price = float(order_bump.get('price', 0))
            bump_message = order_bump.get('message', '')
            bump_description = order_bump.get('description', 'B├┤nus')
            bump_media_url = order_bump.get('media_url')
            bump_media_type = order_bump.get('media_type', 'video')
            accept_text = order_bump.get('accept_text', '')
            decline_text = order_bump.get('decline_text', '')
            
            # Calcular pre├ºo total atual
            current_total = session['original_price'] + session['total_bump_value']
            total_with_this_bump = current_total + bump_price
            
            logger.info(f"­ƒÄü Exibindo Order Bump {current_index + 1}/{len(order_bumps)}: {bump_description} (+R$ {bump_price:.2f})")
            
            # Usar APENAS a mensagem configurada pelo usu├írio
            order_bump_message = bump_message.strip()
            
            # Textos personalizados ou padr├úo
            accept_button_text = accept_text.strip() if accept_text else f'Ô£à SIM! Quero por R$ {total_with_this_bump:.2f}'
            decline_button_text = decline_text.strip() if decline_text else f'ÔØî N├âO, continuar com R$ {current_total:.2f}'
            
            # Ô£à CORRE├ç├âO: Bot├Áes com callback_data usando apenas chat_id (sem bot_id na chave)
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
            
            logger.info(f"­ƒÄü Order Bump {current_index + 1} - Bot├Áes: {len(buttons)}")
            logger.info(f"  - Aceitar: {accept_button_text}")
            logger.info(f"  - Recusar: {decline_button_text}")
            
            # Verificar se m├¡dia ├® v├ílida
            valid_media = bump_media_url and '/c/' not in bump_media_url and bump_media_url.startswith('http')
            
            # Enviar com ou sem m├¡dia
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
                    # Fallback sem m├¡dia se falhar
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
            
            logger.info(f"Ô£à Order Bump {current_index + 1} exibido!")
            
        except Exception as e:
            logger.error(f"ÔØî Erro ao exibir pr├│ximo order bump: {e}")
            import traceback
            traceback.print_exc()
    
    def _finalize_order_bump_session(self, bot_id: int, token: str, chat_id: int, user_key: str):
        """
        Finaliza a sess├úo de order bumps e gera PIX final
        VERS├âO REDIS: Com idempot├¬ncia multi-worker via Redis
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_key: Chave da sess├úo do usu├írio
        """
        try:
            import time
            import json as json_lib  # Ô£à Prote├º├úo contra shadowing do m├│dulo json
            current_time = time.time()
            
            # Ô£à REDIS MIGRATION: Chaves para sess├úo e cache PIX
            redis_conn = get_redis_connection()
            session_key = f"gb:ob_session:{user_key}"
            pix_cache_key = f"gb:pix_cache:{user_key}"
            
            # Ô£à IDEMPOT├èNCIA: Verificar se PIX j├í foi gerado recentemente (Redis)
            pix_cache_json = redis_conn.get(pix_cache_key)
            if pix_cache_json:
                cached = json_lib.loads(pix_cache_json)
                pix_data = cached.get('pix_data')
                logger.info(f"­ƒöä PIX em cache Redis reutilizado (idempot├¬ncia): {pix_data.get('payment_id')}")
                self._send_pix_message(token, chat_id, pix_data, "­ƒöä Reenviando seu PIX:")
                return  # N├âO gerar novo PIX
            
            # Ô£à LOCK AT├öMICO: Claim gera├º├úo para evitar duplicata entre workers
            pix_claim_key = f"gb:pix_claim:{user_key}"
            claimed = redis_conn.set(pix_claim_key, "1", nx=True, ex=120)
            if not claimed:
                logger.info(f"­ƒöä PIX sendo gerado por outro worker, ignorando")
                return
            
            # Ô£à REDIS MIGRATION: Buscar sess├úo do Redis
            session_json = redis_conn.get(session_key)
            if not session_json:
                logger.error(f"ÔØî Sess├úo de order bump n├úo encontrada no Redis: {session_key}")
                return  # Realmente n├úo temos dados - erro
            
            session = json_lib.loads(session_json)
            
            # Ô£à IDEMPOT├èNCIA: Verificar se sess├úo j├í gerou PIX
            if session.get('status') == 'pix_generated':
                payment_id = session.get('payment_id')
                logger.info(f"­ƒöä Sess├úo j├í gerou PIX anteriormente: {payment_id}")
                # Tentar recuperar do cache (j├í verificado acima, mas double-check)
                pix_cache_json = redis_conn.get(pix_cache_key)
                if pix_cache_json:
                    cached = json_lib.loads(pix_cache_json)
                    self._send_pix_message(token, chat_id, cached['pix_data'], "­ƒöä Reenviando seu PIX:")
                    return
            
            # Ô£à VALIDA├ç├âO: Verificar se chat_id corresponde ao chat_id da sess├úo
            session_chat_id = session.get('chat_id')
            if session_chat_id and session_chat_id != chat_id:
                logger.warning(f"ÔÜá´©Å Chat ID mismatch em _finalize_order_bump_session: recebido {chat_id}, mas sess├úo ├® do chat {session_chat_id}. Usando chat_id da sess├úo.")
                chat_id = session_chat_id  # Ô£à Corrigir chat_id para o da sess├úo
            
            # Ô£à VALIDA├ç├âO: Usar bot_id da sess├úo se dispon├¡vel (garante consist├¬ncia)
            session_bot_id = session.get('bot_id', bot_id)
            if session_bot_id != bot_id:
                logger.warning(f"ÔÜá´©Å Bot ID mismatch em _finalize_order_bump_session: recebido {bot_id}, mas sess├úo ├® do bot {session_bot_id}. Usando bot_id da sess├úo.")
                session_bot_data = self.bot_state.get_bot_data(session_bot_id)
                if session_bot_data:
                    token = session_bot_data['token']
                    bot_id = session_bot_id
                else:
                    logger.error(f"ÔØî Bot {session_bot_id} da sess├úo n├úo est├í mais ativo no Redis!")
                    return
            
            original_price = session['original_price']
            original_description = session['original_description']
            button_index = session['button_index']
            accepted_bumps = session['accepted_bumps']
            total_bump_value = session['total_bump_value']
            
            final_price = original_price + total_bump_value
            
            logger.info(f"­ƒÄü Finalizando sess├úo - Pre├ºo original: R$ {original_price:.2f}, Bumps aceitos: {len(accepted_bumps)}, Valor total: R$ {final_price:.2f}")
            
            # Buscar config do bot
            from internal_logic.core.models import Bot, BotUser
            from flask import current_app
            from internal_logic.core.extensions import db
            
            bot_config = None
            with current_app.app_context():
                from sqlalchemy.orm import joinedload
                bot_model = Bot.query.options(joinedload(Bot.config)).get(bot_id)
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
                description=f"{original_description} + {len(accepted_bumps)} b├┤nus" if accepted_bumps else original_description,
                customer_name=customer_name,
                customer_username=customer_username,
                customer_user_id=str(chat_id),
                order_bump_shown=True,
                order_bump_accepted=len(accepted_bumps) > 0,
                order_bump_value=total_bump_value
            )
            
            # Ô£à UX FIX: Tratamento Amig├ível de Rate Limit
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                self.send_telegram_message(
                    chat_id=chat_id,
                    message=f"ÔÅ│ <b>Aguarde {wait_time_msg}...</b>\n\nVoc├¬ j├í gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                    token=token
                )
                return
            
            if pix_data and pix_data.get('pix_code'):
                # Criar descri├º├úo detalhada
                bump_descriptions = [bump.get('description', 'B├┤nus') for bump in accepted_bumps]
                description_text = f"{original_description}"
                if bump_descriptions:
                    description_text += f" + {', '.join(bump_descriptions)}"
                
                # Adicionar amount ao pix_data para cache completo
                pix_data['amount'] = final_price
                pix_data['description'] = description_text
                
                self._send_pix_message(token, chat_id, pix_data, "­ƒÄü Seu PIX com b├┤nus:")
                
                logger.info(f"Ô£à PIX FINAL COM {len(accepted_bumps)} ORDER BUMPS ENVIADO! ID: {pix_data.get('payment_id')}")
                
                # Ô£à REDIS MIGRATION: Salvar no cache PIX com TTL 5 minutos
                if pix_data.get('payment_id'):
                    cache_data = {
                        'pix_data': pix_data,
                        'timestamp': current_time,
                        'payment_id': pix_data.get('payment_id')
                    }
                    redis_conn.setex(pix_cache_key, 300, json_lib.dumps(cache_data))
                    logger.info(f"­ƒÆ¥ PIX salvo no cache Redis: {pix_cache_key} (TTL 5min)")
                
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
                        logger.error(f"ÔØî Erro ao agendar downsells: {e}", exc_info=True)
            else:
                self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="ÔØî Erro ao gerar PIX. Entre em contato com o suporte."
                )
            
            # Ô£à REDIS MIGRATION: Atualizar sess├úo com status 'pix_generated'
            session['status'] = 'pix_generated'
            session['pix_generated_at'] = current_time
            session['payment_id'] = pix_data.get('payment_id') if pix_data else None
            # Ô£à Atualizar no Redis com TTL renovado de 10 minutos
            redis_conn.setex(session_key, 600, json_lib.dumps(session))
            logger.info(f"­ƒöä Sess├úo marcada como 'pix_generated' no Redis: {session_key}")
            
        except Exception as e:
            logger.error(f"ÔØî Erro ao finalizar sess├úo de order bumps: {e}")
            import traceback
            traceback.print_exc()
    
    def _send_pix_message(self, token: str, chat_id: int, pix_data: dict, header_msg: str):
        """
        Envia mensagem de PIX de forma idempotente.
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            pix_data: Dados do PIX (pix_code, payment_id, amount, description)
            header_msg: Mensagem de cabe├ºalho
        """
        try:
            if not pix_data or not pix_data.get('pix_code'):
                logger.error(f"ÔØî _send_pix_message chamado sem pix_code v├ílido")
                return False
            
            pix_code = pix_data.get('pix_code', '')
            payment_id = pix_data.get('payment_id', '')
            amount = pix_data.get('amount', 0)
            description = pix_data.get('description', 'Produto')
            
            payment_message = f"""{header_msg}

­ƒÄ» <b>Produto:</b> {description}
­ƒÆ░ <b>Valor:</b> R$ {amount:.2f}

­ƒô▒ <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>­ƒæå Toque no c├│digo acima para copiar</i>

ÔÅ░ <b>V├ílido por:</b> 30 minutos

­ƒÆí <b>Ap├│s pagar, clique no bot├úo abaixo!</b>"""
            
            buttons = [{
                'text': 'Ô£à Verificar Pagamento',
                'callback_data': f'verify_{payment_id}'
            }]
            
            result = self.send_telegram_message(
                token=token,
                chat_id=str(chat_id),
                message=payment_message.strip(),
                buttons=buttons
            )
            
            if result:
                logger.info(f"Ô£à Mensagem PIX enviada (idempotente): payment_id={payment_id}")
            else:
                logger.warning(f"ÔÜá´©Å Falha ao enviar mensagem PIX: payment_id={payment_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"ÔØî Erro em _send_pix_message: {e}")
            return False
    
    def _show_downsell_order_bump(self, bot_id: int, token: str, chat_id: int, user_info: Dict[str, Any],
                                 downsell_price: float, downsell_description: str, downsell_index: int,
                                 order_bump: Dict[str, Any]):
        """
        Exibe Order Bump PERSONALIZADO para DOWSELL com M├ìDIA e BOT├òES CUSTOMIZ├üVEIS
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_info: Dados do usu├írio
            downsell_price: Pre├ºo do downsell
            downsell_description: Descri├º├úo do downsell
            downsell_index: ├ìndice do downsell
            order_bump: Dados completos do order bump
        """
        try:
            bump_message = order_bump.get('message', '')
            
            # Ô£à FIX S├èNIOR: Blindagem contra valores nulos e strings vazias no banco de dados
            raw_price = order_bump.get('price')
            try:
                if raw_price is None or str(raw_price).strip() == '':
                    bump_price = 0.0
                else:
                    bump_price = float(raw_price)
            except (ValueError, TypeError):
                logger.warning(f"ÔÜá´©Å Valor de Order Bump inv├ílido detectado ('{raw_price}'). Assumindo 0.0 para n├úo interromper a venda.")
                bump_price = 0.0
                
            bump_description = order_bump.get('description', 'B├┤nus')
            bump_media_url = order_bump.get('media_url')
            bump_media_type = order_bump.get('media_type', 'video')
            accept_text = order_bump.get('accept_text', '')
            decline_text = order_bump.get('decline_text', '')
            total_price = downsell_price + bump_price
            
            logger.info(f"­ƒÄü Exibindo Order Bump para Downsell: {bump_description} (+R$ {bump_price:.2f})")
            
            # Usar APENAS a mensagem configurada pelo usu├írio
            order_bump_message = bump_message.strip()
            
            # Textos personalizados ou padr├úo
            accept_button_text = accept_text.strip() if accept_text else f'Ô£à SIM! Quero por R$ {total_price:.2f}'
            decline_button_text = decline_text.strip() if decline_text else f'ÔØî N├âO, continuar com R$ {downsell_price:.2f}'
            
            # Bot├Áes com callback_data espec├¡fico para downsell
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
            
            logger.info(f"­ƒÄü Order Bump Downsell - Bot├Áes: {len(buttons)}")
            logger.info(f"  - Aceitar: {accept_button_text}")
            logger.info(f"  - Recusar: {decline_button_text}")
            
            # Verificar se m├¡dia ├® v├ílida
            valid_media = bump_media_url and '/c/' not in bump_media_url and bump_media_url.startswith('http')
            
            # Enviar com ou sem m├¡dia
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
                    # Fallback sem m├¡dia se falhar
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
            
            logger.info(f"Ô£à Order Bump Downsell exibido!")
            
        except Exception as e:
            logger.error(f"ÔØî Erro ao exibir Order Bump Downsell: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_order_bump(self, bot_id: int, token: str, chat_id: int, user_info: Dict[str, Any],
                        original_price: float, original_description: str, button_index: int,
                        order_bump: Dict[str, Any]):
        """
        Exibe Order Bump PERSONALIZADO com M├ìDIA e BOT├òES CUSTOMIZ├üVEIS
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            user_info: Dados do usu├írio
            original_price: Pre├ºo original
            original_description: Descri├º├úo original
            button_index: ├ìndice do bot├úo
            order_bump: Dados completos do order bump
        """
        try:
            bump_message = order_bump.get('message', '')
            
            # Ô£à FIX S├èNIOR: Blindagem contra valores nulos e strings vazias no banco de dados
            raw_price = order_bump.get('price')
            try:
                if raw_price is None or str(raw_price).strip() == '':
                    bump_price = 0.0
                else:
                    bump_price = float(raw_price)
            except (ValueError, TypeError):
                logger.warning(f"ÔÜá´©Å Valor de Order Bump inv├ílido detectado ('{raw_price}'). Assumindo 0.0 para n├úo interromper a venda.")
                bump_price = 0.0
                
            bump_description = order_bump.get('description', 'B├┤nus')
            bump_media_url = order_bump.get('media_url')
            bump_media_type = order_bump.get('media_type', 'video')
            bump_audio_enabled = order_bump.get('audio_enabled', False)
            bump_audio_url = order_bump.get('audio_url', '')
            accept_text = order_bump.get('accept_text', '')
            decline_text = order_bump.get('decline_text', '')
            total_price = original_price + bump_price
            
            logger.info(f"­ƒÄü Exibindo Order Bump: {bump_description} (+R$ {bump_price:.2f})")
            
            # Usar APENAS a mensagem configurada pelo usu├írio
            order_bump_message = bump_message.strip()
            
            # Textos personalizados ou padr├úo
            accept_button_text = accept_text.strip() if accept_text else f'Ô£à SIM! Quero por R$ {total_price:.2f}'
            decline_button_text = decline_text.strip() if decline_text else f'ÔØî N├âO, continuar com R$ {original_price:.2f}'
            
            buttons = [
                {
                    'text': accept_button_text,
                    'callback_data': f'bump_yes_{button_index}'  # Ô£à CORRE├ç├âO: Apenas ├¡ndice (< 15 bytes)
                },
                {
                    'text': decline_button_text,
                    'callback_data': f'bump_no_{button_index}'  # Ô£à CORRE├ç├âO: Apenas ├¡ndice (< 15 bytes)
                }
            ]
            
            # Verificar se m├¡dia ├® v├ílida
            valid_media = False
            if bump_media_url and '/c/' not in bump_media_url and bump_media_url.startswith('http'):
                valid_media = True
            
            # Enviar com ou sem m├¡dia
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
                    # Fallback sem m├¡dia se falhar
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
            
            logger.info(f"Ô£à Order Bump exibido!")
            
            # Ô£à Enviar ├íudio adicional se habilitado
            if bump_audio_enabled and bump_audio_url:
                logger.info(f"­ƒÄñ Enviando ├íudio complementar do Order Bump...")
                audio_result = self.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="",
                    media_url=bump_audio_url,
                    media_type='audio',
                    buttons=None
                )
                if audio_result:
                    logger.info(f"Ô£à ├üudio complementar do Order Bump enviado")
            
        except Exception as e:
            logger.error(f"ÔØî Erro ao exibir order bump: {e}")
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
        Envia arquivo (foto/v├¡deo) pelo Telegram usando multipart/form-data
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            file_path: Caminho local do arquivo
            message: Mensagem de texto (caption)
            media_type: Tipo da m├¡dia ('photo', 'video', 'document')
            buttons: Lista de bot├Áes inline
        
        Returns:
            dict com resultado da API ou False se falhar
        """
        try:
            base_url = f"https://api.telegram.org/bot{token}"

            # Ô£à Robustez: normalizar media_type (evita 'VIDEO'/'Video'/None quebrando envio de m├¡dia)
            if file_path and (media_type is None or (isinstance(media_type, str) and not media_type.strip())):
                media_type = 'video'
            if isinstance(media_type, str):
                media_type = media_type.strip().lower()
            
            # Preparar teclado inline se houver bot├Áes
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
            else:  # photo (padr├úo)
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
                    logger.info(f"Ô£à Arquivo {media_type} enviado para chat {chat_id}")
                    
                    # Ô£à CHAT: Salvar mensagem enviada pelo bot no banco
                    try:
                        from flask import current_app
                        from internal_logic.core.extensions import db
                        from internal_logic.core.models import BotUser, BotMessage, Bot
                        import json as json_lib
                        import uuid as uuid_lib
                        
                        with current_app.app_context():
                            # Ô£à REDIS BRAIN: Buscar bot pelo token
                            # Como n├úo temos ├¡ndice reverso no Redis, buscar direto no banco
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
                                    
                                    # Obter file_id do Telegram (para reutiliza├º├úo futura)
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
                                    logger.debug(f"Ô£à Arquivo {media_type} enviado salvo no banco")
                                else:
                                    logger.debug(f"ÔÜá´©Å BotUser n├úo encontrado para salvar arquivo enviado")
                            else:
                                logger.debug(f"ÔÜá´©Å Bot n├úo encontrado pelo token para salvar arquivo enviado")
                    except Exception as e:
                        logger.error(f"ÔØî Erro ao salvar arquivo enviado no banco: {e}")
                    
                    return result_data
                else:
                    logger.error(f"ÔØî Telegram API retornou erro: {result_data.get('description', 'Erro desconhecido')}")
                    return False
            else:
                logger.error(f"ÔØî Erro ao enviar arquivo: {response.text}")
                return False
                
        except FileNotFoundError:
            logger.error(f"ÔØî Arquivo n├úo encontrado: {file_path}")
            return False
        except requests.exceptions.Timeout:
            logger.error(f"ÔÅ▒´©Å Timeout ao enviar arquivo para chat {chat_id}")
            return False
        except Exception as e:
            logger.error(f"ÔØî Erro ao enviar arquivo Telegram: {e}", exc_info=True)
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
        - USER_FATAL: Erro do usu├írio (n├úo punir bot)
        - BOT_FATAL: Erro do bot (desativar imediatamente)
        - RETRYABLE: Erro transit├│rio (tentar novamente)
        
        Args:
            error_str: String do erro em lowercase
            
        Returns:
            'USER_FATAL', 'BOT_FATAL', ou 'RETRYABLE'
        """
        error_lower = error_str.lower()
        
        # Verificar BOT_FATAL primeiro (prioridade m├íxima)
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
        
        # Por padr├úo, considerar RETRYABLE (fail-safe)
        return 'RETRYABLE'

    def _apply_circuit_breaker(self, token: str, error_bucket: str, error_description: str):
        """
        ­ƒö┤ DESATIVADO: Circuit Breaker removido (colunas n├úo existem no banco legado)
        
        Mantido para compatibilidade - apenas loga, n├úo modifica banco.
        """
        # Ô£à COLUNAS REMOVIDAS: health_status, circuit_breaker_until, 
        # error_count, consecutive_failures, last_health_check
        # Usar apenas logging, sem writes no banco
        if error_bucket == 'BOT_FATAL':
            logger.critical(f"­ƒö┤ BOT_FATAL detectado: {error_description[:200]}")
        elif error_bucket == 'RETRYABLE':
            logger.warning(f"ÔÜá´©Å RETRYABLE detectado: {error_description[:200]}")
        # N├âO faz nenhuma opera├º├úo no banco - colunas n├úo existem
        return

    def _reset_circuit_breaker_on_success(self, token: str):
        """
        ­ƒö┤ DESATIVADO: Circuit Breaker reset removido (colunas n├úo existem no banco legado)
        
        Mantido para compatibilidade - apenas loga, n├úo modifica banco.
        """
        # Ô£à COLUNAS REMOVIDAS: consecutive_failures, health_status, circuit_breaker_until, last_health_check
        # N├úo faz nada - as colunas n├úo existem no banco legado
        return 

    def _save_outgoing_message(self, bot_id: int, chat_id: str, message_text: str = None,
                                message_type: str = 'text', media_url: str = None,
                                message_id: str = None):
        """Salva registro de mensagem outgoing no banco para aparecer no chat"""
        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser, BotMessage
            import uuid

            with current_app.app_context():
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=str(chat_id),
                    archived=False
                ).first()
                if not bot_user:
                    return

                msg_id = message_id or str(uuid.uuid4().hex)
                bot_message = BotMessage(
                    bot_id=bot_id,
                    bot_user_id=bot_user.id,
                    telegram_user_id=str(chat_id),
                    message_id=msg_id,
                    message_text=message_text,
                    message_type=message_type,
                    direction='outgoing',
                    media_url=media_url,
                    is_read=True,
                )
                db.session.add(bot_message)
                db.session.commit()
        except Exception as e:
            logger.error(f"ÔØî Erro ao salvar mensagem outgoing: {e}")

    def send_telegram_message(self, token: str, chat_id: str, message: str, 
                             media_url: Optional[str] = None, 
                             media_type: str = 'video',
                             audio_url: Optional[str] = None,
                             buttons: Optional[list] = None,
                             bot_id: Optional[int] = None,
                             save_message: bool = False):
        """
        Envia mensagem pelo Telegram (delegado ao BotMessenger)
        
        Args:
            token: Token do bot
            chat_id: ID do chat
            message: Mensagem de texto
            media_url: URL da m├¡dia (opcional)
            media_type: Tipo da m├¡dia (video, photo ou audio)
            audio_url: URL do ├íudio (opcional)
            buttons: Lista de bot├Áes inline
            bot_id: ID do bot (necess├írio se save_message=True)
            save_message: Se True, salva BotMessage no banco
            
        Returns:
            bool: True se enviado com sucesso
        """
        try:
            result = self.messenger.send_message_with_media(
                token=token,
                chat_id=chat_id,
                message=message,
                media_type=media_type,
                media_url=media_url,
                audio_url=audio_url,
                reply_markup=self.messenger.build_keyboard(buttons) if buttons else None
            )

            if result and save_message:
                resolved_bot_id = bot_id
                if not resolved_bot_id:
                    from internal_logic.core.models import Bot
                    bot = Bot.query.filter_by(token=token).first()
                    if bot:
                        resolved_bot_id = bot.id

                if resolved_bot_id:
                    actual_type = media_type if media_url else 'text'
                    self._save_outgoing_message(
                        bot_id=resolved_bot_id,
                        chat_id=chat_id,
                        message_text=message,
                        message_type=actual_type,
                        media_url=media_url,
                    )

            return result
        except Exception as e:
            logger.error(f"ÔØî Erro ao enviar mensagem: {e}")
            if any(x in str(e) for x in ['401', 'Unauthorized', 'bot was kicked', 'bot was blocked']):
                bot_id_to_offline = bot_id
                if not bot_id_to_offline:
                    try:
                        from internal_logic.core.models import Bot as BotModel
                        bot_rec = BotModel.query.filter_by(token=token).first()
                        if bot_rec:
                            bot_id_to_offline = bot_rec.id
                    except Exception:
                        pass
                if bot_id_to_offline:
                    try:
                        from internal_logic.core.models import PoolBot
                        from internal_logic.core.extensions import db
                        PoolBot.query.filter_by(bot_id=bot_id_to_offline).update({
                            'status': 'offline',
                        })
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
            return False
    
    def get_bot_status(self, bot_id: int, verify_telegram: bool = False) -> Dict[str, Any]:
        """
        Obt├®m status de um bot via Redis (├║nica fonte de verdade)
        
        Args:
            bot_id: ID do bot
            verify_telegram: Se True, verifica REALMENTE se bot responde no Telegram
        
        Returns:
            Informa├º├Áes de status
        """
        # Ô£à REDIS BRAIN: Buscar dados do bot no Redis
        bot_info = self.bot_state.get_bot_data(bot_id)
        if not bot_info:
            return {
                'is_running': False,
                'status': 'stopped'
            }
        
        token = bot_info.get('token')
        
        # Ô£à VERIFICA├ç├âO REAL: Se solicitado, verificar se bot responde no Telegram
        if verify_telegram and token:
            try:
                url = f"https://api.telegram.org/bot{token}/getMe"
                with self.messenger.telegram_http_semaphore:
                    response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if not data.get('ok'):
                        # Token inv├ílido ou bot n├úo responde
                        logger.warning(f"ÔÜá´©Å Bot {bot_id} n├úo responde no Telegram (token inv├ílido/bloqueado)")
                        return {
                            'is_running': False,
                            'status': 'offline',
                            'reason': 'telegram_unreachable'
                        }
                else:
                    # Erro de conex├úo
                    logger.warning(f"ÔÜá´©Å Bot {bot_id} n├úo acess├¡vel via Telegram API (status {response.status_code})")
                    return {
                        'is_running': False,
                        'status': 'offline',
                        'reason': 'api_error'
                    }
            except Exception as e:
                logger.warning(f"ÔÜá´©Å Erro ao verificar bot {bot_id} no Telegram: {e}")
                return {
                    'is_running': False,
                    'status': 'offline',
                    'reason': 'verification_failed'
                }
        
        # Bot est├í ativo no Redis e (se verificado) responde no Telegram
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
    # Ô£à SISTEMA DE ASSINATURAS - Ativa├º├úo e Gerenciamento
    # ============================================================================
    
    def _activate_subscription(self, subscription_id: int) -> bool:
        return activate_subscription(subscription_id)
    
    def _handle_new_chat_member(self, bot_id: int, chat_id: int, telegram_user_id: str):
        handle_new_chat_member(bot_id, chat_id, telegram_user_id, activate_func=activate_subscription)
    
    def cancel_downsells(self, payment_id: str):
        cancel_scheduled_downsells(payment_id)
