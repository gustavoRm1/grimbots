"""
Bot Intelligence Service - GrimBots
====================================
Serviço inteligente de seleção de bots com estratégias avançadas de load balancing.

Recursos:
- Round Robin (distribuição circular)
- Weighted Random (probabilidade proporcional)
- Least Connections (menor carga)
- Priority-based (prioridade configurada)
- Failover automático para bots degraded
"""

import logging
import random
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BotIntelligenceService:
    """
    🧠 Serviço de Inteligência de Seleção de Bots
    
    Implementa estratégias avançadas de distribuição:
    - round_robin: Um por vez, ciclo contínuo
    - weighted: Probabilidade baseada em peso
    - least_connections: Menor número de conexões ativas
    - priority: Ordem de prioridade configurada
    - random: Aleatório puro (fallback)
    """
    
    @classmethod
    def select_bot(cls, pool) -> Optional[Any]:
        """
        🎯 Seleciona o melhor bot baseado na estratégia do pool
        
        Args:
            pool: Instância de RedirectPool
            
        Returns:
            PoolBot selecionado ou None
        """
        try:
            strategy = getattr(pool, 'distribution_strategy', 'round_robin')
            
            # Obter bots elegíveis (enabled e não em circuit breaker)
            eligible_bots = cls._get_eligible_bots(pool)
            
            if not eligible_bots:
                # Fallback: tentar bots degraded (offline mas configurados)
                return cls._select_degraded_fallback(pool)
            
            # Aplicar estratégia de seleção
            if strategy == 'round_robin':
                return cls._strategy_round_robin(pool, eligible_bots)
            elif strategy == 'weighted':
                return cls._strategy_weighted(eligible_bots)
            elif strategy == 'least_connections':
                return cls._strategy_least_connections(eligible_bots)
            elif strategy == 'priority':
                return cls._strategy_priority(eligible_bots)
            else:
                # Fallback para random
                return cls._strategy_random(eligible_bots)
                
        except Exception as e:
            logger.error(f"❌ Erro na seleção de bot: {e}")
            return cls._select_any_available(pool)
    
    @classmethod
    def _get_eligible_bots(cls, pool) -> List[Any]:
        """
        🔍 Retorna bots elegíveis (online, enabled, sem circuit breaker)
        """
        eligible = []
        
        try:
            pool_bots = list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []
            
            for pool_bot in pool_bots:
                # Verificar se bot está habilitado
                if not getattr(pool_bot, 'is_enabled', True):
                    continue
                
                # Verificar status
                status = getattr(pool_bot, 'status', 'unknown')
                if status != 'online':
                    continue
                
                # Verificar circuit breaker
                circuit_until = getattr(pool_bot, 'circuit_breaker_until', None)
                if circuit_until and circuit_until > datetime.now():
                    continue
                
                eligible.append(pool_bot)
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao filtrar bots elegíveis: {e}")
        
        return eligible
    
    @classmethod
    def _strategy_round_robin(cls, pool, bots: List[Any]) -> Optional[Any]:
        """
        🔄 Estratégia Round Robin
        
        Mantém um índice rotativo baseado no total de redirects do pool.
        """
        if not bots:
            return None
        
        try:
            total_redirects = getattr(pool, 'total_redirects', 0)
            index = total_redirects % len(bots)
            return bots[index]
        except Exception:
            return bots[0] if bots else None
    
    @classmethod
    def _strategy_weighted(cls, bots: List[Any]) -> Optional[Any]:
        """
        ⚖️ Estratégia Weighted Random
        
        Probabilidade proporcional ao peso configurado.
        """
        if not bots:
            return None
        
        if len(bots) == 1:
            return bots[0]
        
        # Calcular pesos totais
        weights = []
        for bot in bots:
            weight = getattr(bot, 'weight', 1)
            weights.append(max(weight, 1))  # Mínimo 1
        
        total_weight = sum(weights)
        
        # Selecionar com base na probabilidade
        r = random.uniform(0, total_weight)
        cumulative = 0
        
        for i, bot in enumerate(bots):
            cumulative += weights[i]
            if r <= cumulative:
                return bot
        
        return bots[-1]  # Fallback para último
    
    @classmethod
    def _strategy_least_connections(cls, bots: List[Any]) -> Optional[Any]:
        """
        📉 Estratégia Least Connections
        
        Seleciona o bot com menos conexões ativas.
        """
        if not bots:
            return None
        
        # Ordenar por total_redirects (proxy para carga)
        sorted_bots = sorted(bots, key=lambda b: getattr(b, 'total_redirects', 0))
        return sorted_bots[0] if sorted_bots else None
    
    @classmethod
    def _strategy_priority(cls, bots: List[Any]) -> Optional[Any]:
        """
        🎯 Estratégia Priority-based
        
        Seleciona o bot com maior prioridade configurada.
        """
        if not bots:
            return None
        
        # Ordenar por prioridade (maior primeiro)
        sorted_bots = sorted(
            bots, 
            key=lambda b: getattr(b, 'priority', 0), 
            reverse=True
        )
        return sorted_bots[0] if sorted_bots else None
    
    @classmethod
    def _strategy_random(cls, bots: List[Any]) -> Optional[Any]:
        """
        🎲 Estratégia Random
        
        Seleção puramente aleatória.
        """
        return random.choice(bots) if bots else None
    
    @classmethod
    def _select_degraded_fallback(cls, pool) -> Optional[Any]:
        """
        🔄 Fallback para bots degraded
        
        Quando nenhum bot está 100% online, tenta:
        1. Bot com menos falhas consecutivas
        2. Bot que ficou offline mais recentemente
        3. Qualquer bot configurado
        """
        try:
            pool_bots = list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []
            
            if not pool_bots:
                return None
            
            # Tentar encontrar bot com menos falhas
            sorted_by_failures = sorted(
                pool_bots,
                key=lambda b: getattr(b, 'consecutive_failures', 0)
            )
            
            # Retornar o com menos falhas (mesmo se offline)
            best_candidate = sorted_by_failures[0]
            
            logger.warning(
                f"🔄 Fallback degraded: bot_id={best_candidate.bot_id} "
                f"(falhas={getattr(best_candidate, 'consecutive_failures', 0)}, "
                f"status={getattr(best_candidate, 'status', 'unknown')})"
            )
            
            return best_candidate
            
        except Exception as e:
            logger.error(f"❌ Erro no fallback degraded: {e}")
            return None
    
    @classmethod
    def _select_any_available(cls, pool) -> Optional[Any]:
        """
        🆘 Último recurso: qualquer bot disponível
        """
        try:
            pool_bots = list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []
            return pool_bots[0] if pool_bots else None
        except Exception:
            return None
    
    @classmethod
    def get_bot_telegram_url(cls, pool_bot) -> Optional[str]:
        """
        🔗 Extrai URL do Telegram do bot
        
        Args:
            pool_bot: Instância de PoolBot
            
        Returns:
            str: URL do Telegram ou None
        """
        try:
            bot = getattr(pool_bot, 'bot', None)
            if not bot:
                return None
            
            # Tentar username primeiro
            username = getattr(bot, 'username', None)
            if username:
                return f"https://t.me/{username}"
            
            # Fallback: extrair do token
            token = getattr(bot, 'token', '')
            if token and ':' in token:
                parts = token.split(':')
                if len(parts) > 1:
                    username_part = parts[1].split('-')[0]
                    return f"https://t.me/{username_part}"
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao extrair URL do bot: {e}")
            return None
