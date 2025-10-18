"""
Verifica pagamentos no banco
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Verificando pagamentos...")

# Total de pagamentos
cursor.execute("SELECT COUNT(*) FROM payments")
total = cursor.fetchone()[0]
print(f"   Total de pagamentos: {total}")

# Por status
cursor.execute("SELECT status, COUNT(*), SUM(amount) FROM payments GROUP BY status")
by_status = cursor.fetchall()

print("\nPor status:")
for status, count, amount in by_status:
    print(f"   {status}: {count} pagamento(s) - R$ {amount or 0:.2f}")

# Últimos 10 pagamentos
print("\nUltimos 10 pagamentos:")
cursor.execute("""
    SELECT id, customer_name, product_name, amount, status, created_at 
    FROM payments 
    ORDER BY id DESC 
    LIMIT 10
""")
payments = cursor.fetchall()

for p in payments:
    print(f"   #{p[0]} - {p[1]} - {p[2]} - R$ {p[3]:.2f} - {p[4]} - {p[5]}")

conn.close()

