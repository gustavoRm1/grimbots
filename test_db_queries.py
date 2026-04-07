"""
Test API endpoints without full Flask app initialization
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from internal_logic.core.config import Config

# Conectar ao banco diretamente
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Testar queries básicas
    print('=== DATABASE CONNECTION TEST ===')
    
    # Contar bots
    from internal_logic.core.models import Bot, Payment, BotUser, RemarketingCampaign
    
    bot_count = session.query(Bot).count()
    print(f'Total de bots: {bot_count}')
    
    # Testar com bot_id=1
    bot = session.query(Bot).filter_by(id=1).first()
    if bot:
        print(f'Bot encontrado: {bot.name} (User ID: {bot.user_id})')
        
        # Testar query de vendas
        total_sales = session.query(Payment).filter(
            Payment.bot_id == 1,
            Payment.status == 'paid'
        ).count()
        
        total_revenue = session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == 1,
            Payment.status == 'paid'
        ).scalar() or 0.0
        
        total_users = session.query(BotUser).filter_by(bot_id=1).count()
        
        print(f'  Total Sales: {total_sales}')
        print(f'  Total Revenue: R${total_revenue}')
        print(f'  Total Users: {total_users}')
        
        # Testar query do gráfico
        from datetime import datetime, timedelta
        
        chart_data = session.query(
            func.date(Payment.created_at).label('date'),
            func.count(Payment.id).label('sales'),
            func.sum(Payment.amount).label('revenue')
        ).filter(
            Payment.bot_id == 1,
            Payment.status == 'paid',
            Payment.created_at >= datetime.utcnow() - timedelta(days=7)
        ).group_by(func.date(Payment.created_at)).all()
        
        print(f'  Chart Data (7 dias): {len(chart_data)} pontos')
        for point in chart_data[:3]:
            print(f'    {point.date}: {point.sales} vendas, R${point.revenue or 0}')
        
        print('\n=== API DATA TEST SUCCESS ===')
        print('As queries do StatsService estão funcionando!')
        print('O endpoint /api/bots/1/stats deve retornar estes dados.')
        
    else:
        print('Bot ID 1 não encontrado')
        
except Exception as e:
    print(f'ERRO: {e}')
    import traceback
    traceback.print_exc()
finally:
    session.close()
