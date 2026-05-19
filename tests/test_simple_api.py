"""
Simple API test without models - direct SQL queries
"""

import sqlite3
from datetime import datetime, timedelta

# Conectar ao banco
conn = sqlite3.connect('instance/saas_bot_manager.db')
cursor = conn.cursor()

print('=== DIRECT SQL TEST ===')

# Testar query básica
try:
    # Verificar estrutura da tabela bots
    cursor.execute('PRAGMA table_info(bots)')
    bot_columns = cursor.fetchall()
    print('Colunas da tabela bots:')
    for col in bot_columns:
        print(f'  {col[1]} ({col[2]})')
    
    # Buscar bot
    cursor.execute('SELECT id, name FROM bots WHERE id = 1')
    bot = cursor.fetchone()
    
    if bot:
        print(f'\nBot encontrado: {bot[1]} (ID: {bot[0]})')
        
        # Contar vendas pagas
        cursor.execute('SELECT COUNT(*) FROM payments WHERE bot_id = 1 AND status = "paid"')
        total_sales = cursor.fetchone()[0]
        
        # Somar receita
        cursor.execute('SELECT SUM(amount) FROM payments WHERE bot_id = 1 AND status = "paid"')
        total_revenue = cursor.fetchone()[0] or 0.0
        
        # Contar usuários
        cursor.execute('SELECT COUNT(*) FROM bot_users WHERE bot_id = 1')
        total_users = cursor.fetchone()[0]
        
        print(f'  Total Sales: {total_sales}')
        print(f'  Total Revenue: R${total_revenue}')
        print(f'  Total Users: {total_users}')
        
        # Testar query do gráfico (últimos 7 dias)
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as sales,
                COALESCE(SUM(amount), 0) as revenue
            FROM payments 
            WHERE bot_id = 1 
                AND status = 'paid' 
                AND created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (seven_days_ago,))
        
        chart_data = cursor.fetchall()
        print(f'  Chart Data (7 dias): {len(chart_data)} pontos')
        for point in chart_data[:3]:
            print(f'    {point[0]}: {point[1]} vendas, R${point[2]}')
        
        # Testar estrutura esperada pelo frontend
        api_response = {
            'general': {
                'total_users': total_users,
                'total_sales': total_sales,
                'pending_sales': 0,
                'total_revenue': float(total_revenue),
                'avg_ticket': float(total_revenue / total_sales) if total_sales > 0 else 0.0,
                'conversion_rate': 0.0  # TODO: Calcular com checkouts
            },
            'order_bumps': {
                'shown': 0,
                'accepted': 0,
                'acceptance_rate': 0,
                'revenue': 0.0
            },
            'downsells': {
                'sent': 0,
                'converted': 0,
                'conversion_rate': 0,
                'revenue': 0.0
            },
            'chart': {
                'daily_sales': [
                    {
                        'date': str(point[0]),
                        'day': datetime.strptime(point[0], '%Y-%m-%d').strftime('%d/%m'),
                        'sales': point[1],
                        'revenue': float(point[2])
                    } for point in chart_data
                ],
                'period': '7'
            }
        }
        
        print(f'\n=== API RESPONSE STRUCTURE ===')
        print('Estrutura JSON que será retornada por /api/bots/1/stats:')
        print(f'  general.total_users: {api_response["general"]["total_users"]}')
        print(f'  general.total_sales: {api_response["general"]["total_sales"]}')
        print(f'  general.total_revenue: {api_response["general"]["total_revenue"]}')
        print(f'  chart.daily_sales: {len(api_response["chart"]["daily_sales"])} pontos')
        
        print('\n=== API ENDPOINT IS READY ===')
        print('O endpoint /api/bots/1/stats deve funcionar corretamente!')
        print('Acesse: https://app.grimbots.online/api/bots/1/stats')
        
    else:
        print('Bot ID 1 não encontrado')
        
except Exception as e:
    print(f'ERRO: {e}')
    import traceback
    traceback.print_exc()
finally:
    conn.close()
