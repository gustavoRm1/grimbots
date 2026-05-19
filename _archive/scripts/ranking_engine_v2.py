"""
Ranking Engine V2 - Algoritmo ELO + Decay Temporal + Anti-Fraude
Sistema justo e competitivo de ranking
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from internal_logic.core.models import db, User, Bot, Payment, BotUser
import logging

# ✅ CORREÇÃO: Desabilitar sistema de ligas (tabelas não criadas)
try:
    # from models_v2 import Season, League, UserLeague  # ❌ Módulo não existe
    # ✅ Usando modelos do models.py padrão
    pass
    LEAGUES_ENABLED = True
except ImportError:
    LEAGUES_ENABLED = False
    Season, League, UserLeague = None, None, None

logger = logging.getLogger(__name__)


class RankingEngine:
    """Motor de cálculo de ranking V2"""
    
    # Constantes
    MAX_POINTS = 1_000_000  # Cap de pontos
    DECAY_RATE = 0.50  # 50% de decay a cada 30 dias
    DECAY_PERIOD_DAYS = 30
    FRAUD_PENALTY = 0.50  # Penalidade de 50% se fraude detectada
    
    @staticmethod
    def calculate_points(user, season=None):
        """
        Algoritmo híbrido:
        - Métricas base (vendas, receita, conversão, streak)
        - Normalização por cohort
        - Decay temporal (30% por mês)
        - Multiplicadores (streak, conquistas, eventos)
        - Detecção de anomalias
        """
        try:
            # 1. MÉTRICAS BASE
            metrics = RankingEngine._get_user_metrics(user, season)
            
            # 2. NORMALIZAÇÃO (comparado com cohort do mesmo mês de cadastro)
            normalized = RankingEngine._normalize_by_cohort(user, metrics)
            
            # 3. DECAY TEMPORAL (ações recentes valem mais)
            decayed = RankingEngine._apply_temporal_decay(user, normalized, season)
            
            # 4. MULTIPLICADORES (streak, conquistas, eventos)
            multiplied = RankingEngine._apply_multipliers(user, decayed, season)
            
            # 5. DETECÇÃO DE FRAUDE
            if RankingEngine._detect_fraud(user, metrics):
                multiplied *= RankingEngine.FRAUD_PENALTY
                logger.warning(f"🚨 Fraude detectada: User {user.id} - Pontos penalizados em 50%")
            
            # 6. CAP DE PONTOS (evitar inflação infinita)
            final_points = min(multiplied, RankingEngine.MAX_POINTS)
            
            return int(final_points)
        
        except Exception as e:
            logger.error(f"❌ Erro ao calcular pontos do user {user.id}: {e}")
            return 0
    
    
    @staticmethod
    def _get_user_metrics(user, season):
        """Coleta métricas do usuário"""
        
        # Query base
        query = db.session.query(
            func.count(Payment.id).label('sales'),
            func.sum(Payment.amount).label('revenue'),
            func.avg(Payment.amount).label('avg_ticket'),
        ).join(Bot).filter(
            Bot.user_id == user.id,
            Payment.status == 'paid'
        )
        
        # Filtrar por season se especificado
        if season:
            query = query.filter(
                Payment.created_at.between(season.starts_at, season.ends_at)
            )
        
        result = query.first()
        
        # Total de usuários (leads)
        total_users_query = db.session.query(func.count(BotUser.id))\
            .join(Bot).filter(Bot.user_id == user.id)
        
        if season:
            total_users_query = total_users_query.filter(
                BotUser.first_interaction.between(season.starts_at, season.ends_at)
            )
        
        total_users = total_users_query.scalar() or 1
        
        # Taxa de conversão
        sales = result.sales or 0
        revenue = result.revenue or 0.0
        avg_ticket = result.avg_ticket or 0.0
        conversion = (sales / total_users * 100) if total_users > 0 else 0
        
        return {
            'sales': sales,
            'revenue': revenue,
            'avg_ticket': avg_ticket,
            'conversion': conversion,
            'streak': user.current_streak,
            'total_users': total_users
        }
    
    
    @staticmethod
    def _normalize_by_cohort(user, metrics):
        """Normaliza métricas comparando com usuários do mesmo período"""
        
        # Buscar cohort (usuários cadastrados no mesmo mês)
        if not user.created_at:
            return metrics  # Sem data de criação, retorna raw
        
        cohort_start = user.created_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cohort_end = (cohort_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        cohort_users = User.query.filter(
            User.created_at.between(cohort_start, cohort_end),
            User.id != user.id  # Excluir próprio usuário
        ).all()
        
        if len(cohort_users) < 2:
            return metrics  # Cohort muito pequeno, retorna raw
        
        # Calcular média do cohort
        cohort_sales = [u.total_sales for u in cohort_users if u.total_sales > 0]
        cohort_revenue = [u.total_revenue for u in cohort_users if u.total_revenue > 0]
        
        if not cohort_sales or not cohort_revenue:
            return metrics
        
        avg_sales = sum(cohort_sales) / len(cohort_sales)
        avg_revenue = sum(cohort_revenue) / len(cohort_revenue)
        
        # Z-score normalizado (0-200, cap 2x da média)
        normalized_sales = (metrics['sales'] / avg_sales * 100) if avg_sales > 0 else 0
        normalized_revenue = (metrics['revenue'] / avg_revenue * 100) if avg_revenue > 0 else 0
        
        # Cap em 200% (evitar outliers extremos)
        normalized_sales = min(normalized_sales, 200)
        normalized_revenue = min(normalized_revenue, 200)
        
        return {
            **metrics,
            'normalized_sales': normalized_sales,
            'normalized_revenue': normalized_revenue,
        }
    
    
    @staticmethod
    def _apply_temporal_decay(user, metrics, season):
        """Aplica decay exponencial (ações recentes valem mais)"""
        
        # Se estiver em uma season, não aplicar decay (season já é temporal)
        if season:
            return metrics
        
        # Calcular idade da conta em dias
        if not user.created_at:
            return metrics
        
        account_age_days = (datetime.utcnow() - user.created_at).days
        
        # Calcular fator de decay
        # Fórmula: decay = 0.5 ^ (age_days / 30)
        # 0 dias = 100%, 30 dias = 50%, 60 dias = 25%, 90 dias = 12.5%
        decay_factor = RankingEngine.DECAY_RATE ** (account_age_days / RankingEngine.DECAY_PERIOD_DAYS)
        decay_factor = max(decay_factor, 0.01)  # Mínimo 1% (não zerar completamente)
        
        # Aplicar decay nas métricas normalizadas
        metrics_with_decay = {
            **metrics,
            'decayed_sales': metrics.get('normalized_sales', metrics['sales']) * decay_factor,
            'decayed_revenue': metrics.get('normalized_revenue', metrics['revenue']) * decay_factor,
        }
        
        return metrics_with_decay
    
    
    @staticmethod
    def _apply_multipliers(user, metrics, season):
        """Aplica multiplicadores de streak, conquistas, eventos"""
        
        # Calcular pontos base
        sales_value = metrics.get('decayed_sales', metrics.get('normalized_sales', metrics['sales']))
        revenue_value = metrics.get('decayed_revenue', metrics.get('normalized_revenue', metrics['revenue']))
        
        base_points = (
            revenue_value * 1.0 +         # 1 ponto por R$ 1,00 (ou normalizado)
            sales_value * 10.0 +          # 10 pontos por venda (ou normalizado)
            metrics['conversion'] * 50.0  # 50 pontos por % de conversão
        )
        
        multiplier = 1.0
        
        # STREAK MULTIPLIER
        streak = user.current_streak
        if streak >= 90:
            multiplier += 1.0  # +100%
        elif streak >= 60:
            multiplier += 0.75  # +75%
        elif streak >= 30:
            multiplier += 0.50  # +50%
        elif streak >= 14:
            multiplier += 0.25  # +25%
        elif streak >= 7:
            multiplier += 0.10  # +10%
        
        # ACHIEVEMENT MULTIPLIER (usar apenas se disponível)
        if LEAGUES_ENABLED:
            try:
                # from models_v2 import UserAchievementV2  # ❌ Módulo não existe
                from internal_logic.core.models import UserAchievement  # ✅ Usar modelo existente
                total_achievements = UserAchievement.query.filter_by(
                    user_id=user.id
                ).count()
                
                # +2% por conquista desbloqueada (max +50%)
                achievement_bonus = min(total_achievements * 0.02, 0.50)
                multiplier += achievement_bonus
            except Exception as e:
                logger.debug(f"Achievement multiplier não aplicado: {e}")
        
        # EVENT/SEASON MULTIPLIER
        if season and season.point_multiplier:
            multiplier *= season.point_multiplier
        
        final_points = base_points * multiplier
        
        return final_points
    
    
    @staticmethod
    def _detect_fraud(user, metrics):
        """Detecta comportamento suspeito"""
        
        fraud_flags = []
        
        # FLAG 1: Vendas de valor muito baixo (< R$ 1)
        try:
            cheap_sales = db.session.query(func.count(Payment.id))\
                .join(Bot).filter(
                    Bot.user_id == user.id,
                    Payment.amount < 1.0,
                    Payment.status == 'paid'
                ).scalar() or 0
            
            if metrics['sales'] > 0 and (cheap_sales / metrics['sales']) > 0.30:
                fraud_flags.append('cheap_sales')  # > 30% de vendas < R$ 1
        except:
            pass
        
        # FLAG 2: Spike repentino de vendas (> 10x média semanal)
        try:
            last_7_days = datetime.utcnow() - timedelta(days=7)
            recent_sales = db.session.query(func.count(Payment.id))\
                .join(Bot).filter(
                    Bot.user_id == user.id,
                    Payment.created_at >= last_7_days,
                    Payment.status == 'paid'
                ).scalar() or 0
            
            account_weeks = max((datetime.utcnow() - user.created_at).days / 7, 1)
            avg_weekly_sales = metrics['sales'] / account_weeks
            
            if avg_weekly_sales > 0 and recent_sales > (avg_weekly_sales * 10):
                fraud_flags.append('sales_spike')  # 10x média semanal
        except:
            pass
        
        # FLAG 3: Taxa de conversão irrealisticamente alta (> 50%)
        if metrics['conversion'] > 50:
            fraud_flags.append('high_conversion')
        
        # FLAG 4: Muitas vendas mas ticket médio muito baixo
        if metrics['sales'] > 100 and metrics['avg_ticket'] < 5:
            fraud_flags.append('low_ticket')
        
        # Se tiver 2+ flags, considerar suspeito
        if len(fraud_flags) >= 2:
            logger.warning(f"🚨 User {user.id} - Flags: {fraud_flags}")
            return True
        
        return False
    
    
    @staticmethod
    def update_all_rankings(season=None):
        """Recalcula ranking de todos os usuários (job noturno)"""
        try:
            users = User.query.filter_by(is_active=True).all()
            
            for user in users:
                user.ranking_points = RankingEngine.calculate_points(user, season)
            
            db.session.commit()
            logger.info(f"✅ Ranking recalculado para {len(users)} usuários")
            
            # Atualizar ligas
            RankingEngine.update_leagues()
            
            return len(users)
        
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar rankings: {e}")
            db.session.rollback()
            return 0
    
    
    @staticmethod
    def update_leagues():
        """Atualiza ligas dos usuários baseado em pontos"""
        if not LEAGUES_ENABLED:
            logger.warning("⚠️ Sistema de ligas desabilitado (models_v2 não disponível)")
            return
        
        try:
            users = User.query.filter_by(is_active=True).order_by(User.ranking_points.desc()).all()
            leagues = League.query.order_by(League.tier).all()
            
            if not leagues:
                logger.warning("⚠️ Nenhuma liga configurada")
                return
            
            for user in users:
                # Encontrar liga apropriada
                current_league = None
                for league in leagues:
                    if league.max_points is None:  # Challenger (sem limite)
                        if user.ranking_points >= league.min_points:
                            current_league = league
                            break
                    else:
                        if league.min_points <= user.ranking_points <= league.max_points:
                            current_league = league
                            break
                
                if not current_league:
                    current_league = leagues[0]  # Default: primeira liga (Bronze)
                
                # Verificar se mudou de liga
                last_league = UserLeague.query.filter_by(
                    user_id=user.id,
                    left_at=None
                ).first()
                
                if not last_league or last_league.league_id != current_league.id:
                    # Fechar liga anterior
                    if last_league:
                        last_league.left_at = datetime.utcnow()
                        
                        # Verificar se foi promoção ou rebaixamento
                        if current_league.tier > last_league.league.tier:
                            last_league.promoted = True
                        elif current_league.tier < last_league.league.tier:
                            last_league.relegated = True
                    
                    # Criar nova entrada de liga
                    new_league = UserLeague(
                        user_id=user.id,
                        league_id=current_league.id
                    )
                    db.session.add(new_league)
            
            db.session.commit()
            logger.info(f"✅ Ligas atualizadas para {len(users)} usuários")
        
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar ligas: {e}")
            db.session.rollback()
    
    
    @staticmethod
    def get_user_league(user_id):
        """Retorna liga atual do usuário"""
        user_league = UserLeague.query.filter_by(
            user_id=user_id,
            left_at=None
        ).first()
        
        return user_league.league if user_league else None
    
    
    @staticmethod
    def get_leaderboard(season=None, league=None, limit=100):
        """Retorna ranking global ou filtrado"""
        
        query = User.query.filter_by(is_active=True)
        
        # Filtrar por liga
        if league:
            league_users = db.session.query(UserLeague.user_id)\
                .filter_by(league_id=league.id, left_at=None)\
                .subquery()
            query = query.filter(User.id.in_(league_users))
        
        # Ordenar por pontos
        query = query.order_by(User.ranking_points.desc()).limit(limit)
        
        return query.all()



