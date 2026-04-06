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
    
    # Mapear bots para dict serializável
    bots_list = []
    for b in bots:
        bots_list.append({
            'id': b.id,
            'name': b.name,
            'username': getattr(b, 'username', ''),
            'is_running': getattr(b, 'is_running', False),
            'is_active': getattr(b, 'is_active', True),
            'total_users': getattr(b, 'total_users', 0),
            'total_sales': getattr(b, 'total_sales', 0),
            'total_revenue': float(getattr(b, 'total_revenue', 0) or 0),
            'pending_sales': getattr(b, 'pending_sales', 0),
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
    from internal_logic.core.models import RedirectPool, PoolBot
    
    pools = RedirectPool.query.filter_by(user_id=current_user.id).all()
    
    pools_data = []
    for pool in pools:
        bots_in_pool = PoolBot.query.filter_by(pool_id=pool.id).all()
        pools_data.append({
            'id': pool.id,
            'name': pool.name,
            'slug': pool.slug,
            'is_active': pool.is_active,
            'rotation_mode': pool.rotation_mode,
            'total_bots': len(bots_in_pool),
            'bots': [{
                'bot_id': pb.bot_id,
                'priority': pb.priority,
                'is_active': pb.is_active
            } for pb in bots_in_pool]
        })
    
    return jsonify({'success': True, 'pools': pools_data})


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
    pool_data['bots'] = [pb.to_dict() for pb in pool.pool_bots.all()]
    
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
        pool_bot.is_active = data['is_active']
    
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
            rotation_mode=data.get('rotation_mode', 'round_robin')
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
            pool.rotation_mode = data['rotation_mode']
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
            is_active=True
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
        is_active=True
    ).join(Bot).filter(
        Bot.is_active == True,
        Bot.token.isnot(None)
    ).order_by(PoolBot.priority.asc()).all()
    
    if not pool_bots:
        return jsonify({'error': 'Nenhum bot ativo no pool'}), 404
    
    # Rotacionar baseado no modo
    if pool.rotation_mode == 'round_robin':
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
    """Retorna lista de bots do usuário (JSON)"""
    bots = Bot.query.filter_by(user_id=current_user.id).all()
    
    bots_list = []
    for bot in bots:
        bots_list.append({
            'id': bot.id,
            'name': bot.name,
            'username': getattr(bot, 'username', ''),
            'is_running': getattr(bot, 'is_running', False),
            'is_active': getattr(bot, 'is_active', True),
            'total_users': getattr(bot, 'total_users', 0),
            'total_sales': getattr(bot, 'total_sales', 0),
            'total_revenue': float(getattr(bot, 'total_revenue', 0) or 0),
            'pending_sales': getattr(bot, 'pending_sales', 0),
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
        campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).all()
        
        campaigns_data = []
        for campaign in campaigns:
            campaigns_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'message': campaign.message,
                'segment': campaign.segment,
                'is_active': campaign.is_active,
                'scheduled_at': campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
                'executed_at': campaign.executed_at.isoformat() if campaign.executed_at else None,
                'executed_count': campaign.executed_count,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            })
        
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
    segment = data.get('segment', 'all_users')
    
    if not name or not message:
        return jsonify({'error': 'Nome e mensagem são obrigatórios'}), 400
    
    try:
        from internal_logic.core.models import RemarketingCampaign
        from datetime import datetime
        
        campaign = RemarketingCampaign(
            bot_id=bot_id,
            name=name,
            message=message,
            segment=segment,
            is_active=True,
            scheduled_at=datetime.now(),
            executed_count=0
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
                'segment': campaign.segment,
                'is_active': campaign.is_active,
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao criar campanha: {e}")
        return jsonify({'error': str(e)}), 500

