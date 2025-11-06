"""
Tracking Service V4 - Universal e Definitivo
Sistema robusto de tracking para Meta Pixel com alta Match Quality (8-10/10)

Características V4:
- Tracking Token único por transação
- Recuperação multi-estratégia de fbp/fbc
- TTL de 30 dias (persistência)
- external_id imutável e ordenado
- Consistência total entre PageView e Purchase
- Compatibilidade com versão QI 300 (métodos estáticos mantidos)
"""

import os
import redis
import json
import hashlib
import logging
import time
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Conectar ao Redis
try:
    r = redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
except:
    r = None
    logger.warning("⚠️ Redis não disponível - tracking será limitado")


class TrackingServiceV4:
    """
    Tracking Service V4 - Universal e Definitivo
    
    Funcionalidades:
    - Geração de tracking_token único
    - Geração de fbp/fbc consistentes
    - External ID array imutável e ordenado
    - Persistência robusta no Redis
    - Recuperação multi-chave
    """
    
    TTL_DAYS = 30  # TTL padrão de 30 dias
    
    def __init__(self, redis_client: redis.Redis = None):
        """
        Args:
            redis_client: Cliente Redis (opcional, usa padrão se não fornecido)
        """
        self.redis = redis_client or r
    
    def generate_tracking_token(
        self,
        bot_id: int,
        customer_user_id: str,
        payment_id: Optional[int] = None,
        fbclid: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
    ) -> str:
        """
        Gera tracking_token único e imutável.
        
        Formato: tracking_{hash}
        Hash = SHA256(bot_id|customer_user_id|payment_id|fbclid|timestamp)
        
        Args:
            bot_id: ID do bot
            customer_user_id: ID do cliente (Telegram user ID)
            payment_id: ID do pagamento (opcional)
            fbclid: Facebook Click ID (opcional)
            utm_source: UTM Source (opcional)
            utm_medium: UTM Medium (opcional)
            utm_campaign: UTM Campaign (opcional)
        
        Returns:
            str: tracking_token único
        """
        timestamp = int(time.time())
        payload = f"{bot_id}|{customer_user_id}|{payment_id or 0}|{fbclid or ''}|{utm_source or ''}|{utm_medium or ''}|{utm_campaign or ''}|{timestamp}"
        token_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"tracking_{token_hash}"
    
    def generate_fbp(self, telegram_user_id: str) -> str:
        """
        Gera _fbp cookie do Meta Pixel.
        
        Formato: fb.{version}.{timestamp}.{random}
        """
        version = 1
        timestamp = int(time.time() * 1000)
        # Usar hash do telegram_user_id para garantir consistência
        random = int(hashlib.md5(telegram_user_id.encode()).hexdigest()[:9], 16)
        return f"fb.{version}.{timestamp}.{random}"
    
    def generate_fbc(self, fbclid: str, timestamp: Optional[int] = None) -> str:
        """
        Gera _fbc cookie do Meta Pixel (se fbclid presente).
        
        Formato: fb.{version}.{timestamp}.{fbclid}
        """
        if not fbclid:
            return None
        
        version = 1
        if not timestamp:
            timestamp = int(time.time() * 1000)
        
        return f"fb.{version}.{timestamp}.{fbclid}"
    
    def build_external_id_array(
        self,
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> List[str]:
        """
        Constrói array de external_id consistente e imutável.
        
        Ordem de prioridade (IMUTÁVEL):
        1. SHA256(fbclid) se presente
        2. SHA256(telegram_user_id) se presente
        3. SHA256(email) se presente
        4. SHA256(phone) se presente
        
        IMPORTANTE: A ordem NUNCA muda para garantir Match Quality.
        
        Args:
            fbclid: Facebook Click ID
            telegram_user_id: ID do usuário no Telegram
            email: Email do usuário
            phone: Telefone do usuário
        
        Returns:
            List[str]: Array ordenado de external_id hashes
        """
        external_ids = []
        
        # 1. fbclid (maior prioridade)
        if fbclid:
            external_ids.append(self._hash_data(fbclid))
        
        # 2. telegram_user_id
        if telegram_user_id:
            external_ids.append(self._hash_data(str(telegram_user_id)))
        
        # 3. email
        if email:
            external_ids.append(self._hash_data(email.lower().strip()))
        
        # 4. phone
        if phone:
            # Normalizar phone (remover caracteres não numéricos)
            phone_clean = ''.join(filter(str.isdigit, phone))
            if phone_clean:
                external_ids.append(self._hash_data(phone_clean))
        
        return external_ids
    
    def _hash_data(self, data: str) -> str:
        """Hash SHA256 de dados"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def save_tracking_data(
        self,
        tracking_token: str,
        bot_id: int,
        customer_user_id: str,
        payment_id: Optional[int] = None,
        fbclid: Optional[str] = None,
        fbp: Optional[str] = None,
        fbc: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        external_ids: Optional[List[str]] = None,
        **kwargs
    ) -> bool:
        """
        Salva dados de tracking no Redis com múltiplas chaves para recuperação robusta.
        
        Chaves criadas:
        - tracking:token:{tracking_token}
        - tracking:fbclid:{fbclid} (se presente)
        - tracking:hash:{hash(telegram_user_id)} (se presente)
        - tracking:chat:{bot_id}:{customer_user_id}
        - tracking:payment:{payment_id} (se presente)
        
        Args:
            tracking_token: Token único de tracking (obrigatório)
            bot_id: ID do bot
            customer_user_id: ID do cliente
            payment_id: ID do pagamento (opcional)
            fbclid: Facebook Click ID (opcional)
            fbp: Facebook Browser ID (opcional)
            fbc: Facebook Click Browser ID (opcional)
            utm_source: UTM Source (opcional)
            utm_medium: UTM Medium (opcional)
            utm_campaign: UTM Campaign (opcional)
            external_ids: Array de external_ids (opcional)
            **kwargs: Campos adicionais
        
        Returns:
            bool: True se salvo com sucesso, False caso contrário
        """
        if not self.redis:
            logger.warning("⚠️ Redis não disponível - tracking não será persistido")
            return False
        
        try:
            tracking_data = {
                'tracking_token': tracking_token,
                'bot_id': bot_id,
                'customer_user_id': customer_user_id,
                'payment_id': payment_id,
                'fbclid': fbclid,
                'fbp': fbp,
                'fbc': fbc,
                'utm_source': utm_source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'external_ids': external_ids or [],
                'created_at': datetime.utcnow().isoformat(),
                **kwargs
            }
            
            data_json = json.dumps(tracking_data)
            ttl_seconds = self.TTL_DAYS * 24 * 3600
            
            # Chave principal: tracking_token
            self.redis.setex(
                f"tracking:token:{tracking_token}",
                ttl_seconds,
                data_json
            )
            
            # Chave por fbclid
            if fbclid:
                self.redis.setex(
                    f"tracking:fbclid:{fbclid}",
                    ttl_seconds,
                    data_json
                )
            
            # Chave por hash do telegram_user_id
            if customer_user_id:
                user_hash = self._hash_data(str(customer_user_id))
                self.redis.setex(
                    f"tracking:hash:{user_hash}",
                    ttl_seconds,
                    data_json
                )
            
            # Chave por chat (bot_id + customer_user_id)
            self.redis.setex(
                f"tracking:chat:{bot_id}:{customer_user_id}",
                ttl_seconds,
                data_json
            )
            
            # Chave por payment_id
            if payment_id:
                self.redis.setex(
                    f"tracking:payment:{payment_id}",
                    ttl_seconds,
                    data_json
                )
            
            logger.debug(f"✅ Tracking data salvo: token={tracking_token}, bot_id={bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar tracking data: {e}", exc_info=True)
            return False
    
    def recover_tracking_data(
        self,
        tracking_token: Optional[str] = None,
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        payment_id: Optional[int] = None,
        bot_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Recupera dados de tracking usando estratégia de múltiplas chaves.
        
        Ordem de tentativa:
        1. tracking_token (se fornecido) - PRIORIDADE MÁXIMA
        2. fbclid (se fornecido)
        3. payment_id (se fornecido)
        4. hash(telegram_user_id) (se fornecido)
        5. chat (bot_id + customer_user_id) (se ambos fornecidos)
        
        Args:
            tracking_token: Token único de tracking
            fbclid: Facebook Click ID
            telegram_user_id: ID do usuário no Telegram
            payment_id: ID do pagamento
            bot_id: ID do bot
        
        Returns:
            Dict com dados de tracking ou None se não encontrado
        """
        if not self.redis:
            return None
        
        try:
            # 1. Por tracking_token (PRIORIDADE MÁXIMA)
            if tracking_token:
                data = self.redis.get(f"tracking:token:{tracking_token}")
                if data:
                    return json.loads(data)
            
            # 2. Por fbclid
            if fbclid:
                data = self.redis.get(f"tracking:fbclid:{fbclid}")
                if data:
                    return json.loads(data)
            
            # 3. Por payment_id
            if payment_id:
                data = self.redis.get(f"tracking:payment:{payment_id}")
                if data:
                    return json.loads(data)
            
            # 4. Por hash do telegram_user_id
            if telegram_user_id:
                user_hash = self._hash_data(str(telegram_user_id))
                data = self.redis.get(f"tracking:hash:{user_hash}")
                if data:
                    return json.loads(data)
            
            # 5. Por chat
            if bot_id and telegram_user_id:
                data = self.redis.get(f"tracking:chat:{bot_id}:{telegram_user_id}")
                if data:
                    return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao recuperar tracking data: {e}", exc_info=True)
            return None


# ==================== COMPATIBILIDADE COM VERSÃO QI 300 ====================
# Manter métodos estáticos para compatibilidade com código existente

class TrackingService:
    """
    Serviço de tracking robusto para Meta Pixel
    
    Garante:
    - Match Quality 8-10/10
    - Consistência entre PageView e Purchase
    - Recuperação robusta em qualquer cenário
    """
    
    TTL_DAYS = 30  # ✅ 30 dias de persistência (não 7)
    
    @staticmethod
    def generate_fbp() -> str:
        """
        Gera _fbp quando não disponível no cookie
        
        Formato: fb.{version}.{timestamp}.{random}
        Exemplo: fb.1.1762413994.1234567890
        """
        import random
        timestamp = int(datetime.now().timestamp())
        random_part = random.randint(1000000000, 9999999999)
        return f"fb.1.{timestamp}.{random_part}"
    
    @staticmethod
    def generate_fbc(fbclid: str) -> str:
        """
        Gera _fbc corretamente: fb.1.{timestamp}.{fbclid}
        
        Formato: fb.1.{timestamp}.{fbclid}
        """
        if not fbclid:
            return None
        
        timestamp = int(datetime.now().timestamp())
        return f"fb.1.{timestamp}.{fbclid}"
    
    @staticmethod
    def hash_fbclid(fbclid: str) -> str:
        """Gera hash SHA256 do fbclid para external_id"""
        if not fbclid:
            return None
        return hashlib.sha256(fbclid.encode('utf-8')).hexdigest()
    
    @staticmethod
    def hash_telegram_id(telegram_id: str) -> str:
        """Gera hash SHA256 do telegram_user_id para external_id"""
        if not telegram_id:
            return None
        return hashlib.sha256(str(telegram_id).encode('utf-8')).hexdigest()
    
    @staticmethod
    def build_external_id_array(fbclid: str, telegram_user_id: str) -> List[str]:
        """
        Constrói array de external_id IMUTÁVEL e CONSISTENTE
        
        Ordem CRÍTICA (nunca alterar):
        1. hash(fbclid) - sempre primeiro
        2. hash(telegram_user_id) - sempre segundo
        
        Retorna array ordenado e sem duplicatas
        """
        external_ids = []
        
        # 1. SEMPRE fbclid primeiro (prioridade máxima)
        if fbclid:
            fbclid_hash = TrackingService.hash_fbclid(fbclid)
            if fbclid_hash and fbclid_hash not in external_ids:
                external_ids.append(fbclid_hash)
        
        # 2. SEMPRE telegram_user_id segundo
        if telegram_user_id:
            telegram_hash = TrackingService.hash_telegram_id(telegram_user_id)
            if telegram_hash and telegram_hash not in external_ids:
                external_ids.append(telegram_hash)
        
        return external_ids
    
    @staticmethod
    def save_tracking_data(
        fbclid: Optional[str] = None,
        fbp: Optional[str] = None,
        fbc: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        grim: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        utms: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Salva tracking data no Redis com múltiplas estratégias de chave
        
        Estratégias:
        1. tracking:fbclid:{fbclid} - chave exata (se fbclid disponível)
        2. tracking:hash:{hash_prefix} - chave por hash (12 primeiros chars)
        3. tracking:chat:{telegram_user_id} - chave por chat_id
        4. tracking_grim:{grim} - chave por grim (se disponível) - ✅ FUNCIONA MESMO SEM FBCLID
        
        ✅ CRÍTICO: fbp e fbc são sempre gerados se não fornecidos
        """
        if not r:
            logger.warning("⚠️ Redis não disponível - tracking não salvo")
            return False
        
        # ✅ CRÍTICO QI 300: NÃO gerar FBP no servidor
        # FBP deve ser SEMPRE gerado pelo browser (via Meta Pixel JS)
        # Se não fornecido, deixar vazio (browser gerará)
        # Não gerar aqui para evitar inconsistência
        
        # ✅ CRÍTICO: Sempre gerar fbc se não fornecido mas tiver fbclid
        if not fbc and fbclid:
            fbc = TrackingService.generate_fbc(fbclid)
            logger.debug(f"🔑 _fbc gerado automaticamente no save_tracking_data() (fbclid presente)")
        
        # ✅ Bloqueios corrigidos (agora salva por grim mesmo sem fbclid)
        if not fbclid and not grim:
            logger.warning("⚠️ Sem fbclid e sem grim — não é possível salvar tracking")
            return False
        
        tracking_data = {
            'fbclid': fbclid,
            'fbp': fbp or '',
            'fbc': fbc or '',
            'ip': ip_address or '',
            'ua': user_agent or '',
            'grim': grim or '',
            'telegram_user_id': str(telegram_user_id) if telegram_user_id else '',
            'utms': utms or {},
            'timestamp': int(datetime.now().timestamp()),
            'source': 'redirect'
        }
        
        ttl_seconds = TrackingService.TTL_DAYS * 24 * 3600
        
        try:
            # ✅ 1. Salvar por fbclid
            if fbclid:
                key1 = f"tracking:fbclid:{fbclid}"
                r.setex(key1, ttl_seconds, json.dumps(tracking_data))
                logger.debug(f"🔑 Tracking salvo: {key1}")
                
                # ✅ 1b. Salvar hash
                fbclid_hash = TrackingService.hash_fbclid(fbclid)
                if fbclid_hash:
                    key2 = f"tracking:hash:{fbclid_hash[:12]}"
                    r.setex(key2, ttl_seconds, json.dumps(tracking_data))
                    logger.debug(f"🔑 Tracking salvo: {key2}")
            
            # ✅ 2. Salvar por GRIM (mesmo sem fbclid!)
            if grim:
                key3 = f"tracking_grim:{grim}"
                r.setex(key3, ttl_seconds, json.dumps(tracking_data))
                logger.debug(f"🔑 Tracking salvo: {key3}")
            
            # ✅ 3. Salvar por chat_id (se disponível)
            if telegram_user_id:
                key4 = f"tracking:chat:{telegram_user_id}"
                r.setex(key4, ttl_seconds, json.dumps(tracking_data))
                logger.debug(f"🔑 Tracking salvo: {key4}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro salvando tracking: {e}")
            return False
    
    @staticmethod
    def recover_tracking_data(
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        grim: Optional[str] = None,
        hash_prefix: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Recupera tracking data usando múltiplas estratégias (ordem de prioridade)
        
        Estratégias (em ordem de prioridade):
        1. tracking:fbclid:{fbclid} - mais confiável
        2. tracking:hash:{hash_prefix} - fallback por hash
        3. tracking:chat:{telegram_user_id} - fallback por chat
        4. tracking_grim:{grim} - fallback por grim
        5. Busca por padrão (último recurso)
        
        Retorna dict com: fbclid, fbp, fbc, ip, ua, grim, utms
        """
        if not r:
            logger.warning("⚠️ Redis não disponível - tracking não recuperado")
            return None
        
        tracking_data = None
        strategy_used = None
        
        # Estratégia 1: Chave exata por fbclid (MÁXIMA PRIORIDADE)
        if fbclid:
            key1 = f"tracking:fbclid:{fbclid}"
            try:
                data = r.get(key1)
                if data:
                    tracking_data = json.loads(data)
                    strategy_used = "fbclid_exact"
                    logger.info(f"✅ Tracking recuperado via {strategy_used}: {key1}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao recuperar {key1}: {e}")
        
        # Estratégia 2: Chave por hash prefix
        if not tracking_data and hash_prefix:
            key2 = f"tracking:hash:{hash_prefix}"
            try:
                data = r.get(key2)
                if data:
                    tracking_data = json.loads(data)
                    strategy_used = "hash_prefix"
                    logger.info(f"✅ Tracking recuperado via {strategy_used}: {key2}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao recuperar {key2}: {e}")
        
        # Estratégia 3: Chave por telegram_user_id
        if not tracking_data and telegram_user_id:
            key3 = f"tracking:chat:{telegram_user_id}"
            try:
                data = r.get(key3)
                if data:
                    tracking_data = json.loads(data)
                    strategy_used = "chat_id"
                    logger.info(f"✅ Tracking recuperado via {strategy_used}: {key3}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao recuperar {key3}: {e}")
        
        # Estratégia 4: Chave por grim
        if not tracking_data and grim:
            key4 = f"tracking_grim:{grim}"
            try:
                data = r.get(key4)
                if data:
                    tracking_data = json.loads(data)
                    strategy_used = "grim"
                    logger.info(f"✅ Tracking recuperado via {strategy_used}: {key4}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao recuperar {key4}: {e}")
        
        # Estratégia 5: Busca por padrão (último recurso - custoso)
        if not tracking_data and fbclid:
            try:
                # Buscar por padrão tracking:fbclid:*{fbclid}*
                pattern = f"tracking:fbclid:*{fbclid[-20:]}*"
                for key in r.scan_iter(match=pattern):
                    data = r.get(key)
                    if data:
                        parsed = json.loads(data)
                        if parsed.get('fbclid') == fbclid:
                            tracking_data = parsed
                            strategy_used = "pattern_match"
                            logger.info(f"✅ Tracking recuperado via {strategy_used}: {key}")
                            break
            except Exception as e:
                logger.warning(f"⚠️ Erro na busca por padrão: {e}")
        
        if tracking_data:
            # ✅ CORREÇÃO CRÍTICA: Garantir que fbp e fbc existam (evitar 'NoneType' object is not subscriptable)
            # Se fbp ou fbc forem None, definir como string vazia
            if tracking_data.get('fbp') is None:
                tracking_data['fbp'] = ''
            if tracking_data.get('fbc') is None:
                tracking_data['fbc'] = ''
            
            logger.info(f"📊 Tracking recuperado: fbclid={tracking_data.get('fbclid', 'N/A')[:20] if tracking_data.get('fbclid') else 'N/A'}... | fbp={'✅' if tracking_data.get('fbp') else '❌'} | fbc={'✅' if tracking_data.get('fbc') else '❌'} | strategy={strategy_used}")
        
        return tracking_data

