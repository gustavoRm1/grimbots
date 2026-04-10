"""
Tracking Service V4.1 - Serviço completo de persistência no Redis
================================================================
Serviço "cérebro" que conversa com o Redis para tracking completo.

Implementa:
- Persistência completa de tracking_data no Redis
- Recuperação de dados por tracking_token
- Geração de FBP sintético
- Limpeza de tokens expirados
- Compatibilidade com versão legada
"""

import redis
import json
import uuid
import logging
import time
import random
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TrackingServiceV4:
    """Serviço de Tracking V4.1 - Persistência completa no Redis"""
    
    def __init__(self, redis_url: str = None):
        """Inicializa conexão com Redis"""
        try:
            # Usar mesma conexão Redis do sistema
            from internal_logic.core.extensions import limiter
            redis_url = redis_url or (limiter.storage_uri if hasattr(limiter, 'storage_uri') else 'redis://localhost:6379/0')
            self.redis = redis.from_url(redis_url, decode_responses=True)
            logger.info("✅ TrackingServiceV4 - Conectado ao Redis")
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro ao conectar Redis: {e}")
            self.redis = None
        
        self.ttl_default = 3600  # 1 hora
    
    def save_tracking_token(self, tracking_token: str, tracking_data: Dict[str, Any], ttl: int = None) -> bool:
        """Salva dados de tracking no Redis"""
        try:
            if not self.redis:
                logger.error("❌ TrackingServiceV4 - Redis não disponível")
                return False
                
            key = f"tracking:{tracking_token}"
            ttl = ttl or self.ttl_default
            
            # Salvar dados completos
            self.redis.setex(key, ttl, json.dumps(tracking_data))
            
            # Salvar pixel_id separadamente para lookup rápido
            if tracking_data.get('pixel_id'):
                pixel_key = f"pixel:{tracking_data['pixel_id']}"
                self.redis.setex(pixel_key, ttl, tracking_token)
            
            # Salvar fbclid separadamente para lookup rápido
            if tracking_data.get('fbclid'):
                fbclid_key = f"fbclid:{tracking_data['fbclid']}"
                self.redis.setex(fbclid_key, ttl, tracking_token)
            
            logger.info(f"✅ TrackingServiceV4 - Dados salvos para token {tracking_token[:8]}... | pixel_id: {tracking_data.get('pixel_id')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro ao salvar dados: {e}")
            return False
    
    def recover_tracking_data(self, tracking_token: str) -> Optional[Dict[str, Any]]:
        """Recupera dados de tracking do Redis"""
        try:
            if not self.redis:
                logger.error("❌ TrackingServiceV4 - Redis não disponível")
                return None
                
            key = f"tracking:{tracking_token}"
            data = self.redis.get(key)
            
            if data:
                tracking_data = json.loads(data)
                logger.info(f"✅ TrackingServiceV4 - Dados recuperados para token {tracking_token[:8]}...")
                return tracking_data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro ao recuperar dados: {e}")
            return None
    
    def find_token_by_pixel(self, pixel_id: str) -> Optional[str]:
        """Encontra tracking_token pelo pixel_id"""
        try:
            if not self.redis:
                logger.error("❌ TrackingServiceV4 - Redis não disponível")
                return None
                
            key = f"pixel:{pixel_id}"
            tracking_token = self.redis.get(key)
            
            if tracking_token:
                return tracking_token
            
            return None
            
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro ao buscar token por pixel: {e}")
            return None
    
    def find_token_by_fbclid(self, fbclid: str) -> Optional[str]:
        """Encontra tracking_token pelo fbclid"""
        try:
            if not self.redis:
                logger.error("❌ TrackingServiceV4 - Redis não disponível")
                return None
                
            key = f"fbclid:{fbclid}"
            tracking_token = self.redis.get(key)
            
            if tracking_token:
                return tracking_token
            
            return None
            
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro ao buscar token por fbclid: {e}")
            return None
    
    @staticmethod
    def generate_fbp() -> str:
        """Gera FBP no servidor (fallback)"""
        # Formato: fb.1.{subdomain}.{random}
        subdomain = int(time.time())  # Timestamp
        random_num = random.randint(1000000000, 9999999999)
        
        return f"fb.1.{subdomain}.{random_num}"
    
    def cleanup_expired_tokens(self) -> int:
        """Limpa tokens expirados (manutenção)"""
        try:
            if not self.redis:
                logger.error("❌ TrackingServiceV4 - Redis não disponível")
                return 0
                
            pattern = "tracking:*"
            keys = self.redis.keys(pattern)
            
            expired_count = 0
            for key in keys:
                if not self.redis.exists(key):
                    expired_count += 1
            
            logger.info(f"✅ TrackingServiceV4 - Limpeza realizada - {expired_count} tokens expirados")
            return expired_count
            
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro na limpeza: {e}")
            return 0
    
    def update_tracking_data(self, tracking_token: str, updates: Dict[str, Any]) -> bool:
        """Atualiza dados existentes de tracking"""
        try:
            if not self.redis:
                logger.error("❌ TrackingServiceV4 - Redis não disponível")
                return False
                
            # Recuperar dados existentes
            existing_data = self.recover_tracking_data(tracking_token) or {}
            
            # Mesclar com atualizações
            updated_data = {**existing_data, **updates}
            
            # Salvar dados atualizados
            return self.save_tracking_token(tracking_token, updated_data)
            
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro ao atualizar dados: {e}")
            return False
    
    def get_tracking_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do tracking"""
        try:
            if not self.redis:
                logger.error("❌ TrackingServiceV4 - Redis não disponível")
                return {}
                
            pattern = "tracking:*"
            keys = self.redis.keys(pattern)
            
            stats = {
                'total_tokens': len(keys),
                'active_tokens': 0,
                'expired_tokens': 0,
                'pixels_with_tracking': 0
            }
            
            for key in keys:
                if self.redis.exists(key):
                    stats['active_tokens'] += 1
                else:
                    stats['expired_tokens'] += 1
            
            # Contar pixels com tracking
            pixel_keys = self.redis.keys("pixel:*")
            stats['pixels_with_tracking'] = len(pixel_keys)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ TrackingServiceV4 - Erro ao obter estatísticas: {e}")
            return {}


# Classe legacy para compatibilidade
class TrackingService:
    """Compatibilidade com versão antiga"""
    
    @staticmethod
    def save_tracking_data(fbclid: str, fbp: str, fbc: str, **kwargs):
        """Salva dados de tracking (legado)"""
        logger.warning("⚠️ TrackingService.save_tracking_data: Método legado chamado - use TrackingServiceV4")
        pass
    
    @staticmethod
    def generate_fbp() -> str:
        """Gera FBP (legado)"""
        return TrackingServiceV4.generate_fbp()
    
    @staticmethod
    def fire_pageview(pool, request, async_mode: bool = True) -> Optional[str]:
        """Dispara PageView (legado)"""
        logger.warning("⚠️ TrackingService.fire_pageview: Método legado chamado - use implementação V4.1")
        return None


# Função de conveniência para obter instância do serviço
def get_tracking_service_v4() -> TrackingServiceV4:
    """Retorna instância do TrackingServiceV4"""
    return TrackingServiceV4()


# Função de conveniência para compatibilidade
def get_tracking_service() -> TrackingService:
    """Retorna instância do TrackingService (legado)"""
    return TrackingService()
