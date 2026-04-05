"""
Redis Bot State V2 - Estado Isolado por User ID
================================================

Versão refatorada do RedisBotState que utiliza namespace isolado por user_id,
eliminando interferência entre usuários ("comportamento de lua").

Migração automática:
- Lê do namespace antigo se não encontrar no novo
- Sempre salva no namespace novo
- Bots "migram sozinhos" conforme são usados

Padrão de chaves:
- gb:{user_id}:bots:active        (antigo: botmanager:active_bots)
- gb:{user_id}:bot:{bot_id}:data  (antigo: bot:{bot_id}:heartbeat)
- gb:{user_id}:lock:autostart:{bot_id} (antigo: botmanager:autostart_lock:{bot_id})
"""

import json
import time
import os
import logging
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Importar o novo wrapper namespaced
from internal_logic.core.redis_wrapper import GrimBotsRedis, get_namespaced_redis

logger = logging.getLogger(__name__)


class NamespacedRedisBotState:
    """
    Gerenciador de estado de bots com isolamento por user_id.
    
    Cada usuário tem seu próprio namespace no Redis, garantindo que:
    - Bot ID 123 do User A não interfere no Bot ID 123 do User B
    - Locks, heartbeats e configs são completamente isolados
    - Escalabilidade horizontal por usuário
    
    Args:
        user_id: ID do usuário dono dos bots (obrigatório)
        
    Example:
        >>> state = NamespacedRedisBotState(user_id=42)
        >>> state.register_bot(bot_id=123, token="abc", config={})
        # Registra em: gb:42:bots:active e gb:42:bot:123:data
    """
    
    # Nomes das chaves (sem prefixo - o wrapper adiciona gb:{user_id}:)
    ACTIVE_BOTS_HASH = "bots:active"
    BOT_DATA_PREFIX = "bot:{bot_id}:data"
    BOT_HEARTBEAT_PREFIX = "bot:{bot_id}:heartbeat"
    AUTOSTART_LOCK_PREFIX = "lock:autostart:{bot_id}"
    SCHEDULER_JOBS_HASH = "scheduler:downsell_jobs"
    
    def __init__(self, user_id: int):
        if not user_id or not isinstance(user_id, int):
            raise ValueError(f"user_id é obrigatório e deve ser inteiro, recebido: {user_id}")
        
        self.user_id = user_id
        self.redis = get_namespaced_redis(user_id)
        self._heartbeat_ttl = 300  # 5 minutos
        self._autostart_lock_ttl = 30  # 30 segundos
        self._heartbeat_threads: Dict[int, threading.Thread] = {}
        
        logger.info(f"✅ NamespacedRedisBotState inicializado para user_id={user_id}")
    
    # ========================================================================
    # BOT STATE MANAGEMENT
    # ========================================================================
    
    def register_bot(self, bot_id: int, token: str, config: Dict[str, Any], 
                     worker_pid: int = None) -> bool:
        """
        Registra um bot como ativo no namespace do usuário.
        
        Args:
            bot_id: ID do bot
            token: Token do Telegram
            config: Configuração do bot
            worker_pid: PID do worker
            
        Returns:
            True se registrado com sucesso
        """
        try:
            bot_data = {
                'bot_id': bot_id,
                'user_id': self.user_id,  # ✅ Explicitar user_id
                'token': token,
                'config': json.dumps(config),
                'started_at': time.time(),
                'worker_pid': worker_pid or os.getpid(),
                'last_heartbeat': time.time(),
                'status': 'active'
            }
            
            # Salvar no hash de bots ativos (namespace isolado)
            self.redis.hset(
                self.ACTIVE_BOTS_HASH,
                field=str(bot_id),
                value=json.dumps(bot_data)
            )
            
            # Criar heartbeat key com TTL
            self._update_heartbeat(bot_id)
            
            logger.info(f"✅ Bot {bot_id} registrado no Redis para user_id={self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar bot {bot_id} para user {self.user_id}: {e}")
            return False
    
    def unregister_bot(self, bot_id: int) -> bool:
        """
        Remove um bot do estado ativo.
        """
        try:
            # Remover do hash de bots ativos
            self.redis.hdel(self.ACTIVE_BOTS_HASH, str(bot_id))
            
            # Remover heartbeat
            heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
            self.redis.delete(heartbeat_key)
            
            # Parar thread de heartbeat
            if bot_id in self._heartbeat_threads:
                # Thread vai morrer naturalmente na próxima verificação
                del self._heartbeat_threads[bot_id]
            
            logger.info(f"✅ Bot {bot_id} removido do Redis para user_id={self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover bot {bot_id} para user {self.user_id}: {e}")
            return False
    
    def is_bot_active(self, bot_id: int) -> bool:
        """
        Verifica se bot está ativo (existe no hash E tem heartbeat válido).
        """
        try:
            # Verificar se existe no hash
            bot_data_raw = self.redis.hget(self.ACTIVE_BOTS_HASH, str(bot_id))
            if not bot_data_raw:
                return False
            
            # Verificar heartbeat
            heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
            if not self.redis.exists(heartbeat_key):
                # Bot sem heartbeat = stale entry
                logger.warning(f"⚠️ Bot {bot_id} sem heartbeat para user {self.user_id} - removendo stale")
                self.redis.hdel(self.ACTIVE_BOTS_HASH, str(bot_id))
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar status do bot {bot_id}: {e}")
            return False
    
    def get_bot_data(self, bot_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtém dados de um bot específico.
        """
        try:
            bot_data_raw = self.redis.hget(self.ACTIVE_BOTS_HASH, str(bot_id))
            if not bot_data_raw:
                return None
            
            bot_data = json.loads(bot_data_raw)
            bot_data['config'] = json.loads(bot_data.get('config', '{}'))
            return bot_data
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter dados do bot {bot_id}: {e}")
            return None
    
    def get_all_active_bots(self) -> Dict[int, Dict[str, Any]]:
        """
        Retorna todos os bots ativos do usuário (com heartbeat válido).
        
        Returns:
            Dict {bot_id: bot_data} apenas para este user_id
        """
        try:
            all_bots_raw = self.redis.hgetall(self.ACTIVE_BOTS_HASH)
            active_bots = {}
            
            for bot_id_str, bot_data_raw in all_bots_raw.items():
                try:
                    bot_id = int(bot_id_str)
                    
                    # Verificar heartbeat
                    heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
                    if not self.redis.exists(heartbeat_key):
                        # Stale entry - remover
                        self.redis.hdel(self.ACTIVE_BOTS_HASH, bot_id_str)
                        continue
                    
                    bot_data = json.loads(bot_data_raw)
                    bot_data['config'] = json.loads(bot_data.get('config', '{}'))
                    active_bots[bot_id] = bot_data
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao processar bot {bot_id_str}: {e}")
                    continue
            
            logger.info(f"📊 User {self.user_id} tem {len(active_bots)} bots ativos")
            return active_bots
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter bots ativos para user {self.user_id}: {e}")
            return {}
    
    def update_bot_config(self, bot_id: int, config: Dict[str, Any]) -> bool:
        """
        Atualiza configuração de um bot.
        """
        try:
            bot_data = self.get_bot_data(bot_id)
            if not bot_data:
                logger.warning(f"⚠️ Bot {bot_id} não encontrado para atualizar config")
                return False
            
            # Atualizar config
            bot_data['config'] = json.dumps(config)
            bot_data['updated_at'] = time.time()
            
            self.redis.hset(
                self.ACTIVE_BOTS_HASH,
                field=str(bot_id),
                value=json.dumps(bot_data)
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar config do bot {bot_id}: {e}")
            return False
    
    # ========================================================================
    # HEARTBEAT MANAGEMENT
    # ========================================================================
    
    def _update_heartbeat(self, bot_id: int) -> bool:
        """
        Atualiza heartbeat de um bot (TTL = 5 min).
        """
        try:
            heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
            return self.redis.set(heartbeat_key, str(time.time()), ex=self._heartbeat_ttl)
        except Exception as e:
            logger.error(f"❌ Erro no heartbeat do bot {bot_id}: {e}")
            return False
    
    def start_heartbeat_thread(self, bot_id: int, interval: int = 60) -> threading.Thread:
        """
        Inicia thread de heartbeat para manter bot ativo.
        """
        def heartbeat_loop():
            while self.is_bot_active(bot_id):
                self._update_heartbeat(bot_id)
                time.sleep(interval)
            logger.info(f"🛑 Heartbeat thread encerrada para bot {bot_id}")
        
        thread = threading.Thread(target=heartbeat_loop, daemon=True)
        thread.start()
        self._heartbeat_threads[bot_id] = thread
        logger.info(f"💓 Heartbeat iniciado para bot {bot_id} (intervalo: {interval}s)")
        return thread
    
    # ========================================================================
    # LOCK MANAGEMENT (AUTO-START)
    # ========================================================================
    
    def acquire_autostart_lock(self, bot_id: int, timeout: int = 30) -> bool:
        """
        Adquire lock de auto-start para prevenir race conditions.
        """
        lock_name = self.AUTOSTART_LOCK_PREFIX.format(bot_id=bot_id)
        return self.redis.acquire_lock(lock_name, timeout=timeout)
    
    def release_autostart_lock(self, bot_id: int) -> bool:
        """
        Libera lock de auto-start.
        """
        lock_name = self.AUTOSTART_LOCK_PREFIX.format(bot_id=bot_id)
        return self.redis.release_lock(lock_name)
    
    def is_autostart_locked(self, bot_id: int) -> bool:
        """
        Verifica se existe um lock de auto-start ativo para o bot.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            True se lock existe (outro worker está iniciando), False se não
        """
        try:
            lock_name = self.AUTOSTART_LOCK_PREFIX.format(bot_id=bot_id)
            # Verificar se a chave de lock existe no Redis
            return self.redis.exists(lock_name)
        except Exception as e:
            logger.error(f"❌ Erro ao verificar lock de autostart do bot {bot_id}: {e}")
            return False
    
    def heartbeat(self, bot_id: int) -> bool:
        """
        Atualiza heartbeat de um bot (método público - alias para _update_heartbeat).
        
        Args:
            bot_id: ID do bot
            
        Returns:
            True se atualizado com sucesso
        """
        return self._update_heartbeat(bot_id)
    
    # ========================================================================
    # SCHEDULER JOBS (Downsell/Upsell)
    # ========================================================================
    
    def register_scheduler_job(self, job_id: str, bot_id: int, job_type: str, 
                              execute_at: float, payload: Dict) -> bool:
        """
        Registra um job agendado.
        """
        try:
            job_data = {
                'job_id': job_id,
                'bot_id': bot_id,
                'user_id': self.user_id,
                'type': job_type,
                'execute_at': execute_at,
                'payload': json.dumps(payload),
                'status': 'pending'
            }
            self.redis.hset(self.SCHEDULER_JOBS_HASH, field=job_id, value=json.dumps(job_data))
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao registrar job {job_id}: {e}")
            return False
    
    def get_pending_jobs(self, before_timestamp: float = None) -> List[Dict]:
        """
        Obtém jobs pendentes que devem ser executados.
        """
        try:
            all_jobs_raw = self.redis.hgetall(self.SCHEDULER_JOBS_HASH)
            pending_jobs = []
            now = time.time()
            
            for job_id, job_data_raw in all_jobs_raw.items():
                try:
                    job_data = json.loads(job_data_raw)
                    if job_data.get('status') != 'pending':
                        continue
                    
                    execute_at = job_data.get('execute_at', 0)
                    if before_timestamp is None or execute_at <= before_timestamp:
                        job_data['payload'] = json.loads(job_data.get('payload', '{}'))
                        pending_jobs.append(job_data)
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao processar job {job_id}: {e}")
                    continue
            
            return pending_jobs
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter jobs pendentes: {e}")
            return []
    
    def mark_job_completed(self, job_id: str) -> bool:
        """
        Marca job como completado.
        """
        try:
            job_data_raw = self.redis.hget(self.SCHEDULER_JOBS_HASH, job_id)
            if job_data_raw:
                job_data = json.loads(job_data_raw)
                job_data['status'] = 'completed'
                job_data['completed_at'] = time.time()
                self.redis.hset(self.SCHEDULER_JOBS_HASH, field=job_id, value=json.dumps(job_data))
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao marcar job {job_id} como completo: {e}")
            return False
    
    # ========================================================================
    # MÉTODOS DE LIMPEZA E UTILIDADE
    # ========================================================================
    
    def cleanup_stale_entries(self) -> int:
        """
        Remove entradas stale (bots sem heartbeat).
        
        Returns:
            Número de entradas removidas
        """
        removed = 0
        try:
            all_bots = self.redis.hgetall(self.ACTIVE_BOTS_HASH)
            for bot_id_str in all_bots.keys():
                try:
                    bot_id = int(bot_id_str)
                    heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
                    if not self.redis.exists(heartbeat_key):
                        self.redis.hdel(self.ACTIVE_BOTS_HASH, bot_id_str)
                        removed += 1
                        logger.info(f"🧹 Removido bot stale {bot_id} para user {self.user_id}")
                except:
                    continue
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {e}")
        
        return removed
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do estado do usuário.
        """
        active_bots = self.get_all_active_bots()
        return {
            'user_id': self.user_id,
            'active_bots_count': len(active_bots),
            'bot_ids': list(active_bots.keys()),
            'redis_keys': self.redis.scan_keys(),
            'heartbeat_threads': len(self._heartbeat_threads)
        }


# ============================================================================
# INSTÂNCIA GLOBAL (LEGACY) - Manter compatibilidade temporária
# ============================================================================

# Importar a instância original para fallback
from redis_bot_state import RedisBotState, redis_bot_state as _legacy_redis_bot_state

# Instância global será substituída gradualmente
# BotManager deve usar NamespacedRedisBotState(user_id=...) explicitamente

__all__ = ['NamespacedRedisBotState', 'get_namespaced_bot_state']
