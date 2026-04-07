"""
LEGACY BOT STATISTICS - CÓDIGO COMPLETO EXTRAÍDO
================================================
Extraído de old_app_before_refactor.py (linhas ~5245-5400)

Este arquivo contém a lógica completa de cálculo de estatísticas do bot
incluindo métricas, gráficos e conversão que precisa ser migrada.
"""

# ============================================================================
# IMPORTS NECESSÁRIOS
# ============================================================================
from sqlalchemy import func, extract, case
from datetime import datetime, timedelta
from models import BotUser, Payment
from utils import get_brazil_time


# ============================================================================
# FUNÇÃO PRINCIPAL: get_bot_stats(bot_id)
# ============================================================================
"""
@app.route('/api/bots/<int:bot_id>/stats', methods=['GET'])
@login_required
def get_bot_stats(bot_id):
    \"\"\"API para estatísticas detalhadas de um bot específico\"\"\"
    from sqlalchemy import func, extract, case
    from models import BotUser
    
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # ============================================================================
    # MÉTRICAS PRINCIPAIS
    # ============================================================================
    
    # Total de usuários do bot
    total_users = BotUser.query.filter_by(bot_id=bot_id, archived=False).count()
    
    # Vendas pagas
    total_sales = Payment.query.filter_by(bot_id=bot_id, status='paid').count()
    
    # Taxa de conversão
    conversion_rate = (total_sales / total_users * 100) if total_users > 0 else 0
    
    # Receita total
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id == bot_id, 
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    # ============================================================================
    # MÉTRICAS POR PERÍODO (HOJE VS ONTEM)
    # ============================================================================
    
    # Hoje
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = Payment.query.filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= today_start
    ).count()
    
    today_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= today_start
    ).scalar() or 0.0
    
    # Ontem
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_start
    
    yesterday_sales = Payment.query.filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= yesterday_start,
        Payment.created_at < yesterday_end
    ).count()
    
    yesterday_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= yesterday_start,
        Payment.created_at < yesterday_end
    ).scalar() or 0.0
    
    # ============================================================================
    # MÉTRICAS DE CONVERSAO AVANÇADAS
    # ============================================================================
    
    # Diferenciação: PIX Gerado vs Venda Real
    pix_generated = Payment.query.filter_by(bot_id=bot_id, status='pending').count()
    real_sales = Payment.query.filter_by(bot_id=bot_id, status='paid').count()
    
    # Taxa de conversão do PIX
    pix_conversion_rate = (real_sales / pix_generated * 100) if pix_generated > 0 else 0
    
    # ============================================================================
    # GRÁFICO DE VENDAS (ÚLTIMOS 7 DIAS)
    # ============================================================================
    
    period = 7  # Padrão: 7 dias
    start_date = get_brazil_time() - timedelta(days=period)
    
    # Query para vendas por dia
    sales_by_day = db.session.query(
        func.date(Payment.created_at).label('date'),
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= start_date
    ).group_by(func.date(Payment.created_at)).all()
    
    # Preencher dias sem vendas (do mais antigo ao mais recente)
    daily_sales = []
    for i in range(period):
        date = (get_brazil_time() - timedelta(days=(period - 1 - i))).date()
        day_data = next((s for s in sales_by_day if str(s.date) == str(date)), None)
        daily_sales.append({
            'date': date.strftime('%d/%m'),
            'sales': day_data.sales if day_data else 0,
            'revenue': float(day_data.revenue) if day_data else 0.0
        })
    
    # ============================================================================
    # MÉTRICAS ADICIONAIS (TICKET MÉDIO, ETC)
    # ============================================================================
    
    # Ticket médio
    avg_ticket = (total_revenue / total_sales) if total_sales > 0 else 0
    
    # Vendas por status
    sales_by_status = db.session.query(
        Payment.status,
        func.count(Payment.id).label('count')
    ).filter(Payment.bot_id == bot_id).group_by(Payment.status).all()
    
    status_breakdown = {status: count for status, count in sales_by_status}
    
    # ============================================================================
    # CONTRATO DO FRONTEND (VARIÁVEIS ENVIADAS)
    # ============================================================================
    
    stats = {
        # Métricas principais
        'total_users': total_users,
        'total_sales': total_sales,
        'total_revenue': float(total_revenue),
        'conversion_rate': float(conversion_rate),
        'avg_ticket': float(avg_ticket),
        
        # Hoje vs Ontem
        'today_sales': today_sales,
        'today_revenue': float(today_revenue),
        'yesterday_sales': yesterday_sales,
        'yesterday_revenue': float(yesterday_revenue),
        
        # Conversão PIX
        'pix_generated': pix_generated,
        'pix_conversion_rate': float(pix_conversion_rate),
        
        # Gráfico
        'daily_sales': daily_sales,  # Lista de dicts com 'date', 'sales', 'revenue'
        
        # Breakdown por status
        'status_breakdown': status_breakdown,
        
        # Período do gráfico
        'chart_period': 7  # dias
    }
    
    return jsonify(stats)
"""


# ============================================================================
# FUNÇÕES AUXILIARES DE CÁLCULO DE PERÍODO
# ============================================================================

def get_period_start(period_type):
    \"\"\"Calcula o início do período baseado no tipo\"\"\"
    now = get_brazil_time()
    
    if period_type == 'today':
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period_type == 'yesterday':
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period_type == 'week':
        return now - timedelta(days=7)
    elif period_type == 'month':
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period_type == 'year':
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return now - timedelta(days=30)  # Padrão: 30 dias


def format_currency(amount):
    \"\"\"Formata valor monetário em BRL\"\"\"
    return f"R$ {amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def calculate_growth_rate(current, previous):
    \"\"\"Calcula taxa de crescimento percentual\"\"\"
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return ((current - previous) / previous) * 100


# ============================================================================
# QUERIES SQL ALCHEMY PADRÃO
# ============================================================================

def get_revenue_query(bot_id, start_date=None, end_date=None):
    \"\"\"Query padrão para receita\"\"\"
    query = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid'
    )
    
    if start_date:
        query = query.filter(Payment.created_at >= start_date)
    if end_date:
        query = query.filter(Payment.created_at <= end_date)
        
    return query.scalar() or 0.0


def get_sales_count_query(bot_id, start_date=None, end_date=None, status='paid'):
    \"\"\"Query padrão para contagem de vendas\"\"\"
    query = Payment.query.filter(
        Payment.bot_id == bot_id,
        Payment.status == status
    )
    
    if start_date:
        query = query.filter(Payment.created_at >= start_date)
    if end_date:
        query = query.filter(Payment.created_at <= end_date)
        
    return query.count()


def get_sales_by_period_query(bot_id, period_days=7):
    \"\"\"Query para vendas agrupadas por dia\"\"\"
    start_date = get_brazil_time() - timedelta(days=period_days)
    
    return db.session.query(
        func.date(Payment.created_at).label('date'),
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.bot_id == bot_id,
        Payment.status == 'paid',
        Payment.created_at >= start_date
    ).group_by(func.date(Payment.created_at)).all()


# ============================================================================
# ESTRUTURA DE DADOS ESPERADA PELO FRONTEND
# ============================================================================

FRONTEND_CONTRACT = {
    'stats': {
        'total_users': 'int',
        'total_sales': 'int', 
        'total_revenue': 'float',
        'conversion_rate': 'float',
        'avg_ticket': 'float',
        'today_sales': 'int',
        'today_revenue': 'float',
        'yesterday_sales': 'int',
        'yesterday_revenue': 'float',
        'pix_generated': 'int',
        'pix_conversion_rate': 'float',
        'status_breakdown': 'dict',
        'chart_period': 'int'
    },
    'daily_sales': [
        {
            'date': 'string (DD/MM)',
            'sales': 'int',
            'revenue': 'float'
        }
    ]
}

# ============================================================================
# OBSERVAÇÕES CRÍTICAS PARA MIGRAÇÃO
# ============================================================================

"""
1. DIFERENCIAÇÃO CRÍTICA:
   - 'Venda Real' = status='paid'
   - 'PIX Gerado' = status='pending'
   
2. FILTROS DE DATA:
   - Hoje: created_at >= today_start
   - Ontem: created_at >= yesterday_start AND < yesterday_end
   - 7 dias: created_at >= (now - 7 days)
   - 30 dias: created_at >= (now - 30 days)
   
3. GRÁFICO:
   - daily_sales é uma LISTA de dicts
   - Cada dict tem: date (DD/MM), sales (int), revenue (float)
   - Preencher dias sem vendas com zeros
   
4. CONVERSÃO:
   - Taxa = (vendas / usuarios) * 100
   - PIX Conversion = (paid / pending) * 100
   
5. QUERY PATTERNS:
   - Usar func.sum() para valores monetários
   - Usar func.count() para contagens
   - Agrupar por func.date() para gráficos diários
"""
