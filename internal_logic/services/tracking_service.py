"""
Tracking Service - GrimBots
===========================
Serviço profissional de rastreamento de conversões via Meta CAPI (Conversions API).

Recursos:
- Envio assíncrono de eventos para Meta Pixel/CAPI
- Suporte a PageView, ViewContent, Purchase
- Deduplicação de eventos via event_id
- Retry automático com backoff
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
    def fire_viewcontent(cls, pool, request, bot_id: int, async_mode: bool = True) -> Optional[str]:
        """
        🔥 Dispara evento ViewContent para Meta Pixel/CAPI
        
        Args:
            pool: Instância de RedirectPool
            request: Objeto request do Flask
            bot_id: ID do bot selecionado
            async_mode: Se True, envia via task assíncrona
            
        Returns:
            str: event_id para tracking
        """
        try:
            if not pool.meta_tracking_enabled or not pool.meta_pixel_id:
                return None
            
            event_id = cls._generate_event_id()
            
            payload = {
                'event_name': 'ViewContent',
                'event_id': event_id,
                'event_time': int(datetime.now().timestamp()),
                'action_source': 'website',
                'user_data': cls._extract_user_data(request),
                'custom_data': {
                    'content_name': f"Bot {bot_id}",
                    'content_ids': [f"bot_{bot_id}"],
                    'content_type': 'product',
                    'value': 0.0,
                    'currency': 'BRL'
                }
            }
            
            if async_mode:
                cls._send_event_async(pool.meta_pixel_id, pool.meta_access_token, payload)
            else:
                cls._send_event_sync(pool.meta_pixel_id, pool.meta_access_token, payload)
            
            logger.debug(f"📊 ViewContent fired: {event_id} for bot {bot_id}")
            return event_id
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao disparar ViewContent: {e}")
            return None
    
    @classmethod
    def fire_purchase(cls, pool, request, value: float, currency: str = 'BRL', 
                      order_id: Optional[str] = None, async_mode: bool = True) -> Optional[str]:
        """
        🔥 Dispara evento Purchase para Meta Pixel/CAPI
        
        Args:
            pool: Instância de RedirectPool
            request: Objeto request do Flask
            value: Valor da compra
            currency: Moeda (default: BRL)
            order_id: ID do pedido
            async_mode: Se True, envia via task assíncrona
            
        Returns:
            str: event_id para tracking
        """
        try:
            if not pool.meta_tracking_enabled or not pool.meta_pixel_id:
                return None
            
            event_id = cls._generate_event_id()
            
            payload = {
                'event_name': 'Purchase',
                'event_id': event_id,
                'event_time': int(datetime.now().timestamp()),
                'action_source': 'website',
                'user_data': cls._extract_user_data(request),
                'custom_data': {
                    'content_name': pool.name,
                    'content_ids': [pool.slug],
                    'content_type': 'product_group',
                    'value': float(value),
                    'currency': currency,
                    'order_id': order_id or str(uuid.uuid4())[:8]
                }
            }
            
            if async_mode:
                cls._send_event_async(pool.meta_pixel_id, pool.meta_access_token, payload)
            else:
                cls._send_event_sync(pool.meta_pixel_id, pool.meta_access_token, payload)
            
            logger.info(f"💰 Purchase fired: {event_id} - R$ {value}")
            return event_id
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao disparar Purchase: {e}")
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
        """Envia evento de forma assíncrona via RQ/Celery"""
        try:
            from tasks_async import send_meta_capi_event
            send_meta_capi_event.delay(pixel_id, access_token, payload)
        except ImportError:
            # Fallback para envio síncrono se task não disponível
            cls._send_event_sync(pixel_id, access_token, payload)
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
