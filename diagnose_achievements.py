#!/usr/bin/env python3
"""
DIAGNÓSTICO COMPLETO DE ACHIEVEMENTS
Execute na VPS para verificar tudo
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'

def diagnose():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("DIAGNOSTICO COMPLETO - ACHIEVEMENTS SYSTEM")
    print("=" * 80)
    
    # 1. Verificar tabelas
    print("\n[1] TABELAS:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    has_achievements = 'achievements' in tables
    has_user_achievements = 'user_achievements' in tables
    
    print(f"   achievements: {'OK' if has_achievements else 'FALTANDO!'}")
    print(f"   user_achievements: {'OK' if has_user_achievements else 'FALTANDO!'}")
    
    if not has_achievements or not has_user_achievements:
        print("\n   ERRO CRITICO: Tabelas nao existem!")
        print("   Execute: python init_db.py")
        conn.close()
        return
    
    # 2. Achievements cadastrados
    print("\n[2] ACHIEVEMENTS CADASTRADOS:")
    cursor.execute("SELECT COUNT(*) FROM achievements")
    total_ach = cursor.fetchone()[0]
    print(f"   Total: {total_ach}")
    
    if total_ach == 0:
        print("   PROBLEMA: Nenhum achievement cadastrado!")
        print("   Execute: python setup_achievements.py")
    else:
        cursor.execute("SELECT id, name, requirement_type, requirement_value, points FROM achievements ORDER BY requirement_value")
        for row in cursor.fetchall():
            print(f"   #{row[0]} - {row[1]} ({row[2]} >= {row[3]}) +{row[4]}pts")
    
    # 3. Usuários e suas vendas
    print("\n[3] USUARIOS E VENDAS:")
    cursor.execute("""
        SELECT 
            u.id,
            u.username,
            COUNT(DISTINCT CASE WHEN p.status = 'paid' THEN p.id END) as vendas_pagas,
            SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as receita,
            u.ranking_points
        FROM users u
        LEFT JOIN bots b ON u.id = b.user_id
        LEFT JOIN payments p ON b.id = p.bot_id
        WHERE u.is_admin = 0
        GROUP BY u.id, u.username, u.ranking_points
    """)
    
    users = cursor.fetchall()
    for row in users:
        print(f"   @{row[1]} (ID:{row[0]})")
        print(f"      Vendas pagas: {row[2]}")
        print(f"      Receita: R$ {row[3] or 0:.2f}")
        print(f"      Pontos ranking: {row[4] or 0}")
    
    # 4. UserAchievements
    print("\n[4] CONQUISTAS DESBLOQUEADAS:")
    cursor.execute("SELECT COUNT(*) FROM user_achievements")
    total_ua = cursor.fetchone()[0]
    print(f"   Total: {total_ua}")
    
    if total_ua == 0:
        print("   PROBLEMA: Nenhuma conquista desbloqueada!")
        print("   Execute: python setup_achievements.py")
    else:
        cursor.execute("""
            SELECT 
                u.username,
                a.name,
                a.points,
                ua.unlocked_at
            FROM user_achievements ua
            JOIN users u ON ua.user_id = u.id
            JOIN achievements a ON ua.achievement_id = a.id
            ORDER BY u.username, ua.unlocked_at DESC
        """)
        
        current_user = None
        for row in cursor.fetchall():
            if current_user != row[0]:
                print(f"\n   @{row[0]}:")
                current_user = row[0]
            print(f"      - {row[1]} (+{row[2]}pts) - {row[3][:19]}")
    
    # 5. Relacionamento User -> UserAchievement
    print("\n[5] VALIDACAO DE RELACIONAMENTO:")
    cursor.execute("""
        SELECT 
            u.id,
            u.username,
            COUNT(ua.id) as total_achievements
        FROM users u
        LEFT JOIN user_achievements ua ON u.id = ua.user_id
        WHERE u.is_admin = 0
        GROUP BY u.id, u.username
    """)
    
    for row in cursor.fetchall():
        status = "OK" if row[2] > 0 else "SEM CONQUISTAS"
        print(f"   User #{row[0]} (@{row[1]}): {row[2]} conquista(s) - {status}")
    
    print("\n" + "=" * 80)
    print("FIM DO DIAGNOSTICO")
    print("=" * 80)
    
    conn.close()

if __name__ == '__main__':
    diagnose()

