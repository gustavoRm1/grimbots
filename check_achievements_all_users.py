"""
Força verificação de achievements para todos os usuários
"""

from models import db, User, Achievement, UserAchievement
from achievement_checker_v2 import AchievementChecker
from flask import Flask
from pathlib import Path

# Criar app mínimo
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def check_all_users():
    """Verifica achievements para todos os usuários"""
    with app.app_context():
        print("Verificando achievements para todos usuarios...")
        
        users = User.query.filter_by(is_admin=False, is_banned=False).all()
        print(f"   Total de usuarios: {len(users)}")
        
        total_unlocked = 0
        
        for user in users:
            print(f"\n   Usuario: @{user.username}")
            
            try:
                # Verificar conquistas
                newly_unlocked = AchievementChecker.check_all_achievements(user)
                
                if newly_unlocked:
                    print(f"      {len(newly_unlocked)} conquista(s) desbloqueada(s)!")
                    for ach in newly_unlocked:
                        print(f"         - {ach.name} (+{ach.points} pts)")
                    total_unlocked += len(newly_unlocked)
                else:
                    print(f"      Nenhuma conquista nova")
                
            except Exception as e:
                print(f"      ERRO: {e}")
        
        print(f"\n   Total de conquistas desbloqueadas: {total_unlocked}")
        print("   Concluido!")

if __name__ == '__main__':
    check_all_users()

