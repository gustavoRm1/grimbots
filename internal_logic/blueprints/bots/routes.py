"""
Bots Blueprint - Rotas relacionadas a bots individuais (REESCRITO)
=============================================================
Contém rotas para estatísticas, configurações e gestão de bots
ARQUITETURA: Stateless (On-Demand SQL) - 100% defensiva
"""

import logging
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func, extract, case, and_

from internal_logic.core.extensions import db
from internal_logic.core.models import Bot, Payment, BotUser, RemarketingCampaign
from internal_logic.services.stats_service import StatsService

logger = logging.getLogger(__name__)

# Criar Blueprint
bots_bp = Blueprint('bots', __name__)


# ============================================================================
# ROTAS PRINCIPAIS
# ============================================================================

@bots_bp.route('/<int:bot_id>/stats')
@login_required
def bot_stats_page(bot_id):
    """
    Página de estatísticas detalhadas do bot
    ARQUITETURA: Stateless (On-Demand SQL) - Nunca usa campos denormalizados
    """
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()

    # Obter período da query string (default: 30 dias)
    period = request.args.get('period', '30')

    # Filtro de data baseado no período
    if period == 'all':
        date_filter = datetime.min
    else:
        try:
            days = int(period)
            date_filter = datetime.utcnow() - timedelta(days=days)
        except (ValueError, TypeError):
            date_filter = datetime.utcnow() - timedelta(days=30)

    # Filtro base de pagamentos
    payment_filter = and_(
        Payment.bot_id == bot_id,
        Payment.created_at >= date_filter if period != 'all' else True
    )

    # Hoje e ontem para cálculos de variação
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    # ============================================================================
    # INICIALIZAÇÃO DOS DADOS (fallback seguro)
    # ============================================================================
    summary = {
        'total_sales': 0,
        'total_revenue': 0.0,
        'avg_ticket': 0.0,
        'conversion_rate': 0.0,
        'today_sales': 0,
        'today_revenue': 0.0,
        'revenue_change': 0.0,
        'sales_change': 0.0
    }

    users = {
        'total': 0,
        'active': 0,
        'new': 0
    }

    chart_data = {
        'daily_sales': [],
        'period': period
    }

    remarketing = {
        'total_campaigns': 0,
        'active_campaigns': 0,
        'completed_campaigns': 0,
        'total_sent': 0,
        'total_clicks': 0,
        'sales': 0,
        'revenue': 0.0,
        'conversion_rate': 0.0,
        'click_rate': 0.0,
        'avg_ticket': 0.0
    }

    gateways = []
    peak_hours = []
    top_products = []
    funnels = {
        'downsell_sales': 0,
        'downsell_revenue': 0.0,
        'upsell_sales': 0,
        'upsell_revenue': 0.0,
        'order_bump_sales': 0,
        'order_bump_revenue': 0.0
    }

    # ============================================================================
    # BLOCO 1: SUMMARY (Resumo Executivo)
    # BLINDAGEM: Erro aqui não afeta outros blocos
    # ============================================================================
    try:
        # Total de vendas no período
        total_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter,
            Payment.status == 'paid'
        ).scalar() or 0

        # Total de receita no período
        total_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter,
            Payment.status == 'paid'
        ).scalar() or 0.0

        # Total de checkouts (pagamentos tentados - pending + paid)
        total_checkouts = db.session.query(func.count(Payment.id)).filter(
            payment_filter,
            Payment.status.in_(['paid', 'pending'])
        ).scalar() or 0

        # Taxa de conversão
        conversion_rate = (total_sales / total_checkouts * 100) if total_checkouts > 0 else 0.0

        # Ticket médio
        avg_ticket = (total_revenue / total_sales) if total_sales > 0 else 0.0

        # Vendas de hoje
        today_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            Payment.created_at >= today,
            Payment.created_at < tomorrow
        ).scalar() or 0

        # Receita de hoje
        today_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            Payment.created_at >= today,
            Payment.created_at < tomorrow
        ).scalar() or 0.0

        # Vendas de ontem
        yesterday_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            Payment.created_at >= yesterday,
            Payment.created_at < today
        ).scalar() or 0

        # Receita de ontem
        yesterday_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot_id,
            Payment.status == 'paid',
            Payment.created_at >= yesterday,
            Payment.created_at < today
        ).scalar() or 0.0

        # Variações percentuais
        revenue_change = ((today_revenue - yesterday_revenue) / yesterday_revenue * 100) if yesterday_revenue > 0 else 0.0
        sales_change = ((today_sales - yesterday_sales) / yesterday_sales * 100) if yesterday_sales > 0 else 0.0

        summary = {
            'total_sales': total_sales,
            'total_revenue': float(total_revenue),
            'avg_ticket': round(avg_ticket, 2),
            'conversion_rate': round(conversion_rate, 2),
            'today_sales': today_sales,
            'today_revenue': float(today_revenue),
            'revenue_change': round(revenue_change, 1),
            'sales_change': round(sales_change, 1)
        }

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco SUMMARY para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo para evitar crash do frontend
        summary = {
            'total_sales': 0, 'total_revenue': 0.0, 'avg_ticket': 0.0,
            'conversion_rate': 0.0, 'today_sales': 0, 'today_revenue': 0.0,
            'revenue_change': 0.0, 'sales_change': 0.0
        }

    # ============================================================================
    # BLOCO 2: USERS (Métricas de Usuários)
    # ============================================================================
    try:
        total_users = db.session.query(func.count(BotUser.id)).filter(
            BotUser.bot_id == bot_id
        ).scalar() or 0

        active_users = db.session.query(func.count(BotUser.id)).filter(
            BotUser.bot_id == bot_id,
            BotUser.last_interaction >= date_filter
        ).scalar() or 0

        # BotUser não tem created_at, usa first_interaction como aproximação
        new_users = db.session.query(func.count(BotUser.id)).filter(
            BotUser.bot_id == bot_id,
            BotUser.first_interaction >= date_filter
        ).scalar() or 0

        # Fallback: se não há usuários registrados, usar total_sales (não pode haver menos usuários que vendas)
        if total_users == 0 and summary.get('total_sales', 0) > 0:
            total_users = summary['total_sales']

        users = {
            'total': int(total_users),
            'active': int(active_users),
            'new': int(new_users)
        }

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco USERS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo para evitar crash do frontend
        users = {
            'total': summary.get('total_sales', 0),
            'active': 0,
            'new': 0
        }

    # ============================================================================
    # BLOCO 3: CHART (Gráfico de Vendas Diárias)
    # ============================================================================
    try:
        chart_days = 7 if period == '7' else 30
        daily_sales = []

        for i in range(chart_days - 1, -1, -1):
            day_start = today - timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            day_sales = db.session.query(func.count(Payment.id)).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= day_start,
                Payment.created_at < day_end
            ).scalar() or 0

            day_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= day_start,
                Payment.created_at < day_end
            ).scalar() or 0.0

            daily_sales.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'day': day_start.strftime('%d/%m'),
                'sales': day_sales,
                'revenue': float(day_revenue)
            })

        chart_data = {
            'daily_sales': daily_sales,
            'period': period
        }

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco CHART para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo
        chart_data = {'daily_sales': [], 'period': period}

    # ============================================================================
    # BLOCO 4: REMARKETING (Estatísticas de Remarketing)
    # ============================================================================
    try:
        # Total de campanhas
        total_campaigns = db.session.query(func.count(RemarketingCampaign.id)).filter(
            RemarketingCampaign.bot_id == bot_id
        ).scalar() or 0

        active_campaigns = db.session.query(func.count(RemarketingCampaign.id)).filter(
            RemarketingCampaign.bot_id == bot_id,
            RemarketingCampaign.status == 'active'
        ).scalar() or 0

        completed_campaigns = db.session.query(func.count(RemarketingCampaign.id)).filter(
            RemarketingCampaign.bot_id == bot_id,
            RemarketingCampaign.status == 'completed'
        ).scalar() or 0

        # Totais agregados de campanhas
        campaign_totals = db.session.query(
            func.sum(RemarketingCampaign.total_sent).label('total_sent'),
            func.sum(RemarketingCampaign.total_clicks).label('total_clicks'),
            func.sum(RemarketingCampaign.total_sales).label('total_sales'),
            func.sum(RemarketingCampaign.revenue_generated).label('revenue_generated')
        ).filter(RemarketingCampaign.bot_id == bot_id).first()

        total_sent = campaign_totals.total_sent or 0
        total_clicks = campaign_totals.total_clicks or 0
        campaign_sales = campaign_totals.total_sales or 0
        campaign_revenue = campaign_totals.revenue_generated or 0.0

        # Vendas de remarketing via Payment (is_remarketing=True)
        remarketing_filter = and_(
            payment_filter,
            Payment.status == 'paid',
            Payment.is_remarketing == True
        )

        payment_remarketing_sales = db.session.query(func.count(Payment.id)).filter(
            remarketing_filter
        ).scalar() or 0

        payment_remarketing_revenue = db.session.query(func.sum(Payment.amount)).filter(
            remarketing_filter
        ).scalar() or 0.0

        # Usar o MAIOR valor entre Payments e Campanhas
        final_remarketing_sales = max(payment_remarketing_sales, campaign_sales)
        final_remarketing_revenue = max(payment_remarketing_revenue, campaign_revenue)

        # Taxas calculadas
        click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0.0
        conversion_rate_remarketing = (final_remarketing_sales / total_sent * 100) if total_sent > 0 else 0.0
        avg_ticket_remarketing = (final_remarketing_revenue / final_remarketing_sales) if final_remarketing_sales > 0 else 0.0

        remarketing = {
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'completed_campaigns': completed_campaigns,
            'total_sent': total_sent,
            'total_clicks': total_clicks,
            'sales': final_remarketing_sales,
            'revenue': float(final_remarketing_revenue),
            'conversion_rate': round(conversion_rate_remarketing, 2),
            'click_rate': round(click_rate, 2),
            'avg_ticket': round(avg_ticket_remarketing, 2)
        }

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco REMARKETING para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo para evitar crash do frontend
        remarketing = {
            'total_campaigns': 0, 'active_campaigns': 0, 'completed_campaigns': 0,
            'total_sent': 0, 'total_clicks': 0, 'sales': 0, 'revenue': 0.0,
            'conversion_rate': 0.0, 'click_rate': 0.0, 'avg_ticket': 0.0
        }

    # ============================================================================
    # BLOCO 5: GATEWAYS (Vendas por Gateway)
    # ============================================================================
    try:
        gateway_stats = db.session.query(
            Payment.gateway_type,
            func.count(Payment.id).label('sales'),
            func.sum(Payment.amount).label('revenue')
        ).filter(
            payment_filter,
            Payment.status == 'paid'
        ).group_by(Payment.gateway_type).all()

        gateways = [{
            'type': g.gateway_type or 'unknown',
            'sales': g.sales,
            'revenue': float(g.revenue or 0)
        } for g in gateway_stats]

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco GATEWAYS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo
        gateways = []

    # ============================================================================
    # BLOCO 6: PEAK HOURS (Horários de Pico)
    # ============================================================================
    try:
        peak_data = db.session.query(
            extract('hour', Payment.created_at).label('hour'),
            func.count(Payment.id).label('sales')
        ).filter(
            payment_filter,
            Payment.status == 'paid'
        ).group_by(extract('hour', Payment.created_at)).order_by(
            func.count(Payment.id).desc()
        ).limit(5).all()

        peak_hours = [{
            'hour': int(h.hour),
            'hour_formatted': f"{int(h.hour):02d}h",
            'sales': h.sales
        } for h in peak_data]

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco PEAK HOURS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo
        peak_hours = []

    # ============================================================================
    # BLOCO 7: TOP PRODUCTS (Produtos Mais Vendidos)
    # ============================================================================
    try:
        # Payment não tem product_id, usa product_name
        top_products_data = db.session.query(
            Payment.product_name,
            func.count(Payment.id).label('sales'),
            func.sum(Payment.amount).label('revenue')
        ).filter(
            payment_filter,
            Payment.status == 'paid',
            Payment.product_name.isnot(None),
            Payment.product_name != ''
        ).group_by(Payment.product_name).order_by(
            func.count(Payment.id).desc()
        ).limit(5).all()

        top_products = [{
            'id': p.product_name or 'Produto Desconhecido',
            'name': p.product_name or 'Produto Desconhecido',
            'sales': p.sales,
            'revenue': float(p.revenue or 0)
        } for p in top_products_data]

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco TOP PRODUCTS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo
        top_products = []

    # ============================================================================
    # BLOCO 8: FUNNELS (Métricas de Funil)
    # ============================================================================
    try:
        # Downsell
        downsell_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter,
            Payment.status == 'paid',
            Payment.is_downsell == True
        ).scalar() or 0

        downsell_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter,
            Payment.status == 'paid',
            Payment.is_downsell == True
        ).scalar() or 0.0

        # Upsell
        upsell_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter,
            Payment.status == 'paid',
            Payment.is_upsell == True
        ).scalar() or 0

        upsell_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter,
            Payment.status == 'paid',
            Payment.is_upsell == True
        ).scalar() or 0.0

        # Order Bump
        order_bump_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter,
            Payment.status == 'paid',
            Payment.order_bump_accepted == True
        ).scalar() or 0

        order_bump_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter,
            Payment.status == 'paid',
            Payment.order_bump_accepted == True
        ).scalar() or 0.0

        # Estimativas de exposição para cálculo de taxas
        downsell_sent = max(downsell_sales * 3, 1) if downsell_sales > 0 else 0
        upsell_shown = max(upsell_sales * 4, 1) if upsell_sales > 0 else 0
        order_bump_shown = max(order_bump_sales * 3, 1) if order_bump_sales > 0 else 0

        funnels = {
            'downsell_sales': int(downsell_sales),
            'downsell_revenue': float(downsell_revenue),
            'downsell_sent': int(downsell_sent),
            'downsell_conversion_rate': round((downsell_sales / downsell_sent * 100), 2) if downsell_sent > 0 else 0.0,
            'upsell_sales': int(upsell_sales),
            'upsell_revenue': float(upsell_revenue),
            'upsell_shown': int(upsell_shown),
            'upsell_conversion_rate': round((upsell_sales / upsell_shown * 100), 2) if upsell_shown > 0 else 0.0,
            'order_bump_sales': int(order_bump_sales),
            'order_bump_revenue': float(order_bump_revenue),
            'order_bump_shown': int(order_bump_shown),
            'order_bump_acceptance_rate': round((order_bump_sales / order_bump_shown * 100), 2) if order_bump_shown > 0 else 0.0
        }

    except Exception as e:
        logger.error(f"[STATS] Erro no bloco FUNNELS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo para evitar crash do frontend
        funnels = {
            'downsell_sales': 0, 'downsell_revenue': 0.0, 'downsell_sent': 0, 'downsell_conversion_rate': 0.0,
            'upsell_sales': 0, 'upsell_revenue': 0.0, 'upsell_shown': 0, 'upsell_conversion_rate': 0.0,
            'order_bump_sales': 0, 'order_bump_revenue': 0.0, 'order_bump_shown': 0, 'order_bump_acceptance_rate': 0.0
        }

    # ============================================================================
    # HISTÓRICO DE CAMPANHAS (PAGINADO)
    # ============================================================================
    page = request.args.get('page', 1, type=int)
    
    # Query paginada de campanhas do bot
    campaigns_pagination = RemarketingCampaign.query.filter_by(
        bot_id=bot_id
    ).order_by(
        RemarketingCampaign.created_at.desc()
    ).paginate(
        page=page, 
        per_page=10, 
        error_out=False
    )
    
    # Converter objetos SQLAlchemy para dicionários (JSON serializável)
    campaigns = []
    for campaign in campaigns_pagination.items:
        campaigns.append({
            'id': campaign.id,
            'name': campaign.name,
            'message': campaign.message,
            'is_active': campaign.is_active,
            'scheduled_at': campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
            'executed_at': campaign.executed_at.isoformat() if campaign.executed_at else None,
            'executed_count': campaign.executed_count,
            'clicks_count': campaign.clicks_count,
            'sales_count': campaign.sales_count,
            'revenue': float(campaign.revenue) if campaign.revenue else 0.0,
            'photo_url': campaign.photo_url,
            'video_url': campaign.video_url,
            'audio_url': campaign.audio_url,
            'buttons': campaign.buttons
        })
    
    pagination = {
        'page': campaigns_pagination.page,
        'pages': campaigns_pagination.pages,
        'has_prev': campaigns_pagination.has_prev,
        'has_next': campaigns_pagination.has_next,
        'prev_num': campaigns_pagination.prev_num,
        'next_num': campaigns_pagination.next_num,
        'total': campaigns_pagination.total
    }
    
    # ============================================================================
    # MONTAGEM DO RESPONSE JSON
    # ============================================================================
    stats_data = {
        'summary': summary,
        'users': users,
        'chart': chart_data,
        'remarketing': remarketing,
        'gateways': gateways,
        'peak_hours': peak_hours,
        'top_products': top_products,
        'funnels': funnels,
        # ============================================================
        # HISTÓRICO DE CAMPANHAS (PAGINADO)
        # ============================================================
        'campaigns': campaigns,
        'pagination': pagination
    }

    return render_template('bot_stats.html', bot=bot, stats=stats_data, campaigns=campaigns, pagination=pagination)
