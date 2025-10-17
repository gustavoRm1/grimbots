"""
Forçar adição de colunas success_message e pending_message
"""
import sqlite3
import os

db_path = 'instance/grimbots.db'

if not os.path.exists(db_path):
    print("ERRO: Banco nao encontrado")
    exit(1)

print(f"Conectando ao banco: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Verificar colunas atuais
    cursor.execute("PRAGMA table_info(bot_configs)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Colunas atuais: {columns}")
    
    # Tentar adicionar success_message
    if 'success_message' not in columns:
        try:
            print("\nAdicionando coluna success_message...")
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN success_message TEXT")
            conn.commit()
            print("OK: success_message adicionada!")
        except sqlite3.OperationalError as e:
            print(f"ERRO ao adicionar success_message: {e}")
    else:
        print("\nColuna success_message JA EXISTE")
    
    # Tentar adicionar pending_message
    if 'pending_message' not in columns:
        try:
            print("\nAdicionando coluna pending_message...")
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN pending_message TEXT")
            conn.commit()
            print("OK: pending_message adicionada!")
        except sqlite3.OperationalError as e:
            print(f"ERRO ao adicionar pending_message: {e}")
    else:
        print("\nColuna pending_message JA EXISTE")
    
    # Verificar novamente
    print("\n=== VERIFICACAO FINAL ===")
    cursor.execute("PRAGMA table_info(bot_configs)")
    columns_after = cursor.fetchall()
    
    for col in columns_after:
        if 'message' in col[1]:
            print(f"{col[0]:2d}. {col[1]:25s} {col[2]:10s}")
    
    column_names_after = [col[1] for col in columns_after]
    print(f"\nsuccess_message existe? {'SIM' if 'success_message' in column_names_after else 'NAO'}")
    print(f"pending_message existe? {'SIM' if 'pending_message' in column_names_after else 'NAO'}")
    
except Exception as e:
    print(f"\nERRO GERAL: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()
    print("\nConexao fechada")

