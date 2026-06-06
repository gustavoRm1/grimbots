"""
Tracking Service - Meta Pixel Functions
====================================
Serviço responsável pelo tracking de eventos do Meta Pixel.

✅ TRANSPLANTED: Funções completas do legado com PageView, ViewContent e Purchase
Adaptado para nova arquitetura com imports corretos.
"""

import logging
import json
import uuid
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class TrackingService:
    """
    📊 Serviço de Tracking Profissional (Meta CAPI)
    
    Integra com Meta Conversions API para:
    - PageView: Rastreamento de visualizações de página
    - ViewContent: Interesse no conteúdo
    - Purchase: Conversões de venda
    
    Todos os eventos são enviados de forma assíncrona via Celery/RQ.
    """
    
    # Meta CAPI Endpoint
    META_CAPI_URL = "https://graph.facebook.com/v18.0/{pixel_id}/events"
    
    def __init__(self):
        """Inicializa conexão com Redis"""
        try:
            import redis
            from internal_logic.core.extensions import limiter
            # Usar mesma conexão Redis do limiter
            redis_url = limiter.storage_uri if hasattr(limiter, 'storage_uri') else 'redis://localhost:6379/0'
            self.redis = redis.from_url(redis_url, decode_responses=True)
            logger.info(" TrackingService - Conectado ao Redis")
        except Exception as e:
            logger.error(f" TrackingService - Erro ao conectar Redis: {e}")
            self.redis = None
    
    def recover_tracking_data(self, tracking_token: str):
        """Recupera dados completos de tracking do Redis"""
        try:
            if not tracking_token:
                return None
                
            if not self.redis:
                logger.error(" TrackingService - Redis não disponível")
                return None
            
            key = f"tracking:{tracking_token}"
            data = self.redis.get(key)
            
            if data:
                tracking_data = json.loads(data)
                logger.info(f"[TRACKING_SERVICE] Dados recuperados para token {tracking_token[:8]}...")
                return tracking_data
                
            return None
            
        except Exception as e:
            logger.error(f"[TRACKING_SERVICE] Erro ao recuperar dados de tracking: {e}")
            return None
    
    @classmethod
    def fire_pageview(cls, pool, request, async_mode: bool = True) -> Optional[str]:
        """
        🔥 Dispara evento PageView para Meta Pixel/CAPI
        
        Args:
            pool: Instância de RedirectPool
            request: Objeto request do Flask
            async_mode: Se True, envia via task assíncrona
            
        Returns:
            str: event_id para tracking
        """
        try:
            if not pool.meta_tracking_enabled or not pool.meta_pixel_id:
                return None
            
            event_id = cls._generate_event_id()
            
            payload = {
                'event_name': 'PageView',
                'event_id': event_id,
                'event_time': int(datetime.now().timestamp()),
                'action_source': 'website',
                'user_data': cls._extract_user_data(request),
                'custom_data': {
                    'content_name': pool.name,
                    'content_ids': [pool.slug],
                    'content_type': 'product_group'
                }
            }
            
            if async_mode:
                cls._send_event_async(pool.meta_pixel_id, pool.meta_access_token, payload)
            else:
                cls._send_event_sync(pool.meta_pixel_id, pool.meta_access_token, payload)
            
            logger.debug(f"📊 PageView fired: {event_id} for pool {pool.id}")
            return event_id
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao disparar PageView: {e}")
            return None
    
    
    @classmethod
    def _extract_user_data(cls, request) -> Dict[str, Any]:
        """Extrai dados do usuário de forma segura para CAPI"""
        user_data = {}
        
        # Client IP
        client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', '')
        if client_ip:
            # Hash SHA256 do IP (conforme requisitos do Meta CAPI)
            user_data['client_ip_address'] = cls._hash_sha256(client_ip)
        
        # User Agent
        user_agent = request.headers.get('User-Agent', '')
        if user_agent:
            user_data['client_user_agent'] = cls._hash_sha256(user_agent)
        
        # FBCLID (Facebook Click ID) - se presente
        fbclid = request.args.get('fbclid', '')
        if fbclid:
            user_data['fbc'] = f"fb.1.{int(datetime.now().timestamp())}.{fbclid}"
        
        # FBP (Browser ID) - se presente no cookie
        fbp = request.cookies.get('_fbp', '')
        if fbp:
            user_data['fbp'] = fbp
        
        return user_data
    
    @classmethod
    def _hash_sha256(cls, value: str) -> str:
        """Hash SHA256 para dados sensíveis (CAPI compliance)"""
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
    
    @classmethod
    def _generate_event_id(cls) -> str:
        """Gera ID único para deduplicação de eventos"""
        return str(uuid.uuid4())
    
    @classmethod
    def _send_event_async(cls, pixel_id: str, access_token: str, payload: Dict):
        """Envia evento de forma assíncrona via Celery"""
        try:
            from celery_app import send_meta_event
            send_meta_event.delay(pixel_id, access_token, payload)
        except Exception as e:
            logger.warning(f"⚠️ Falha ao enfileirar evento: {e}")
    
    @classmethod
    def _send_event_sync(cls, pixel_id: str, access_token: str, payload: Dict):
        """Envia evento de forma síncrona (fallback)"""
        try:
            url = cls.META_CAPI_URL.format(pixel_id=pixel_id)
            
            data = {
                'data': [payload],
                'access_token': access_token
            }
            
            # Enviar com timeout curto (não bloquear redirect)
            response = requests.post(
                url,
                json=data,
                timeout=2.0,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.debug(f"📊 Evento enviado: {payload.get('event_name')}")
            else:
                logger.warning(f"⚠️ Meta CAPI retornou {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao enviar evento: {e}")
