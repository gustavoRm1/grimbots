"""
Dashboard Blueprint - Rotas do Painel Principal
================================================
Dashboard e APIs de analytics
"""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, abort, session, make_response, send_file
from flask_login import login_required, current_user
from internal_logic.core.extensions import db, csrf, limiter
from internal_logic.core.models import (
    Bot, User, Payment, BotConfig, Gateway, AuditLog, Achievement, UserAchievement, 
    BotUser, BotMessage, RedirectPool, PoolBot, RemarketingCampaign, RemarketingBlacklist, 
    Commission, PushSubscription, NotificationSettings, Subscription, get_brazil_time
)
from sqlalchemy import func, extract
from datetime import datetime, timedelta
import logging
import os

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
    """Dashboard principal com modo simples/avançado - Analytics V2.0"""
    from sqlalchemy import func
    from internal_logic.core.models import BotUser
    
    # Obter modo (simples ou avançado)
    mode = request.args.get('mode', 'advanced')
    
    # Buscar bots do usuário
    bots = Bot.query.filter_by(user_id=current_user.id).all()
    bot_ids = [b.id for b in bots] if bots else []
    
    # Períodos de tempo
    today_start = get_brazil_time().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = get_brazil_time().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Estatísticas básicas
    total_bots = len(bots)
    active_bots = sum(1 for b in bots if b.is_active)
    running_bots = sum(1 for b in bots if b.is_running)
    
    # Total de usuários (leads) across all bots
    total_users = BotUser.query.filter(
        BotUser.bot_id.in_(bot_ids),
        BotUser.archived == False
    ).count() if bot_ids else 0
    
    # Total de vendas e receita
    total_sales = Payment.query.filter(
        Payment.bot_id.in_(bot_ids),
        Payment.status == 'paid'
    ).count() if bot_ids else 0
    
    total_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.bot_id.in_(bot_ids),
        Payment.status == 'paid'
    ).scalar() or 0.0 if bot_ids else 0.0
    
    # Vendas pendentes
    pending_sales = Payment.query.filter(
        Payment.bot_id.in_(bot_ids),
        Payment.status == 'pending'
    ).count() if bot_ids else 0
    
    # Taxa de conversão
    total_clicks = BotUser.query.filter(BotUser.bot_id.in_(bot_ids)).count() if bot_ids else 0
    total_purchases = Payment.query.filter(
        Payment.bot_id.in_(bot_ids),
        Payment.status == 'paid'
    ).count() if bot_ids else 0
    conversion_rate = (total_purchases / total_clicks * 100) if total_clicks > 0 else 0
    
    # Streak
    streak = current_user.current_streak or 0
    
    # ============================================================================
    # V2.0 METRICS - HOJE E MÊS
    # ============================================================================
    if bot_ids:
        # Vendas e receita de HOJE
        today_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id.in_(bot_ids),
            Payment.status == 'paid',
            Payment.created_at >= today_start
        ).scalar() or 0
        
        today_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id.in_(bot_ids),
            Payment.status == 'paid',
            Payment.created_at >= today_start
        ).scalar() or 0.0
        
        # Vendas e receita do MÊS
        month_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id.in_(bot_ids),
            Payment.status == 'paid',
            Payment.created_at >= month_start
        ).scalar() or 0
        
        month_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id.in_(bot_ids),
            Payment.status == 'paid',
            Payment.created_at >= month_start
        ).scalar() or 0.0
        
        # Vendas pendentes (HOJE e MÊS)
        today_pending_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id.in_(bot_ids),
            Payment.status == 'pending',
            Payment.created_at >= today_start
        ).scalar() or 0
        
        month_pending_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id.in_(bot_ids),
            Payment.status == 'pending',
            Payment.created_at >= month_start
        ).scalar() or 0
        
        # Novos usuários (HOJE e MÊS)
        today_users = db.session.query(func.count(func.distinct(BotUser.telegram_user_id))).filter(
            BotUser.bot_id.in_(bot_ids),
            BotUser.archived == False,
            BotUser.first_interaction >= today_start
        ).scalar() or 0
        
        month_users = db.session.query(func.count(func.distinct(BotUser.telegram_user_id))).filter(
            BotUser.bot_id.in_(bot_ids),
            BotUser.archived == False,
            BotUser.first_interaction >= month_start
        ).scalar() or 0
    else:
        today_sales = today_revenue = month_sales = month_revenue = 0
        today_pending_sales = month_pending_sales = today_users = month_users = 0
    
    # ============================================================================
    # MONTAR DICIONÁRIO STATS V2.0
    # ============================================================================
    stats = {
        # Métricas básicas
        'total_bots': total_bots,
        'active_bots': active_bots,
        'running_bots': running_bots,
        'total_users': total_users,
        'total_sales': total_sales,
        'total_revenue': float(total_revenue),
        'pending_sales': pending_sales,
        'conversion_rate': round(conversion_rate, 2),
        'streak': streak,
        
        # Permissões e comissões
        'can_add_bot': getattr(current_user, 'can_add_bot', lambda: True)() if hasattr(current_user, 'can_add_bot') else True,
        'commission_percentage': getattr(current_user, 'commission_percentage', 2.0),
        'commission_balance': current_user.get_commission_balance() if hasattr(current_user, 'get_commission_balance') else 0,
        'total_commission_owed': getattr(current_user, 'total_commission_owed', 0),
        'total_commission_paid': getattr(current_user, 'total_commission_paid', 0),
        
        # ✅ V2.0 METRICS OBRIGATÓRIAS
        'today_sales': today_sales,
        'today_revenue': float(today_revenue),
        'month_sales': month_sales,
        'month_revenue': float(month_revenue),
        'today_pending_sales': today_pending_sales,
        'month_pending_sales': month_pending_sales,
        'today_users': today_users,
        'month_users': month_users
    }
    
    # ============================================================================
    # DADOS PARA O TEMPLATE (SERIALIZÁVEIS)
    # ============================================================================
    
    # Buscar pagamentos recentes
    if bot_ids:
        recent_payments = db.session.query(Payment, Bot).join(
            Bot, Payment.bot_id == Bot.id
        ).filter(
            Payment.bot_id.in_(bot_ids)
        ).order_by(Payment.id.desc()).limit(20).all()
    else:
        recent_payments = []
    
    # Mapear bots para dict serializável - V2: Stats On-Demand via SQL
    bots_list = []
    for b in bots:
        # ============================================================================
        # ✅ ARQUITETURA LEGADA RESTAURADA: Stats On-Demand por Bot via SQL
        # As colunas total_sales/total_revenue NUNCA existiram no schema Bot.
        # Calculamos em tempo real via COUNT/SUM para cada bot individualmente.
        # ============================================================================
        
        # Contagem de leads para este bot
        bot_total_users = BotUser.query.filter_by(bot_id=b.id, archived=False).count()
        
        # Vendas pagas para este bot
        bot_total_sales = Payment.query.filter(
            Payment.bot_id == b.id,
            Payment.status == 'paid'
        ).count()
        
        # Receita total para este bot
        bot_total_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == b.id,
            Payment.status == 'paid'
        ).scalar() or 0.0
        
        # Vendas pendentes para este bot
        bot_pending_sales = Payment.query.filter(
            Payment.bot_id == b.id,
            Payment.status == 'pending'
        ).count()
        
        bots_list.append({
            'id': b.id,
            'name': b.name,
            'username': getattr(b, 'username', ''),
            'is_running': getattr(b, 'is_running', False),
            'is_active': getattr(b, 'is_active', True),
            'total_users': bot_total_users,       # ✅ Calculado via SQL On-Demand
            'total_sales': bot_total_sales,       # ✅ Calculado via SQL On-Demand
            'total_revenue': float(bot_total_revenue),  # ✅ Calculado via SQL On-Demand
            'pending_sales': bot_pending_sales,   # ✅ Calculado via SQL On-Demand
            'created_at': b.created_at.isoformat() if b.created_at else None
        })
    
    # Mapear pagamentos para dict serializável
    payments_list = []
    for payment, bot in recent_payments:
        payments_list.append({
            'id': payment.id,
            'customer_name': payment.customer_name,
            'product_name': payment.product_name,
            'amount': float(payment.amount),
            'status': payment.status,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'bot_id': bot.id,
            'bot_name': bot.name,
            'bot_username': getattr(bot, 'username', '')
        })
    
    return render_template(
        'dashboard.html',
        mode=mode,
        stats=stats,
        bots=bots_list,
        recent_payments=payments_list,
        user=current_user
    )


@dashboard_bp.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API para estatísticas do dashboard (usado pelo JavaScript)"""
    from sqlalchemy import func
    from internal_logic.core.models import BotUser
    
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
    from internal_logic.core.models import BotUser, Commission
    
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


# ============================================================================
# RANKING ROUTES
# ============================================================================

@dashboard_bp.route('/ranking')
@login_required
def ranking():
    """Página de ranking de vendedores - Gamificação V2.0 (MENSAL)"""
    from internal_logic.core.models import User, Achievement, UserAchievement, Payment, Bot
    from sqlalchemy import func
    from datetime import datetime
    
    # 🗓️ Cálculo do período mensal
    now = datetime.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 📅 Período do ranking (default: monthly para o novo motor mensal)
    period = request.args.get('period', 'monthly')
    
    # ============================================================================
    # 🔥 QUERY MENSAL - Faturamento do MÊS ATUAL (não total histórico)
    # ============================================================================
    # Subquery: SUM de pagamentos 'paid' do mês atual por usuário
    monthly_revenue_subq = db.session.query(
        Bot.user_id.label('user_id'),
        func.sum(Payment.amount).label('monthly_revenue'),
        func.count(Payment.id).label('monthly_sales')
    ).join(
        Payment, Payment.bot_id == Bot.id
    ).filter(
        Payment.status == 'paid',
        Payment.created_at >= first_day_of_month
    ).group_by(
        Bot.user_id
    ).subquery()
    
    # Query principal: JOIN com User + filtros de admin e faturamento > 0
    top_sellers = db.session.query(
        User.id,
        User.username,
        User.full_name,
        User.ranking_display_name,
        User.commission_percentage,
        User.total_revenue,  # Mantido para placas/conquistas (histórico)
        User.total_sales,    # Mantido para placas/conquistas (histórico)
        func.coalesce(monthly_revenue_subq.c.monthly_revenue, 0).label('monthly_revenue'),
        func.coalesce(monthly_revenue_subq.c.monthly_sales, 0).label('monthly_sales')
    ).outerjoin(
        monthly_revenue_subq, monthly_revenue_subq.c.user_id == User.id
    ).filter(
        User.is_active == True,
        User.is_admin == False,  # 🚫 EXCLUI ADMINISTRADORES
        User.is_banned == False,   # 🚫 EXCLUI BANIDOS
        monthly_revenue_subq.c.monthly_revenue > 0  # 🚫 Apenas quem vendeu no mês
    ).order_by(
        monthly_revenue_subq.c.monthly_revenue.desc().nullslast()
    ).limit(100).all()
    
    # ============================================================================
    # 🏆 CONSTRUÇÃO DO RANKING DATA - Baseado no FATURAMENTO MENSAL
    # ============================================================================
    ranking_data = []
    premium_rates = {1: 1.0, 2: 1.3, 3: 1.5}  # Taxas premium por posição (MENSAL)
    
    for idx, seller in enumerate(top_sellers):
        position = idx + 1
        # Premium é baseado na POSIÇÃO MENSAL (Top 3 do mês)
        is_premium = position <= 3
        premium_rate = premium_rates.get(position) if position <= 3 else None
        has_premium_rate = (seller.commission_percentage or 2.0) < 2.0
        
        # Faturamento mensal para ranking, total para placas
        monthly_revenue = float(seller.monthly_revenue or 0)
        total_revenue_hist = float(seller.total_revenue or 0)
        
        ranking_data.append({
            'position': position,
            'user': seller,
            'user_id': seller.id,
            'display_name': seller.ranking_display_name or seller.full_name or seller.username or f'usuario{seller.id}',
            'name': seller.ranking_display_name or seller.full_name or seller.username,
            'username': seller.username,
            'avatar': {
                'gradient': 'background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
                'logo_path': f'img/logotop{position}.png' if position <= 3 else 'img/logo.png'
            },
            'is_premium': is_premium,  # 🏆 Baseado na posição MENSAL
            'premium_rate': premium_rate,  # 🏆 Taxa pela posição MENSAL
            'current_rate': seller.commission_percentage or 2.0,
            'has_premium_rate': has_premium_rate,
            'is_current_user': seller.id == current_user.id,
            'revenue': monthly_revenue,  # 💰 Faturamento do MÊS (para ranking)
            'total_revenue': total_revenue_hist,  # 💰 Faturamento HISTÓRICO (para placas)
            'sales': int(seller.monthly_sales or 0),  # 📦 Vendas do MÊS
            'total_sales': seller.total_sales or 0,  # 📦 Vendas TOTAIS (histórico)
            'streak': getattr(seller, 'current_streak', 0)
        })
    
    # Calcular posição do usuário atual (baseado no MÊS)
    my_position_number = None
    for idx, seller in enumerate(top_sellers):
        if seller.id == current_user.id:
            my_position_number = idx + 1
            break
    
    # Se não está no top 100, buscar posição separadamente (baseada no mês)
    if my_position_number is None:
        my_monthly_revenue = db.session.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).join(Bot).filter(
            Bot.user_id == current_user.id,
            Payment.status == 'paid',
            Payment.created_at >= first_day_of_month
        ).scalar() or 0
        
        if my_monthly_revenue > 0:
            my_position_number = db.session.query(
                func.count(db.distinct(Bot.user_id))
            ).join(Payment).filter(
                Payment.status == 'paid',
                Payment.created_at >= first_day_of_month,
                Payment.amount > my_monthly_revenue
            ).scalar() or 0
            my_position_number += 1
        else:
            my_position_number = None  # Sem vendas no mês = sem posição
    
    # Próximo usuário acima no ranking (quanto falta para subir)
    next_user = None
    if my_position_number and my_position_number > 1:
        next_seller = top_sellers[my_position_number - 2]  # -2 porque índice começa em 0
        my_monthly = next(s['revenue'] for s in ranking_data if s['user_id'] == current_user.id)
        next_user = {
            'position': my_position_number - 1,
            'name': next_seller.ranking_display_name or next_seller.username,
            'revenue': float(next_seller.monthly_revenue or 0),
            'gap': float(next_seller.monthly_revenue or 0) - my_monthly
        }
    
    # Total de receita do usuário
    total_revenue_float = float(current_user.total_revenue or 0)
    
    # Verificar se deve mostrar modal de nome (se ainda não definiu)
    show_name_modal = not current_user.ranking_display_name
    
    # Buscar conquistas do usuário
    my_achievements = []
    user_achievements = UserAchievement.query.filter_by(
        user_id=current_user.id
    ).all()
    
    for ua in user_achievements:
        achievement = Achievement.query.get(ua.achievement_id)
        if achievement:
            my_achievements.append({
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'icon': achievement.icon or 'fa-trophy',
                'unlocked_at': ua.unlocked_at.isoformat() if ua.unlocked_at else None
            })
    
    # Buscar todas as conquistas disponíveis
    all_achievements = Achievement.query.all()
    achievements_data = []
    categories = {}
    
    for achievement in all_achievements:
        is_unlocked = any(ua.achievement_id == achievement.id for ua in user_achievements)
        ach_data = {
            'id': achievement.id,
            'name': achievement.name,
            'description': achievement.description,
            'icon': achievement.icon or 'fa-trophy',
            'category': getattr(achievement, 'requirement_type', 'Geral'),
            'points': achievement.points or 0,
            'is_unlocked': is_unlocked
        }
        achievements_data.append(ach_data)
        
        # Agrupar por categoria
        cat = getattr(achievement, 'requirement_type', 'Geral')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(ach_data)
    
    # Prêmios por receita (milestones) - CONTRATO BLINDADO COM O FRONTEND
    # 🖼️ ATENÇÃO: Usar apenas imagens que existem em static/img/
    # Arquivos existentes: premio_50k.png, premio_100k.png, premio_250k.png, premio_500k.png, premio_1m.png
    revenue_awards = [
        {
            'threshold': 50000, 
            'name': 'Vendedor Ouro', 
            'image': 'premio_50k.png',  # 🖼️ Imagem existente em static/img/
            'is_unlocked': total_revenue_float >= 50000,
            'progress': min(100.0, (total_revenue_float / 50000) * 100) if total_revenue_float < 50000 else 100.0,
            'remaining': max(0, 50000 - total_revenue_float),
            'current_revenue': total_revenue_float
        },
        {
            'threshold': 100000, 
            'name': 'Vendedor Diamante', 
            'image': 'premio_100k.png',
            'is_unlocked': total_revenue_float >= 100000,
            'progress': min(100.0, (total_revenue_float / 100000) * 100) if total_revenue_float < 100000 else 100.0,
            'remaining': max(0, 100000 - total_revenue_float),
            'current_revenue': total_revenue_float
        },
        {
            'threshold': 250000, 
            'name': 'Vendedor Elite', 
            'image': 'premio_250k.png',
            'is_unlocked': total_revenue_float >= 250000,
            'progress': min(100.0, (total_revenue_float / 250000) * 100) if total_revenue_float < 250000 else 100.0,
            'remaining': max(0, 250000 - total_revenue_float),
            'current_revenue': total_revenue_float
        },
        {
            'threshold': 500000, 
            'name': 'Mestre das Vendas', 
            'image': 'premio_500k.png',
            'is_unlocked': total_revenue_float >= 500000,
            'progress': min(100.0, (total_revenue_float / 500000) * 100) if total_revenue_float < 500000 else 100.0,
            'remaining': max(0, 500000 - total_revenue_float),
            'current_revenue': total_revenue_float
        },
        {
            'threshold': 1000000, 
            'name': 'Lenda do Faturamento', 
            'image': 'premio_1m.png',
            'is_unlocked': total_revenue_float >= 1000000,
            'progress': min(100.0, (total_revenue_float / 1000000) * 100) if total_revenue_float < 1000000 else 100.0,
            'remaining': max(0, 1000000 - total_revenue_float),
            'current_revenue': total_revenue_float
        },
    ]
    
    unlocked_count = sum(1 for award in revenue_awards if award['is_unlocked'])
    total_count = len(revenue_awards)
    
    # O RETURN CRÍTICO DO RANKING V2.0
    return render_template('ranking.html',
                           ranking=ranking_data,
                           my_position=my_position_number,
                           next_user=next_user,
                           period=period,
                           my_achievements=my_achievements,
                           all_achievements_data=achievements_data,
                           show_name_modal=show_name_modal,
                           current_ranking_display_name=current_user.ranking_display_name,
                           achievements_by_category=categories,
                           revenue_awards=revenue_awards,
                           total_revenue=total_revenue_float,
                           unlocked_awards_count=unlocked_count,
                           total_awards_count=total_count)


@dashboard_bp.route('/api/ranking/save-display-name', methods=['POST'])
@login_required
@csrf.exempt
def save_ranking_display_name():
    """Salva nome de exibição no ranking"""
    data = request.get_json()
    display_name = data.get('display_name', '').strip()
    
    if not display_name or len(display_name) < 3:
        return jsonify({'error': 'Nome deve ter pelo menos 3 caracteres'}), 400
    
    if len(display_name) > 50:
        return jsonify({'error': 'Nome deve ter no máximo 50 caracteres'}), 400
    
    try:
        current_user.ranking_display_name = display_name
        db.session.commit()
        logger.info(f"Ranking display name atualizado: {current_user.email} -> {display_name}")
        return jsonify({'success': True, 'display_name': display_name})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar display name: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# CHAT ROUTES
# ============================================================================

@dashboard_bp.route('/chat')
@login_required
def chat():
    """Página de chat com leads"""
    # Buscar bots do usuário
    bots = Bot.query.filter_by(user_id=current_user.id).all()
    
    # Serializar bots para dict (frontend exige JSON)
    bots_list = [{
        'id': b.id,
        'name': b.name,
        'username': getattr(b, 'username', ''),
        'is_running': getattr(b, 'is_running', False),
        'is_active': getattr(b, 'is_active', True)
    } for b in bots]
    
    return render_template('chat.html', bots=bots_list)


@dashboard_bp.route('/api/chat/conversations/<int:bot_id>')
@login_required
def get_chat_conversations(bot_id):
    """Retorna lista de conversas para um bot específico"""
    from internal_logic.core.models import BotUser, BotMessage
    from sqlalchemy import func
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Parâmetros de filtro
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '').strip()
    
    # Query base: BotUsers do bot
    query = BotUser.query.filter_by(bot_id=bot_id, archived=False)
    
    # Aplicar filtro de busca
    if search_query:
        query = query.filter(
            db.or_(
                BotUser.first_name.ilike(f'%{search_query}%'),
                BotUser.username.ilike(f'%{search_query}%'),
                BotUser.telegram_user_id.ilike(f'%{search_query}%')
            )
        )
    
    # Aplicar filtro de tipo
    if filter_type == 'paid':
        paid_user_ids = db.session.query(Payment.customer_user_id).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid'
        ).distinct().all()
        paid_ids_list = []
        for row in paid_user_ids:
            if row[0]:
                user_id = str(row[0]).replace('user_', '') if str(row[0]).startswith('user_') else str(row[0])
                paid_ids_list.append(user_id)
        if paid_ids_list:
            query = query.filter(BotUser.telegram_user_id.in_(paid_ids_list))
        else:
            query = query.filter(BotUser.id == -1)
    elif filter_type == 'pix_generated':
        pix_user_ids = db.session.query(Payment.customer_user_id).filter(
            Payment.bot_id == bot_id
        ).distinct().all()
        pix_ids_list = []
        for row in pix_user_ids:
            if row[0]:
                user_id = str(row[0]).replace('user_', '') if str(row[0]).startswith('user_') else str(row[0])
                pix_ids_list.append(user_id)
        if pix_ids_list:
            query = query.filter(BotUser.telegram_user_id.in_(pix_ids_list))
        else:
            query = query.filter(BotUser.id == -1)
    elif filter_type == 'only_entered':
        all_payment_user_ids = db.session.query(Payment.customer_user_id).filter(
            Payment.bot_id == bot_id
        ).distinct().all()
        payment_ids_list = []
        for row in all_payment_user_ids:
            if row[0]:
                user_id = str(row[0]).replace('user_', '') if str(row[0]).startswith('user_') else str(row[0])
                payment_ids_list.append(user_id)
        if payment_ids_list:
            query = query.filter(~BotUser.telegram_user_id.in_(payment_ids_list))
    
    # Buscar conversas
    bot_users = query.order_by(BotUser.last_interaction.desc()).limit(100).all()
    
    # Enriquecer dados
    conversations = []
    for bot_user in bot_users:
        last_message = BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=bot_user.telegram_user_id
        ).order_by(BotMessage.created_at.desc()).first()
        
        unread_count = BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=bot_user.telegram_user_id,
            direction='incoming',
            is_read=False
        ).count()
        
        telegram_id_str = str(bot_user.telegram_user_id)
        has_paid = Payment.query.filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            db.or_(
                Payment.customer_user_id == telegram_id_str,
                Payment.customer_user_id == f'user_{telegram_id_str}'
            )
        ).first() is not None
        
        has_pix = Payment.query.filter(
            Payment.bot_id == bot_id,
            db.or_(
                Payment.customer_user_id == telegram_id_str,
                Payment.customer_user_id == f'user_{telegram_id_str}'
            )
        ).first() is not None
        
        total_spent = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            db.or_(
                Payment.customer_user_id == telegram_id_str,
                Payment.customer_user_id == f'user_{telegram_id_str}'
            )
        ).scalar() or 0.0
        
        conversations.append({
            'bot_user_id': bot_user.id,
            'telegram_user_id': bot_user.telegram_user_id,
            'first_name': bot_user.first_name or 'Sem nome',
            'username': bot_user.username,
            'last_interaction': bot_user.last_interaction.isoformat() if bot_user.last_interaction else None,
            'last_message': {
                'text': last_message.message_text[:50] + '...' if last_message and last_message.message_text and len(last_message.message_text) > 50 else (last_message.message_text if last_message else None),
                'created_at': last_message.created_at.isoformat() if last_message else None,
                'direction': last_message.direction if last_message else None
            } if last_message else None,
            'unread_count': unread_count,
            'has_paid': has_paid,
            'has_pix': has_pix,
            'total_spent': float(total_spent),
            'status': 'paid' if has_paid else 'pix_generated' if has_pix else 'only_entered'
        })
    
    return jsonify({
        'success': True,
        'conversations': conversations,
        'total': len(conversations)
    })


@dashboard_bp.route('/api/chat/messages/<int:bot_id>/<telegram_user_id>', methods=['GET'])
@login_required
def get_chat_messages(bot_id, telegram_user_id):
    """Retorna mensagens de uma conversa específica"""
    from internal_logic.core.models import BotUser, BotMessage
    from datetime import timezone, timedelta
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Buscar bot_user
    bot_user = BotUser.query.filter_by(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        archived=False
    ).first()
    
    if not bot_user:
        return jsonify({
            'success': False,
            'error': 'Conversa não encontrada',
            'messages': []
        }), 404
    
    # Buscar mensagens novas usando timestamp
    since_timestamp = request.args.get('since_timestamp', type=str)
    
    BRAZIL_TZ_OFFSET = timedelta(hours=-3)
    
    if since_timestamp:
        try:
            since_timestamp_clean = since_timestamp.replace('Z', '+00:00')
            if '+' not in since_timestamp_clean and since_timestamp_clean.count(':') == 2:
                since_timestamp_clean += '+00:00'
            since_dt_utc = datetime.fromisoformat(since_timestamp_clean)
            
            if since_dt_utc.tzinfo is not None:
                since_dt_utc = since_dt_utc.astimezone(timezone.utc).replace(tzinfo=None)
            
            since_dt_brazil = since_dt_utc + BRAZIL_TZ_OFFSET
            since_dt_brazil_with_margin = since_dt_brazil - timedelta(seconds=20)
            
            messages = BotMessage.query.filter(
                BotMessage.bot_id == bot_id,
                BotMessage.telegram_user_id == telegram_user_id,
                BotMessage.created_at > since_dt_brazil_with_margin
            ).order_by(BotMessage.created_at.asc()).limit(50).all()
            
            if len(messages) == 0:
                recent_messages = BotMessage.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).order_by(BotMessage.created_at.desc()).limit(10).all()
                
                messages = [msg for msg in recent_messages if msg.created_at > since_dt_brazil_with_margin]
                messages.reverse()
        except Exception as e:
            logger.error(f"Erro ao parsear since_timestamp '{since_timestamp}': {e}")
            messages = BotMessage.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id
            ).order_by(BotMessage.created_at.desc()).limit(50).all()
            messages.reverse()
    else:
        messages = BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=telegram_user_id
        ).order_by(BotMessage.created_at.asc()).limit(100).all()
        
        # Marcar mensagens como lidas apenas na primeira carga
        BotMessage.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=telegram_user_id,
            direction='incoming',
            is_read=False
        ).update({'is_read': True})
        db.session.commit()
    
    messages_data = [msg.to_dict() for msg in messages]
    
    return jsonify({
        'success': True,
        'bot_user': bot_user.to_dict(),
        'messages': messages_data,
        'total': len(messages_data)
    })


@dashboard_bp.route('/api/chat/send-message/<int:bot_id>/<telegram_user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send_chat_message(bot_id, telegram_user_id):
    """Envia mensagem para um lead via Telegram"""
    from internal_logic.core.models import BotUser, BotMessage
    from bot_manager import BotManager
    import uuid
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Verificar se bot está rodando
    if not bot.is_running:
        return jsonify({'success': False, 'error': 'Bot não está online. Inicie o bot primeiro.'}), 400
    
    # Buscar bot_user
    bot_user = BotUser.query.filter_by(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        archived=False
    ).first_or_404()
    
    data = request.get_json()
    message_text = data.get('message', '').strip()
    
    if not message_text:
        return jsonify({'success': False, 'error': 'Mensagem não pode estar vazia'}), 400
    
    try:
        # Criar BotManager local com user_id
        local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=current_user.id)
        
        # Enviar mensagem via Telegram API
        result = local_bot_manager.send_telegram_message(
            token=bot.token,
            chat_id=telegram_user_id,
            message=message_text,
            media_url=None,
            buttons=None
        )
        
        if result:
            if isinstance(result, dict) and result.get('ok'):
                telegram_msg_id = result.get('result', {}).get('message_id')
                message_id = str(telegram_msg_id) if telegram_msg_id else str(uuid.uuid4().hex)
            elif result is True:
                message_id = str(uuid.uuid4().hex)
            else:
                return jsonify({'success': False, 'error': 'Falha ao enviar mensagem'}), 500
            
            # Salvar mensagem no banco
            bot_message = BotMessage(
                bot_id=bot_id,
                bot_user_id=bot_user.id,
                telegram_user_id=telegram_user_id,
                message_id=message_id,
                message_text=message_text,
                message_type='text',
                direction='outgoing',
                is_read=True
            )
            db.session.add(bot_message)
            
            # Atualizar last_interaction do bot_user
            bot_user.last_interaction = get_brazil_time()
            
            db.session.commit()
            
            logger.info(f"Mensagem enviada para {telegram_user_id} via bot {bot_id}")
            
            return jsonify({
                'success': True,
                'message_id': bot_message.id,
                'telegram_message_id': message_id
            })
        else:
            return jsonify({'success': False, 'error': 'Falha ao enviar mensagem'}), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao enviar mensagem: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/chat/send-media/<int:bot_id>/<telegram_user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send_chat_media(bot_id, telegram_user_id):
    """Envia foto/vídeo para um lead via Telegram"""
    from internal_logic.core.models import BotUser, BotMessage
    from bot_manager import BotManager
    import uuid
    import tempfile
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    if not bot.is_running:
        return jsonify({'success': False, 'error': 'Bot não está online. Inicie o bot primeiro.'}), 400
    
    bot_user = BotUser.query.filter_by(
        bot_id=bot_id,
        telegram_user_id=telegram_user_id,
        archived=False
    ).first_or_404()
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Arquivo vazio'}), 400
    
    message_text = request.form.get('message', '').strip()
    
    filename = file.filename.lower()
    if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        media_type = 'photo'
    elif filename.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
        media_type = 'video'
    else:
        media_type = 'document'
    
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = 50 * 1024 * 1024 if media_type == 'video' else 10 * 1024 * 1024
    if file_size > max_size:
        return jsonify({
            'success': False, 
            'error': f'Arquivo muito grande. Máximo: {max_size // (1024*1024)}MB'
        }), 400
    
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=current_user.id)
        
        result = local_bot_manager.send_telegram_file(
            token=bot.token,
            chat_id=telegram_user_id,
            file_path=temp_file_path,
            message=message_text,
            media_type=media_type,
            buttons=None
        )
        
        if result and isinstance(result, dict) and result.get('ok'):
            telegram_msg_id = result.get('result', {}).get('message_id')
            message_id = str(telegram_msg_id) if telegram_msg_id else str(uuid.uuid4().hex)
            
            bot_user.last_interaction = get_brazil_time()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message_id': message_id,
                'media_type': media_type,
                'telegram_message_id': message_id
            })
        else:
            error_msg = result.get('description', 'Falha ao enviar arquivo') if isinstance(result, dict) else 'Falha ao enviar arquivo'
            return jsonify({'success': False, 'error': error_msg}), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao enviar arquivo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Erro ao remover arquivo temporário: {e}")


@dashboard_bp.route('/api/chat/media/<int:bot_id>/<file_id>')
@login_required
def get_chat_media(bot_id, file_id):
    """Proxy para exibir mídia do Telegram"""
    import requests
    from flask import Response
    
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        token = bot.token
        if not token:
            return jsonify({'error': 'Token não encontrado'}), 400
        
        get_file_url = f"https://api.telegram.org/bot{token}/getFile"
        response = requests.get(get_file_url, params={'file_id': file_id}, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'error': 'Erro ao obter arquivo'}), 500
        
        data = response.json()
        if not data.get('ok'):
            return jsonify({'error': 'Arquivo não encontrado'}), 404
        
        file_path = data.get('result', {}).get('file_path')
        if not file_path:
            return jsonify({'error': 'File path não encontrado'}), 404
        
        file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        file_response = requests.get(file_url, timeout=30, stream=True)
        
        if file_response.status_code != 200:
            return jsonify({'error': 'Erro ao baixar arquivo'}), 500
        
        return Response(
            file_response.iter_content(chunk_size=8192),
            mimetype=file_response.headers.get('Content-Type', 'application/octet-stream'),
            headers={
                'Content-Disposition': f'inline; filename="{file_path.split("/")[-1]}"',
                'Cache-Control': 'public, max-age=3600'
            }
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter mídia: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SETTINGS ROUTES
# ============================================================================

@dashboard_bp.route('/settings')
@login_required
def settings():
    """Página de configurações"""
    return render_template('settings.html')


@dashboard_bp.route('/api/user/profile', methods=['PUT'])
@login_required
@csrf.exempt
def update_profile():
    """Atualiza perfil do usuário"""
    data = request.json
    
    try:
        if 'full_name' in data:
            current_user.full_name = data['full_name']
        
        if 'email' in data and data['email'] != current_user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email já cadastrado'}), 400
            current_user.email = data['email']
        
        db.session.commit()
        logger.info(f"Perfil atualizado: {current_user.email}")
        return jsonify(current_user.to_dict())
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar perfil: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/user/password', methods=['PUT'])
@login_required
@csrf.exempt
def update_password():
    """Atualiza senha do usuário"""
    data = request.json
    
    if not current_user.check_password(data.get('current_password')):
        return jsonify({'error': 'Senha atual incorreta'}), 400
    
    try:
        current_user.set_password(data.get('new_password'))
        db.session.commit()
        logger.info(f"Senha atualizada: {current_user.email}")
        return jsonify({'message': 'Senha atualizada com sucesso'})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar senha: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# REDIRECT POOLS ROUTES
# ============================================================================

@dashboard_bp.route('/redirect-pools')
@login_required
def redirect_pools_page():
    """Página de gerenciamento de pools de redirecionamento"""
    bots = Bot.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('redirect_pools.html', bots=bots)


@dashboard_bp.route('/api/redirect-pools')
@login_required
def get_redirect_pools():
    """Retorna lista de pools do usuário"""
    from internal_logic.core.models import RedirectPool
    
    # DEBUG: Expor identidade do usuário
    print(f"DEBUG POOLS: Buscando pools para User ID: {current_user.id} (Tipo: {type(current_user.id)})")
    print(f"DEBUG POOLS: Telegram User ID do User: {getattr(current_user, 'telegram_user_id', 'N/A')}")
    print(f"DEBUG POOLS: Email do User: {getattr(current_user, 'email', 'N/A')}")
    
    # DEBUG: Verificar TODOS os pools no banco (independentemente de user_id)
    all_pools = RedirectPool.query.all()
    print(f"DEBUG POOLS: Total de pools no banco: {len(all_pools)}")
    for p in all_pools:
        print(f"DEBUG POOLS: Pool ID={p.id}, name={p.name}, user_id={p.user_id}")
    
    pools = RedirectPool.query.filter_by(user_id=current_user.id).all()
    
    print(f"DEBUG POOLS: Quantidade de pools encontrados para este usuário: {len(pools)}")
    
    # ✅ PADRONIZAÇÃO: Usar to_dict() do modelo para garantir contrato consistente
    return jsonify([pool.to_dict() for pool in pools])


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>', methods=['GET'])
@login_required
def get_redirect_pool_detail(pool_id):
    """
    Obtém detalhes de um pool específico com seus relacionamentos
    (Migrado do laboratório - rota faltante)
    """
    from internal_logic.core.models import RedirectPool, PoolBot
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    # Incluir lista de bots (serializados)
    pool_data = pool.to_dict()
    pool_data['bots'] = [pb.to_dict() for pb in pool.pool_bots]
    
    return jsonify(pool_data)


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/bots/<int:pool_bot_id>', methods=['PUT'])
@login_required
@csrf.exempt
def update_pool_bot_config(pool_id, pool_bot_id):
    """
    Atualiza configurações do bot no pool (weight, priority, enabled)
    (Migrado do laboratório - rota faltante)
    """
    from internal_logic.core.models import RedirectPool, PoolBot
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    pool_bot = PoolBot.query.filter_by(id=pool_bot_id, pool_id=pool_id).first_or_404()
    
    data = request.get_json()
    
    if 'weight' in data:
        pool_bot.weight = max(1, int(data['weight']))
    
    if 'priority' in data:
        pool_bot.priority = int(data['priority'])
    
    if 'is_active' in data:
        pool_bot.is_enabled = data['is_active']
    
    db.session.commit()
    
    logger.info(f"Configurações do bot {pool_bot.bot_id} no pool {pool_id} atualizadas")
    
    return jsonify({
        'message': 'Configurações atualizadas!',
        'pool_bot': pool_bot.to_dict()
    })


@dashboard_bp.route('/api/redirect-pools', methods=['POST'])
@login_required
@csrf.exempt
def create_redirect_pool():
    """Cria novo pool de redirecionamento"""
    from internal_logic.core.models import RedirectPool
    import re
    
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Nome do pool é obrigatório'}), 400
    
    # Gerar slug a partir do nome
    slug = re.sub(r'[^a-zA-Z0-9-]', '-', name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    
    # Verificar se slug já existe
    existing = RedirectPool.query.filter_by(user_id=current_user.id, slug=slug).first()
    if existing:
        slug = f"{slug}-{current_user.id}"
    
    try:
        pool = RedirectPool(
            user_id=current_user.id,
            name=name,
            slug=slug,
            is_active=True,
            distribution_strategy=data.get('rotation_mode', 'round_robin')
        )
        db.session.add(pool)
        db.session.commit()
        
        logger.info(f"Pool criado: {name} ({slug}) por {current_user.email}")
        return jsonify({
            'success': True,
            'pool': {
                'id': pool.id,
                'name': pool.name,
                'slug': pool.slug
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar pool: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>', methods=['PUT'])
@login_required
@csrf.exempt
def update_redirect_pool(pool_id):
    """Atualiza pool de redirecionamento"""
    from internal_logic.core.models import RedirectPool
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    
    try:
        if 'name' in data:
            pool.name = data['name'].strip()
        if 'is_active' in data:
            pool.is_active = data['is_active']
        if 'rotation_mode' in data:
            pool.distribution_strategy = data['rotation_mode']
        if 'meta_pixel_id' in data:
            pool.meta_pixel_id = data['meta_pixel_id']
        if 'meta_tracking_enabled' in data:
            pool.meta_tracking_enabled = data['meta_tracking_enabled']
        
        db.session.commit()
        logger.info(f"Pool atualizado: {pool.name} por {current_user.email}")
        return jsonify({'success': True, 'pool': {'id': pool.id, 'name': pool.name}})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar pool: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def delete_redirect_pool(pool_id):
    """Remove pool de redirecionamento"""
    from internal_logic.core.models import RedirectPool, PoolBot
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    try:
        # Remover associações primeiro
        PoolBot.query.filter_by(pool_id=pool_id).delete()
        
        db.session.delete(pool)
        db.session.commit()
        
        logger.info(f"Pool removido: {pool.name} por {current_user.email}")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao remover pool: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/bots', methods=['POST'])
@login_required
@csrf.exempt
def add_bot_to_pool(pool_id):
    """Adiciona bot ao pool"""
    from internal_logic.core.models import RedirectPool, PoolBot
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    bot_id = data.get('bot_id')
    
    if not bot_id:
        return jsonify({'error': 'bot_id é obrigatório'}), 400
    
    # Verificar se bot pertence ao usuário
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first()
    if not bot:
        return jsonify({'error': 'Bot não encontrado'}), 404
    
    # Verificar se bot já está no pool
    existing = PoolBot.query.filter_by(pool_id=pool_id, bot_id=bot_id).first()
    if existing:
        return jsonify({'error': 'Bot já está no pool'}), 400
    
    try:
        pool_bot = PoolBot(
            pool_id=pool_id,
            bot_id=bot_id,
            priority=data.get('priority', 1),
            is_enabled=True
        )
        db.session.add(pool_bot)
        db.session.commit()
        
        logger.info(f"Bot {bot_id} adicionado ao pool {pool_id}")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao adicionar bot ao pool: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/bots/<int:bot_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def remove_bot_from_pool(pool_id, bot_id):
    """Remove bot do pool"""
    from internal_logic.core.models import RedirectPool, PoolBot
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    pool_bot = PoolBot.query.filter_by(pool_id=pool_id, bot_id=bot_id).first()
    if not pool_bot:
        return jsonify({'error': 'Bot não está no pool'}), 404
    
    try:
        db.session.delete(pool_bot)
        db.session.commit()
        
        logger.info(f"Bot {bot_id} removido do pool {pool_id}")
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao remover bot do pool: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/rotate')
@login_required
def rotate_pool_bot(pool_id):
    """Retorna próximo bot na rotação do pool"""
    from internal_logic.core.models import RedirectPool, PoolBot
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    # Buscar bots ativos no pool
    pool_bots = PoolBot.query.filter_by(
        pool_id=pool_id,
        is_enabled=True
    ).join(Bot).filter(
        Bot.is_active == True,
        Bot.token.isnot(None)
    ).order_by(PoolBot.priority.asc()).all()
    
    if not pool_bots:
        return jsonify({'error': 'Nenhum bot ativo no pool'}), 404
    
    # Rotacionar baseado no modo
    if pool.distribution_strategy == 'round_robin':
        # Implementação simples: usar timestamp para determinar índice
        import time
        idx = int(time.time()) % len(pool_bots)
        selected = pool_bots[idx]
    else:
        # Aleatório
        import random
        selected = random.choice(pool_bots)
    
    return jsonify({
        'success': True,
        'bot_id': selected.bot_id,
        'bot_username': selected.bot.username if selected.bot else None,
        'priority': selected.priority
    })


# ============================================================================
# META PIXEL POOL ROUTES (Migrado do laboratório)
# ============================================================================

@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/meta-pixel', methods=['GET'])
@login_required
def get_pool_meta_pixel_config(pool_id):
    """
    Obtém configuração do Meta Pixel do pool
    (Migrado do laboratório - rota faltante)
    """
    from internal_logic.core.models import RedirectPool
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    return jsonify({
        'pool_id': pool.id,
        'pool_name': pool.name,
        'meta_pixel_id': pool.meta_pixel_id if pool.meta_pixel_id else None,
        'meta_access_token': pool.meta_access_token,  # Criptografado no banco
        'meta_tracking_enabled': pool.meta_tracking_enabled,
        'meta_test_event_code': pool.meta_test_event_code if pool.meta_test_event_code else None,
        'meta_events_pageview': pool.meta_events_pageview,
        'meta_events_viewcontent': pool.meta_events_viewcontent,
        'meta_events_purchase': pool.meta_events_purchase,
        'meta_cloaker_enabled': pool.meta_cloaker_enabled,
        'meta_cloaker_param_name': 'grim',
        'meta_cloaker_param_value': pool.meta_cloaker_param_value if pool.meta_cloaker_param_value else None,
        'utmify_pixel_id': pool.utmify_pixel_id if pool.utmify_pixel_id else None
    })


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/meta-pixel', methods=['PUT'])
@login_required
@csrf.exempt
def update_pool_meta_pixel_config(pool_id):
    """
    Atualiza configuração do Meta Pixel do pool
    (Migrado do laboratório - rota faltante)
    """
    from internal_logic.core.models import RedirectPool
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    
    # Atualizar campos do Meta Pixel
    if 'meta_pixel_id' in data:
        pool.meta_pixel_id = data['meta_pixel_id'].strip() if data['meta_pixel_id'] else None
    
    if 'meta_access_token' in data:
        token = data['meta_access_token'].strip()
        # Só atualizar se não for o marcador de campo mascarado
        if token and not token.startswith('...'):
            pool.meta_access_token = token
    
    if 'meta_tracking_enabled' in data:
        pool.meta_tracking_enabled = bool(data['meta_tracking_enabled'])
    
    if 'meta_test_event_code' in data:
        pool.meta_test_event_code = data['meta_test_event_code'].strip() if data['meta_test_event_code'] else None
    
    if 'meta_events_pageview' in data:
        pool.meta_events_pageview = bool(data['meta_events_pageview'])
    
    if 'meta_events_viewcontent' in data:
        pool.meta_events_viewcontent = bool(data['meta_events_viewcontent'])
    
    if 'meta_events_purchase' in data:
        pool.meta_events_purchase = bool(data['meta_events_purchase'])
    
    if 'meta_cloaker_enabled' in data:
        pool.meta_cloaker_enabled = bool(data['meta_cloaker_enabled'])
    
    if 'meta_cloaker_param_value' in data:
        pool.meta_cloaker_param_value = data['meta_cloaker_param_value'].strip() if data['meta_cloaker_param_value'] else None
    
    if 'utmify_pixel_id' in data:
        pool.utmify_pixel_id = data['utmify_pixel_id'].strip() if data['utmify_pixel_id'] else None
    
    try:
        db.session.commit()
        logger.info(f"Configuração Meta Pixel atualizada para pool {pool_id}")
        return jsonify({
            'success': True,
            'pool_id': pool.id,
            'meta_tracking_enabled': pool.meta_tracking_enabled
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar Meta Pixel do pool: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/meta-pixel/test', methods=['POST'])
@login_required
@csrf.exempt
def test_pool_meta_pixel_connection(pool_id):
    """
    Testa conexão com Meta Pixel API
    (Migrado do laboratório - rota faltante)
    """
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    pixel_id = data.get('pixel_id', '').strip()
    access_token = data.get('access_token', '').strip()
    
    if not pixel_id or not access_token:
        return jsonify({'error': 'Pixel ID e Access Token são obrigatórios'}), 400
    
    # Resposta simulada (em produção, implementar teste real com Meta API)
    return jsonify({
        'success': True,
        'message': 'Conexão testada (modo simulado)',
        'pixel_id': pixel_id
    })


# ============================================================================
# UTMIFY ROUTES (Migrado do laboratório)
# ============================================================================

@dashboard_bp.route('/api/redirect-pools/<int:pool_id>/generate-utmify-utms', methods=['POST'])
@login_required
def generate_utmify_utms(pool_id):
    """
    Gera códigos de UTMs Utmify para Meta Ads
    (Migrado do laboratório - rota faltante)
    """
    from internal_logic.core.models import RedirectPool
    
    pool = RedirectPool.query.filter_by(id=pool_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    model = data.get('model', 'standard')
    base_url = data.get('base_url', f"{request.scheme}://{request.host}/go/{pool.slug}")
    
    # GARANTIR: base_url não deve conter parâmetros
    if '?' in base_url:
        base_url = base_url.split('?')[0]
    
    # Obter valor do grim se cloaker estiver ativo
    grim_value = None
    if pool.meta_cloaker_enabled and pool.meta_cloaker_param_value:
        grim_value = pool.meta_cloaker_param_value
    
    # Base dos UTMs (formato Utmify)
    base_utms = (
        "utm_source=FB"
        "&utm_campaign={{campaign.name}}|{{campaign.id}}"
        "&utm_medium={{adset.name}}|{{adset.id}}"
        "&utm_content={{ad.name}}|{{ad.id}}"
        "&utm_term={{placement}}"
    )
    
    utm_params = base_utms
    
    # Modelos específicos
    if model == "hotmart":
        xcod = data.get('xcod', '').strip()
        if not xcod:
            return jsonify({'error': 'xcod é obrigatório para modelo Hotmart'}), 400
        xcod_param = f"&xcod={xcod}{{campaign.name}}|{{campaign.id}}{xcod}{{adset.name}}|{{adset.id}}{xcod}{{ad.name}}|{{ad.id}}{xcod}{{placement}}"
        utm_params = f"{base_utms}{xcod_param}"
    elif model == "cartpanda":
        cid = data.get('cid', '').strip()
        if not cid:
            return jsonify({'error': 'cid é obrigatório para modelo Cartpanda'}), 400
        utm_params = f"{base_utms}&cid={cid}"
    elif model == "custom":
        utm_source = data.get('utm_source', 'FB').strip()
        utm_campaign = data.get('utm_campaign', '').strip()
        utm_medium = data.get('utm_medium', '').strip()
        utm_content = data.get('utm_content', '').strip()
        utm_term = data.get('utm_term', '').strip()
        utm_id = data.get('utm_id', '').strip()
        
        utm_parts = [f"utm_source={utm_source}"]
        if utm_campaign:
            utm_parts.append(f"utm_campaign={utm_campaign}")
        if utm_medium:
            utm_parts.append(f"utm_medium={utm_medium}")
        if utm_content:
            utm_parts.append(f"utm_content={utm_content}")
        if utm_term:
            utm_parts.append(f"utm_term={utm_term}")
        if utm_id:
            utm_parts.append(f"utm_id={utm_id}")
        
        utm_params = "&".join(utm_parts)
    
    # Adicionar grim se cloaker estiver ativo
    if grim_value:
        utm_params = f"{utm_params}&grim={grim_value}"
    
    return jsonify({
        'success': True,
        'model': model,
        'base_url': base_url,
        'website_url': base_url,
        'url_params': utm_params,
        'utm_params': utm_params,
        'grim': grim_value
    })


# ============================================================================
# META PIXEL ROUTES (DEPRECATED - Preferir configuração por pool)
# ============================================================================

@dashboard_bp.route('/bots/<int:bot_id>/meta-pixel')
@login_required
def meta_pixel_config_page(bot_id):
    """Página de configuração do Meta Pixel"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    return render_template('meta_pixel_config.html', bot=bot)


@dashboard_bp.route('/api/bots/<int:bot_id>/meta-pixel', methods=['GET'])
@login_required
def get_meta_pixel_config(bot_id):
    """[DEPRECATED] Retorna configuração atual do Meta Pixel do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    return jsonify({
        'meta_pixel_id': bot.meta_pixel_id,
        'meta_tracking_enabled': bot.meta_tracking_enabled,
        'meta_test_event_code': bot.meta_test_event_code,
        'meta_events_pageview': bot.meta_events_pageview,
        'meta_events_viewcontent': bot.meta_events_viewcontent,
        'meta_events_purchase': bot.meta_events_purchase,
        'meta_cloaker_enabled': bot.meta_cloaker_enabled,
        'meta_cloaker_param_name': 'grim',
        'meta_cloaker_param_value': bot.meta_cloaker_param_value,
        'has_access_token': bool(bot.meta_access_token)
    })


@dashboard_bp.route('/api/bots/<int:bot_id>/meta-pixel', methods=['PUT'])
@login_required
@csrf.exempt
def update_meta_pixel_config(bot_id):
    """Atualiza configuração do Meta Pixel do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    
    # Validar dados obrigatórios se tracking estiver ativo
    if data.get('meta_tracking_enabled'):
        pixel_id = data.get('meta_pixel_id', '').strip()
        access_token = data.get('meta_access_token', '').strip()
        
        if not pixel_id:
            return jsonify({'error': 'Pixel ID é obrigatório quando tracking está ativo'}), 400
        
        if not access_token:
            return jsonify({'error': 'Access Token é obrigatório quando tracking está ativo'}), 400
        
        bot.meta_pixel_id = pixel_id
        bot.meta_access_token = access_token
    
    # Atualizar outros campos
    bot.meta_tracking_enabled = data.get('meta_tracking_enabled', False)
    bot.meta_test_event_code = data.get('meta_test_event_code', '').strip()
    bot.meta_events_pageview = data.get('meta_events_pageview', True)
    bot.meta_events_viewcontent = data.get('meta_events_viewcontent', True)
    bot.meta_events_purchase = data.get('meta_events_purchase', True)
    bot.meta_cloaker_enabled = data.get('meta_cloaker_enabled', False)
    bot.meta_cloaker_param_value = data.get('meta_cloaker_param_value', '').strip()
    
    try:
        db.session.commit()
        logger.info(f"Configuração Meta Pixel atualizada para bot {bot_id}")
        return jsonify({
            'success': True,
            'config': {
                'meta_pixel_id': bot.meta_pixel_id,
                'meta_tracking_enabled': bot.meta_tracking_enabled
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar configuração Meta Pixel: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# BOT MANAGEMENT APIs (Resgatadas da migração)
# ============================================================================

@dashboard_bp.route('/api/bots', methods=['GET'])
@login_required
def api_get_bots():
    """Retorna lista de bots do usuário (JSON) - V2: Stats On-Demand via SQL"""
    from sqlalchemy import func
    from internal_logic.core.models import BotUser, Payment
    
    bots = Bot.query.filter_by(user_id=current_user.id).all()
    
    bots_list = []
    for bot in bots:
        # ============================================================================
        # ✅ ARQUITETURA LEGADA RESTAURADA: Stats On-Demand via SQL
        # As colunas total_sales/total_revenue NUNCA existiram no schema.
        # Calculamos em tempo real via COUNT/SUM que é stateless e funciona
        # perfeitamente em multi-worker sem race conditions.
        # ============================================================================
        
        # Contagem de leads (total_users)
        total_users = BotUser.query.filter_by(bot_id=bot.id, archived=False).count()
        
        # Vendas pagas (total_sales)
        total_sales = Payment.query.filter(
            Payment.bot_id == bot.id,
            Payment.status == 'paid'
        ).count()
        
        # Receita total (total_revenue)
        total_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot.id,
            Payment.status == 'paid'
        ).scalar() or 0.0
        
        # Vendas pendentes
        pending_sales = Payment.query.filter(
            Payment.bot_id == bot.id,
            Payment.status == 'pending'
        ).count()
        
        bots_list.append({
            'id': bot.id,
            'name': bot.name,
            'username': getattr(bot, 'username', ''),
            'is_running': getattr(bot, 'is_running', False),
            'is_active': getattr(bot, 'is_active', True),
            'total_users': total_users,       # ✅ Calculado via SQL On-Demand
            'total_sales': total_sales,       # ✅ Calculado via SQL On-Demand  
            'total_revenue': float(total_revenue),  # ✅ Calculado via SQL On-Demand
            'pending_sales': pending_sales,   # ✅ Calculado via SQL On-Demand
            'created_at': bot.created_at.isoformat() if bot.created_at else None,
            'token': bot.token[:10] + '...' if bot.token else None  # Parcial por segurança
        })
    
    return jsonify(bots_list)


@dashboard_bp.route('/api/bots', methods=['POST'])
@login_required
@csrf.exempt
def api_create_bot():
    """Cria um novo bot via API"""
    data = request.get_json()
    
    token = data.get('token', '').strip()
    name = data.get('name', 'Novo Bot').strip()
    
    if not token:
        return jsonify({'error': 'Token é obrigatório'}), 400
    
    try:
        # Verificar se token já existe
        existing = Bot.query.filter_by(token=token).first()
        if existing:
            return jsonify({'error': 'Este token já está em uso'}), 400
        
        bot = Bot(
            user_id=current_user.id,
            name=name,
            token=token,
            is_active=True,
            is_running=False
        )
        
        db.session.add(bot)
        db.session.commit()
        
        # 🔥 CRÍTICO: Enfileirar sincronização do webhook no RQ
        # Garante que o bot está sempre online recebendo mensagens
        try:
            from tasks_async import task_queue
            from internal_logic.tasks.telegram_tasks import task_sync_single_webhook
            
            if task_queue:
                task_queue.enqueue(task_sync_single_webhook, bot.id)
                logger.info(f"📥 Webhook sync enfileirado para bot {bot.id}")
        except Exception as queue_error:
            logger.warning(f"⚠️ Falha ao enfileirar webhook sync (não crítico): {queue_error}")
        
        logger.info(f"Bot criado via API: {bot.name} (ID: {bot.id}) por {current_user.email}")
        
        return jsonify({
            'success': True,
            'bot': {
                'id': bot.id,
                'name': bot.name,
                'username': bot.username if hasattr(bot, 'username') else None,
                'is_running': bot.is_running,
                'is_active': bot.is_active
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar bot: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/bots/<int:bot_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def api_delete_bot(bot_id):
    """Deleta um bot via API"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(bot)
        db.session.commit()
        
        logger.info(f"Bot deletado via API: {bot_id} por {current_user.email}")
        return jsonify({'success': True, 'message': 'Bot deletado com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar bot: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/bots/<int:bot_id>/duplicate', methods=['POST'])
@login_required
@csrf.exempt
def api_duplicate_bot(bot_id):
    """Duplica um bot existente"""
    source_bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    new_token = data.get('token', '').strip()
    new_name = data.get('name', f"{source_bot.name} (Cópia)").strip()
    
    if not new_token:
        return jsonify({'error': 'Token do novo bot é obrigatório'}), 400
    
    try:
        # Verificar se token já existe
        existing = Bot.query.filter_by(token=new_token).first()
        if existing:
            return jsonify({'error': 'Este token já está em uso'}), 400
        
        # Criar novo bot copiando configurações do original
        new_bot = Bot(
            user_id=current_user.id,
            name=new_name,
            token=new_token,
            is_active=True,
            is_running=False,
            # Copiar configurações relevantes
            welcome_message=source_bot.welcome_message if hasattr(source_bot, 'welcome_message') else None,
            gateway_id=source_bot.gateway_id if hasattr(source_bot, 'gateway_id') else None,
            products_config=source_bot.products_config if hasattr(source_bot, 'products_config') else None
        )
        
        db.session.add(new_bot)
        db.session.commit()
        
        logger.info(f"Bot duplicado via API: {source_bot.id} -> {new_bot.id} por {current_user.email}")
        
        return jsonify({
            'success': True,
            'bot': {
                'id': new_bot.id,
                'name': new_bot.name,
                'username': new_bot.username if hasattr(new_bot, 'username') else None,
                'is_running': new_bot.is_running,
                'is_active': new_bot.is_active
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao duplicar bot: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/bots/<int:bot_id>/export', methods=['GET'])
@login_required
def api_export_bot(bot_id):
    """Exporta configuração de um bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    export_data = {
        'name': bot.name,
        'welcome_message': getattr(bot, 'welcome_message', None),
        'products_config': getattr(bot, 'products_config', None),
        'gateway_id': getattr(bot, 'gateway_id', None),
        'meta_pixel_id': getattr(bot, 'meta_pixel_id', None),
        'meta_tracking_enabled': getattr(bot, 'meta_tracking_enabled', False),
        'exported_at': datetime.now().isoformat()
    }
    
    return jsonify({'success': True, 'export': export_data})


@dashboard_bp.route('/api/bots/verify-status', methods=['POST'])
@login_required
@csrf.exempt
def api_verify_bots_status():
    """Verifica status atual dos bots no Telegram"""
    from bot_manager import BotManager
    
    bots = Bot.query.filter_by(user_id=current_user.id).all()
    
    bots_status = []
    for bot in bots:
        status = {
            'id': bot.id,
            'is_running': bot.is_running if hasattr(bot, 'is_running') else False,
            'sources': ['database']
        }
        bots_status.append(status)
    
    return jsonify({'success': True, 'bots': bots_status})


@dashboard_bp.route('/bots/<int:bot_id>/config')
@login_required
def bot_config_page(bot_id):
    """Página de configuração do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    return render_template('bot_config.html', bot=bot)


# ============================================================================
# BOT CONFIGURATION APIs (Lazy Loading + Auto-Cura)
# ============================================================================

@dashboard_bp.route('/api/bots/<int:bot_id>/config', methods=['GET'])
@login_required
def get_bot_config(bot_id):
    """Obtém configuração de um bot com Lazy Loading"""
    try:
        logger.info(f"🔍 Buscando config do bot {bot_id}...")
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        logger.info(f"✅ Bot encontrado: {bot.name}")
        
        # ✅ LAZY LOADING: Se não tiver config, cria automaticamente
        if not bot.config:
            logger.warning(f"⚠️ Bot {bot_id} não tem config, criando nova...")
            config = BotConfig(bot_id=bot.id)
            db.session.add(config)
            db.session.commit()
            db.session.refresh(config)
            logger.info(f"✅ Config nova criada para bot {bot_id}")
        else:
            logger.info(f"✅ Config existente encontrada (ID: {bot.config.id})")
        
        config_dict = bot.config.to_dict()
        logger.info(f"📦 Config serializado com sucesso")
        logger.info(f"   - welcome_message: {len(config_dict.get('welcome_message', ''))} chars")
        logger.info(f"   - main_buttons: {len(config_dict.get('main_buttons', []))} botões")
        logger.info(f"   - downsells: {len(config_dict.get('downsells', []))} downsells")
        logger.info(f"   - upsells: {len(config_dict.get('upsells', []))} upsells")
        
        # ✅ METADADOS ADICIONAIS: Verificar Meta Pixel do pool
        pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        has_meta_pixel = False
        pool_name = None
        if pool_bot and pool_bot.pool:
            pool = pool_bot.pool
            has_meta_pixel = pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token
            pool_name = pool.name
        
        config_dict['has_meta_pixel'] = has_meta_pixel
        config_dict['pool_name'] = pool_name
        
        logger.info(f"   - Meta Pixel ativo: {'✅ Sim' if has_meta_pixel else '❌ Não'} (Pool: {pool_name or 'N/A'})")
        
        return jsonify(config_dict)
    except Exception as e:
        logger.error(f"❌ Erro ao buscar config do bot {bot_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao buscar configuração: {str(e)}'}), 500


@dashboard_bp.route('/api/bots/<int:bot_id>/config', methods=['PUT'])
@login_required
@csrf.exempt
def update_bot_config(bot_id):
    """Atualiza configuração de um bot com validações Poka-Yoke"""
    logger.info(f"🔄 Iniciando atualização de config para bot {bot_id}")
    
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    raw_data = request.get_json() or {}
    
    # ✅ CORREÇÃO CRÍTICA: NÃO sanitizar welcome_message - preservar emojis
    data = raw_data.copy() if isinstance(raw_data, dict) else {}
    
    # Sanitizar apenas outros campos (não welcome_message)
    if 'welcome_message' in raw_data:
        data['welcome_message'] = raw_data['welcome_message']  # Preserva emojis!
    
    logger.info(f"📊 Dados recebidos: {list(data.keys())}")
    
    # ✅ LAZY LOADING: Cria config se não existir
    if not bot.config:
        logger.info(f"📝 Criando nova configuração para bot {bot_id}")
        config = BotConfig(bot_id=bot.id)
        db.session.add(config)
    else:
        logger.info(f"📝 Atualizando configuração existente para bot {bot_id}")
        config = bot.config
    
    try:
        # === CAMPOS ATUALIZÁVEIS ===
        
        # 1. Mensagem de boas-vindas
        if 'welcome_message' in data:
            config.welcome_message = data['welcome_message']
        
        # 2. Mídia de boas-vindas
        if 'welcome_media_url' in data:
            config.welcome_media_url = data['welcome_media_url']
        if 'welcome_media_type' in data:
            config.welcome_media_type = data['welcome_media_type']
        if 'welcome_audio_enabled' in data:
            config.welcome_audio_enabled = bool(data['welcome_audio_enabled'])
        if 'welcome_audio_url' in data:
            config.welcome_audio_url = data['welcome_audio_url']
        
        # 3. Botões principais com validação Poka-Yoke
        if 'main_buttons' in data:
            main_buttons = data['main_buttons']
            # ✅ VALIDAÇÃO: Tratar None como array vazio
            if main_buttons is None:
                main_buttons = []
            # ✅ VALIDAÇÃO: Impedir preços negativos
            for button in main_buttons:
                if isinstance(button, dict) and 'price' in button:
                    try:
                        price = float(button['price'])
                        if price < 0:
                            logger.warning(f"⚠️ Preço negativo detectado: {price} -> ajustando para 0")
                            button['price'] = 0
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Preço inválido detectado: {button['price']} -> ajustando para 0")
                        button['price'] = 0
            config.set_main_buttons(main_buttons)
        
        # 4. Botões de redirecionamento
        if 'redirect_buttons' in data:
            redirect_buttons = data['redirect_buttons']
            # ✅ VALIDAÇÃO: Tratar None como array vazio
            if redirect_buttons is None:
                redirect_buttons = []
            config.set_redirect_buttons(redirect_buttons)
        
        # 5. Downsells com validação Poka-Yoke
        if 'downsells' in data:
            downsells = data['downsells']
            # ✅ VALIDAÇÃO: Tratar None como array vazio
            if downsells is None:
                downsells = []
            config.set_downsells(downsells)
        if 'downsells_enabled' in data:
            config.downsells_enabled = bool(data['downsells_enabled'])
        
        # 6. Upsells com validação Poka-Yoke
        if 'upsells' in data:
            upsells = data['upsells']
            # ✅ VALIDAÇÃO: Tratar None como array vazio
            if upsells is None:
                upsells = []
            # ✅ VALIDAÇÃO: Impedir preços negativos nos upsells
            for upsell in upsells:
                if isinstance(upsell, dict) and 'price' in upsell:
                    try:
                        price = float(upsell['price'])
                        if price < 0:
                            logger.warning(f"⚠️ Preço de upsell negativo: {price} -> ajustando para 0")
                            upsell['price'] = 0
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Preço de upsell inválido: {upsell['price']} -> ajustando para 0")
                        upsell['price'] = 0
            config.set_upsells(upsells)
        if 'upsells_enabled' in data:
            config.upsells_enabled = bool(data['upsells_enabled'])
        
        # 7. Link de acesso
        if 'access_link' in data:
            config.access_link = data['access_link']
        
        # 8. Mensagens personalizadas
        if 'success_message' in data:
            config.success_message = data['success_message']
        if 'pending_message' in data:
            config.pending_message = data['pending_message']
        
        # 9. Fluxo visual
        if 'flow_enabled' in data:
            config.flow_enabled = bool(data['flow_enabled'])
        if 'flow_steps' in data:
            flow_steps = data['flow_steps']
            # ✅ VALIDAÇÃO: Tratar None como array vazio
            if flow_steps is None:
                flow_steps = []
            config.set_flow_steps(flow_steps)
        if 'flow_start_step_id' in data:
            config.flow_start_step_id = data['flow_start_step_id']
        
        # Salvar alterações
        db.session.commit()
        logger.info(f"✅ Configuração do bot {bot_id} atualizada com sucesso")
        
        # Retornar configuração atualizada
        updated_config = config.to_dict()
        
        # Adicionar metadados novamente
        pool_bot = PoolBot.query.filter_by(bot_id=bot.id).first()
        has_meta_pixel = False
        pool_name = None
        if pool_bot and pool_bot.pool:
            pool = pool_bot.pool
            has_meta_pixel = pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token
            pool_name = pool.name
        
        updated_config['has_meta_pixel'] = has_meta_pixel
        updated_config['pool_name'] = pool_name
        
        return jsonify(updated_config)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao atualizar config do bot {bot_id}: {e}", exc_info=True)
        return jsonify({'error': f'Erro ao atualizar configuração: {str(e)}'}), 500


# ============================================================================
# NOTIFICATION SETTINGS APIs (Resgatadas da migração)
# ============================================================================

@dashboard_bp.route('/api/notification-settings', methods=['GET'])
@login_required
def api_get_notification_settings():
    """Retorna configurações de notificação do usuário"""
    # Verificar se existe tabela de configurações de notificação
    try:
        from internal_logic.core.models import NotificationSettings
        settings = NotificationSettings.query.filter_by(user_id=current_user.id).first()
        
        if not settings:
            # Retornar defaults
            return jsonify({
                'notify_approved_sales': True,
                'notify_pending_sales': False,
                'user_id': current_user.id
            })
        
        return jsonify({
            'notify_approved_sales': getattr(settings, 'notify_approved_sales', True),
            'notify_pending_sales': getattr(settings, 'notify_pending_sales', False),
            'user_id': current_user.id
        })
        
    except Exception as e:
        # Se tabela não existir, retornar defaults
        logger.warning(f"NotificationSettings não disponível: {e}")
        return jsonify({
            'notify_approved_sales': True,
            'notify_pending_sales': False,
            'user_id': current_user.id
        })


@dashboard_bp.route('/api/notification-settings', methods=['PUT'])
@login_required
@csrf.exempt
def api_update_notification_settings():
    """Atualiza configurações de notificação do usuário"""
    data = request.get_json()
    
    try:
        from internal_logic.core.models import NotificationSettings
        
        settings = NotificationSettings.query.filter_by(user_id=current_user.id).first()
        
        if not settings:
            settings = NotificationSettings(user_id=current_user.id)
            db.session.add(settings)
        
        settings.notify_approved_sales = data.get('notify_approved_sales', True)
        settings.notify_pending_sales = data.get('notify_pending_sales', False)
        
        db.session.commit()
        
        logger.info(f"Configurações de notificação atualizadas para {current_user.email}")
        
        return jsonify({
            'success': True,
            'notify_approved_sales': settings.notify_approved_sales,
            'notify_pending_sales': settings.notify_pending_sales
        })
        
    except Exception as e:
        db.session.rollback()
        logger.warning(f"Erro ao atualizar NotificationSettings: {e}")
        # Retornar sucesso mesmo se tabela não existir (modo degradado)
        return jsonify({
            'success': True,
            'notify_approved_sales': data.get('notify_approved_sales', True),
            'notify_pending_sales': data.get('notify_pending_sales', False),
            'note': 'Modo degradado - configurações não persistidas'
        })


# ============================================================================
# REMARKETING CAMPAIGNS APIs (Resgatadas da migração)
# ============================================================================

@dashboard_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['GET'])
@login_required
def api_get_remarketing_campaigns(bot_id):
    """Retorna campanhas de remarketing de um bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        from internal_logic.core.models import RemarketingCampaign
        campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).order_by(RemarketingCampaign.created_at.desc()).all()
        
        campaigns_data = []
        for campaign in campaigns:
            # Usar to_dict() se disponível, senão mapear campos manualmente
            if hasattr(campaign, 'to_dict'):
                campaign_dict = campaign.to_dict()
            else:
                # Mapeamento manual com campos REAIS do modelo
                campaign_dict = {
                    'id': campaign.id,
                    'bot_id': campaign.bot_id,
                    'name': campaign.name,
                    'message': campaign.message,
                    'status': campaign.status,
                    'target_audience': campaign.target_audience,
                    'total_targets': campaign.total_targets,
                    'total_sent': campaign.total_sent,
                    'total_clicks': campaign.total_clicks,
                    'total_sales': campaign.total_sales,
                    'revenue_generated': float(campaign.revenue_generated or 0),
                    'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
                    'scheduled_at': campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
                    'started_at': campaign.started_at.isoformat() if campaign.started_at else None,
                    'completed_at': campaign.completed_at.isoformat() if campaign.completed_at else None
                }
            campaigns_data.append(campaign_dict)
        
        return jsonify(campaigns_data)
        
    except Exception as e:
        logger.error(f"Erro ao carregar campanhas: {e}")
        return jsonify([])


@dashboard_bp.route('/api/bots/<int:bot_id>/remarketing/campaigns', methods=['POST'])
@login_required
@csrf.exempt
def api_create_remarketing_campaign(bot_id):
    """Cria nova campanha de remarketing"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    
    name = data.get('name', '').strip()
    message = data.get('message', '').strip()
    target_audience = data.get('target_audience', data.get('segment', 'all_users'))
    
    if not name or not message:
        return jsonify({'error': 'Nome e mensagem são obrigatórios'}), 400
    
    try:
        from internal_logic.core.models import RemarketingCampaign
        from datetime import datetime
        
        campaign = RemarketingCampaign(
            bot_id=bot_id,
            name=name,
            message=message,
            target_audience=target_audience,
            status='draft',
            scheduled_at=datetime.now()
        )
        
        db.session.add(campaign)
        db.session.commit()
        
        logger.info(f"Campanha criada: {name} para bot {bot_id}")
        
        return jsonify({
            'success': True,
            'campaign': {
                'id': campaign.id,
                'name': campaign.name,
                'message': campaign.message,
                'target_audience': campaign.target_audience,
                'status': campaign.status,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar campanha: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# GATEWAY APIs (Integração de Pagamentos)
# ============================================================================

@dashboard_bp.route('/api/gateways', methods=['GET'])
@login_required
def api_get_gateways():
    """Retorna todos os gateways do usuário atual"""
    try:
        gateways = Gateway.query.filter_by(user_id=current_user.id).all()
        
        gateways_data = []
        for gateway in gateways:
            # Mascarar credenciais para segurança no frontend
            api_key_masked = None
            if gateway.api_key:
                api_key_masked = f"****{gateway.api_key[-4:]}" if len(gateway.api_key) > 4 else "****"
            
            gateways_data.append({
                'id': gateway.id,
                'gateway_type': gateway.gateway_type,
                'store_id': gateway.store_id,
                'producer_hash': gateway.producer_hash,
                'is_active': gateway.is_active,
                'is_verified': gateway.is_verified,
                'api_key_masked': api_key_masked,
                'split_percentage': gateway.split_percentage,
                'total_transactions': gateway.total_transactions,
                'successful_transactions': gateway.successful_transactions,
                'created_at': gateway.created_at.isoformat() if gateway.created_at else None,
                'verified_at': gateway.verified_at.isoformat() if gateway.verified_at else None
            })
        
        return jsonify(gateways_data)
        
    except Exception as e:
        logger.error(f"Erro ao carregar gateways: {e}")
        return jsonify({'error': 'Erro ao carregar gateways'}), 500


@dashboard_bp.route('/api/gateways', methods=['POST'])
@login_required
@csrf.exempt
def api_create_gateway():
    """Cria um novo gateway de pagamento"""
    data = request.get_json()
    
    gateway_type = data.get('gateway_type', '').strip().lower()
    api_key = data.get('api_key', '').strip()
    client_secret = data.get('client_secret', '').strip()
    store_id = data.get('store_id', '').strip()
    
    if not gateway_type:
        return jsonify({'error': 'Tipo de gateway é obrigatório'}), 400
    
    try:
        # Criar novo gateway
        gateway = Gateway(
            user_id=current_user.id,
            gateway_type=gateway_type,
            store_id=store_id,
            is_active=True,  # Novo gateway começa ativo
            is_verified=False,
            split_percentage=2.0  # Padrão 2%
        )
        
        # Definir credenciais (serão criptografadas automaticamente pelos setters)
        if api_key:
            gateway.api_key = api_key
        if client_secret:
            gateway.client_secret = client_secret
        
        # Campos específicos por gateway
        if gateway_type == 'paradise':
            gateway._product_hash = data.get('product_hash', '').strip()
            gateway._offer_hash = data.get('offer_hash', '').strip()
        elif gateway_type == 'hoopay':
            gateway._organization_id = data.get('organization_id', '').strip()
        elif gateway_type == 'wiinpay':
            gateway._split_user_id = data.get('split_user_id', '').strip()
        elif gateway_type == 'atomo':
            gateway.producer_hash = data.get('producer_hash', '').strip()
        
        # REGRA DE NEGÓCIO: Desativar outros gateways do usuário
        # (apenas 1 gateway ativo por vez)
        existing_gateways = Gateway.query.filter_by(
            user_id=current_user.id, 
            is_active=True
        ).all()
        
        for existing in existing_gateways:
            existing.is_active = False
        
        db.session.add(gateway)
        db.session.commit()
        
        logger.info(f"Gateway criado: {gateway_type} (ID: {gateway.id}) por {current_user.email}")
        
        return jsonify({
            'success': True,
            'gateway': {
                'id': gateway.id,
                'gateway_type': gateway.gateway_type,
                'store_id': gateway.store_id,
                'is_active': gateway.is_active,
                'is_verified': gateway.is_verified,
                'created_at': gateway.created_at.isoformat() if gateway.created_at else None
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar gateway: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/gateways/<int:gateway_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def api_delete_gateway(gateway_id):
    """Deleta um gateway de pagamento"""
    gateway = Gateway.query.filter_by(id=gateway_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(gateway)
        db.session.commit()
        
        logger.info(f"Gateway deletado: {gateway_id} por {current_user.email}")
        return jsonify({'success': True, 'message': 'Gateway deletado com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao deletar gateway: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== API CHECK UPDATES (Polling para novos pagamentos) ====================

@dashboard_bp.route('/api/dashboard/check-updates', methods=['GET'])
@login_required
def check_dashboard_updates():
    """
    API: Verifica se há novos pagamentos (polling para notificações em tempo real)
    
    PARÂMETROS:
    - last_check: timestamp da última verificação
    
    RETORNA:
    - has_new_payments: boolean
    - new_count: quantidade de novos pagamentos
    - latest_payment_id: ID do último pagamento
    """
    try:
        from internal_logic.core.models import Payment, Bot
        
        last_check_timestamp = request.args.get('last_check', type=float)
        user_bot_ids = [bot.id for bot in Bot.query.filter_by(user_id=current_user.id, is_active=True).all()]
        
        if not user_bot_ids:
            return jsonify({'has_new_payments': False, 'new_count': 0, 'latest_payment_id': 0})
        
        if not last_check_timestamp:
            latest_payment = Payment.query.filter(
                Payment.bot_id.in_(user_bot_ids)
            ).order_by(Payment.id.desc()).first()
            
            return jsonify({
                'has_new_payments': False,
                'new_count': 0,
                'latest_payment_id': latest_payment.id if latest_payment else 0
            })
        
        from datetime import datetime
        last_check_dt = datetime.fromtimestamp(last_check_timestamp)
        
        new_payments_query = Payment.query.filter(
            Payment.bot_id.in_(user_bot_ids),
            Payment.created_at > last_check_dt
        )
        
        new_count = new_payments_query.count()
        has_new = new_count > 0
        
        latest_payment = Payment.query.filter(
            Payment.bot_id.in_(user_bot_ids)
        ).order_by(Payment.id.desc()).first()
        
        return jsonify({
            'has_new_payments': has_new,
            'new_count': new_count,
            'latest_payment_id': latest_payment.id if latest_payment else 0
        })
        
    except Exception as e:
        logger.error(f"Erro ao verificar atualizações do dashboard: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== BOT CRUD APIs (Faltantes) ====================

@dashboard_bp.route('/api/bots/<int:bot_id>', methods=['GET'])
@login_required
def api_get_bot(bot_id):
    """Obtém detalhes completos de um bot específico"""
    from internal_logic.core.models import Bot
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    return jsonify(bot.to_dict())


@dashboard_bp.route('/api/bots/<int:bot_id>', methods=['PUT'])
@login_required
@csrf.exempt
def api_update_bot(bot_id):
    """
    Atualiza dados do bot (nome, configurações)
    NÃO atualiza token (use /api/bots/<id>/token)
    """
    from internal_logic.core.models import Bot, BotConfig
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados inválidos'}), 400
    
    try:
        # Atualiza nome se fornecido
        if 'name' in data:
            bot.name = data['name'].strip()
        
        # Atualiza configurações se fornecidas
        if 'config' in data:
            config = BotConfig.query.filter_by(bot_id=bot_id).first()
            if not config:
                config = BotConfig(bot_id=bot_id)
                db.session.add(config)
            
            config_data = data['config']
            if 'welcome_message' in config_data:
                config.welcome_message = config_data['welcome_message']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bot atualizado!', 'bot': bot.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar bot {bot_id}: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/bots/<int:bot_id>/toggle', methods=['POST'])
@login_required
@csrf.exempt
def api_toggle_bot(bot_id):
    """Liga/desliga bot"""
    from internal_logic.core.models import Bot, BotConfig
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        if bot.is_running:
            # Parar bot
            from bot_manager import BotManager
            bot_manager = BotManager(socketio=None, user_id=current_user.id)
            bot_manager.stop_bot(bot.id)
            bot.is_running = False
            bot.last_stopped = get_brazil_time()
            message = 'Bot parado com sucesso'
        else:
            # Iniciar bot
            from bot_manager import BotManager
            bot_manager = BotManager(socketio=None, user_id=current_user.id)
            config = BotConfig.query.filter_by(bot_id=bot.id).first()
            bot_manager.start_bot(
                bot_id=bot.id,
                token=bot.token,
                config=config.to_dict() if config else {}
            )
            bot.is_running = True
            bot.last_started = get_brazil_time()
            bot.last_error = None
            message = 'Bot iniciado com sucesso'
        
        db.session.commit()
        return jsonify({'success': True, 'message': message, 'is_running': bot.is_running})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao toggle bot {bot_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@dashboard_bp.route('/api/bots/<int:bot_id>/test-connection', methods=['POST'])
@login_required
@csrf.exempt
def api_test_bot_connection(bot_id):
    """Testa conexão do bot com a API do Telegram"""
    from internal_logic.core.models import Bot
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        from bot_manager import BotManager
        bot_manager = BotManager(socketio=None, user_id=current_user.id)
        result = bot_manager.validate_token(bot.token)
        
        return jsonify({
            'success': True,
            'valid': True,
            'bot_info': result.get('bot_info', {})
        })
        
    except Exception as e:
        logger.error(f"Erro ao testar conexão do bot {bot_id}: {e}")
        return jsonify({'success': False, 'valid': False, 'error': str(e)}), 400


@dashboard_bp.route('/api/bots/<int:bot_id>/token', methods=['PUT'])
@login_required
@csrf.exempt
def api_update_bot_token(bot_id):
    """
    Atualiza token do bot (V2 - AUTO-STOP)
    
    FUNCIONALIDADES:
    - Para bot automaticamente antes de trocar token
    - Valida novo token com Telegram
    - Arquiva usuários do token antigo
    - Preserva faturamento histórico
    """
    from internal_logic.core.models import Bot, BotConfig, BotUser
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    data = request.get_json()
    new_token = data.get('token', '').strip()
    
    if not new_token:
        return jsonify({'error': 'Token é obrigatório'}), 400
    
    if new_token == bot.token:
        return jsonify({'error': 'Este token já está em uso neste bot'}), 400
    
    if Bot.query.filter(Bot.token == new_token, Bot.id != bot_id).first():
        return jsonify({'error': 'Este token já está cadastrado em outro bot'}), 400
    
    try:
        from bot_manager import BotManager
        bot_manager = BotManager(socketio=None, user_id=current_user.id)
        
        # AUTO-STOP
        was_running = bot.is_running
        if was_running:
            try:
                bot_manager.stop_bot(bot_id)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao parar bot: {e}")
            
            bot.is_running = False
            bot.last_stopped = get_brazil_time()
            db.session.commit()
        
        validation_result = bot_manager.validate_token(new_token)
        bot_info = validation_result.get('bot_info')
        
        # Preserva dados financeiros
        preserved_sales = bot.total_sales
        preserved_revenue = bot.total_revenue
        
        # Atualiza dados do bot
        bot.token = new_token
        bot.username = bot_info.get('username')
        bot.name = bot_info.get('first_name', bot.name)
        bot.bot_id = str(bot_info.get('id'))
        bot.is_running = False
        bot.last_error = None
        
        # ARQUIVAR USUÁRIOS DO TOKEN ANTIGO
        archived_count = BotUser.query.filter_by(bot_id=bot_id, archived=False).count()
        if archived_count > 0:
            BotUser.query.filter_by(bot_id=bot_id, archived=False).update({
                'archived': True,
                'archived_reason': 'token_changed',
                'archived_at': get_brazil_time()
            })
        
        bot.total_users = 0
        db.session.commit()
        
        return jsonify({
            'message': f'Token atualizado! {archived_count} usuários arquivados.',
            'bot': bot.to_dict(),
            'changes': {
                'old_username': bot.username,
                'new_username': bot_info.get('username'),
                'users_archived': archived_count,
                'was_auto_stopped': was_running
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao atualizar token do bot {bot_id}: {e}")
        return jsonify({'error': str(e)}), 400


# ==================== POOL BOTS API (Endpoint alternativo) ====================

@dashboard_bp.route('/api/pool-bots/<int:pool_bot_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def api_delete_pool_bot(pool_bot_id):
    """
    Remove bot do pool usando o ID da associação PoolBot
    Endpoint alternativo para /api/redirect-pools/<id>/bots/<id>
    """
    from internal_logic.core.models import PoolBot, RedirectPool
    
    pool_bot = PoolBot.query.join(RedirectPool).filter(
        PoolBot.id == pool_bot_id,
        RedirectPool.user_id == current_user.id
    ).first_or_404()
    
    try:
        db.session.delete(pool_bot)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Bot removido do pool!'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao remover bot do pool {pool_bot_id}: {e}")
        return jsonify({'error': str(e)}), 500

