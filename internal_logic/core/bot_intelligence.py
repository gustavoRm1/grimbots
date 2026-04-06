"""
🤖 BOT INTELLIGENCE SERVICE
Módulo de Seleção Inteligente de Bots + Circuit Breaker

Extraído de: internal_logic/core/models.py (RedirectPool.select_bot) + botmanager.py (linhas 9649-9818)
Responsabilidade: Distribuição de tráfego, health management, circuit breaker
"""

import random
import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, update as sql_update

logger = logging.getLogger(__name__)


class DistributionStrategy(Enum):
    """Estratégias de distribuição de tráfego"""
    ROUND_ROBIN = 'round_robin'
    RANDOM = 'random'
    LEAST_CONNECTIONS = 'least_connections'
    WEIGHTED = 'weighted'


class ErrorBucket(Enum):
    """Classificação de erros do Telegram"""
    BOT_FATAL = 'bot_fatal'      # Token inválido, banido, etc
    USER_FATAL = 'user_fatal'    # Erro do usuário (não punir bot)
    RETRYABLE = 'retryable'      # Erros transitórios (timeout, flood...)


class BotStatus(Enum):
    """Status de saúde do bot"""
    ONLINE = 'online'
    OFFLINE = 'offline'
    DEGRADED = 'degraded'
    UNKNOWN = 'unknown'


@dataclass
class BotSelectionResult:
    """Resultado da seleção de bot"""
    bot_id: int
    pool_bot_id: int
    username: str
    token: str
    weight: int
    priority: int
    status: str
    consecutive_failures: int
    is_fallback: bool = False
    strategy_used: str = ''


@dataclass
class CircuitBreakerState:
    """Estado do Circuit Breaker para um bot"""
    consecutive_failures: int = 0
    circuit_breaker_until: Optional[datetime] = None
    health_status: str = 'online'
    last_error: Optional[str] = None
    error_count: int = 0


class BotIntelligenceService:
    """
    🤖 CÉREBRO DO REDIRECIONAMENTO
    
    Implementa:
    - 4 estratégias de distribuição (round_robin, random, least_connections, weighted)
    - Circuit Breaker com classificação de erros
    - Health check automático
    - Failover para bots degradados
    """
    
    # Palavras-chave para classificação de erros
    BOT_FATAL_KEYWORDS: List[str] = [
        'unauthorized',
        'token is invalid',
        'bot token is invalid',
        '401',
        'bot was banned',
        'this bot has been blocked',
        'terminated by other getupdates request',
        'token revoked',
        'token not found',
        'forbidden'
    ]
    
    RETRYABLE_KEYWORDS: List[str] = [
        'too many requests',
        'retry_after',
        'flood',
        '429',
        '500',
        '502',
        '503',
        '504',
        'bad gateway',
        'service unavailable',
        'gateway timeout',
        'internal server error',
        'connection',
        'timeout',
        'timed out',
        'network',
        'remotedisconnected',
        'connectionreset',
        'connectionrefused',
        'migrate_to_chat_id',
        'retry'
    ]
    
    USER_FATAL_KEYWORDS: List[str] = [
        'user is deactivated',
        'chat not found',
        'bot was blocked by the user',
        'user not found',
        'forbidden: bot was blocked',
        'not enough rights',
        'have no rights'
    ]
    
    def __init__(self, db_session: Session, redis_client=None):
        """
        Inicializa o serviço de inteligência de bots
        
        Args:
            db_session: Sessão SQLAlchemy
            redis_client: Cliente Redis opcional para cache de estado
        """
        self.db = db_session
        self.redis = redis_client
        self._round_robin_indices: Dict[int, int] = {}  # pool_id -> índice atual
    
    # ============================================================================
    # SELEÇÃO DE BOTS - 4 ESTRATÉGIAS
    # ============================================================================
    
    def select_bot(
        self,
        pool_id: int,
        strategy: DistributionStrategy = DistributionStrategy.ROUND_ROBIN,
        exclude_offline: bool = True
    ) -> Optional[BotSelectionResult]:
        """
        Seleciona bot baseado na estratégia configurada
        
        Args:
            pool_id: ID do pool
            strategy: Estratégia de distribuição
            exclude_offline: Se True, ignora bots offline/degraded
            
        Returns:
            BotSelectionResult ou None se nenhum bot disponível
        """
        from internal_logic.core.models import PoolBot, Bot
        
        # Buscar bots habilitados do pool
        query = self.db.query(PoolBot).filter(
            and_(
                PoolBot.pool_id == pool_id,
                PoolBot.is_enabled == True
            )
        ).join(Bot)
        
        # Filtrar por status (se exclude_offline=True)
        if exclude_offline:
            query = query.filter(PoolBot.status == BotStatus.ONLINE.value)
        
        pool_bots = query.all()
        
        if not pool_bots:
            # 🔄 FAILOVER: Tentar bots degradados
            logger.warning(f"🔄 Pool {pool_id}: Nenhum bot online, tentando degradados...")
            degraded = self._get_best_degraded_bot(pool_id)
            if degraded:
                return BotSelectionResult(
                    bot_id=degraded.bot.id,
                    pool_bot_id=degraded.id,
                    username=degraded.bot.username,
                    token=degraded.bot.token,
                    weight=degraded.weight or 1,
                    priority=degraded.priority or 0,
                    status=degraded.status,
                    consecutive_failures=degraded.consecutive_failures or 0,
                    is_fallback=True,
                    strategy_used='degraded_fallback'
                )
            return None
        
        # Aplicar estratégia de seleção
        if strategy == DistributionStrategy.ROUND_ROBIN:
            selected = self._select_round_robin(pool_id, pool_bots)
        elif strategy == DistributionStrategy.RANDOM:
            selected = self._select_random(pool_bots)
        elif strategy == DistributionStrategy.LEAST_CONNECTIONS:
            selected = self._select_least_connections(pool_bots)
        elif strategy == DistributionStrategy.WEIGHTED:
            selected = self._select_weighted(pool_bots)
        else:
            selected = self._select_round_robin(pool_id, pool_bots)
        
        if not selected:
            return None
        
        return BotSelectionResult(
            bot_id=selected.bot.id,
            pool_bot_id=selected.id,
            username=selected.bot.username,
            token=selected.bot.token,
            weight=selected.weight or 1,
            priority=selected.priority or 0,
            status=selected.status,
            consecutive_failures=selected.consecutive_failures or 0,
            is_fallback=False,
            strategy_used=strategy.value
        )
    
    def _select_round_robin(self, pool_id: int, pool_bots: List[Any]) -> Optional[Any]:
        """
        Round Robin: Seleciona o bot com menos redirects totais
        Mantém estado do índice para distribuição justa
        """
        if not pool_bots:
            return None
        
        # Ordenar por total_redirects (menor primeiro)
        sorted_bots = sorted(pool_bots, key=lambda b: b.total_redirects or 0)
        return sorted_bots[0]
    
    def _select_random(self, pool_bots: List[Any]) -> Optional[Any]:
        """Random: Seleção aleatória pura"""
        if not pool_bots:
            return None
        return random.choice(pool_bots)
    
    def _select_least_connections(self, pool_bots: List[Any]) -> Optional[Any]:
        """
        Least Connections: Seleciona o bot com menos conexões ativas
        Ideal para requests de longa duração
        """
        if not pool_bots:
            return None
        return min(pool_bots, key=lambda b: b.active_connections or 0)
    
    def _select_weighted(self, pool_bots: List[Any]) -> Optional[Any]:
        """
        Weighted: Seleção ponderada baseada no campo weight
        Bots com maior weight têm mais chance de serem selecionados
        """
        if not pool_bots:
            return None
        
        # Filtrar apenas bots com weight > 0
        valid_bots = [b for b in pool_bots if (b.weight or 1) > 0]
        if not valid_bots:
            return pool_bots[0]
        
        # Calcular peso total
        total_weight = sum(b.weight or 1 for b in valid_bots)
        
        # Sortear número entre 0 e total_weight
        pick = random.uniform(0, total_weight)
        current = 0
        
        for bot in valid_bots:
            current += bot.weight or 1
            if current >= pick:
                return bot
        
        # Fallback (não deveria acontecer)
        return valid_bots[-1]
    
    def _get_best_degraded_bot(self, pool_id: int) -> Optional[Any]:
        """
        FAILOVER: Retorna o bot degradado com menos falhas consecutivas
        """
        from internal_logic.core.models import PoolBot
        
        return self.db.query(PoolBot).filter(
            and_(
                PoolBot.pool_id == pool_id,
                PoolBot.is_enabled == True,
                PoolBot.status == BotStatus.DEGRADED.value,
                or_(
                    PoolBot.circuit_breaker_until == None,
                    PoolBot.circuit_breaker_until <= datetime.now()
                )
            )
        ).order_by(PoolBot.consecutive_failures.asc()).first()
    
    # ============================================================================
    # CIRCUIT BREAKER
    # ============================================================================
    
    def classify_telegram_error(self, error_str: str) -> ErrorBucket:
        """
        Classifica erro do Telegram em 3 buckets:
        - BOT_FATAL: Token inválido, banido (desativar bot)
        - USER_FATAL: Erro do usuário (não punir bot)
        - RETRYABLE: Erros transitórios (aplicar backoff)
        
        Args:
            error_str: Mensagem de erro do Telegram
            
        Returns:
            ErrorBucket classificado
        """
        if not error_str:
            return ErrorBucket.RETRYABLE
        
        error_lower = error_str.lower()
        
        # Verificar BOT_FATAL (mais grave)
        for keyword in self.BOT_FATAL_KEYWORDS:
            if keyword in error_lower:
                logger.error(f"🚫 BOT FATAL detectado: '{keyword}' em '{error_str[:100]}'")
                return ErrorBucket.BOT_FATAL
        
        # Verificar USER_FATAL (não punir bot)
        for keyword in self.USER_FATAL_KEYWORDS:
            if keyword in error_lower:
                logger.info(f"👤 USER FATAL detectado: '{keyword}' (bot não punido)")
                return ErrorBucket.USER_FATAL
        
        # Padrão: RETRYABLE
        for keyword in self.RETRYABLE_KEYWORDS:
            if keyword in error_lower:
                logger.warning(f"🔄 RETRYABLE detectado: '{keyword}'")
                return ErrorBucket.RETRYABLE
        
        # Fail-safe: se não identificar, considerar retryable
        logger.warning(f"❓ Erro não classificado, assumindo RETRYABLE: {error_str[:100]}")
        return ErrorBucket.RETRYABLE
    
    def apply_circuit_breaker(
        self,
        bot_id: int,
        pool_bot_id: int,
        error_bucket: ErrorBucket,
        error_description: str,
        threshold: int = 5,
        block_duration_minutes: int = 30
    ) -> bool:
        """
        Aplica Circuit Breaker baseado na classificação do erro
        
        Args:
            bot_id: ID do bot
            pool_bot_id: ID do pool_bot (associação)
            error_bucket: Classificação do erro
            error_description: Descrição do erro
            threshold: Número de falas antes do circuit breaker (default: 5)
            block_duration_minutes: Duração do bloqueio (default: 30 min)
            
        Returns:
            True se o bot foi desativado/bloqueado
        """
        from internal_logic.core.models import Bot, PoolBot
        
        # BOT_FATAL: Desativar bot IMEDIATAMENTE
        if error_bucket == ErrorBucket.BOT_FATAL:
            logger.critical(f"🚨 BOT FATAL: Desativando bot {bot_id} permanentemente")
            
            try:
                # Desativar no modelo Bot
                self.db.execute(
                    sql_update(Bot)
                    .where(Bot.id == bot_id)
                    .values(
                        is_active=False,
                        health_status='offline',
                        error_count=Bot.error_count + 1,
                        last_error=f"BOT_FATAL: {error_description[:500]}"
                    )
                )
                
                # Desativar no PoolBot
                self.db.execute(
                    sql_update(PoolBot)
                    .where(PoolBot.id == pool_bot_id)
                    .values(
                        status='offline',
                        consecutive_failures=PoolBot.consecutive_failures + 1
                    )
                )
                
                self.db.commit()
                
                # Desregistrar do Redis (se disponível)
                if self.redis:
                    self.redis.delete(f'bot:{bot_id}')
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao desativar bot {bot_id}: {e}")
                self.db.rollback()
                return False
        
        # RETRYABLE: Incrementar falhas e aplicar circuit breaker se necessário
        if error_bucket == ErrorBucket.RETRYABLE:
            try:
                # Buscar estado atual
                pool_bot = self.db.query(PoolBot).get(pool_bot_id)
                if not pool_bot:
                    return False
                
                new_failures = (pool_bot.consecutive_failures or 0) + 1
                
                if new_failures >= threshold:
                    # Aplicar circuit breaker
                    circuit_breaker_until = datetime.now() + timedelta(minutes=block_duration_minutes)
                    
                    self.db.execute(
                        sql_update(PoolBot)
                        .where(PoolBot.id == pool_bot_id)
                        .values(
                            consecutive_failures=new_failures,
                            status='degraded',
                            circuit_breaker_until=circuit_breaker_until,
                            last_error=error_description[:500]
                        )
                    )
                    
                    logger.warning(
                        f"⏸️ Circuit Breaker ativado para bot {bot_id}: "
                        f"{new_failures} falhas, bloqueado até {circuit_breaker_until}"
                    )
                else:
                    # Apenas incrementar contador
                    self.db.execute(
                        sql_update(PoolBot)
                        .where(PoolBot.id == pool_bot_id)
                        .values(
                            consecutive_failures=new_failures,
                            status='degraded',
                            last_error=error_description[:500]
                        )
                    )
                    
                    logger.info(
                        f"⚠️ Falha {new_failures}/{threshold} para bot {bot_id}"
                    )
                
                self.db.commit()
                return new_failures >= threshold
                
            except Exception as e:
                logger.error(f"❌ Erro no circuit breaker: {e}")
                self.db.rollback()
                return False
        
        # USER_FATAL: Não fazer nada (não punir bot por erro do usuário)
        if error_bucket == ErrorBucket.USER_FATAL:
            logger.info(f"👤 USER FATAL: Bot {bot_id} não punido")
            return False
        
        return False
    
    def reset_circuit_breaker_on_success(self, bot_id: int, pool_bot_id: int) -> bool:
        """
        Reseta Circuit Breaker quando mensagem é enviada com sucesso
        Só faz update se o bot estava machucado (consecutive_failures > 0 ou status != online)
        
        Args:
            bot_id: ID do bot
            pool_bot_id: ID do pool_bot
            
        Returns:
            True se foi resetado
        """
        from internal_logic.core.models import PoolBot
        
        try:
            pool_bot = self.db.query(PoolBot).get(pool_bot_id)
            if not pool_bot:
                return False
            
            # 🟢 Só faz update se o bot estava machucado!
            if (pool_bot.consecutive_failures or 0) > 0 or pool_bot.status != 'online':
                self.db.execute(
                    sql_update(PoolBot)
                    .where(PoolBot.id == pool_bot_id)
                    .values(
                        consecutive_failures=0,
                        status='online',
                        circuit_breaker_until=None,
                        last_health_check=datetime.now()
                    )
                )
                self.db.commit()
                
                logger.info(f"✅ Circuit Breaker resetado para bot {bot_id} (estava machucado)")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao resetar circuit breaker: {e}")
            self.db.rollback()
            return False
    
    def is_circuit_breaker_active(self, pool_bot_id: int) -> bool:
        """
        Verifica se o circuit breaker está ativo para um bot
        
        Args:
            pool_bot_id: ID do pool_bot
            
        Returns:
            True se estiver bloqueado
        """
        from internal_logic.core.models import PoolBot
        
        try:
            pool_bot = self.db.query(PoolBot).get(pool_bot_id)
            if not pool_bot:
                return True  # Bot não existe = bloqueado
            
            # Verificar circuit breaker
            if pool_bot.circuit_breaker_until:
                if pool_bot.circuit_breaker_until > datetime.now():
                    return True  # Ainda bloqueado
                else:
                    # Liberado - limpar campo
                    self.db.execute(
                        sql_update(PoolBot)
                        .where(PoolBot.id == pool_bot_id)
                        .values(circuit_breaker_until=None)
                    )
                    self.db.commit()
                    return False
            
            # Verificar se está offline ou degradado
            if pool_bot.status in ('offline', 'unknown'):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar circuit breaker: {e}")
            return True  # Em caso de erro, considerar bloqueado
    
    # ============================================================================
    # HEALTH CHECK
    # ============================================================================
    
    async def validate_bot_token(
        self,
        token: str,
        http_client: Callable
    ) -> Dict[str, Any]:
        """
        Valida token do Telegram via API
        
        Args:
            token: Token do bot Telegram
            http_client: Função async para fazer requests HTTP
            
        Returns:
            Dict com resultado da validação
        """
        try:
            result = await http_client(f"https://api.telegram.org/bot{token}/getMe")
            
            if result.get('ok'):
                return {
                    'valid': True,
                    'bot_info': result.get('result', {}),
                    'error': None
                }
            else:
                return {
                    'valid': False,
                    'bot_info': None,
                    'error': result.get('description', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'valid': False,
                'bot_info': None,
                'error': str(e)
            }
    
    def update_pool_health(self, pool_id: int) -> int:
        """
        Atualiza health score de um pool baseado nos bots ativos
        
        Args:
            pool_id: ID do pool
            
        Returns:
            Health score (0-100)
        """
        from internal_logic.core.models import PoolBot, RedirectPool
        
        try:
            # Contar bots ativos
            total_bots = self.db.query(PoolBot).filter(
                PoolBot.pool_id == pool_id
            ).count()
            
            if total_bots == 0:
                health_score = 0
            else:
                active_bots = self.db.query(PoolBot).filter(
                    and_(
                        PoolBot.pool_id == pool_id,
                        PoolBot.is_enabled == True,
                        PoolBot.status == 'online'
                    )
                ).count()
                
                health_score = int((active_bots / total_bots) * 100)
            
            # Atualizar pool
            self.db.execute(
                sql_update(RedirectPool)
                .where(RedirectPool.id == pool_id)
                .values(health_score=health_score)
            )
            self.db.commit()
            
            logger.info(f"📊 Health score do pool {pool_id}: {health_score}%")
            return health_score
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar health do pool {pool_id}: {e}")
            self.db.rollback()
            return 0


# Factory function
def get_bot_intelligence_service(db_session: Session, redis_client=None) -> BotIntelligenceService:
    """
    Factory para obter instância do BotIntelligenceService
    
    Args:
        db_session: Sessão SQLAlchemy
        redis_client: Cliente Redis opcional
        
    Returns:
        Instância de BotIntelligenceService
    """
    return BotIntelligenceService(db_session, redis_client)
