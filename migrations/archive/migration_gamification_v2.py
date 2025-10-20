"""
Migration Script - Gamificação V2.0
Cria todas as tabelas novas e popula dados iniciais
"""

from app import app
from models import db
from models_v2 import (
    AchievementV2, UserAchievementV2,
    League, UserLeague,
    Season, SeasonLeaderboard,
    Title, UserTitle,
    GamificationNotification,
    GamificationAnalytics
)
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Executa migração completa"""
    
    with app.app_context():
        logger.info("🚀 Iniciando migração Gamificação V2.0...")
        
        try:
            # 1. Criar tabelas
            logger.info("📊 Criando tabelas...")
            db.create_all()
            logger.info("✅ Tabelas criadas")
            
            # 2. Seed de Ligas
            logger.info("🏆 Criando ligas...")
            seed_leagues()
            logger.info("✅ Ligas criadas")
            
            # 3. Seed de Conquistas
            logger.info("🎯 Criando conquistas...")
            seed_achievements()
            logger.info("✅ Conquistas criadas")
            
            # 4. Criar Season 1
            logger.info("📅 Criando Season 1...")
            seed_season_1()
            logger.info("✅ Season 1 criada")
            
            # 5. Criar Títulos básicos
            logger.info("👑 Criando títulos...")
            seed_titles()
            logger.info("✅ Títulos criados")
            
            logger.info("🎉 Migração concluída com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro na migração: {e}")
            db.session.rollback()
            raise


def seed_leagues():
    """Cria 8 ligas"""
    
    leagues_data = [
        {
            'name': 'Bronze',
            'slug': 'bronze',
            'tier': 1,
            'color': '#CD7F32',
            'icon': 'fa-medal',
            'min_points': 0,
            'max_points': 10000,
            'commission_discount': 0.0,
            'benefits': {}
        },
        {
            'name': 'Prata',
            'slug': 'silver',
            'tier': 2,
            'color': '#C0C0C0',
            'icon': 'fa-medal',
            'min_points': 10000,
            'max_points': 25000,
            'commission_discount': 5.0,
            'benefits': {}
        },
        {
            'name': 'Ouro',
            'slug': 'gold',
            'tier': 3,
            'color': '#FFD700',
            'icon': 'fa-award',
            'min_points': 25000,
            'max_points': 50000,
            'commission_discount': 10.0,
            'benefits': {'priority_support': True}
        },
        {
            'name': 'Platina',
            'slug': 'platinum',
            'tier': 4,
            'color': '#E5E4E2',
            'icon': 'fa-award',
            'min_points': 50000,
            'max_points': 100000,
            'commission_discount': 15.0,
            'benefits': {'priority_support': True, 'max_bots': 50}
        },
        {
            'name': 'Diamante',
            'slug': 'diamond',
            'tier': 5,
            'color': '#B9F2FF',
            'icon': 'fa-gem',
            'min_points': 100000,
            'max_points': 250000,
            'commission_discount': 20.0,
            'benefits': {'priority_support': True, 'max_bots': 100}
        },
        {
            'name': 'Mestre',
            'slug': 'master',
            'tier': 6,
            'color': '#9B30FF',
            'icon': 'fa-star',
            'min_points': 250000,
            'max_points': 500000,
            'commission_discount': 25.0,
            'benefits': {'priority_support': True, 'max_bots': 200, 'api_access': True}
        },
        {
            'name': 'Grão-Mestre',
            'slug': 'grandmaster',
            'tier': 7,
            'color': '#FF1493',
            'icon': 'fa-crown',
            'min_points': 500000,
            'max_points': 1000000,
            'commission_discount': 30.0,
            'benefits': {'priority_support': True, 'max_bots': 500, 'api_access': True, 'consulting': True}
        },
        {
            'name': 'Challenger',
            'slug': 'challenger',
            'tier': 8,
            'color': '#F59E0B',
            'icon': 'fa-trophy',
            'min_points': 1000000,
            'max_points': None,  # Sem limite
            'commission_discount': 50.0,
            'benefits': {'priority_support': True, 'max_bots': 9999, 'api_access': True, 'consulting': True, 'white_label': True}
        }
    ]
    
    for league_data in leagues_data:
        league = League.query.filter_by(slug=league_data['slug']).first()
        if not league:
            league = League(**league_data)
            db.session.add(league)
    
    db.session.commit()


def seed_achievements():
    """Cria conquistas iniciais"""
    
    # Importar do arquivo de seed
    from achievement_seed_v2 import get_all_achievements
    
    achievements_data = get_all_achievements()
    
    for achievement_data in achievements_data:
        achievement = AchievementV2.query.filter_by(slug=achievement_data['slug']).first()
        if not achievement:
            achievement = AchievementV2(**achievement_data)
            db.session.add(achievement)
    
    db.session.commit()
    
    logger.info(f"✅ {len(achievements_data)} conquistas criadas")


def seed_season_1():
    """Cria Season 1"""
    
    season = Season.query.filter_by(number=1).first()
    if not season:
        now = datetime.utcnow()
        season = Season(
            name='Temporada 1: Ascensão',
            slug='season-1-ascensao',
            number=1,
            theme='Lançamento',
            description='A primeira temporada competitiva do grimbots! Prove seu valor e conquiste seu lugar no Hall da Fama.',
            starts_at=now,
            ends_at=now + timedelta(days=90),  # 3 meses
            is_active=True,
            point_multiplier=1.0,
            rewards={
                'top_1': {
                    'title': 'Campeão S1',
                    'commission_discount': 100.0,  # 6 meses grátis
                    'duration_months': 6
                },
                'top_10': {
                    'title': 'Elite S1',
                    'commission_discount': 50.0,  # 3 meses 50% off
                    'duration_months': 3
                },
                'top_50': {
                    'commission_discount': 25.0,  # 1 mês 25% off
                    'duration_months': 1
                },
                'top_100': {
                    'badge': 'Participante S1'
                }
            }
        )
        db.session.add(season)
        db.session.commit()


def seed_titles():
    """Cria títulos básicos"""
    
    titles_data = [
        {
            'name': 'Empreendedor',
            'prefix': '[EMPREENDEDOR]',
            'color': '#34D399',
            'rarity': 'uncommon',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Magnata',
            'prefix': '[MAGNATA]',
            'color': '#F59E0B',
            'rarity': 'epic',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Lenda das Vendas',
            'prefix': '[LENDA]',
            'color': '#EF4444',
            'rarity': 'legendary',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Relâmpago',
            'prefix': '[⚡]',
            'color': '#3B82F6',
            'rarity': 'epic',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Estrategista',
            'prefix': '[ESTRATEGISTA]',
            'color': '#A855F7',
            'rarity': 'rare',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Mago',
            'prefix': '[MAGO]',
            'color': '#EC4899',
            'rarity': 'legendary',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Elite',
            'prefix': '[ELITE]',
            'color': '#8B5CF6',
            'rarity': 'rare',
            'requirement_type': 'ranking',
            'is_permanent': False,
            'expires_after_days': 30
        },
        {
            'name': 'Campeão',
            'prefix': '[CAMPEÃO]',
            'color': '#F59E0B',
            'rarity': 'legendary',
            'requirement_type': 'ranking',
            'is_permanent': False,
            'expires_after_days': 30
        },
        {
            'name': 'Campeão S1',
            'prefix': '[CAMPEÃO S1]',
            'color': '#F59E0B',
            'rarity': 'mythic',
            'requirement_type': 'season_rank',
            'is_permanent': True
        },
        {
            'name': 'Elite S1',
            'prefix': '[ELITE S1]',
            'color': '#8B5CF6',
            'rarity': 'epic',
            'requirement_type': 'season_rank',
            'is_permanent': True
        },
        {
            'name': 'Imortal',
            'prefix': '[IMORTAL]',
            'color': '#EF4444',
            'rarity': 'mythic',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Coruja',
            'prefix': '[🦉]',
            'color': '#6366F1',
            'rarity': 'rare',
            'requirement_type': 'achievement',
            'is_permanent': True
        },
        {
            'name': 'Sortudo',
            'prefix': '[🍀]',
            'color': '#10B981',
            'rarity': 'legendary',
            'requirement_type': 'achievement',
            'is_permanent': True
        }
    ]
    
    for title_data in titles_data:
        title = Title.query.filter_by(name=title_data['name']).first()
        if not title:
            title = Title(**title_data)
            db.session.add(title)
    
    db.session.commit()


if __name__ == '__main__':
    run_migration()



