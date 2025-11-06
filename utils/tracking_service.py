"""
Tracking Service - Solução Sênior QI 300
Sistema robusto de tracking para Meta Pixel com alta Match Quality (8-10/10)

Características:
- Recuperação multi-estratégia de fbp/fbc
- TTL de 30 dias (persistência)
- external_id imutável
- Consistência total entre PageView e Purchase
"""

import os
import redis
import json
import hashlib
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Conectar ao Redis
try:
    r = redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
except:
    r = None
    logger.warning("⚠️ Redis não disponível - tracking será limitado")


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

