"""
Verificar estrutura do banco de dados
"""
import sqlite3
import os

db_path = 'instance/grimbots.db'

if not os.path.exists(db_path):
    print(f"ERRO: Banco nao encontrado em {db_path}")
    exit(1)

print(f"Banco encontrado: {db_path}")
print(f"Tamanho: {os.path.getsize(db_path) / 1024:.2f} KB")
print("")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Listar todas as colunas de bot_configs
cursor.execute("PRAGMA table_info(bot_configs)")
columns = cursor.fetchall()

print("=== COLUNAS EM bot_configs ===")
for col in columns:
    print(f"{col[0]:2d}. {col[1]:25s} {col[2]:10s}")

print(f"\nTotal de colunas: {len(columns)}")

# Verificar se as colunas existem
column_names = [col[1] for col in columns]
print(f"\nsuccess_message existe? {'SIM' if 'success_message' in column_names else 'NAO'}")
print(f"pending_message existe? {'SIM' if 'pending_message' in column_names else 'NAO'}")

# Contar registros
cursor.execute("SELECT COUNT(*) FROM bot_configs")
count = cursor.fetchone()[0]
print(f"\nTotal de registros em bot_configs: {count}")

conn.close()

