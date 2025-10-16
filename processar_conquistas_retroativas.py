#!/usr/bin/env python3
"""
Processa conquistas retroativas para vendas já existentes
"""

from app import app, db
from models import User
from app import check_and_unlock_achievements
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def processar_conquistas():
    """Processa conquistas para todos os usuários com vendas"""
    with app.app_context():
        users = User.query.filter(User.total_sales > 0).all()
        
        print(f"\n{'='*60}")
        print(f"PROCESSANDO CONQUISTAS RETROATIVAS")
        print(f"{'='*60}\n")
        print(f"Total de usuarios com vendas: {len(users)}\n")
        
        total_conquistas = 0
        
        for user in users:
            print(f"\nProcessando: {user.username}")
            print(f"  Vendas: {user.total_sales}")
            print(f"  Receita: R$ {user.total_revenue:.2f}")
            
            try:
                new_achievements = check_and_unlock_achievements(user)
                if new_achievements:
                    print(f"  [OK] {len(new_achievements)} conquista(s) desbloqueada(s)!")
                    for ach in new_achievements:
                        print(f"    - {ach.name}")
                    total_conquistas += len(new_achievements)
                else:
                    print(f"  [INFO] Nenhuma nova conquista")
            except Exception as e:
                print(f"  [ERRO] {e}")
        
        print(f"\n{'='*60}")
        print(f"RESUMO FINAL")
        print(f"{'='*60}")
        print(f"Usuarios processados: {len(users)}")
        print(f"Total de conquistas desbloqueadas: {total_conquistas}")
        print(f"\n[OK] Processamento concluido!")

if __name__ == "__main__":
    processar_conquistas()

