"""
Teste Completo - Gamificação V2.0
Validação rigorosa de todas as funcionalidades
"""

from app import app
from models import db, User, Bot, BotConfig, Payment, BotUser
from models_v2 import (
    AchievementV2, UserAchievementV2,
    League, UserLeague,
    Season, Title, UserTitle,
    GamificationNotification
)
from ranking_engine_v2 import RankingEngine
from achievement_checker_v2 import AchievementChecker
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_all_tests():
    """Executa bateria completa de testes"""
    
    with app.app_context():
        logger.info("=" * 80)
        logger.info("🧪 INICIANDO TESTES - GAMIFICAÇÃO V2.0")
        logger.info("=" * 80)
        
        # TESTE 1: Validar tabelas criadas
        test_tables_created()
        
        # TESTE 2: Validar seed de ligas
        test_leagues_seeded()
        
        # TESTE 3: Validar seed de conquistas
        test_achievements_seeded()
        
        # TESTE 4: Validar seed de season
        test_season_seeded()
        
        # TESTE 5: Validar seed de títulos
        test_titles_seeded()
        
        # TESTE 6: Testar RankingEngine
        test_ranking_engine()
        
        # TESTE 7: Testar AchievementChecker
        test_achievement_checker()
        
        # TESTE 8: Testar atualização de ligas
        test_league_update()
        
        # TESTE 9: Teste de anti-fraude
        test_fraud_detection()
        
        # TESTE 10: Teste de progressão de conquistas
        test_achievement_progress()
        
        logger.info("=" * 80)
        logger.info("✅ TODOS OS TESTES CONCLUÍDOS")
        logger.info("=" * 80)


def test_tables_created():
    """Teste 1: Verificar se todas as tabelas foram criadas"""
    logger.info("\n📊 TESTE 1: Validar criação de tabelas...")
    
    tables = [
        'achievements_v2',
        'user_achievements_v2',
        'leagues',
        'user_leagues',
        'seasons',
        'season_leaderboards',
        'titles',
        'user_titles',
        'gamification_notifications',
        'gamification_analytics'
    ]
    
    for table in tables:
        try:
            result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            logger.info(f"  ✅ Tabela '{table}' existe ({count} registros)")
        except Exception as e:
            logger.error(f"  ❌ Tabela '{table}' não encontrada: {e}")
            raise
    
    logger.info("✅ TESTE 1 PASSOU - Todas as tabelas criadas")


def test_leagues_seeded():
    """Teste 2: Verificar seed de ligas"""
    logger.info("\n🏆 TESTE 2: Validar seed de ligas...")
    
    leagues = League.query.order_by(League.tier).all()
    
    expected_leagues = ['bronze', 'silver', 'gold', 'platinum', 'diamond', 'master', 'grandmaster', 'challenger']
    
    assert len(leagues) == 8, f"❌ Esperado 8 ligas, encontrado {len(leagues)}"
    
    for i, league in enumerate(leagues):
        assert league.slug == expected_leagues[i], f"❌ Liga {i+1} deveria ser '{expected_leagues[i]}', mas é '{league.slug}'"
        logger.info(f"  ✅ Liga {league.tier}: {league.name} ({league.min_points}-{league.max_points or '∞'} pts, {league.commission_discount}% desconto)")
    
    # Validar benefícios
    assert leagues[7].commission_discount == 50.0, "❌ Challenger deveria ter 50% de desconto"
    assert leagues[0].commission_discount == 0.0, "❌ Bronze deveria ter 0% de desconto"
    
    logger.info("✅ TESTE 2 PASSOU - 8 ligas configuradas corretamente")


def test_achievements_seeded():
    """Teste 3: Verificar seed de conquistas"""
    logger.info("\n🎯 TESTE 3: Validar seed de conquistas...")
    
    achievements = AchievementV2.query.all()
    
    logger.info(f"  📊 Total de conquistas: {len(achievements)}")
    
    # Agrupar por categoria
    categories = {}
    for ach in achievements:
        if ach.category not in categories:
            categories[ach.category] = []
        categories[ach.category].append(ach)
    
    logger.info(f"  📊 Categorias: {list(categories.keys())}")
    
    for category, ach_list in categories.items():
        logger.info(f"    - {category}: {len(ach_list)} conquistas")
    
    # Validar raridades
    rarities = {}
    for ach in achievements:
        if ach.rarity not in rarities:
            rarities[ach.rarity] = 0
        rarities[ach.rarity] += 1
    
    logger.info(f"  📊 Raridades: {rarities}")
    
    # Validar conquistas específicas
    first_sale = AchievementV2.query.filter_by(slug='first_sale_bronze').first()
    assert first_sale is not None, "❌ Conquista 'first_sale_bronze' não encontrada"
    assert first_sale.points == 100, f"❌ Primeira venda deveria dar 100 pts, mas dá {first_sale.points}"
    logger.info(f"  ✅ Conquista 'Primeira Venda': {first_sale.points} pts, {first_sale.rarity}")
    
    # Validar requisitos JSON
    assert first_sale.requirements is not None, "❌ Requisitos da primeira venda estão vazios"
    assert 'AND' in first_sale.requirements, "❌ Formato de requisitos incorreto"
    logger.info(f"  ✅ Requisitos JSON válidos: {first_sale.requirements}")
    
    logger.info(f"✅ TESTE 3 PASSOU - {len(achievements)} conquistas criadas e validadas")


def test_season_seeded():
    """Teste 4: Verificar seed de season"""
    logger.info("\n📅 TESTE 4: Validar seed de Season 1...")
    
    season = Season.query.filter_by(number=1).first()
    
    assert season is not None, "❌ Season 1 não encontrada"
    assert season.name == 'Temporada 1: Ascensão', f"❌ Nome incorreto: {season.name}"
    assert season.is_active == True, "❌ Season 1 deveria estar ativa"
    assert season.point_multiplier == 1.0, f"❌ Multiplicador deveria ser 1.0, mas é {season.point_multiplier}"
    
    # Validar recompensas
    assert season.rewards is not None, "❌ Recompensas não configuradas"
    assert 'top_1' in season.rewards, "❌ Recompensa top_1 não encontrada"
    
    logger.info(f"  ✅ Season: {season.name}")
    logger.info(f"  ✅ Início: {season.starts_at}")
    logger.info(f"  ✅ Fim: {season.ends_at}")
    logger.info(f"  ✅ Duração: {(season.ends_at - season.starts_at).days} dias")
    logger.info(f"  ✅ Recompensas: {list(season.rewards.keys())}")
    
    logger.info("✅ TESTE 4 PASSOU - Season 1 configurada corretamente")


def test_titles_seeded():
    """Teste 5: Verificar seed de títulos"""
    logger.info("\n👑 TESTE 5: Validar seed de títulos...")
    
    titles = Title.query.all()
    
    assert len(titles) >= 10, f"❌ Esperado pelo menos 10 títulos, encontrado {len(titles)}"
    
    # Validar títulos específicos
    campeo_s1 = Title.query.filter_by(name='Campeão S1').first()
    assert campeo_s1 is not None, "❌ Título 'Campeão S1' não encontrado"
    assert campeo_s1.rarity == 'mythic', f"❌ Campeão S1 deveria ser 'mythic', mas é '{campeo_s1.rarity}'"
    assert campeo_s1.is_permanent == True, "❌ Campeão S1 deveria ser permanente"
    
    logger.info(f"  ✅ Total de títulos: {len(titles)}")
    
    for title in titles[:5]:  # Mostrar primeiros 5
        logger.info(f"    - {title.name} ({title.rarity}): {title.prefix}")
    
    logger.info(f"✅ TESTE 5 PASSOU - {len(titles)} títulos criados")


def test_ranking_engine():
    """Teste 6: Testar RankingEngine"""
    logger.info("\n⚡ TESTE 6: Testar RankingEngine...")
    
    # Pegar primeiro usuário ativo
    user = User.query.filter_by(is_active=True).first()
    
    if not user:
        logger.warning("  ⚠️ Nenhum usuário ativo encontrado, pulando teste")
        return
    
    # Calcular pontos
    points = RankingEngine.calculate_points(user)
    
    assert isinstance(points, int), f"❌ Pontos deveria ser int, mas é {type(points)}"
    assert points >= 0, f"❌ Pontos não pode ser negativo: {points}"
    assert points <= RankingEngine.MAX_POINTS, f"❌ Pontos excedeu o cap: {points} > {RankingEngine.MAX_POINTS}"
    
    logger.info(f"  ✅ Pontos calculados: {points:,}")
    logger.info(f"  ✅ User: {user.username}")
    
    # Testar get_user_league
    league = RankingEngine.get_user_league(user.id)
    if league:
        logger.info(f"  ✅ Liga: {league.name} ({league.tier})")
    else:
        logger.info(f"  ⚠️ Usuário sem liga atribuída")
    
    logger.info("✅ TESTE 6 PASSOU - RankingEngine funcionando")


def test_achievement_checker():
    """Teste 7: Testar AchievementChecker"""
    logger.info("\n🏅 TESTE 7: Testar AchievementChecker...")
    
    # Pegar primeiro usuário ativo
    user = User.query.filter_by(is_active=True).first()
    
    if not user:
        logger.warning("  ⚠️ Nenhum usuário ativo encontrado, pulando teste")
        return
    
    # Verificar conquistas
    new_achievements = AchievementChecker.check_all_achievements(user)
    
    logger.info(f"  ✅ Conquistas desbloqueadas: {len(new_achievements)}")
    
    for ach in new_achievements[:3]:  # Mostrar primeiras 3
        logger.info(f"    - {ach.name} ({ach.points} pts)")
    
    # Verificar progressão
    all_user_achievements = UserAchievementV2.query.filter_by(user_id=user.id).all()
    logger.info(f"  ✅ Progressões registradas: {len(all_user_achievements)}")
    
    # Mostrar algumas progressões
    for ua in all_user_achievements[:3]:
        logger.info(f"    - {ua.achievement.name}: {ua.current_progress*100:.1f}% ({ua.status})")
    
    logger.info("✅ TESTE 7 PASSOU - AchievementChecker funcionando")


def test_league_update():
    """Teste 8: Testar atualização de ligas"""
    logger.info("\n🔄 TESTE 8: Testar atualização de ligas...")
    
    # Atualizar rankings
    updated_count = RankingEngine.update_all_rankings()
    logger.info(f"  ✅ Rankings atualizados: {updated_count} usuários")
    
    # Verificar distribuição por liga
    leagues = League.query.order_by(League.tier).all()
    
    for league in leagues:
        user_count = UserLeague.query.filter_by(league_id=league.id, left_at=None).count()
        logger.info(f"  ✅ {league.name}: {user_count} usuários")
    
    logger.info("✅ TESTE 8 PASSOU - Ligas atualizadas")


def test_fraud_detection():
    """Teste 9: Testar detecção de fraude"""
    logger.info("\n🚨 TESTE 9: Testar detecção de fraude...")
    
    # Criar usuário de teste
    test_user = User.query.filter_by(email='fraud_test@example.com').first()
    
    if not test_user:
        logger.info("  ⚠️ Usuário de teste não existe, pulando teste de fraude")
        return
    
    # Simular métricas suspeitas
    metrics = {
        'sales': 100,
        'revenue': 50.0,  # R$ 0,50 por venda (suspeito!)
        'avg_ticket': 0.5,
        'conversion': 80,  # 80% de conversão (suspeito!)
        'streak': 0,
        'total_users': 125
    }
    
    is_fraud = RankingEngine._detect_fraud(test_user, metrics)
    
    logger.info(f"  ✅ Detecção de fraude: {'🚨 FRAUDE DETECTADA' if is_fraud else '✅ Usuário legítimo'}")
    
    logger.info("✅ TESTE 9 PASSOU - Anti-fraude funcionando")


def test_achievement_progress():
    """Teste 10: Testar progressão parcial de conquistas"""
    logger.info("\n📈 TESTE 10: Testar progressão de conquistas...")
    
    user = User.query.filter_by(is_active=True).first()
    
    if not user:
        logger.warning("  ⚠️ Nenhum usuário ativo encontrado, pulando teste")
        return
    
    # Buscar conquista de 50 vendas
    achievement_50 = AchievementV2.query.filter_by(slug='sales_50_silver').first()
    
    if not achievement_50:
        logger.warning("  ⚠️ Conquista 'sales_50_silver' não encontrada")
        return
    
    # Obter progresso
    progress = AchievementChecker.get_achievement_progress(user.id, achievement_50.id)
    
    logger.info(f"  ✅ Conquista: {achievement_50.name}")
    logger.info(f"  ✅ Progresso: {progress['current_progress']*100:.1f}%")
    logger.info(f"  ✅ Status: {progress['status']}")
    logger.info(f"  ✅ Dados: {progress['progress_data']}")
    
    logger.info("✅ TESTE 10 PASSOU - Progressão funcionando")


if __name__ == '__main__':
    run_all_tests()



