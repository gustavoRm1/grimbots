"""
Seed de Achievements Básicos
Popula conquistas iniciais no banco
"""

from models import db, Achievement
from flask import Flask
from pathlib import Path

# Criar app mínimo
app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Achievements básicos
ACHIEVEMENTS = [
    # Vendas
    {
        'name': 'Primeira Venda',
        'description': 'Realize sua primeira venda',
        'icon': '🎯',
        'badge_color': 'gold',
        'requirement_type': 'sales',
        'requirement_value': 1,
        'points': 50,
        'rarity': 'common'
    },
    {
        'name': 'Vendedor Iniciante',
        'description': 'Realize 10 vendas',
        'icon': '📈',
        'badge_color': 'blue',
        'requirement_type': 'sales',
        'requirement_value': 10,
        'points': 100,
        'rarity': 'common'
    },
    {
        'name': 'Vendedor Profissional',
        'description': 'Realize 50 vendas',
        'icon': '💼',
        'badge_color': 'gold',
        'requirement_type': 'sales',
        'requirement_value': 50,
        'points': 500,
        'rarity': 'rare'
    },
    {
        'name': 'Mestre das Vendas',
        'description': 'Realize 100 vendas',
        'icon': '👑',
        'badge_color': 'gold',
        'requirement_type': 'sales',
        'requirement_value': 100,
        'points': 1000,
        'rarity': 'epic'
    },
    
    # Receita
    {
        'name': 'Primeiro R$ 100',
        'description': 'Fature R$ 100 em vendas',
        'icon': '💰',
        'badge_color': 'green',
        'requirement_type': 'revenue',
        'requirement_value': 100,
        'points': 100,
        'rarity': 'common'
    },
    {
        'name': 'R$ 1.000 Faturados',
        'description': 'Fature R$ 1.000 em vendas',
        'icon': '💸',
        'badge_color': 'green',
        'requirement_type': 'revenue',
        'requirement_value': 1000,
        'points': 500,
        'rarity': 'rare'
    },
    {
        'name': 'Milionário Digital',
        'description': 'Fature R$ 10.000 em vendas',
        'icon': '🤑',
        'badge_color': 'gold',
        'requirement_type': 'revenue',
        'requirement_value': 10000,
        'points': 2000,
        'rarity': 'epic'
    },
    
    # Streak
    {
        'name': 'Consistência',
        'description': 'Venda por 3 dias consecutivos',
        'icon': '🔥',
        'badge_color': 'orange',
        'requirement_type': 'streak',
        'requirement_value': 3,
        'points': 200,
        'rarity': 'common'
    },
    {
        'name': 'Imparável',
        'description': 'Venda por 7 dias consecutivos',
        'icon': '⚡',
        'badge_color': 'gold',
        'requirement_type': 'streak',
        'requirement_value': 7,
        'points': 500,
        'rarity': 'rare'
    },
    {
        'name': 'Lendário',
        'description': 'Venda por 30 dias consecutivos',
        'icon': '🌟',
        'badge_color': 'gold',
        'requirement_type': 'streak',
        'requirement_value': 30,
        'points': 2000,
        'rarity': 'legendary'
    },
    
    # Conversão
    {
        'name': 'Taxa de Ouro',
        'description': 'Atinja 50% de conversão',
        'icon': '🎖️',
        'badge_color': 'gold',
        'requirement_type': 'conversion_rate',
        'requirement_value': 50,
        'points': 1000,
        'rarity': 'epic'
    },
]

def seed_achievements():
    """Popula achievements no banco"""
    with app.app_context():
        print("Populando achievements...")
        
        # Verificar quantos já existem
        existing = Achievement.query.count()
        print(f"   Achievements existentes: {existing}")
        
        if existing > 0:
            print(f"   Ja existem {existing} achievements. Deseja substituir? (s/N)")
            response = input().strip().lower()
            if response != 's':
                print("   Operacao cancelada.")
                return
            
            # Limpar
            Achievement.query.delete()
            db.session.commit()
            print("   Achievements anteriores removidos")
        
        # Inserir novos
        for ach_data in ACHIEVEMENTS:
            achievement = Achievement(**ach_data)
            db.session.add(achievement)
        
        db.session.commit()
        print(f"   {len(ACHIEVEMENTS)} achievements criados com sucesso!")
        
        # Listar
        print("\nAchievements cadastrados:")
        for ach in Achievement.query.all():
            print(f"   {ach.icon} {ach.name} - {ach.requirement_type} >= {ach.requirement_value} (+{ach.points} pts)")

if __name__ == '__main__':
    seed_achievements()

