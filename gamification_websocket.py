"""
Gamification WebSocket - Notificações em tempo real
"""

from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from models_v2 import GamificationNotification
import logging

logger = logging.getLogger(__name__)


def register_gamification_events(socketio):
    """Registra eventos WebSocket de gamificação"""
    
    @socketio.on('subscribe_gamification')
    def handle_subscribe():
        """Cliente se inscreve para receber notificações de gamificação"""
        if not current_user.is_authenticated:
            return
        
        room = f'user_{current_user.id}_gamification'
        join_room(room)
        emit('subscribed', {'room': room})
        logger.info(f"👤 User {current_user.id} inscrito em notificações de gamificação")
    
    
    @socketio.on('unsubscribe_gamification')
    def handle_unsubscribe():
        """Cliente cancela inscrição"""
        if not current_user.is_authenticated:
            return
        
        room = f'user_{current_user.id}_gamification'
        leave_room(room)
        emit('unsubscribed', {'room': room})
        logger.info(f"👤 User {current_user.id} desinscrito de notificações de gamificação")


def notify_achievement_unlocked(socketio, user_id, achievement):
    """Notifica desbloqueio de conquista em tempo real"""
    try:
        # Determinar animação baseada em raridade
        animations = {
            'common': 'sparkles',
            'uncommon': 'stars',
            'rare': 'fireworks',
            'epic': 'confetti',
            'legendary': 'confetti_gold',
            'mythic': 'confetti_rainbow'
        }
        
        animation = animations.get(achievement.rarity, 'sparkles')
        
        # Sons baseados em raridade
        sounds = {
            'common': 'achievement_common.mp3',
            'uncommon': 'achievement_uncommon.mp3',
            'rare': 'achievement_rare.mp3',
            'epic': 'achievement_epic.mp3',
            'legendary': 'achievement_legendary.mp3',
            'mythic': 'achievement_mythic.mp3'
        }
        
        sound = sounds.get(achievement.rarity, 'achievement_common.mp3')
        
        # Payload
        payload = {
            'type': 'achievement_unlocked',
            'achievement': {
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'icon': achievement.icon,
                'rarity': achievement.rarity,
                'points': achievement.points,
                'reward_type': achievement.reward_type,
                'reward_value': achievement.reward_value
            },
            'animation': animation,
            'sound': sound,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Enviar via WebSocket
        socketio.emit(
            'achievement_unlocked',
            payload,
            room=f'user_{user_id}_gamification'
        )
        
        logger.info(f"🏆 Notificação de conquista enviada: {achievement.name} → User {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificação de conquista: {e}")


def notify_level_up(socketio, user_id, old_league, new_league):
    """Notifica promoção de liga"""
    try:
        payload = {
            'type': 'league_promotion',
            'old_league': old_league.to_dict() if old_league else None,
            'new_league': new_league.to_dict(),
            'animation': 'promotion',
            'sound': 'level_up.mp3',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        socketio.emit(
            'league_promotion',
            payload,
            room=f'user_{user_id}_gamification'
        )
        
        logger.info(f"📈 Notificação de promoção enviada: {new_league.name} → User {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificação de promoção: {e}")


def notify_title_unlocked(socketio, user_id, title):
    """Notifica desbloqueio de título"""
    try:
        payload = {
            'type': 'title_unlocked',
            'title': {
                'id': title.id,
                'name': title.name,
                'prefix': title.prefix,
                'color': title.color,
                'rarity': title.rarity
            },
            'animation': 'title_glow',
            'sound': 'title_unlock.mp3',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        socketio.emit(
            'title_unlocked',
            payload,
            room=f'user_{user_id}_gamification'
        )
        
        logger.info(f"👑 Notificação de título enviada: {title.name} → User {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificação de título: {e}")


def notify_season_ending(socketio, season, days_left):
    """Notifica fim iminente de season (broadcast)"""
    try:
        payload = {
            'type': 'season_ending',
            'season': {
                'name': season.name,
                'number': season.number,
                'ends_at': season.ends_at.isoformat()
            },
            'days_left': days_left,
            'animation': 'countdown',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Broadcast para todos os usuários
        socketio.emit('season_ending', payload, broadcast=True)
        
        logger.info(f"📅 Notificação de fim de season enviada: {season.name} ({days_left} dias restantes)")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificação de season: {e}")


def notify_ranking_update(socketio, user_id, old_position, new_position):
    """Notifica mudança significativa no ranking"""
    try:
        # Apenas notificar se mudou 10+ posições
        if abs(old_position - new_position) < 10:
            return
        
        direction = 'up' if new_position < old_position else 'down'
        delta = abs(old_position - new_position)
        
        payload = {
            'type': 'ranking_update',
            'old_position': old_position,
            'new_position': new_position,
            'delta': delta,
            'direction': direction,
            'animation': 'rank_up' if direction == 'up' else 'rank_down',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        socketio.emit(
            'ranking_update',
            payload,
            room=f'user_{user_id}_gamification'
        )
        
        logger.info(f"📊 Notificação de ranking enviada: #{old_position} → #{new_position} → User {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificação de ranking: {e}")






