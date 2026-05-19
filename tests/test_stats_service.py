"""
Test StatsService integrity with Bot ID 94
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from internal_logic.services.stats_service import StatsService
from internal_logic.core.extensions import db
from sqlalchemy import text

def test_bot_94_data():
    print('=== TESTING BOT ID 94 INTEGRITY ===')
    
    try:
        # Criar contexto de aplicação Flask
        from internal_logic.core.extensions import create_app
        app = create_app()
        
        with app.app_context():
            # Test 1: Verificar se Bot ID 94 existe
            engine = db.engine
            connection = engine.connect()
            
            bot_check = connection.execute(
                text("SELECT id, name, user_id FROM bots WHERE id = :bot_id"),
                {"bot_id": 94}
            ).first()
            
            if bot_check:
                print(f'Bot ID 94 encontrado: {bot_check.name} (User ID: {bot_check.user_id})')
            else:
                print('Bot ID 94 NÃO encontrado - usando fallbacks')
            
            # Test 2: Verificar dados de pagamentos
            payments_check = connection.execute(
                text("SELECT COUNT(*) as count FROM payments WHERE bot_id = :bot_id"),
                {"bot_id": 94}
            ).scalar()
            
            print(f'Payments para Bot 94: {payments_check}')
            
            # Test 3: Testar StatsService diretamente
            print('\n=== TESTING STATSSERVICE METHODS ===')
            
            # Testar get_bot_metrics
            try:
                metrics = StatsService.get_bot_metrics(94, 30)
                print(f'get_bot_metrics(94): SUCESSO')
                print(f'  total_sales: {metrics["total_sales"]}')
                print(f'  total_revenue: {metrics["total_revenue"]}')
                print(f'  total_users: {metrics["total_users"]}')
            except Exception as e:
                print(f'get_bot_metrics(94): ERRO - {e}')
            
            # Testar get_sales_chart_data
            try:
                chart_data = StatsService.get_sales_chart_data(94, 7)
                print(f'get_sales_chart_data(94): SUCESSO - {len(chart_data)} pontos')
            except Exception as e:
                print(f'get_sales_chart_data(94): ERRO - {e}')
            
            # Testar get_remarketing_metrics
            try:
                remarketing = StatsService.get_remarketing_metrics(94)
                print(f'get_remarketing_metrics(94): SUCESSO')
                print(f'  total_campaigns: {remarketing["total_campaigns"]}')
                print(f'  total_sent: {remarketing["total_sent"]}')
            except Exception as e:
                print(f'get_remarketing_metrics(94): ERRO - {e}')
            
            # Testar get_gateway_stats
            try:
                gateway_stats = StatsService.get_gateway_stats(94, 30)
                print(f'get_gateway_stats(94): SUCESSO - {len(gateway_stats)} gateways')
            except Exception as e:
                print(f'get_gateway_stats(94): ERRO - {e}')
            
            # Testar get_peak_hours
            try:
                peak_hours = StatsService.get_peak_hours(94, 30)
                print(f'get_peak_hours(94): SUCESSO - {len(peak_hours)} horas')
            except Exception as e:
                print(f'get_peak_hours(94): ERRO - {e}')
            
            connection.close()
            print('\n=== INTEGRITY TEST COMPLETED ===')
        
    except Exception as e:
        print(f'ERRO CRÍTICO NO TESTE: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bot_94_data()
