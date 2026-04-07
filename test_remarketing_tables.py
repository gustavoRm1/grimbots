"""
Test remarketing tables and fix SQL queries
"""

import sqlite3

# Conectar ao banco
conn = sqlite3.connect('instance/saas_bot_manager.db')
cursor = conn.cursor()

print('=== REMARKETING TABLES CHECK ===')

# Verificar tabelas de remarketing
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%remarket%'")
tables = cursor.fetchall()

print('Tabelas de remarketing encontradas:')
for table in tables:
    print(f'  {table[0]}')
    
    # Verificar estrutura
    cursor.execute(f'PRAGMA table_info({table[0]})')
    columns = cursor.fetchall()
    print(f'    Colunas: {[col[1] for col in columns]}')

# Testar query de remarketing com nome correto da tabela
if tables:
    table_name = tables[0][0]  # Usar primeira tabela encontrada
    
    print(f'\n=== TESTANDO COM TABELA: {table_name} ===')
    
    # Testar contagem
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name} WHERE bot_id = 1')
        count = cursor.fetchone()[0]
        print(f'Total de campanhas para bot 1: {count}')
        
        # Testar query de totais
        cursor.execute(f'''
            SELECT 
                COALESCE(SUM(total_sent), 0) as total_sent,
                COALESCE(SUM(total_clicks), 0) as total_clicks,
                COALESCE(SUM(total_sales), 0) as total_sales,
                COALESCE(SUM(revenue_generated), 0) as revenue_generated
            FROM {table_name} 
            WHERE bot_id = 1
        ''')
        totals = cursor.fetchone()
        print(f'Totais: {totals}')
        
    except Exception as e:
        print(f'ERRO na query: {e}')

conn.close()
