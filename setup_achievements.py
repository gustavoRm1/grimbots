#!/usr/bin/env python3
"""
Setup de Achievements - Execute na VPS
USO: python setup_achievements.py
"""

from models import db, Achievement, User, UserAchievement
from achievement_checker_v2 import AchievementChecker
from ranking_engine_v2 import RankingEngine
from flask import Flask
from pathlib import Path

# Criar app
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Achievements básicos
ACHIEVEMENTS = [
    {'name': 'Primeira Venda', 'description': 'Realize sua primeira venda', 'icon': '🎯', 'badge_color': 'gold', 'requirement_type': 'sales', 'requirement_value': 1, 'points': 50, 'rarity': 'common'},
    {'name': 'Vendedor Iniciante', 'description': 'Realize 10 vendas', 'icon': '📈', 'badge_color': 'blue', 'requirement_type': 'sales', 'requirement_value': 10, 'points': 100, 'rarity': 'common'},
    {'name': 'Vendedor Profissional', 'description': 'Realize 50 vendas', 'icon': '💼', 'badge_color': 'gold', 'requirement_type': 'sales', 'requirement_value': 50, 'points': 500, 'rarity': 'rare'},
    {'name': 'Mestre das Vendas', 'description': 'Realize 100 vendas', 'icon': '👑', 'badge_color': 'gold', 'requirement_type': 'sales', 'requirement_value': 100, 'points': 1000, 'rarity': 'epic'},
    {'name': 'Primeiro R$ 100', 'description': 'Fature R$ 100 em vendas', 'icon': '💰', 'badge_color': 'green', 'requirement_type': 'revenue', 'requirement_value': 100, 'points': 100, 'rarity': 'common'},
    {'name': 'R$ 1.000 Faturados', 'description': 'Fature R$ 1.000 em vendas', 'icon': '💸', 'badge_color': 'green', 'requirement_type': 'revenue', 'requirement_value': 1000, 'points': 500, 'rarity': 'rare'},
    {'name': 'Milionário Digital', 'description': 'Fature R$ 10.000 em vendas', 'icon': '🤑', 'badge_color': 'gold', 'requirement_type': 'revenue', 'requirement_value': 10000, 'points': 2000, 'rarity': 'epic'},
    {'name': 'Consistência', 'description': 'Venda por 3 dias consecutivos', 'icon': '🔥', 'badge_color': 'orange', 'requirement_type': 'streak', 'requirement_value': 3, 'points': 200, 'rarity': 'common'},
    {'name': 'Imparável', 'description': 'Venda por 7 dias consecutivos', 'icon': '⚡', 'badge_color': 'gold', 'requirement_type': 'streak', 'requirement_value': 7, 'points': 500, 'rarity': 'rare'},
    {'name': 'Lendário', 'description': 'Venda por 30 dias consecutivos', 'icon': '🌟', 'badge_color': 'gold', 'requirement_type': 'streak', 'requirement_value': 30, 'points': 2000, 'rarity': 'legendary'},
    {'name': 'Taxa de Ouro', 'description': 'Atinja 50% de conversão', 'icon': '🎖️', 'badge_color': 'gold', 'requirement_type': 'conversion_rate', 'requirement_value': 50, 'points': 1000, 'rarity': 'epic'},
]

def main():
    with app.app_context():
        print("=" * 60)
        print("SETUP DE ACHIEVEMENTS - GRPAY")
        print("=" * 60)
        
        # 1. Popular achievements (se não existirem)
        existing = Achievement.query.count()
        print(f"\n[1/2] Achievements no banco: {existing}")
        
        if existing == 0:
            print("      Criando achievements...")
            for ach_data in ACHIEVEMENTS:
                achievement = Achievement(**ach_data)
                db.session.add(achievement)
            db.session.commit()
            print(f"      {len(ACHIEVEMENTS)} achievements criados!")
        else:
            print("      Achievements ja existem. OK!")
        
        # 2. Verificar conquistas de TODOS os usuários
        users = User.query.filter_by(is_admin=False, is_banned=False).all()
        print(f"\n[2/2] Verificando conquistas de {len(users)} usuario(s)...")
        
        total_unlocked = 0
        for user in users:
            try:
                newly_unlocked = AchievementChecker.check_all_achievements(user)
                
                # Recalcular pontos
                user.ranking_points = RankingEngine.calculate_points(user)
                db.session.commit()
                
                total_achievements = UserAchievement.query.filter_by(user_id=user.id).count()
                
                print(f"      @{user.username}: {len(newly_unlocked)} novas | Total: {total_achievements} | Pontos: {user.ranking_points}")
                total_unlocked += len(newly_unlocked)
                
            except Exception as e:
                print(f"      ERRO em @{user.username}: {e}")
        
        print("\n" + "=" * 60)
        print(f"CONCLUIDO!")
        print(f"   Total de conquistas desbloqueadas: {total_unlocked}")
        print("=" * 60)

if __name__ == '__main__':
    main()

