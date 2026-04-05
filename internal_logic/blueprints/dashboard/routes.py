"""
Dashboard Blueprint - Rotas do Painel Principal
================================================
Dashboard e APIs de analytics
"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from internal_logic.core.extensions import db
from models import Bot, Payment, User
from sqlalchemy import func, extract
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Criar Blueprint
dashboard_bp = Blueprint('dashboard', __name__)


def get_brazil_time():
    """Retorna o horário atual do Brasil (UTC-3)"""
    from datetime import timedelta
    from datetime import datetime as dt
    return dt.utcnow() + timedelta(hours=-3)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal com modo simples/avançado"""
    from sqlalchemy import func
    from models import BotUser
    
    # Obter modo (simples ou avançado)
    mode = request.args.get('mode', 'advanced')
    
    # Estatísticas básicas
    bots_count = Bot.query.filter_by(user_id=current_user.id).count()
    active_bots = Bot.query.filter_by(user_id=current_user.id, is_active=True).count()
    
    # Vendas hoje
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = Payment.query.join(Bot).filter(
        Bot.user_id == current_user.id,
        Payment.status == 'paid',
        Payment.created_at >= today_start
    ).count()
    
    # Receita total
    total_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
        Bot.user_id == current_user.id,
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    # Taxa de conversão
    user_bot_ids = [bot.id for bot in current_user.bots]
    total_clicks = BotUser.query.filter(BotUser.bot_id.in_(user_bot_ids)).count() if user_bot_ids else 0
    total_purchases = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).count() if user_bot_ids else 0
    conversion_rate = (total_purchases / total_clicks * 100) if total_clicks > 0 else 0
    
    # Streak
    streak = current_user.current_streak or 0
    
    return render_template(
        'dashboard.html',
        mode=mode,
        stats={
            'bots_count': bots_count,
            'active_bots': active_bots,
            'today_sales': today_sales,
            'total_revenue': total_revenue,
            'conversion_rate': round(conversion_rate, 2),
            'streak': streak
        },
        user=current_user
    )


@dashboard_bp.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API para estatísticas do dashboard (usado pelo JavaScript)"""
    from sqlalchemy import func
    from models import BotUser
    
    # IDs dos bots do usuário
    user_bot_ids = [bot.id for bot in current_user.bots]
    
    if not user_bot_ids:
        return jsonify({
            'today_sales': 0,
            'today_revenue': 0,
            'total_revenue': 0,
            'conversion_rate': 0,
            'active_bots': 0,
            'total_bots': 0
        })
    
    # Vendas hoje
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    today_stats = db.session.query(
        func.count(Payment.id).label('count'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid',
        Payment.created_at >= today_start
    ).first()
    
    # Receita total
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    # Bots
    total_bots = len(user_bot_ids)
    active_bots = Bot.query.filter(
        Bot.id.in_(user_bot_ids),
        Bot.is_active == True
    ).count()
    
    # Taxa de conversão
    total_clicks = BotUser.query.filter(BotUser.bot_id.in_(user_bot_ids)).count()
    total_purchases = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).count()
    conversion_rate = (total_purchases / total_clicks * 100) if total_clicks > 0 else 0
    
    return jsonify({
        'today_sales': today_stats.count if today_stats else 0,
        'today_revenue': float(today_stats.revenue) if today_stats and today_stats.revenue else 0.0,
        'total_revenue': float(total_revenue),
        'conversion_rate': round(conversion_rate, 2),
        'active_bots': active_bots,
        'total_bots': total_bots
    })


@dashboard_bp.route('/api/dashboard/sales-chart')
@login_required
def api_sales_chart():
    """API para dados do gráfico de vendas (últimos N dias: 7/30/90)"""
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Ler período desejado (default 7). Aceitar apenas 7, 30, 90
    try:
        period = int(request.args.get('period', 7))
    except Exception:
        period = 7
    if period not in (7, 30, 90):
        period = 7
    
    start_date = get_brazil_time() - timedelta(days=period)
    
    # IDs dos bots do usuário
    user_bot_ids = [bot.id for bot in current_user.bots]
    
    if not user_bot_ids:
        # Retornar dados vazios
        result = []
        for i in range(period):
            date = (get_brazil_time() - timedelta(days=(period - 1 - i))).date()
            result.append({
                'date': date.strftime('%d/%m'),
                'sales': 0,
                'revenue': 0.0
            })
        return jsonify(result)
    
    # Query para vendas por dia
    sales_by_day = db.session.query(
        func.date(Payment.created_at).label('date'),
        func.count(Payment.id).label('sales'),
        func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.created_at >= start_date,
        Payment.status == 'paid'
    ).group_by(func.date(Payment.created_at))\
     .order_by(func.date(Payment.created_at))\
     .all()
    
    # Preencher dias sem vendas (do mais antigo ao mais recente)
    result = []
    for i in range(period):
        date = (get_brazil_time() - timedelta(days=(period - 1 - i))).date()
        day_data = next((s for s in sales_by_day if str(s.date) == str(date)), None)
        result.append({
            'date': date.strftime('%d/%m'),
            'sales': day_data.sales if day_data else 0,
            'revenue': float(day_data.revenue) if day_data and day_data.revenue is not None else 0.0
        })
    
    return jsonify(result)


@dashboard_bp.route('/api/dashboard/analytics')
@login_required
def api_dashboard_analytics():
    """API para métricas avançadas e analytics"""
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta
    from models import BotUser, Commission
    
    # IDs dos bots do usuário
    user_bot_ids = [bot.id for bot in current_user.bots]
    
    if not user_bot_ids:
        return jsonify({
            'conversion_rate': 0,
            'avg_ticket': 0,
            'order_bump_stats': {},
            'downsell_stats': {},
            'peak_hours': [],
            'commission_data': {}
        })
    
    # 1. TAXA DE CONVERSÃO (cliques vs compras)
    total_clicks = BotUser.query.filter(BotUser.bot_id.in_(user_bot_ids)).count()
    total_purchases = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).count()
    conversion_rate = (total_purchases / total_clicks * 100) if total_clicks > 0 else 0
    
    # 2. TICKET MÉDIO
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).scalar() or 0.0
    avg_ticket = (total_revenue / total_purchases) if total_purchases > 0 else 0
    
    # 2.1. VENDAS HOJE
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid',
        Payment.created_at >= today_start
    ).count()
    
    # 3. PERFORMANCE DE ORDER BUMPS
    order_bump_shown_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.order_bump_shown == True
    ).count()
    
    order_bump_accepted_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.order_bump_accepted == True
    ).count()
    
    order_bump_revenue = db.session.query(func.sum(Payment.order_bump_value)).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.order_bump_accepted == True,
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    order_bump_acceptance_rate = (order_bump_accepted_count / order_bump_shown_count * 100) if order_bump_shown_count > 0 else 0
    
    # 4. PERFORMANCE DE DOWNSELLS
    downsell_sent_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.is_downsell == True
    ).count()
    
    downsell_paid_count = Payment.query.filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.is_downsell == True,
        Payment.status == 'paid'
    ).count()
    
    downsell_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.is_downsell == True,
        Payment.status == 'paid'
    ).scalar() or 0.0
    
    downsell_conversion_rate = (downsell_paid_count / downsell_sent_count * 100) if downsell_sent_count > 0 else 0
    
    # 5. HORÁRIOS DE PICO (vendas por hora)
    peak_hours_data = db.session.query(
        extract('hour', Payment.created_at).label('hour'),
        func.count(Payment.id).label('sales')
    ).filter(
        Payment.bot_id.in_(user_bot_ids),
        Payment.status == 'paid'
    ).group_by(extract('hour', Payment.created_at))\
     .order_by(extract('hour', Payment.created_at))\
     .all()
    
    peak_hours = [
        {'hour': int(h.hour), 'sales': h.sales}
        for h in peak_hours_data
    ]
    
    # 6. DADOS DE COMISSÕES
    commission_data = {
        'total_commissions': 0,
        'paid_commissions': 0,
        'pending_commissions': 0
    }
    
    return jsonify({
        'conversion_rate': round(conversion_rate, 2),
        'avg_ticket': round(avg_ticket, 2),
        'today_sales': today_sales,
        'order_bump_stats': {
            'shown': order_bump_shown_count,
            'accepted': order_bump_accepted_count,
            'rate': round(order_bump_acceptance_rate, 2),
            'revenue': float(order_bump_revenue)
        },
        'downsell_stats': {
            'sent': downsell_sent_count,
            'paid': downsell_paid_count,
            'rate': round(downsell_conversion_rate, 2),
            'revenue': float(downsell_revenue)
        },
        'peak_hours': peak_hours,
        'commission_data': commission_data
    })
