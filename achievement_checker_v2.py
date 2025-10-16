"""
Achievement Checker V2 - Sistema de verificação e progressão de conquistas
Suporta requisitos compostos, progressão parcial e conquistas secretas
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from models import db, User, Bot, Payment, BotUser
import logging

# ✅ CORREÇÃO: Desabilitar sistema V2 se tabelas não existirem
try:
    from models_v2 import AchievementV2, UserAchievementV2, GamificationNotification
    ACHIEVEMENTS_V2_ENABLED = True
except ImportError:
    ACHIEVEMENTS_V2_ENABLED = False
    AchievementV2, UserAchievementV2, GamificationNotification = None, None, None

logger = logging.getLogger(__name__)


class AchievementChecker:
    """Sistema de verificação de conquistas"""
    
    @staticmethod
    def check_all_achievements(user):
        """Verifica todas as conquistas desbloqueáveis para um usuário"""
        if not ACHIEVEMENTS_V2_ENABLED:
            logger.debug("Sistema de conquistas V2 desabilitado")
            return []
        
        try:
            # Buscar todas as conquistas ativas
            achievements = AchievementV2.query.filter(
                db.or_(
                    AchievementV2.expires_at.is_(None),
                    AchievementV2.expires_at > datetime.utcnow()
                )
            ).all()
            
            newly_unlocked = []
            
            for achievement in achievements:
                # Verificar se já possui
                user_achievement = UserAchievementV2.query.filter_by(
                    user_id=user.id,
                    achievement_id=achievement.id
                ).first()
                
                # Se já completou e não pode repetir, skip
                if user_achievement and user_achievement.status == 'completed':
                    if achievement.max_completions == 1:
                        continue
                    
                    # Verificar cooldown
                    if achievement.cooldown_hours and user_achievement.last_completion:
                        cooldown_end = user_achievement.last_completion + timedelta(hours=achievement.cooldown_hours)
                        if datetime.utcnow() < cooldown_end:
                            continue
                
                # Verificar progresso
                progress = AchievementChecker._check_achievement_progress(user, achievement)
                
                # Criar/atualizar registro de progresso
                if not user_achievement:
                    user_achievement = UserAchievementV2(
                        user_id=user.id,
                        achievement_id=achievement.id,
                        status='in_progress'
                    )
                    db.session.add(user_achievement)
                
                user_achievement.current_progress = progress['percentage']
                user_achievement.progress_data = progress['data']
                
                # Se completou
                if progress['percentage'] >= 1.0 and user_achievement.status != 'completed':
                    user_achievement.status = 'completed'
                    user_achievement.unlocked_at = datetime.utcnow()
                    if user_achievement.completion_count is None:
                        user_achievement.completion_count = 0
                    user_achievement.completion_count += 1
                    user_achievement.last_completion = datetime.utcnow()
                    
                    # Aplicar recompensas
                    AchievementChecker._apply_rewards(user, achievement)
                    
                    # Criar notificação
                    AchievementChecker._create_notification(user, achievement)
                    
                    newly_unlocked.append(achievement)
                    
                    logger.info(f"🏆 Achievement unlocked: {achievement.name} - User {user.id}")
            
            db.session.commit()
            return newly_unlocked
        
        except Exception as e:
            logger.error(f"❌ Erro ao verificar conquistas do user {user.id}: {e}")
            db.session.rollback()
            return []
    
    
    @staticmethod
    def _check_achievement_progress(user, achievement):
        """Verifica progresso de uma conquista específica"""
        
        requirements = achievement.requirements
        
        if not requirements:
            return {'percentage': 0.0, 'data': {}}
        
        # Processar requisitos
        if 'AND' in requirements:
            return AchievementChecker._check_and_requirements(user, requirements['AND'])
        elif 'OR' in requirements:
            return AchievementChecker._check_or_requirements(user, requirements['OR'])
        else:
            # Requisito único
            return AchievementChecker._check_single_requirement(user, requirements)
    
    
    @staticmethod
    def _check_and_requirements(user, requirements):
        """Verifica requisitos com lógica AND (todos devem ser atendidos)"""
        
        total_requirements = len(requirements)
        met_requirements = 0
        data = {}
        
        for req in requirements:
            result = AchievementChecker._check_single_requirement(user, req)
            data[req['type']] = result['data']
            
            if result['percentage'] >= 1.0:
                met_requirements += 1
        
        percentage = met_requirements / total_requirements if total_requirements > 0 else 0
        
        return {
            'percentage': percentage,
            'data': data
        }
    
    
    @staticmethod
    def _check_or_requirements(user, requirements):
        """Verifica requisitos com lógica OR (pelo menos um deve ser atendido)"""
        
        max_progress = 0.0
        best_data = {}
        
        for req in requirements:
            result = AchievementChecker._check_single_requirement(user, req)
            
            if result['percentage'] > max_progress:
                max_progress = result['percentage']
                best_data = result['data']
        
        return {
            'percentage': max_progress,
            'data': best_data
        }
    
    
    @staticmethod
    def _check_single_requirement(user, requirement):
        """Verifica um requisito individual"""
        
        req_type = requirement.get('type')
        operator = requirement.get('operator', '>=')
        target_value = requirement.get('value')
        
        current_value = AchievementChecker._get_metric_value(user, req_type)
        
        # Comparar
        met = False
        if operator == '>=':
            met = current_value >= target_value
        elif operator == '>':
            met = current_value > target_value
        elif operator == '==':
            met = current_value == target_value
        elif operator == '<=':
            met = current_value <= target_value
        elif operator == '<':
            met = current_value < target_value
        
        # Calcular percentagem de progresso
        if met:
            percentage = 1.0
        else:
            if operator in ['>=', '>']:
                percentage = min(current_value / target_value, 1.0) if target_value > 0 else 0
            else:
                percentage = 0.0  # Para outros operadores, ou está completo ou não
        
        return {
            'percentage': percentage,
            'data': {
                'current': current_value,
                'target': target_value,
                'met': met
            }
        }
    
    
    @staticmethod
    def _get_metric_value(user, metric_type):
        """Obtém valor atual de uma métrica"""
        
        try:
            # Vendas
            if metric_type == 'sales':
                return db.session.query(func.count(Payment.id))\
                    .join(Bot).filter(
                        Bot.user_id == user.id,
                        Payment.status == 'paid'
                    ).scalar() or 0
            
            # Receita
            elif metric_type == 'revenue':
                return db.session.query(func.sum(Payment.amount))\
                    .join(Bot).filter(
                        Bot.user_id == user.id,
                        Payment.status == 'paid'
                    ).scalar() or 0.0
            
            # Ticket médio
            elif metric_type == 'avg_ticket':
                return db.session.query(func.avg(Payment.amount))\
                    .join(Bot).filter(
                        Bot.user_id == user.id,
                        Payment.status == 'paid'
                    ).scalar() or 0.0
            
            # Taxa de conversão
            elif metric_type == 'conversion_rate':
                total_sales = db.session.query(func.count(Payment.id))\
                    .join(Bot).filter(
                        Bot.user_id == user.id,
                        Payment.status == 'paid'
                    ).scalar() or 0
                
                total_users = db.session.query(func.count(BotUser.id))\
                    .join(Bot).filter(Bot.user_id == user.id).scalar() or 1
                
                return (total_sales / total_users * 100) if total_users > 0 else 0
            
            # Streak
            elif metric_type == 'streak':
                return user.current_streak
            
            # Total de usuários (leads)
            elif metric_type == 'bot_users':
                return db.session.query(func.count(BotUser.id))\
                    .join(Bot).filter(Bot.user_id == user.id).scalar() or 0
            
            # Order bumps aceitos
            elif metric_type == 'order_bump_accepted':
                return db.session.query(func.count(Payment.id))\
                    .join(Bot).filter(
                        Bot.user_id == user.id,
                        Payment.order_bump_accepted == True
                    ).scalar() or 0
            
            # Downsell conversions
            elif metric_type == 'downsell_conversions':
                return db.session.query(func.count(Payment.id))\
                    .join(Bot).filter(
                        Bot.user_id == user.id,
                        Payment.is_downsell == True,
                        Payment.status == 'paid'
                    ).scalar() or 0
            
            # Posição no ranking
            elif metric_type == 'ranking_position':
                position = db.session.query(func.count(User.id))\
                    .filter(User.ranking_points > user.ranking_points)\
                    .scalar() or 0
                return position + 1
            
            # Vendas diárias (máximo)
            elif metric_type == 'daily_sales':
                max_daily = db.session.query(
                    func.date(Payment.created_at).label('date'),
                    func.count(Payment.id).label('count')
                ).join(Bot).filter(
                    Bot.user_id == user.id,
                    Payment.status == 'paid'
                ).group_by(func.date(Payment.created_at))\
                .order_by(func.count(Payment.id).desc())\
                .first()
                
                return max_daily.count if max_daily else 0
            
            # Receita diária (máxima)
            elif metric_type == 'daily_revenue':
                max_daily = db.session.query(
                    func.date(Payment.created_at).label('date'),
                    func.sum(Payment.amount).label('total')
                ).join(Bot).filter(
                    Bot.user_id == user.id,
                    Payment.status == 'paid'
                ).group_by(func.date(Payment.created_at))\
                .order_by(func.sum(Payment.amount).desc())\
                .first()
                
                return max_daily.total if max_daily else 0.0
            
            # Configuração completa
            elif metric_type == 'bot_config_complete':
                bot = Bot.query.filter_by(user_id=user.id).first()
                if not bot or not bot.config:
                    return False
                
                config = bot.config
                complete = bool(
                    config.welcome_message and
                    config.welcome_media_url and
                    config.access_link and
                    config.main_buttons
                )
                return 1 if complete else 0
            
            # Order bump ativo
            elif metric_type == 'order_bump_enabled':
                bot = Bot.query.filter_by(user_id=user.id).first()
                if not bot or not bot.config:
                    return 0
                
                buttons = bot.config.get_main_buttons()
                for btn in buttons:
                    if btn.get('order_bump', {}).get('enabled'):
                        return 1
                return 0
            
            # Horas desde primeira venda
            elif metric_type == 'first_sale_hours':
                first_payment = Payment.query.join(Bot).filter(
                    Bot.user_id == user.id,
                    Payment.status == 'paid'
                ).order_by(Payment.created_at).first()
                
                if not first_payment:
                    return 999999  # Ainda não tem primeira venda
                
                hours = (first_payment.created_at - user.created_at).total_seconds() / 3600
                return hours
            
            # Default
            else:
                logger.warning(f"⚠️ Métrica desconhecida: {metric_type}")
                return 0
        
        except Exception as e:
            logger.error(f"❌ Erro ao obter métrica {metric_type} do user {user.id}: {e}")
            return 0
    
    
    @staticmethod
    def _apply_rewards(user, achievement):
        """Aplica recompensas da conquista"""
        
        reward_type = achievement.reward_type
        reward_value = achievement.reward_value or {}
        
        # XP (pontos)
        if reward_type == 'xp' or achievement.points > 0:
            if user.ranking_points is None:
                user.ranking_points = 0
            user.ranking_points += achievement.points
        
        # Desconto de comissão temporário
        elif reward_type == 'commission_discount':
            # TODO: Implementar sistema de descontos temporários
            # Por enquanto, apenas registrar
            logger.info(f"💰 Desconto de {reward_value.get('discount')}% por {reward_value.get('duration_days')} dias - User {user.id}")
        
        # Título
        elif reward_type == 'title':
            # TODO: Criar título e atribuir ao usuário
            from models_v2 import Title, UserTitle
            
            title_name = reward_value.get('title')
            if title_name:
                # Buscar ou criar título
                title = Title.query.filter_by(name=title_name).first()
                if not title:
                    title = Title(
                        name=title_name,
                        prefix=f"[{title_name.upper()}]",
                        color='#F59E0B',
                        rarity=achievement.rarity,
                        requirement_type='achievement',
                        requirement_id=achievement.id
                    )
                    db.session.add(title)
                    db.session.flush()
                
                # Atribuir ao usuário
                user_title = UserTitle.query.filter_by(
                    user_id=user.id,
                    title_id=title.id
                ).first()
                
                if not user_title:
                    user_title = UserTitle(
                        user_id=user.id,
                        title_id=title.id
                    )
                    db.session.add(user_title)
                
                logger.info(f"👑 Título '{title_name}' desbloqueado - User {user.id}")
        
        # Multiplicador
        elif reward_type == 'multiplier':
            # TODO: Implementar sistema de multiplicadores temporários
            logger.info(f"⚡ Multiplicador {reward_value.get('multiplier')}x por {reward_value.get('duration_days')} dias - User {user.id}")
        
        # Moeda/Gems
        elif reward_type == 'currency':
            # TODO: Implementar sistema de moedas
            logger.info(f"💎 {reward_value.get('amount')} gems - User {user.id}")
    
    
    @staticmethod
    def _create_notification(user, achievement):
        """Cria notificação de conquista desbloqueada"""
        
        notification = GamificationNotification(
            user_id=user.id,
            type='achievement',
            title='🏆 Conquista Desbloqueada!',
            message=f'{achievement.name} - {achievement.description}',
            icon=achievement.icon or 'fa-trophy',
            color=AchievementChecker._get_rarity_color(achievement.rarity),
            data={
                'achievement_id': achievement.id,
                'achievement_slug': achievement.slug,
                'points_earned': achievement.points,
                'rarity': achievement.rarity,
                'tier': achievement.tier,
                'reward_type': achievement.reward_type,
                'reward_value': achievement.reward_value
            },
            is_popup=True
        )
        
        db.session.add(notification)
    
    
    @staticmethod
    def _get_rarity_color(rarity):
        """Retorna cor baseada na raridade"""
        colors = {
            'common': '#D1D5DB',
            'uncommon': '#34D399',
            'rare': '#3B82F6',
            'epic': '#A855F7',
            'legendary': '#F59E0B',
            'mythic': '#EF4444',
            'divine': '#EC4899'
        }
        return colors.get(rarity, '#D1D5DB')
    
    
    @staticmethod
    def get_user_achievements(user_id, status=None, category=None):
        """Retorna conquistas do usuário"""
        
        query = UserAchievementV2.query.filter_by(user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if category:
            query = query.join(AchievementV2).filter(AchievementV2.category == category)
        
        return query.all()
    
    
    @staticmethod
    def get_achievement_progress(user_id, achievement_id):
        """Retorna progresso detalhado de uma conquista"""
        
        user_achievement = UserAchievementV2.query.filter_by(
            user_id=user_id,
            achievement_id=achievement_id
        ).first()
        
        if user_achievement:
            return {
                'current_progress': user_achievement.current_progress,
                'progress_data': user_achievement.progress_data,
                'status': user_achievement.status,
                'unlocked_at': user_achievement.unlocked_at.isoformat() if user_achievement.unlocked_at else None
            }
        
        return {
            'current_progress': 0.0,
            'progress_data': {},
            'status': 'locked',
            'unlocked_at': None
        }

