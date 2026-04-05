"""
GrimBots Redis Wrapper - Isolamento de Namespace por User ID
===========================================================

Este módulo implementa um wrapper isolado do Redis que garante que os dados
de cada usuário sejam completamente separados, eliminando o "comportamento
de lua" onde ações de um usuário interferem em outro.

Padrão de namespace: gb:{user_id}:{key_name}

Exemplo:
- Antes: "botmanager:active_bots" (global)
- Depois: "gb:42:active_bots" (isolated para user_id=42)

Regras:
1. Todo acesso ao Redis DEVE passar por esta classe
2. user_id é obrigatório no construtor
3. Métodos de fallback garantem compatibilidade retroativa
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from functools import wraps

logger = logging.getLogger(__name__)


def _get_redis_client():
    """Retorna cliente Redis singleton (lazy import para evitar circular)."""
    from redis_manager import get_redis_connection
    return get_redis_connection()


def _with_fallback(operation_name):
    """
    Decorator para implementar protocolo de fallback:
    1º: Tenta operação na chave namespaced
    2º: Se não encontrar, tenta chave global (legado)
    3º: SEMPRE salva no namespace novo (migração automática)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, key: str, *args, **kwargs):
            namespaced_key = self._key(key)
            
            # Para operações de leitura, implementar fallback
            if operation_name in ('get', 'hget', 'hgetall', 'exists'):
                # 1º: Tentar chave namespaced
                result = func(self, namespaced_key, *args, **kwargs)
                
                # 2º: Se não encontrou, tentar chave global (legado)
                if result is None or result == {} or result == []:
                    legacy_result = self._legacy_operation(operation_name, key, *args, **kwargs)
                    if legacy_result is not None:
                        logger.debug(f"🔄 Fallback ativado: {key} encontrado em namespace global, migrando...")
                        # Migrar para novo namespace automaticamente
                        self._migrate_key(key, legacy_result)
                        return legacy_result
                
                return result
            
            # Para operações de escrita, SEMPRE usar namespace novo
            return func(self, namespaced_key, *args, **kwargs)
        
        return wrapper
    return decorator


class GrimBotsRedis:
    """
    Cliente Redis com namespace isolado por user_id.
    
    Cada instância opera em seu próprio namespace: gb:{user_id}:*
    
    Args:
        user_id: ID do usuário (obrigatório para isolamento)
        
    Example:
        >>> redis_user_42 = GrimBotsRedis(user_id=42)
        >>> redis_user_42.set("active_bots", "bot_123")
        # Salva em: gb:42:active_bots
        
        >>> redis_user_99 = GrimBotsRedis(user_id=99)
        >>> redis_user_99.set("active_bots", "bot_456")
        # Salva em: gb:99:active_bots (completamente isolado)
    """
    
    def __init__(self, user_id: int):
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id deve ser um inteiro positivo, recebido: {user_id}")
        
        self.user_id = user_id
        self.prefix = f"gb:{user_id}"
        self._redis = None  # Lazy initialization
    
    @property
    def redis(self):
        """Lazy initialization do cliente Redis."""
        if self._redis is None:
            self._redis = _get_redis_client()
        return self._redis
    
    def _key(self, name: str) -> str:
        """
        Gera chave com namespace obrigatório.
        
        Args:
            name: Nome da chave (sem prefixo)
            
        Returns:
            Chave completa com namespace: gb:{user_id}:{name}
        """
        # Garantir que não estamos duplicando namespace
        if name.startswith(f"gb:{self.user_id}:"):
            return name
        if name.startswith("gb:") and f"gb:{self.user_id}:" not in name:
            raise ValueError(f"Tentativa de acesso a namespace diferente: {name}")
        
        return f"{self.prefix}:{name}"
    
    def _legacy_operation(self, operation: str, key: str, *args, **kwargs):
        """
        Executa operação na chave global (legado) para fallback.
        """
        try:
            if operation == 'get':
                return self.redis.get(key)
            elif operation == 'hget':
                return self.redis.hget(*args, key) if args else self.redis.hget(key, *args)
            elif operation == 'hgetall':
                return self.redis.hgetall(key)
            elif operation == 'exists':
                return self.redis.exists(key)
        except Exception as e:
            logger.debug(f"Erro no fallback para {key}: {e}")
            return None
        return None
    
    def _migrate_key(self, key: str, value: Any):
        """
        Migra dado do namespace global para o novo namespace.
        Executado automaticamente quando fallback encontra dado antigo.
        """
        try:
            namespaced_key = self._key(key)
            if isinstance(value, dict):
                self.redis.hset(namespaced_key, mapping=value)
            elif isinstance(value, (str, bytes)):
                self.redis.set(namespaced_key, value)
            elif isinstance(value, (list, set)):
                for item in value:
                    self.redis.sadd(namespaced_key, item)
            logger.info(f"✅ Migração automática: {key} → {namespaced_key}")
        except Exception as e:
            logger.warning(f"⚠️ Falha na migração de {key}: {e}")
    
    # =====================================================================
    # OPERAÇÕES BÁSICAS (GET, SET, DELETE)
    # =====================================================================
    
    def get(self, key: str) -> Optional[str]:
        """
        Obtém valor da chave (com fallback para namespace global).
        
        Args:
            key: Nome da chave
            
        Returns:
            Valor da chave ou None
        """
        namespaced_key = self._key(key)
        
        # Tentar namespace novo
        result = self.redis.get(namespaced_key)
        if result is not None:
            return result.decode('utf-8') if isinstance(result, bytes) else result
        
        # Fallback: tentar namespace global
        legacy_result = self.redis.get(key)
        if legacy_result is not None:
            value = legacy_result.decode('utf-8') if isinstance(legacy_result, bytes) else legacy_result
            logger.debug(f"🔄 Fallback GET: {key} → migrando para {namespaced_key}")
            # Migrar automaticamente
            self.redis.set(namespaced_key, legacy_result)
            return value
        
        return None
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """
        Define valor da chave (SEMPRE no namespace isolado).
        
        Args:
            key: Nome da chave
            value: Valor a ser armazenado
            ex: TTL em segundos (opcional)
            
        Returns:
            True se sucesso, False se erro
        """
        namespaced_key = self._key(key)
        try:
            if ex:
                self.redis.setex(namespaced_key, ex, value)
            else:
                self.redis.set(namespaced_key, value)
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao SET {namespaced_key}: {e}")
            return False
    
    def setex(self, key: str, seconds: int, value: str) -> bool:
        """Define valor com TTL (SET EXpire)."""
        return self.set(key, value, ex=seconds)
    
    def delete(self, key: str) -> int:
        """
        Remove chave (tenta namespace novo, depois global para cleanup).
        
        Returns:
            Número de chaves removidas
        """
        namespaced_key = self._key(key)
        removed = 0
        
        # Remover do namespace novo
        if self.redis.delete(namespaced_key):
            removed += 1
        
        # Também tentar remover do namespace global (cleanup)
        try:
            if self.redis.delete(key):
                removed += 1
                logger.debug(f"🧹 Cleanup: removido {key} do namespace global")
        except:
            pass
        
        return removed
    
    def exists(self, key: str) -> bool:
        """Verifica se chave existe (com fallback)."""
        namespaced_key = self._key(key)
        
        # Verificar namespace novo
        if self.redis.exists(namespaced_key):
            return True
        
        # Fallback: verificar namespace global
        if self.redis.exists(key):
            return True
        
        return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """Define TTL na chave."""
        namespaced_key = self._key(key)
        return bool(self.redis.expire(namespaced_key, seconds))
    
    def ttl(self, key: str) -> int:
        """Retorna TTL restante da chave."""
        namespaced_key = self._key(key)
        return self.redis.ttl(namespaced_key)
    
    # =====================================================================
    # OPERAÇÕES HASH (HGET, HSET, HDEL)
    # =====================================================================
    
    def hget(self, key: str, field: str) -> Optional[str]:
        """
        Obtém campo específico de hash (com fallback).
        """
        namespaced_key = self._key(key)
        
        # Tentar namespace novo
        result = self.redis.hget(namespaced_key, field)
        if result is not None:
            return result.decode('utf-8') if isinstance(result, bytes) else result
        
        # Fallback: tentar namespace global
        legacy_result = self.redis.hget(key, field)
        if legacy_result is not None:
            value = legacy_result.decode('utf-8') if isinstance(legacy_result, bytes) else legacy_result
            logger.debug(f"🔄 Fallback HGET: {key}.{field} → migrando")
            # Migrar campo específico
            self.redis.hset(namespaced_key, field, legacy_result)
            return value
        
        return None
    
    def hset(self, key: str, field: Optional[str] = None, value: Optional[str] = None, 
             mapping: Optional[Dict[str, str]] = None) -> int:
        """
        Define campo(s) em hash (SEMPRE no namespace isolado).
        
        Args:
            key: Nome do hash
            field: Campo específico (ou None se usando mapping)
            value: Valor do campo (ou None se usando mapping)
            mapping: Dict com múltiplos campos
            
        Returns:
            Número de campos adicionados
        """
        namespaced_key = self._key(key)
        
        try:
            if mapping:
                # Converter valores para bytes/strings
                clean_mapping = {}
                for k, v in mapping.items():
                    if isinstance(v, (dict, list)):
                        clean_mapping[k] = json.dumps(v)
                    else:
                        clean_mapping[k] = str(v) if v is not None else ""
                return self.redis.hset(namespaced_key, mapping=clean_mapping)
            elif field is not None:
                str_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                return self.redis.hset(namespaced_key, field, str_value)
            else:
                raise ValueError("hset requer 'mapping' ou 'field+value'")
        except Exception as e:
            logger.error(f"❌ Erro ao HSET {namespaced_key}: {e}")
            return 0
    
    def hgetall(self, key: str) -> Dict[str, str]:
        """
        Obtém todos os campos de hash (com fallback).
        """
        namespaced_key = self._key(key)
        
        # Tentar namespace novo
        result = self.redis.hgetall(namespaced_key)
        if result:
            return {k.decode('utf-8') if isinstance(k, bytes) else k: 
                    v.decode('utf-8') if isinstance(v, bytes) else v 
                    for k, v in result.items()}
        
        # Fallback: tentar namespace global
        legacy_result = self.redis.hgetall(key)
        if legacy_result:
            logger.debug(f"🔄 Fallback HGETALL: {key} → migrando para {namespaced_key}")
            decoded = {k.decode('utf-8') if isinstance(k, bytes) else k: 
                      v.decode('utf-8') if isinstance(v, bytes) else v 
                      for k, v in legacy_result.items()}
            # Migrar hash completo
            self.redis.hset(namespaced_key, mapping=legacy_result)
            return decoded
        
        return {}
    
    def hdel(self, key: str, *fields) -> int:
        """Remove campo(s) de hash."""
        namespaced_key = self._key(key)
        return self.redis.hdel(namespaced_key, *fields)
    
    def hkeys(self, key: str) -> List[str]:
        """Lista todos os campos de hash."""
        namespaced_key = self._key(key)
        keys = self.redis.hkeys(namespaced_key)
        return [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
    
    def hvals(self, key: str) -> List[str]:
        """Lista todos os valores de hash."""
        namespaced_key = self._key(key)
        vals = self.redis.hvals(namespaced_key)
        return [v.decode('utf-8') if isinstance(v, bytes) else v for v in vals]
    
    # =====================================================================
    # OPERAÇÕES INCR/DECR (CONTADORES)
    # =====================================================================
    
    def incr(self, key: str, amount: int = 1) -> int:
        """
        Incrementa contador (SEMPRE no namespace isolado).
        
        Returns:
            Novo valor do contador
        """
        namespaced_key = self._key(key)
        return self.redis.incr(namespaced_key, amount)
    
    def decr(self, key: str, amount: int = 1) -> int:
        """Decrementa contador."""
        namespaced_key = self._key(key)
        return self.redis.decr(namespaced_key, amount)
    
    # =====================================================================
    # OPERAÇÕES DE SET (SADD, SMEMBERS, SREM)
    # =====================================================================
    
    def sadd(self, key: str, *members) -> int:
        """Adiciona membros a um set."""
        namespaced_key = self._key(key)
        return self.redis.sadd(namespaced_key, *members)
    
    def smembers(self, key: str) -> set:
        """Obtém todos os membros de um set (com fallback)."""
        namespaced_key = self._key(key)
        
        # Tentar namespace novo
        result = self.redis.smembers(namespaced_key)
        if result:
            return {m.decode('utf-8') if isinstance(m, bytes) else m for m in result}
        
        # Fallback
        legacy_result = self.redis.smembers(key)
        if legacy_result:
            decoded = {m.decode('utf-8') if isinstance(m, bytes) else m for m in legacy_result}
            logger.debug(f"🔄 Fallback SMEMBERS: {key} → migrando")
            # Migrar
            self.redis.sadd(namespaced_key, *legacy_result)
            return decoded
        
        return set()
    
    def srem(self, key: str, *members) -> int:
        """Remove membros de um set."""
        namespaced_key = self._key(key)
        return self.redis.srem(namespaced_key, *members)
    
    def sismember(self, key: str, member: str) -> bool:
        """Verifica se membro existe no set."""
        namespaced_key = self._key(key)
        return bool(self.redis.sismember(namespaced_key, member))
    
    # =====================================================================
    # OPERAÇÕES DE LOCK (DISTRIBUTED LOCKING)
    # =====================================================================
    
    def acquire_lock(self, lock_name: str, timeout: int = 30) -> bool:
        """
        Adquire lock distribuído (SET NX EX).
        
        Args:
            lock_name: Nome do lock
            timeout: TTL em segundos
            
        Returns:
            True se lock adquirido, False se já existe
        """
        namespaced_key = self._key(f"lock:{lock_name}")
        return bool(self.redis.set(namespaced_key, "1", nx=True, ex=timeout))
    
    def release_lock(self, lock_name: str) -> bool:
        """Libera lock distribuído."""
        namespaced_key = self._key(f"lock:{lock_name}")
        return bool(self.redis.delete(namespaced_key))
    
    # =====================================================================
    # OPERAÇÕES DE PUB/SUB (MESSAGING)
    # =====================================================================
    
    def publish(self, channel: str, message: str) -> int:
        """Publica mensagem em canal (com namespace)."""
        namespaced_channel = self._key(f"channel:{channel}")
        return self.redis.publish(namespaced_channel, message)
    
    # =====================================================================
    # OPERAÇÕES DE LIMPEZA (CLEANUP)
    # =====================================================================
    
    def clear_namespace(self, pattern: str = "*") -> int:
        """
        Remove todas as chaves do namespace do usuário (CUIDADO!).
        
        Args:
            pattern: Padrão de chaves a remover (padrão: todas)
            
        Returns:
            Número de chaves removidas
        """
        search_pattern = self._key(pattern)
        keys = self.redis.keys(search_pattern)
        if keys:
            return self.redis.delete(*keys)
        return 0
    
    def scan_keys(self, pattern: str = "*") -> List[str]:
        """Lista todas as chaves do namespace."""
        search_pattern = self._key(pattern)
        keys = self.redis.keys(search_pattern)
        return [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do namespace."""
        all_keys = self.scan_keys()
        return {
            "user_id": self.user_id,
            "namespace": self.prefix,
            "total_keys": len(all_keys),
            "keys": all_keys[:100]  # Limitar para não poluir logs
        }


# ============================================================================
# FACTORY PARA OBTER INSTÂNCIA (Helper)
# ============================================================================

def get_namespaced_redis(user_id: int) -> GrimBotsRedis:
    """
    Factory para obter instância de GrimBotsRedis.
    
    Args:
        user_id: ID do usuário
        
    Returns:
        Instância configurada do GrimBotsRedis
        
    Example:
        >>> redis = get_namespaced_redis(user_id=current_user.id)
        >>> redis.set("bot_status", "active")
    """
    return GrimBotsRedis(user_id=user_id)
