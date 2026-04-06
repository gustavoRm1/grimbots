"""
📊 TRACKING SERVICE V4.0
Módulo de Rastreamento Meta Pixel / Conversions API (Server-Side)

Extraído de: app.py (linhas 10517-12240)
Responsabilidade: Parameter Builder, external_id normalization, async CAPI events
"""

import hashlib
import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from flask import Request
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)


@dataclass
class ParameterBuilderResult:
    """Resultado do Server-Side Parameter Builder"""
    fbp: Optional[str] = None
    fbc: Optional[str] = None
    client_ip_address: Optional[str] = None
    fbc_origin: Optional[str] = None
    fbp_origin: Optional[str] = None
    ip_origin: Optional[str] = None


@dataclass
class MetaEventData:
    """Dados de um evento Meta Pixel para envio via CAPI"""
    event_name: str
    event_time: int
    event_id: str
    action_source: str = 'website'
    event_source_url: str = ''
    user_data: Dict[str, Any] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrackingData:
    """Dados de tracking salvos no Redis para matching PageView -> Purchase"""
    fbclid: str
    fbp: Optional[str] = None
    fbc: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    grim: Optional[str] = None
    utms: Dict[str, str] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time()))


class TrackingService:
    """
    📊 PARAMETER BUILDER V4.0 + META CAPI
    
    Arquitetura ASSÍNCRONA (Fire and Forget) para não bloquear redirects.
    Server-Side Parameter Builder conforme Meta best practices.
    """
    
    # Constantes
    MAX_EXTERNAL_ID_LENGTH = 80
    META_API_VERSION = 'v18.0'
    
    def __init__(self, redis_client=None, celery_app=None):
        """
        Inicializa o serviço de tracking
        
        Args:
            redis_client: Cliente Redis para persistência de tracking_data
            celery_app: Instância do Celery para async tasks
        """
        self.redis = redis_client
        self.celery = celery_app
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy initialization do aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'Content-Type': 'application/json'}
            )
        return self._session
    
    # ============================================================================
    # PARAMETER BUILDER V4.0
    # ============================================================================
    
    def process_meta_parameters(
        self,
        request_cookies: Dict[str, str],
        request_args: Dict[str, str],
        request_headers: Dict[str, str],
        request_remote_addr: str,
        referer: Optional[str] = None
    ) -> ParameterBuilderResult:
        """
        SERVER-SIDE PARAMETER BUILDER
        Processa cookies, request e headers conforme Meta best practices
        
        Args:
            request_cookies: Dict com cookies do request
            request_args: Dict com query parameters
            request_headers: Dict com headers
            request_remote_addr: IP do cliente
            referer: URL de referência
            
        Returns:
            ParameterBuilderResult com fbp, fbc, IP e origens
        """
        result = ParameterBuilderResult()
        
        # 1. Extrair FBP (browser cookie)
        fbp_cookie = request_cookies.get('_fbp')
        if fbp_cookie:
            result.fbp = fbp_cookie
            result.fbp_origin = 'cookie'
            logger.debug(f"✅ FBP encontrado no cookie: {fbp_cookie[:20]}...")
        
        # 2. Extrair FBC (click ID)
        fbc_cookie = request_cookies.get('_fbc')
        fbclid_param = request_args.get('fbclid', '').strip()
        
        if fbc_cookie:
            # ✅ Cookie _fbc existe (prioridade máxima)
            result.fbc = fbc_cookie
            result.fbc_origin = 'cookie'
            logger.debug(f"✅ FBC encontrado no cookie: {fbc_cookie[:30]}...")
        elif fbclid_param:
            # ✅ Gerar fbc do fbclid conforme Meta best practices
            # Formato: fb.1.<timestamp>.<fbclid>
            result.fbc = f"fb.1.{int(time.time())}.{fbclid_param}"
            result.fbc_origin = 'generated_from_fbclid'
            logger.info(f"🔄 FBC gerado a partir do fbclid: {result.fbc[:40]}...")
        
        # 3. Extrair IP (prioridade: _fbi cookie > headers > remote_addr)
        fbi_cookie = request_cookies.get('_fbi')
        if fbi_cookie:
            result.client_ip_address = fbi_cookie
            result.ip_origin = 'cookie_fbi'
            logger.debug(f"✅ IP encontrado no cookie _fbi: {fbi_cookie}")
        else:
            # Fallback para headers
            result.client_ip_address = self._get_client_ip_from_headers(
                request_headers, request_remote_addr
            )
            result.ip_origin = 'header'
        
        return result
    
    def _get_client_ip_from_headers(
        self,
        headers: Dict[str, str],
        fallback: str
    ) -> str:
        """
        Extrai IP real do cliente considerando proxies
        
        Args:
            headers: Headers HTTP
            fallback: IP fallback (remote_addr)
            
        Returns:
            IP do cliente
        """
        # Ordem de prioridade para headers de proxy
        ip_headers = [
            'X-Forwarded-For',
            'X-Real-IP',
            'CF-Connecting-IP',
            'X-Client-IP'
        ]
        
        for header in ip_headers:
            value = headers.get(header)
            if value:
                # X-Forwarded-For pode ter múltiplos IPs (client, proxy1, proxy2...)
                ip = value.split(',')[0].strip()
                if ip and ip != 'unknown':
                    return ip
        
        return fallback
    
    # ============================================================================
    # EXTERNAL ID NORMALIZATION
    # ============================================================================
    
    def normalize_external_id(self, external_id_raw: Optional[str]) -> str:
        """
        Normaliza external_id para Meta CAPI
        - Se None/vazio: gera novo ID
        - Se > 80 chars: converte para MD5 (32 chars)
        - Caso contrário: retorna como está
        
        Args:
            external_id_raw: Valor bruto do external_id (fbclid)
            
        Returns:
            external_id normalizado
        """
        if not external_id_raw:
            # Último recurso: gerar novo ID
            return self._generate_external_id()
        
        # Se tem fbclid e é maior que 80 caracteres, normalizar
        if len(external_id_raw) > self.MAX_EXTERNAL_ID_LENGTH:
            # Converter para MD5 (sempre 32 caracteres hex)
            normalized = hashlib.md5(external_id_raw.encode()).hexdigest()
            logger.info(
                f"📏 External ID normalizado (MD5): {external_id_raw[:30]}... -> {normalized[:16]}..."
            )
            return normalized
        
        return external_id_raw
    
    def _generate_external_id(self) -> str:
        """Gera external_id único quando não há fbclid"""
        import uuid
        return f"gen_{uuid.uuid4().hex[:16]}_{int(time.time())}"
    
    def hash_sha256(self, data: str) -> str:
        """Hash SHA256 para dados sensíveis (email, phone)"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    # ============================================================================
    # PERSISTÊNCIA DE TRACKING DATA (Redis)
    # ============================================================================
    
    def save_tracking_data(self, data: TrackingData, ttl: int = 86400) -> bool:
        """
        Salva tracking data no Redis para matching com Purchase
        
        Args:
            data: TrackingData com fbclid, fbp, fbc, etc.
            ttl: Tempo de vida em segundos (default: 24h)
            
        Returns:
            True se salvou com sucesso
        """
        if not self.redis:
            logger.warning("⚠️ Redis não configurado - tracking data não persistido")
            return False
        
        try:
            key = f"tracking:{data.fbclid}"
            self.redis.setex(
                key,
                ttl,
                json.dumps({
                    'fbp': data.fbp,
                    'fbc': data.fbc,
                    'ip_address': data.ip_address,
                    'user_agent': data.user_agent,
                    'grim': data.grim,
                    'utms': data.utms,
                    'timestamp': data.timestamp
                })
            )
            logger.debug(f"💾 Tracking data salvo: {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar tracking data: {e}")
            return False
    
    def get_tracking_data(self, fbclid: str) -> Optional[TrackingData]:
        """
        Recupera tracking data do Redis pelo fbclid
        
        Args:
            fbclid: ID do Facebook click
            
        Returns:
            TrackingData ou None
        """
        if not self.redis:
            return None
        
        try:
            key = f"tracking:{fbclid}"
            data = self.redis.get(key)
            if data:
                parsed = json.loads(data)
                return TrackingData(
                    fbclid=fbclid,
                    fbp=parsed.get('fbp'),
                    fbc=parsed.get('fbc'),
                    ip_address=parsed.get('ip_address'),
                    user_agent=parsed.get('user_agent'),
                    grim=parsed.get('grim'),
                    utms=parsed.get('utms', {}),
                    timestamp=parsed.get('timestamp', int(time.time()))
                )
        except Exception as e:
            logger.error(f"❌ Erro ao recuperar tracking data: {e}")
        
        return None
    
    # ============================================================================
    # META CAPI - EVENTOS ASSÍNCRONOS
    # ============================================================================
    
    async def send_meta_event_async(
        self,
        pixel_id: str,
        access_token: str,
        event_data: MetaEventData,
        test_event_code: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Envia evento para Meta Conversions API de forma ASSÍNCRONA
        
        Args:
            pixel_id: ID do pixel Meta
            access_token: Token de acesso à API
            event_data: Dados do evento
            test_event_code: Código de teste (opcional)
            
        Returns:
            Tuple (sucesso, mensagem de erro)
        """
        url = f"https://graph.facebook.com/{self.META_API_VERSION}/{pixel_id}/events"
        
        payload = {
            'data': [{
                'event_name': event_data.event_name,
                'event_time': event_data.event_time,
                'event_id': event_data.event_id,
                'action_source': event_data.action_source,
                'event_source_url': event_data.event_source_url,
                'user_data': event_data.user_data,
                'custom_data': event_data.custom_data
            }],
            'access_token': access_token
        }
        
        if test_event_code:
            payload['test_event_code'] = test_event_code
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(
                        f"✅ Meta CAPI: {event_data.event_name} enviado | "
                        f"Events_received: {result.get('events_received', 0)}"
                    )
                    return True, None
                else:
                    error_text = await response.text()
                    logger.error(
                        f"❌ Meta CAPI erro {response.status}: {error_text[:200]}"
                    )
                    return False, error_text
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout no Meta CAPI para {event_data.event_name}")
            return False, "timeout"
        except Exception as e:
            logger.error(f"❌ Erro no Meta CAPI: {e}")
            return False, str(e)
    
    def queue_meta_event_celery(
        self,
        pixel_id: str,
        access_token: str,
        event_data: MetaEventData,
        test_event_code: Optional[str] = None,
        priority: int = 1
    ) -> Optional[str]:
        """
        Enfileira evento Meta no Celery (Fire and Forget)
        
        Args:
            pixel_id: ID do pixel Meta
            access_token: Token de acesso à API
            event_data: Dados do evento
            test_event_code: Código de teste (opcional)
            priority: Prioridade da task Celery (1=alta, 9=baixa)
            
        Returns:
            Task ID ou None
        """
        if not self.celery:
            logger.warning("⚠️ Celery não configurado - evento não enfileirado")
            return None
        
        try:
            # Serializar event_data para dict
            event_dict = {
                'event_name': event_data.event_name,
                'event_time': event_data.event_time,
                'event_id': event_data.event_id,
                'action_source': event_data.action_source,
                'event_source_url': event_data.event_source_url,
                'user_data': event_data.user_data,
                'custom_data': event_data.custom_data
            }
            
            # Enfileirar task
            task = self.celery.send_task(
                'send_meta_event',
                args=[pixel_id, access_token, event_dict, test_event_code],
                priority=priority,
                queue='meta_pixel'
            )
            
            logger.info(
                f"📨 Meta event enfileirado: {event_data.event_name} | "
                f"Task ID: {task.id[:16]}..."
            )
            return task.id
        except Exception as e:
            logger.error(f"❌ Erro ao enfileirar Meta event: {e}")
            return None
    
    # ============================================================================
    # BUILDERS PARA EVENTOS ESPECÍFICOS
    # ============================================================================
    
    def build_pageview_event(
        self,
        request: Request,
        external_id: str,
        fbp: Optional[str],
        fbc: Optional[str],
        ip_address: str,
        user_agent: str
    ) -> MetaEventData:
        """
        Constrói evento PageView com dados do Parameter Builder
        
        Args:
            request: Objeto Request do Flask
            external_id: ID externo normalizado (fbclid)
            fbp: Valor do cookie _fbp
            fbc: Valor do click ID
            ip_address: IP do cliente
            user_agent: User-Agent do cliente
            
        Returns:
            MetaEventData pronto para envio
        """
        import uuid
        
        # Hash do external_id
        external_id_hashed = self.hash_sha256(external_id)
        
        user_data = {
            'external_id': [external_id_hashed],
            'client_ip_address': ip_address,
            'client_user_agent': user_agent
        }
        
        if fbp:
            user_data['fbp'] = fbp
        if fbc:
            user_data['fbc'] = fbc
        
        return MetaEventData(
            event_name='PageView',
            event_time=int(time.time()),
            event_id=f"pv_{uuid.uuid4().hex[:16]}",
            action_source='website',
            event_source_url=request.url,
            user_data=user_data,
            custom_data={}
        )
    
    def build_purchase_event(
        self,
        external_id: str,
        fbp: Optional[str],
        fbc: Optional[str],
        ip_address: str,
        user_agent: str,
        value: float,
        currency: str = 'BRL',
        telegram_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> MetaEventData:
        """
        Constrói evento Purchase com matching ao PageView
        
        Args:
            external_id: ID externo normalizado (fbclid)
            fbp: Valor do cookie _fbp (MESMO do PageView)
            fbc: Valor do click ID (MESMO do PageView)
            ip_address: IP do cliente (MESMO do PageView)
            user_agent: User-Agent do cliente (MESMO do PageView)
            value: Valor da compra
            currency: Moeda (default: BRL)
            telegram_id: ID do Telegram para hash
            email: Email do cliente
            phone: Telefone do cliente
            
        Returns:
            MetaEventData pronto para envio
        """
        import uuid
        
        user_data = {
            'external_id': [self.hash_sha256(external_id)],
            'client_ip_address': ip_address,
            'client_user_agent': user_agent
        }
        
        if fbp:
            user_data['fbp'] = fbp
        if fbc:
            user_data['fbc'] = fbc
        if telegram_id:
            user_data['lead_id'] = self.hash_sha256(telegram_id)
        if email:
            user_data['em'] = self.hash_sha256(email.lower().strip())
        if phone:
            # Remover não-dígitos e hash
            phone_clean = ''.join(filter(str.isdigit, phone))
            if phone_clean:
                user_data['ph'] = self.hash_sha256(phone_clean)
        
        return MetaEventData(
            event_name='Purchase',
            event_time=int(time.time()),
            event_id=f"pur_{uuid.uuid4().hex[:16]}",
            action_source='website',
            event_source_url='',
            user_data=user_data,
            custom_data={
                'value': value,
                'currency': currency
            }
        )
    
    async def close(self):
        """Fecha conexões abertas"""
        if self._session and not self._session.closed:
            await self._session.close()


# Instância singleton
_tracking_service: Optional[TrackingService] = None


def get_tracking_service(redis_client=None, celery_app=None) -> TrackingService:
    """
    Factory para obter instância do TrackingService
    
    Args:
        redis_client: Cliente Redis
        celery_app: Instância Celery
        
    Returns:
        Instância de TrackingService
    """
    global _tracking_service
    
    if _tracking_service is None:
        _tracking_service = TrackingService(redis_client, celery_app)
    
    return _tracking_service
