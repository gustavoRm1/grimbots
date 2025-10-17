"""
Migração: Adicionar campos success_message e pending_message em bot_configs
"""

import sqlite3
import os
import sys

# Forçar UTF-8 no Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def migrate():
    # Caminho do banco de dados
    db_path = 'instance/grimbots.db'
    
    if not os.path.exists(db_path):
        print(f"[ERRO] Banco de dados nao encontrado: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar se as colunas já existem
        cursor.execute("PRAGMA table_info(bot_configs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"[INFO] Colunas atuais em bot_configs: {columns}")
        
        # Adicionar success_message se não existir
        if 'success_message' not in columns:
            print("[+] Adicionando coluna success_message...")
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN success_message TEXT")
            print("[OK] Coluna success_message adicionada!")
        else:
            print("[AVISO] Coluna success_message ja existe")
        
        # Adicionar pending_message se não existir
        if 'pending_message' not in columns:
            print("[+] Adicionando coluna pending_message...")
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN pending_message TEXT")
            print("[OK] Coluna pending_message adicionada!")
        else:
            print("[AVISO] Coluna pending_message ja existe")
        
        conn.commit()
        print("[OK] Migracao concluida com sucesso!")
        
        # Verificar novamente
        cursor.execute("PRAGMA table_info(bot_configs)")
        columns_after = [row[1] for row in cursor.fetchall()]
        print(f"[INFO] Colunas apos migracao: {columns_after}")
        
    except Exception as e:
        print(f"[ERRO] Erro na migracao: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()

