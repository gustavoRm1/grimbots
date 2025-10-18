"""
Debug de Achievements
"""

from models import db, User, Bot, Payment, Achievement
from achievement_checker_v2 import AchievementChecker
from flask import Flask
from pathlib import Path
from sqlalchemy import func

# Criar app mínimo
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def debug():
    """Debug achievements"""
    with app.app_context():
        user = User.query.filter_by(username='Gustavo').first()
        
        if not user:
            print("Usuario nao encontrado")
            return
        
        print(f"Usuario: @{user.username}")
        print(f"ID: {user.id}")
        
        # Calcular métricas
        print("\nMetricas do usuario:")
        
        total_sales = db.session.query(func.count(Payment.id))\
            .join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid'
            ).scalar() or 0
        
        total_revenue = db.session.query(func.sum(Payment.amount))\
            .join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid'
            ).scalar() or 0.0
        
        print(f"   Vendas pagas: {total_sales}")
        print(f"   Receita total: R$ {total_revenue:.2f}")
        print(f"   Streak atual: {user.current_streak or 0}")
        
        # Listar achievements
        print("\nAchievements disponiveis:")
        achievements = Achievement.query.all()
        print(f"   Total: {len(achievements)}")
        
        for ach in achievements:
            print(f"\n   {ach.icon} {ach.name}")
            print(f"      Requisito: {ach.requirement_type} >= {ach.requirement_value}")
            
            # Calcular valor atual
            current_value = AchievementChecker._get_metric_value(user, ach.requirement_type)
            print(f"      Valor atual: {current_value}")
            print(f"      Desbloqueado: {'SIM' if current_value >= ach.requirement_value else 'NAO'}")

if __name__ == '__main__':
    debug()

