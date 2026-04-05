"""
Redis Bot State - Centralização do "Cérebro" dos Bots
Substitui o dicionário self.active_bots volátil por Redis persistente.

⚠️ VERSÃO LEGACY - Mantida para compatibilidade retroativa
Para novo código, use: from internal_logic.core.redis_bot_state_v2 import NamespacedRedisBotState

Arquitetura:
- Hash Map: botmanager:active_bots - Dados dos bots ativos
- Keys com TTL: bot:{bot_id}:heartbeat - Heartbeat de cada bot
- Set: botmanager:started_bot_ids - IDs de bots iniciados (para quick lookup)
- Lock: botmanager:autostart_lock:{bot_id} - Prevenir race conditions no auto-start
"""

import json
import time
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Redis connection singleton
_redis_client = None

def get_redis_client():
    """Retorna cliente Redis singleton."""
    global _redis_client
    if _redis_client is None:
        import redis
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def get_namespaced_bot_state(user_id: int):
    """
    Factory para obter estado isolado por user_id.
    
    ✅ NOVO: Retorna NamespacedRedisBotState que garante isolamento.
    ✅ FALLBACK: Bots migram automaticamente do namespace global.
    
    Args:
        user_id: ID do usuário (obrigatório)
        
    Returns:
        NamespacedRedisBotState ou RedisBotState (legacy)
        
    Example:
        >>> # NOVO (recomendado) - Com namespace isolado
        >>> state = get_namespaced_bot_state(user_id=42)
        >>> state.register_bot(bot_id=123, token="abc", config={})
        
        >>> # LEGACY (mantido para compatibilidade)
        >>> redis_bot_state.register_bot(bot_id=123, ...)
    """
    try:
        from internal_logic.core.redis_bot_state_v2 import NamespacedRedisBotState
        return NamespacedRedisBotState(user_id=user_id)
    except ImportError as e:
        logger.warning(f"⚠️ NamespacedRedisBotState não disponível, usando legacy: {e}")
        return RedisBotState()


class RedisBotState:
    """
    Gerenciador centralizado de estado dos bots via Redis.
    Substitui o dicionário in-memory self.active_bots.
    
    ⚠️ ATENÇÃO: Esta classe usa namespace GLOBAL.
    Para isolamento por usuário, use get_namespaced_bot_state(user_id).
    """
    
    # Keys do Redis
    ACTIVE_BOTS_HASH = "botmanager:active_bots"
    BOT_HEARTBEAT_PREFIX = "bot:{bot_id}:heartbeat"
    AUTOSTART_LOCK_PREFIX = "botmanager:autostart_lock:{bot_id}"
    SCHEDULER_JOBS_HASH = "scheduler:downsell_jobs"
    
    def __init__(self):
        self.redis = get_redis_client()
        self._heartbeat_ttl = 300  # 5 minutos
        self._autostart_lock_ttl = 30  # 30 segundos
    
    # =========================================================================
    # BOT STATE MANAGEMENT
    # =========================================================================
    
    def register_bot(self, bot_id: int, token: str, config: Dict[str, Any], 
                     worker_pid: int = None) -> bool:
        """
        Registra um bot como ativo no Redis.
        
        Args:
            bot_id: ID do bot
            token: Token do Telegram
            config: Configuração do bot
            worker_pid: PID do worker que iniciou o bot
            
        Returns:
            True se registrado com sucesso
        """
        try:
            bot_data = {
                'bot_id': bot_id,
                'token': token,
                'config': json.dumps(config),
                'started_at': time.time(),
                'worker_pid': worker_pid or os.getpid(),
                'last_heartbeat': time.time(),
                'status': 'active'
            }
            
            # Salvar no hash map
            self.redis.hset(self.ACTIVE_BOTS_HASH, bot_id, json.dumps(bot_data))
            
            # Criar heartbeat key com TTL
            self._update_heartbeat(bot_id)
            
            logger.info(f"✅ Bot {bot_id} registrado no Redis (worker {bot_data['worker_pid']})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar bot {bot_id} no Redis: {e}")
            return False
    
    def unregister_bot(self, bot_id: int) -> bool:
        """
        Remove um bot do estado ativo.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            True se removido com sucesso
        """
        try:
            # Remover do hash map
            self.redis.hdel(self.ACTIVE_BOTS_HASH, bot_id)
            
            # Remover heartbeat
            self.redis.delete(self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id))
            
            logger.info(f"✅ Bot {bot_id} removido do Redis")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover bot {bot_id} do Redis: {e}")
            return False
    
    def is_bot_active(self, bot_id: int) -> bool:
        """
        Verifica se um bot está ativo (considerando heartbeat).
        
        Args:
            bot_id: ID do bot
            
        Returns:
            True se bot está ativo e com heartbeat recente
        """
        try:
            # Verificar se existe no hash
            bot_data_raw = self.redis.hget(self.ACTIVE_BOTS_HASH, bot_id)
            if not bot_data_raw:
                return False
            
            # Verificar heartbeat
            heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
            if not self.redis.exists(heartbeat_key):
                # Bot sem heartbeat = stale entry
                logger.warning(f"⚠️ Bot {bot_id} sem heartbeat - removendo entrada stale")
                self.redis.hdel(self.ACTIVE_BOTS_HASH, bot_id)
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar status do bot {bot_id}: {e}")
            return False
    
    def get_bot_data(self, bot_id: int) -> Optional[Dict[str, Any]]:
        """
        Retorna dados de um bot ativo.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            Dict com dados do bot ou None
        """
        try:
            bot_data_raw = self.redis.hget(self.ACTIVE_BOTS_HASH, bot_id)
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
        Retorna todos os bots ativos (com heartbeat válido).
        
        Returns:
            Dict {bot_id: bot_data}
        """
        try:
            all_bots_raw = self.redis.hgetall(self.ACTIVE_BOTS_HASH)
            active_bots = {}
            
            for bot_id, bot_data_raw in all_bots_raw.items():
                try:
                    bot_id = int(bot_id)
                    
                    # Verificar heartbeat
                    heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
                    if not self.redis.exists(heartbeat_key):
                        # Stale entry - remover
                        self.redis.hdel(self.ACTIVE_BOTS_HASH, bot_id)
                        continue
                    
                    bot_data = json.loads(bot_data_raw)
                    bot_data['config'] = json.loads(bot_data.get('config', '{}'))
                    active_bots[bot_id] = bot_data
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao processar bot {bot_id}: {e}")
                    continue
            
            return active_bots
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter bots ativos: {e}")
            return {}
    
    def update_bot_config(self, bot_id: int, config: Dict[str, Any]) -> bool:
        """
        Atualiza configuração de um bot ativo.
        
        Args:
            bot_id: ID do bot
            config: Nova configuração
            
        Returns:
            True se atualizado com sucesso
        """
        try:
            bot_data = self.get_bot_data(bot_id)
            if not bot_data:
                return False
            
            bot_data['config'] = config
            bot_data['updated_at'] = time.time()
            
            # Serializar config para JSON
            bot_data['config'] = json.dumps(config)
            
            self.redis.hset(self.ACTIVE_BOTS_HASH, bot_id, json.dumps(bot_data))
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar config do bot {bot_id}: {e}")
            return False
    
    # =========================================================================
    # HEARTBEAT MECHANISM
    # =========================================================================
    
    def _update_heartbeat(self, bot_id: int) -> bool:
        """Atualiza heartbeat de um bot."""
        try:
            heartbeat_key = self.BOT_HEARTBEAT_PREFIX.format(bot_id=bot_id)
            self.redis.setex(heartbeat_key, self._heartbeat_ttl, str(time.time()))
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar heartbeat do bot {bot_id}: {e}")
            return False
    
    def heartbeat(self, bot_id: int) -> bool:
        """
        Registra heartbeat de um bot (deve ser chamado periodicamente).
        
        Args:
            bot_id: ID do bot
            
        Returns:
            True se heartbeat registrado
        """
        return self._update_heartbeat(bot_id)
    
    def start_heartbeat_thread(self, bot_id: int, interval: int = 60):
        """
        Inicia thread de heartbeat para um bot.
        
        Args:
            bot_id: ID do bot
            interval: Intervalo em segundos entre heartbeats
        """
        import threading
        
        def _heartbeat_loop():
            while self.is_bot_active(bot_id):
                self.heartbeat(bot_id)
                time.sleep(interval)
        
        thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        thread.start()
        logger.info(f"✅ Heartbeat thread iniciada para bot {bot_id} (intervalo: {interval}s)")
    
    # =========================================================================
    # AUTO-START LOCK (Race Condition Prevention)
    # =========================================================================
    
    def acquire_autostart_lock(self, bot_id: int, timeout: int = 30) -> bool:
        """
        Adquire lock para auto-start de um bot.
        Previne race conditions onde múltiplos workers tentam iniciar o mesmo bot.
        
        Args:
            bot_id: ID do bot
            timeout: Timeout do lock em segundos
            
        Returns:
            True se lock adquirido
        """
        try:
            lock_key = self.AUTOSTART_LOCK_PREFIX.format(bot_id=bot_id)
            
            # NX = Only if Not eXists
            acquired = self.redis.set(lock_key, str(time.time()), nx=True, ex=timeout)
            
            if acquired:
                logger.debug(f"🔒 Lock de auto-start adquirido para bot {bot_id}")
                return True
            else:
                logger.debug(f"🔒 Lock de auto-start NÃO adquirido para bot {bot_id} (já em uso)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao adquirir lock de auto-start para bot {bot_id}: {e}")
            return False
    
    def release_autostart_lock(self, bot_id: int) -> bool:
        """
        Libera lock de auto-start.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            True se lock liberado
        """
        try:
            lock_key = self.AUTOSTART_LOCK_PREFIX.format(bot_id=bot_id)
            self.redis.delete(lock_key)
            logger.debug(f"🔓 Lock de auto-start liberado para bot {bot_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao liberar lock de auto-start para bot {bot_id}: {e}")
            return False
    
    def is_autostart_locked(self, bot_id: int) -> bool:
        """
        Verifica se auto-start está bloqueado por outro worker.
        
        Args:
            bot_id: ID do bot
            
        Returns:
            True se lock existe (outro worker está iniciando)
        """
        try:
            lock_key = self.AUTOSTART_LOCK_PREFIX.format(bot_id=bot_id)
            return self.redis.exists(lock_key) > 0
        except Exception as e:
            logger.error(f"❌ Erro ao verificar lock de auto-start para bot {bot_id}: {e}")
            return False  # Em caso de erro, permitir (fail open)
    
    # =========================================================================
    # SCHEDULER JOB MANAGEMENT
    # =========================================================================
    
    def register_downsell_job(self, payment_id: str, bot_id: int, 
                               job_id: str, run_time: float) -> bool:
        """
        Registra um job de downsell no Redis.
        
        Args:
            payment_id: ID do pagamento
            bot_id: ID do bot
            job_id: ID do job do APScheduler
            run_time: Timestamp de execução
            
        Returns:
            True se registrado
        """
        try:
            job_data = {
                'payment_id': payment_id,
                'bot_id': bot_id,
                'job_id': job_id,
                'run_time': run_time,
                'scheduled_at': time.time()
            }
            
            self.redis.hset(self.SCHEDULER_JOBS_HASH, job_id, json.dumps(job_data))
            logger.info(f"✅ Job de downsell registrado: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar job {job_id}: {e}")
            return False
    
    def get_downsell_jobs(self, payment_id: str = None) -> List[Dict[str, Any]]:
        """
        Retorna jobs de downsell registrados.
        
        Args:
            payment_id: Filtrar por payment_id (opcional)
            
        Returns:
            Lista de jobs
        """
        try:
            all_jobs_raw = self.redis.hgetall(self.SCHEDULER_JOBS_HASH)
            jobs = []
            
            for job_id, job_data_raw in all_jobs_raw.items():
                job_data = json.loads(job_data_raw)
                
                if payment_id and job_data.get('payment_id') != payment_id:
                    continue
                
                jobs.append(job_data)
            
            return jobs
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter jobs: {e}")
            return []
    
    def remove_downsell_job(self, job_id: str) -> bool:
        """
        Remove registro de um job de downsell.
        
        Args:
            job_id: ID do job
            
        Returns:
            True se removido
        """
        try:
            self.redis.hdel(self.SCHEDULER_JOBS_HASH, job_id)
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao remover job {job_id}: {e}")
            return False
    
    def cleanup_stale_jobs(self, max_age_hours: int = 24) -> int:
        """
        Limpa jobs antigos do Redis.
        
        Args:
            max_age_hours: Idade máxima em horas
            
        Returns:
            Número de jobs removidos
        """
        try:
            cutoff_time = time.time() - (max_age_hours * 3600)
            all_jobs_raw = self.redis.hgetall(self.SCHEDULER_JOBS_HASH)
            removed = 0
            
            for job_id, job_data_raw in all_jobs_raw.items():
                job_data = json.loads(job_data_raw)
                
                if job_data.get('scheduled_at', 0) < cutoff_time:
                    self.redis.hdel(self.SCHEDULER_JOBS_HASH, job_id)
                    removed += 1
            
            if removed > 0:
                logger.info(f"🧹 {removed} jobs stale removidos do Redis")
            
            return removed
            
        except Exception as e:
            logger.error(f"❌ Erro ao limpar jobs: {e}")
            return 0


# Instância global
redis_bot_state = RedisBotState()
