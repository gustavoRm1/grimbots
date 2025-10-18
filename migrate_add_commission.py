"""
Migration: Adicionar colunas de comissão na tabela users
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'

def migrate():
    """Adiciona colunas faltantes"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Verificando colunas da tabela users...")
    
    # Verificar colunas existentes
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"   Colunas existentes: {len(columns)}")
    
    migrations = []
    
    # Adicionar commission_percentage
    if 'commission_percentage' not in columns:
        migrations.append("ALTER TABLE users ADD COLUMN commission_percentage FLOAT DEFAULT 2.0")
        print("   + commission_percentage")
    
    # Adicionar total_commission_owed
    if 'total_commission_owed' not in columns:
        migrations.append("ALTER TABLE users ADD COLUMN total_commission_owed FLOAT DEFAULT 0.0")
        print("   + total_commission_owed")
    
    # Adicionar total_commission_paid
    if 'total_commission_paid' not in columns:
        migrations.append("ALTER TABLE users ADD COLUMN total_commission_paid FLOAT DEFAULT 0.0")
        print("   + total_commission_paid")
    
    if not migrations:
        print("   Nenhuma migracao necessaria!")
        conn.close()
        return
    
    # Executar migrations
    print(f"\nExecutando {len(migrations)} migration(s)...")
    for sql in migrations:
        try:
            cursor.execute(sql)
            print(f"   OK: {sql[:50]}...")
        except Exception as e:
            print(f"   ERRO: {e}")
    
    conn.commit()
    conn.close()
    print("\nMigration concluida!")

if __name__ == '__main__':
    migrate()

