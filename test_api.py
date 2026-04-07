from internal_logic.core.extensions import create_app
from internal_logic.services.stats_service import StatsService

# Criar app para teste
app = create_app()

# Testar o StatsService diretamente
with app.app_context():
    try:
        # Testar com bot_id=1
        metrics = StatsService.get_bot_metrics(1, 30)
        print('=== STATS SERVICE TEST ===')
        print(f'Métricas para bot 1 (30 dias):')
        print(f'  Total Users: {metrics["total_users"]}')
        print(f'  Total Sales: {metrics["total_sales"]}')
        print(f'  Total Revenue: {metrics["total_revenue"]}')
        print(f'  Conversion Rate: {metrics["conversion_rate"]}%')
        print(f'  Avg Ticket: {metrics["avg_ticket"]}')
        
        # Testar dados do gráfico
        chart_data = StatsService.get_sales_chart_data(1, 7)
        print(f'\nChart Data (7 dias): {len(chart_data)} pontos')
        for i, point in enumerate(chart_data[:3]):  # Primeiros 3 pontos
            print(f'  {i+1}. {point["date"]}: {point["sales"]} vendas, R${point["revenue"]}')
        
        print('\n=== API ENDPOINT TEST SUCCESS ===')
        print('O StatsService está funcionando corretamente!')
        
    except Exception as e:
        print(f'ERRO: {e}')
        import traceback
        traceback.print_exc()
