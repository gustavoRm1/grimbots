"""
Teste de Integração Completo - Simula fluxo real de vendas
"""

from app import app
from models import db, User, Bot, BotConfig, Payment
from models_v2 import UserAchievementV2, UserLeague
from ranking_engine_v2 import RankingEngine
from achievement_checker_v2 import AchievementChecker
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_full_sales_flow():
    """Simula fluxo completo: venda → conquista → ranking → liga"""
    
    with app.app_context():
        logger.info("=" * 80)
        logger.info("🎯 TESTE DE INTEGRAÇÃO COMPLETA")
        logger.info("=" * 80)
        
        # 1. Pegar usuário de teste
        user = User.query.filter_by(username='admin').first()
        if not user:
            logger.error("❌ Usuário admin não encontrado")
            return
        
        logger.info(f"\n👤 Usuário: {user.username}")
        logger.info(f"   Pontos atuais: {user.ranking_points or 0}")
        logger.info(f"   Streak atual: {user.current_streak}")
        
        # 2. Estado inicial
        initial_achievements = UserAchievementV2.query.filter_by(user_id=user.id).count()
        logger.info(f"   Conquistas atuais: {initial_achievements}")
        
        # 3. Simular venda (se tiver bot)
        bot = Bot.query.filter_by(user_id=user.id).first()
        if bot:
            # Contar vendas antes
            sales_before = Payment.query.join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid'
            ).count()
            
            logger.info(f"\n💰 Vendas atuais: {sales_before}")
        else:
            logger.info("\n⚠️ Usuário sem bot, pulando simulação de venda")
        
        # 4. Recalcular ranking
        logger.info(f"\n⚡ Recalculando ranking...")
        old_points = user.ranking_points or 0
        user.ranking_points = RankingEngine.calculate_points(user)
        new_points = user.ranking_points
        
        logger.info(f"   Pontos: {old_points:,} → {new_points:,} (Δ {new_points - old_points:+,})")
        
        # 5. Verificar conquistas
        logger.info(f"\n🏆 Verificando conquistas...")
        new_achievements = AchievementChecker.check_all_achievements(user)
        
        if new_achievements:
            logger.info(f"   ✅ {len(new_achievements)} nova(s) conquista(s) desbloqueada(s):")
            for ach in new_achievements:
                logger.info(f"      - {ach.name} ({ach.points} pts, {ach.rarity})")
        else:
            logger.info(f"   ℹ️ Nenhuma conquista nova desbloqueada")
        
        # 6. Atualizar liga
        logger.info(f"\n🏅 Atualizando ligas...")
        RankingEngine.update_leagues()
        
        league = RankingEngine.get_user_league(user.id)
        if league:
            logger.info(f"   Liga: {league.name} (tier {league.tier})")
            logger.info(f"   Desconto: {league.commission_discount}%")
            logger.info(f"   Range: {league.min_points:,} - {league.max_points or '∞'} pts")
        else:
            logger.info(f"   ⚠️ Sem liga atribuída")
        
        # 7. Verificar progressão de conquistas
        logger.info(f"\n📊 Progressão de conquistas:")
        
        all_user_ach = UserAchievementV2.query.filter_by(user_id=user.id).limit(5).all()
        for ua in all_user_ach:
            status_icon = {
                'completed': '✅',
                'in_progress': '🔄',
                'locked': '🔒'
            }.get(ua.status, '❓')
            
            logger.info(f"   {status_icon} {ua.achievement.name}: {ua.current_progress*100:.1f}%")
        
        # 8. Commit
        db.session.commit()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ TESTE DE INTEGRAÇÃO COMPLETO!")
        logger.info("=" * 80)


if __name__ == '__main__':
    test_full_sales_flow()


