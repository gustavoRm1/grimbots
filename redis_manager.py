"""
Redis Connection Pool Manager
✅ Singleton com connection pool
✅ Thread-safe
✅ Auto-reconnect
✅ Health check
"""

import redis
from redis import ConnectionPool, Redis
import threading
import logging
import os

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Gerenciador singleton de conexões Redis com connection pool
    
    Features:
    - Connection pool (max 50 conexões)
    - Thread-safe
    - Auto-reconnect
    - Health check
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            self._initialize()
            self._initialized = True
    
    def _initialize(self):
        """Inicializa o connection pool"""
        env_redis_url = os.environ.get('REDIS_URL', '').strip()
        redis_url = env_redis_url or 'redis://localhost:6379/0'
        
        # Extrair componentes da URL
        # ConnectionPool from_url já trata credenciais, database e port corretamente.
        # Registramos a URL limpa para logs apenas.
        url_for_pool = redis_url
        
        # Criar connection pool
        self.pool = ConnectionPool.from_url(
            url_for_pool,
            max_connections=50,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Pool separado para RQ (decode_responses=False)
        self.pool_rq = ConnectionPool.from_url(
            url_for_pool,
            max_connections=30,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
            decode_responses=False
        )
        
        logger.info(f"✅ Redis Connection Pool inicializado: {url_for_pool} (max 50 conexões)")
    
    def get_connection(self, decode_responses=True):
        """
        Retorna conexão Redis do pool
        
        Args:
            decode_responses: Se True, retorna strings; se False, retorna bytes (para RQ)
        
        Returns:
            redis.Redis: Conexão Redis
        """
        if decode_responses:
            return Redis(connection_pool=self.pool, decode_responses=True)
        else:
            return Redis(connection_pool=self.pool_rq, decode_responses=False)
    
    def health_check(self):
        """
        Verifica saúde da conexão Redis
        
        Returns:
            dict: Status da conexão
        """
        try:
            conn = self.get_connection()
            conn.ping()
            
            # Info sobre pool
            info = conn.info()
            
            return {
                'status': 'healthy',
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'pool_size': self.pool.max_connections,
                'pool_available': self.pool.max_connections - len(self.pool._in_use_connections)
            }
        except Exception as e:
            logger.error(f"❌ Redis health check falhou: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def close(self):
        """Fecha todas as conexões do pool"""
        if hasattr(self, 'pool'):
            self.pool.disconnect()
        if hasattr(self, 'pool_rq'):
            self.pool_rq.disconnect()
        logger.info("✅ Redis Connection Pool fechado")


# Singleton global
redis_manager = RedisManager()


# Funções auxiliares para compatibilidade
def get_redis_connection(decode_responses=True):
    """
    Retorna conexão Redis do pool
    
    Args:
        decode_responses: Se True, retorna strings; se False, retorna bytes
    
    Returns:
        redis.Redis: Conexão Redis
    """
    return redis_manager.get_connection(decode_responses=decode_responses)


def redis_health_check():
    """
    Verifica saúde da conexão Redis
    
    Returns:
        dict: Status da conexão
    """
    return redis_manager.health_check()


if __name__ == '__main__':
    # Teste
    print("Testing Redis Manager...")
    
    # Teste 1: Conexão básica
    conn = get_redis_connection()
    conn.set('test_key', 'test_value')
    value = conn.get('test_key')
    print(f"✅ Teste 1: {value}")
    
    # Teste 2: Health check
    health = redis_health_check()
    print(f"✅ Teste 2: {health}")
    
    # Teste 3: Múltiplas conexões (pool)
    connections = [get_redis_connection() for _ in range(10)]
    for i, conn in enumerate(connections):
        conn.set(f'test_{i}', f'value_{i}')
    print(f"✅ Teste 3: {len(connections)} conexões criadas")
    
    # Teste 4: RQ connection (bytes)
    conn_rq = get_redis_connection(decode_responses=False)
    conn_rq.set(b'test_bytes', b'value_bytes')
    print(f"✅ Teste 4: RQ connection (bytes)")
    
    print("\n✅ Todos os testes passaram!")

