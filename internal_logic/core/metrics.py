"""
📊 METRICS SERVICE
Módulo de Métricas Atômicas para Evitar Deadlocks

Extraído de: app.py (linhas 6584-6610)
Responsabilidade: Incremento atômico de contadores via SQL UPDATE
"""

import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import update as sql_update, text, func
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class MetricsService:
    """
    📊 SERVIÇO DE MÉTRICAS ATÔMICAS
    
    Implementa padrão de UPDATE atômico SQL para evitar deadlocks:
    - Usa db.session.execute(update(...)) ao invés de SELECT + UPDATE
    - Usa COALESCE para tratar valores NULL
    - Não aborta em caso de erro (métricas são secundárias)
    
    Performance: ~1ms por operação (vs ~10-50ms para SELECT+UPDATE com lock)
    """
    
    def __init__(self, db_session: Session):
        """
        Inicializa o serviço de métricas
        
        Args:
            db_session: Sessão SQLAlchemy
        """
        self.db = db_session
    
    def increment_redirect_counters(
        self,
        pool_id: int,
        pool_bot_id: int,
        skip_on_error: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Incrementa contadores de redirects de forma atômica
        
        Atualiza:
        - PoolBot.total_redirects (redirects deste bot específico)
        - RedirectPool.total_visits (visits totais do pool)
        
        Args:
            pool_id: ID do pool
            pool_bot_id: ID do pool_bot
            skip_on_error: Se True, não levanta exceção em caso de erro
            
        Returns:
            Tuple (sucesso, dict com novos valores ou erro)
        """
        from internal_logic.core.models import PoolBot, RedirectPool
        
        result = {
            'pool_id': pool_id,
            'pool_bot_id': pool_bot_id,
            'pool_total': None,
            'bot_total': None,
            'error': None
        }
        
        try:
            # ✅ CORREÇÃO DEADLOCK: Usar UPDATE atômico
            # UPDATE atômico evita deadlocks e é mais eficiente
            # (1 query ao invés de SELECT + UPDATE com FOR UPDATE)
            
            # 1. Incrementar total_redirects do PoolBot
            self.db.execute(
                sql_update(PoolBot)
                .where(PoolBot.id == pool_bot_id)
                .values(
                    total_redirects=text('COALESCE(total_redirects, 0) + 1')
                )
            )
            
            # 2. Incrementar total_visits do RedirectPool
            self.db.execute(
                sql_update(RedirectPool)
                .where(RedirectPool.id == pool_id)
                .values(
                    total_visits=text('COALESCE(total_visits, 0) + 1')
                )
            )
            
            # Commit das alterações
            self.db.commit()
            
            # Buscar valores atualizados (apenas para logging)
            # Usamos query separada para não afetar a transação principal
            pool_bot = self.db.query(PoolBot).filter_by(id=pool_bot_id).first()
            pool = self.db.query(RedirectPool).filter_by(id=pool_id).first()
            
            if pool_bot:
                result['bot_total'] = pool_bot.total_redirects
            if pool:
                result['pool_total'] = pool.total_redirects
            
            logger.debug(
                f"📊 Métricas atualizadas: Pool {pool_id}={result['pool_total']}, "
                f"Bot {pool_bot_id}={result['bot_total']}"
            )
            
            return True, result
            
        except SQLAlchemyError as e:
            self.db.rollback()
            
            result['error'] = str(e)
            
            # ✅ Não abortar em caso de erro de métricas
            # O redirect deve continuar funcionando mesmo sem métricas
            if skip_on_error:
                logger.warning(
                    f"⚠️ Erro ao atualizar métricas de redirect (não crítico): {e}"
                )
                return False, result
            else:
                logger.error(f"❌ Erro fatal ao atualizar métricas: {e}")
                raise
        
        except Exception as e:
            self.db.rollback()
            result['error'] = str(e)
            
            if skip_on_error:
                logger.warning(f"⚠️ Erro inesperado nas métricas: {e}")
                return False, result
            else:
                raise
    
    def increment_bot_active_connections(
        self,
        pool_bot_id: int,
        increment: int = 1,
        skip_on_error: bool = True
    ) -> Tuple[bool, Optional[int]]:
        """
        Incrementa/decrementa conexões ativas de um bot
        
        Args:
            pool_bot_id: ID do pool_bot
            increment: Valor a incrementar (positivo para +, negativo para -)
            skip_on_error: Se True, não levanta exceção
            
        Returns:
            Tuple (sucesso, novo valor ou None)
        """
        from internal_logic.core.models import PoolBot
        
        try:
            # UPDATE atômico com COALESCE e garantia de não negativo
            self.db.execute(
                sql_update(PoolBot)
                .where(PoolBot.id == pool_bot_id)
                .values(
                    active_connections=text(
                        f'GREATEST(0, COALESCE(active_connections, 0) + ({increment}))'
                    )
                )
            )
            
            self.db.commit()
            
            # Buscar valor atualizado
            pool_bot = self.db.query(PoolBot).filter_by(id=pool_bot_id).first()
            new_value = pool_bot.active_connections if pool_bot else 0
            
            return True, new_value
            
        except SQLAlchemyError as e:
            self.db.rollback()
            
            if skip_on_error:
                logger.warning(f"⚠️ Erro ao atualizar conexões ativas: {e}")
                return False, None
            else:
                raise
        
        except Exception as e:
            self.db.rollback()
            
            if skip_on_error:
                logger.warning(f"⚠️ Erro inesperado nas conexões: {e}")
                return False, None
            else:
                raise
    
    def update_pool_health_metrics(
        self,
        pool_id: int,
        skip_on_error: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Atualiza métricas de saúde do pool
        
        Calcula:
        - total_bots: Total de bots no pool
        - active_bots: Bots habilitados e online
        - health_score: Porcentagem de bots ativos (0-100)
        
        Args:
            pool_id: ID do pool
            skip_on_error: Se True, não levanta exceção
            
        Returns:
            Tuple (sucesso, dict com métricas)
        """
        from internal_logic.core.models import PoolBot, RedirectPool
        
        try:
            # Contar total de bots
            total_bots = self.db.query(func.count(PoolBot.id)).filter(
                PoolBot.pool_id == pool_id
            ).scalar() or 0
            
            # Contar bots ativos (online + habilitados)
            active_bots = self.db.query(func.count(PoolBot.id)).filter(
                PoolBot.pool_id == pool_id,
                PoolBot.is_enabled == True,
                PoolBot.status == 'online'
            ).scalar() or 0
            
            # Calcular health score
            health_score = int((active_bots / total_bots) * 100) if total_bots > 0 else 0
            
            # Atualizar pool
            self.db.execute(
                sql_update(RedirectPool)
                .where(RedirectPool.id == pool_id)
                .values(
                    health_score=health_score
                )
            )
            
            self.db.commit()
            
            result = {
                'pool_id': pool_id,
                'total_bots': total_bots,
                'active_bots': active_bots,
                'health_score': health_score
            }
            
            logger.debug(f"📊 Health metrics atualizadas: {result}")
            return True, result
            
        except SQLAlchemyError as e:
            self.db.rollback()
            
            if skip_on_error:
                logger.warning(f"⚠️ Erro ao atualizar health metrics: {e}")
                return False, {'error': str(e)}
            else:
                raise
        
        except Exception as e:
            self.db.rollback()
            
            if skip_on_error:
                logger.warning(f"⚠️ Erro inesperado no health metrics: {e}")
                return False, {'error': str(e)}
            else:
                raise
    
    def increment_error_counters(
        self,
        pool_bot_id: int,
        error_type: str,
        skip_on_error: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Incrementa contadores de erro para um bot
        
        Args:
            pool_bot_id: ID do pool_bot
            error_type: Tipo do erro (bot_fatal, retryable, user_fatal)
            skip_on_error: Se True, não levanta exceção
            
        Returns:
            Tuple (sucesso, dict com contadores)
        """
        from internal_logic.core.models import PoolBot
        
        try:
            # Mapear tipo de erro para campos
            if error_type == 'bot_fatal':
                update_fields = {
                    'consecutive_failures': 999,  # Força desativação
                    'error_count': text('COALESCE(error_count, 0) + 1')
                }
            else:
                update_fields = {
                    'consecutive_failures': text('COALESCE(consecutive_failures, 0) + 1'),
                    'error_count': text('COALESCE(error_count, 0) + 1')
                }
            
            self.db.execute(
                sql_update(PoolBot)
                .where(PoolBot.id == pool_bot_id)
                .values(**update_fields)
            )
            
            self.db.commit()
            
            # Buscar valores atualizados
            pool_bot = self.db.query(PoolBot).filter_by(id=pool_bot_id).first()
            
            result = {
                'pool_bot_id': pool_bot_id,
                'consecutive_failures': pool_bot.consecutive_failures if pool_bot else 0,
                'total_errors': pool_bot.error_count if pool_bot else 0
            }
            
            return True, result
            
        except SQLAlchemyError as e:
            self.db.rollback()
            
            if skip_on_error:
                logger.warning(f"⚠️ Erro ao incrementar contadores de erro: {e}")
                return False, {'error': str(e)}
            else:
                raise
        
        except Exception as e:
            self.db.rollback()
            
            if skip_on_error:
                logger.warning(f"⚠️ Erro inesperado nos contadores: {e}")
                return False, {'error': str(e)}
            else:
                raise
    
    def get_metrics_summary(
        self,
        pool_id: int
    ) -> Dict[str, Any]:
        """
        Retorna resumo completo de métricas de um pool
        
        Args:
            pool_id: ID do pool
            
        Returns:
            Dict com métricas completas
        """
        from internal_logic.core.models import PoolBot, RedirectPool
        
        try:
            pool = self.db.query(RedirectPool).filter_by(id=pool_id).first()
            
            if not pool:
                return {'error': 'Pool não encontrado'}
            
            # Métricas dos bots
            bots_metrics = []
            pool_bots = self.db.query(PoolBot).filter_by(pool_id=pool_id).all()
            
            for pb in pool_bots:
                bots_metrics.append({
                    'bot_id': pb.bot_id,
                    'username': pb.bot.username if pb.bot else 'unknown',
                    'status': pb.status,
                    'total_redirects': pb.total_redirects or 0,
                    'active_connections': pb.active_connections or 0,
                    'consecutive_failures': pb.consecutive_failures or 0,
                    'error_count': pb.error_count or 0,
                    'weight': pb.weight or 1,
                    'is_enabled': pb.is_enabled
                })
            
            return {
                'pool_id': pool_id,
                'pool_name': pool.name,
                'total_redirects': pool.total_redirects or 0,
                'health_score': pool.health_score or 0,
                'is_active': pool.is_active,
                'distribution_strategy': pool.distribution_strategy,
                'bots_count': len(bots_metrics),
                'active_bots': sum(1 for b in bots_metrics if b['status'] == 'online' and b['is_enabled']),
                'bots': bots_metrics
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar summary de métricas: {e}")
            return {'error': str(e)}


# Factory function
def get_metrics_service(db_session: Session) -> MetricsService:
    """
    Factory para obter instância do MetricsService
    
    Args:
        db_session: Sessão SQLAlchemy
        
    Returns:
        Instância de MetricsService
    """
    return MetricsService(db_session)
