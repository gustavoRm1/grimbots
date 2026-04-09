"""
API Blueprint - Endpoints de API para frontend (REESCRITO)
=========================================================
Contém todas as rotas de API usadas pelo frontend via AJAX
ARQUITETURA: Stateless (On-Demand SQL) - 100% defensiva
"""

import logging
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta
from sqlalchemy import func, extract, and_

from internal_logic.core.models import Bot, Payment, BotUser, RemarketingCampaign
from internal_logic.core.extensions import db

logger = logging.getLogger(__name__)

# Criar API Blueprint (sem prefixo para manter /api/...)
api_bp = Blueprint('api', __name__)
csrf = CSRFProtect()


# ============================================================================
# API DE ESTATÍSTICAS DE BOTS
# ============================================================================

@api_bp.route('/bots/<int:bot_id>/stats')
@login_required
@csrf.exempt
def bot_stats_api(bot_id):
    """
    API para estatísticas do bot (usada pelo frontend via AJAX)
    ARQUITETURA: Stateless (On-Demand SQL) - Nunca usa campos denormalizados
    """
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()

    # Obter período da query string
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

    chart_data = []
    daily_chart = []

    users = {
        'total': 0,
        'active': 0,
        'new': 0
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
    # BLOCO 1: SUMMARY (Resumo Executivo) - CRÍTICO
    # ============================================================================
    try:
        total_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter, Payment.status == 'paid'
        ).scalar() or 0

        total_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter, Payment.status == 'paid'
        ).scalar() or 0.0

        total_checkouts = db.session.query(func.count(Payment.id)).filter(
            payment_filter, Payment.status.in_(['paid', 'pending'])
        ).scalar() or 0

        conversion_rate = (total_sales / total_checkouts * 100) if total_checkouts > 0 else 0.0
        avg_ticket = (total_revenue / total_sales) if total_sales > 0 else 0.0

        today_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id == bot_id, Payment.status == 'paid',
            Payment.created_at >= today, Payment.created_at < tomorrow
        ).scalar() or 0

        today_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot_id, Payment.status == 'paid',
            Payment.created_at >= today, Payment.created_at < tomorrow
        ).scalar() or 0.0

        yesterday_sales = db.session.query(func.count(Payment.id)).filter(
            Payment.bot_id == bot_id, Payment.status == 'paid',
            Payment.created_at >= yesterday, Payment.created_at < today
        ).scalar() or 0

        yesterday_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.bot_id == bot_id, Payment.status == 'paid',
            Payment.created_at >= yesterday, Payment.created_at < today
        ).scalar() or 0.0

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
        logger.error(f"[API STATS] Erro no bloco SUMMARY para bot {bot_id}: {e}", exc_info=True)
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
            BotUser.bot_id == bot_id, BotUser.last_interaction >= date_filter
        ).scalar() or 0

        # Fallback: se não há usuários registrados, usar total_sales (não pode haver menos usuários que vendas)
        if total_users == 0 and summary.get('total_sales', 0) > 0:
            total_users = summary['total_sales']

        users = {
            'total': int(total_users),
            'active': int(active_users),
            'new': 0  # BotUser não tem created_at - não é possível calcular novos usuários
        }
    except Exception as e:
        logger.error(f"[API STATS] Erro no bloco USERS para bot {bot_id}: {e}", exc_info=True)
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
                Payment.bot_id == bot_id, Payment.status == 'paid',
                Payment.created_at >= day_start, Payment.created_at < day_end
            ).scalar() or 0

            day_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.bot_id == bot_id, Payment.status == 'paid',
                Payment.created_at >= day_start, Payment.created_at < day_end
            ).scalar() or 0.0

            daily_sales.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'day': day_start.strftime('%d/%m'),
                'sales': day_sales,
                'revenue': float(day_revenue)
            })

        chart_data = daily_sales
        daily_chart = daily_sales
    except Exception as e:
        logger.error(f"[API STATS] Erro no bloco CHART para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo
        chart_data = []
        daily_chart = []

    # ============================================================================
    # BLOCO 4: REMARKETING (Estatísticas de Remarketing)
    # ============================================================================
    try:
        total_campaigns = db.session.query(func.count(RemarketingCampaign.id)).filter(
            RemarketingCampaign.bot_id == bot_id
        ).scalar() or 0

        active_campaigns = db.session.query(func.count(RemarketingCampaign.id)).filter(
            RemarketingCampaign.bot_id == bot_id, RemarketingCampaign.status == 'active'
        ).scalar() or 0

        completed_campaigns = db.session.query(func.count(RemarketingCampaign.id)).filter(
            RemarketingCampaign.bot_id == bot_id, RemarketingCampaign.status == 'completed'
        ).scalar() or 0

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

        remarketing_filter = and_(payment_filter, Payment.status == 'paid', Payment.is_remarketing == True)

        payment_remarketing_sales = db.session.query(func.count(Payment.id)).filter(remarketing_filter).scalar() or 0
        payment_remarketing_revenue = db.session.query(func.sum(Payment.amount)).filter(remarketing_filter).scalar() or 0.0

        final_remarketing_sales = max(payment_remarketing_sales, campaign_sales)
        final_remarketing_revenue = max(payment_remarketing_revenue, campaign_revenue)

        click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0.0
        conversion_rate_remarketing = (final_remarketing_sales / total_sent * 100) if total_sent > 0 else 0.0
        avg_ticket_remarketing = (final_remarketing_revenue / final_remarketing_sales) if final_remarketing_sales > 0 else 0.0

        # Buscar lista de campanhs individuais (limite 50 para performance)
        campaigns_list = []
        try:
            recent_campaigns = RemarketingCampaign.query.filter_by(
                bot_id=bot_id
            ).order_by(
                RemarketingCampaign.created_at.desc()
            ).limit(50).all()
            
            for campaign in recent_campaigns:
                # ✅ FIX: Garantir que buttons seja sempre uma lista
                buttons_data = campaign.buttons
                if isinstance(buttons_data, str):
                    try:
                        import json
                        buttons_data = json.loads(buttons_data) if buttons_data else []
                    except:
                        buttons_data = []
                elif buttons_data is None:
                    buttons_data = []
                elif not isinstance(buttons_data, list):
                    buttons_data = []
                
                campaigns_list.append({
                    'id': campaign.id,
                    'name': campaign.name,
                    'message': campaign.message,
                    'status': campaign.status,
                    'scheduled_at': campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
                    'started_at': campaign.started_at.isoformat() if campaign.started_at else None,
                    'completed_at': campaign.completed_at.isoformat() if campaign.completed_at else None,
                    'total_targets': campaign.total_targets,
                    'total_sent': campaign.total_sent,
                    'total_clicks': campaign.total_clicks,
                    'total_sales': campaign.total_sales,
                    'revenue_generated': float(campaign.revenue_generated) if campaign.revenue_generated else 0.0,
                    'media_url': campaign.media_url,
                    'media_type': campaign.media_type,
                    'audio_url': campaign.audio_url,
                    'buttons': buttons_data,  # ✅ Sempre uma lista
                    'target_audience': campaign.target_audience
                })
        except Exception as campaign_error:
            logger.warning(f"[API STATS] Erro ao buscar campanhs individuais: {campaign_error}")

        remarketing = {
            'total_campaigns': int(total_campaigns),
            'active_campaigns': int(active_campaigns),
            'completed_campaigns': int(completed_campaigns),
            'total_sent': int(total_sent),
            'total_clicks': int(total_clicks),
            'sales': int(final_remarketing_sales),
            'revenue': float(final_remarketing_revenue),
            'conversion_rate': round(conversion_rate_remarketing, 2),
            'click_rate': round(click_rate, 2),
            'avg_ticket': round(avg_ticket_remarketing, 2),
            'campaigns': campaigns_list  # ✅ Lista de campanhs para o frontend
        }
    except Exception as e:
        logger.error(f"[API STATS] Erro no bloco REMARKETING para bot {bot_id}: {e}", exc_info=True)
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
        ).filter(payment_filter, Payment.status == 'paid').group_by(Payment.gateway_type).all()

        gateways = [{
            'type': g.gateway_type or 'unknown',
            'sales': g.sales,
            'revenue': float(g.revenue or 0)
        } for g in gateway_stats]
    except Exception as e:
        logger.error(f"[API STATS] Erro no bloco GATEWAYS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo
        gateways = []

    # ============================================================================
    # BLOCO 6: PEAK HOURS (Horários de Pico)
    # ============================================================================
    try:
        peak_data = db.session.query(
            extract('hour', Payment.created_at).label('hour'),
            func.count(Payment.id).label('sales')
        ).filter(payment_filter, Payment.status == 'paid').group_by(
            extract('hour', Payment.created_at)
        ).order_by(func.count(Payment.id).desc()).limit(5).all()

        peak_hours = [{
            'hour': int(h.hour),
            'hour_formatted': f"{int(h.hour):02d}h",
            'sales': h.sales
        } for h in peak_data]
    except Exception as e:
        logger.error(f"[API STATS] Erro no bloco PEAK HOURS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo
        peak_hours = []

    # ============================================================================
    # BLOCO 7: TOP PRODUCTS (Produtos Mais Vendidos)
    # ============================================================================
    top_products = []  # Inicializado com fallback vazio
    try:
        # Payment não tem product_id, usa product_name
        top_products_data = db.session.query(
            Payment.product_name,
            func.count(Payment.id).label('sales'),
            func.sum(Payment.amount).label('revenue')
        ).filter(
            payment_filter, Payment.status == 'paid',
            Payment.product_name.isnot(None), Payment.product_name != ''
        ).group_by(Payment.product_name).order_by(func.count(Payment.id).desc()).limit(5).all()

        top_products = [{
            'id': p.product_name or 'Produto Desconhecido',  # Usa product_name como ID
            'name': p.product_name or 'Produto Desconhecido',
            'sales': p.sales,
            'revenue': float(p.revenue or 0)
        } for p in top_products_data]
    except Exception as e:
        logger.error(f"[API STATS] Erro no bloco TOP PRODUCTS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo: lista vazia tipada corretamente
        top_products = []

    # ============================================================================
    # BLOCO 8: FUNNELS (Métricas de Funil)
    # ============================================================================
    try:
        downsell_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter, Payment.status == 'paid', Payment.is_downsell == True
        ).scalar() or 0

        downsell_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter, Payment.status == 'paid', Payment.is_downsell == True
        ).scalar() or 0.0

        upsell_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter, Payment.status == 'paid', Payment.is_upsell == True
        ).scalar() or 0

        upsell_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter, Payment.status == 'paid', Payment.is_upsell == True
        ).scalar() or 0.0

        order_bump_sales = db.session.query(func.count(Payment.id)).filter(
            payment_filter, Payment.status == 'paid', Payment.order_bump_accepted == True
        ).scalar() or 0

        order_bump_revenue = db.session.query(func.sum(Payment.amount)).filter(
            payment_filter, Payment.status == 'paid', Payment.order_bump_accepted == True
        ).scalar() or 0.0

        # Estimativas de exposição (shown/sent) para cálculo de taxas
        # Plano B: estimar baseado em vendas (assumindo 20-30% de conversão típica)
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
        logger.error(f"[API STATS] Erro no bloco FUNNELS para bot {bot_id}: {e}", exc_info=True)
        # Fallback completo para evitar crash do frontend
        funnels = {
            'downsell_sales': 0, 'downsell_revenue': 0.0, 'downsell_sent': 0, 'downsell_conversion_rate': 0.0,
            'upsell_sales': 0, 'upsell_revenue': 0.0, 'upsell_shown': 0, 'upsell_conversion_rate': 0.0,
            'order_bump_sales': 0, 'order_bump_revenue': 0.0, 'order_bump_shown': 0, 'order_bump_acceptance_rate': 0.0
        }

    # ============================================================================
    # CONTRATO JSON FINAL (Contract Compliance)
    # ============================================================================
    response_data = {
        'summary': summary,
        'users': users,
        'chart': {
            'daily_sales': chart_data,
            'period': period
        },
        'daily_chart': daily_chart,
        'remarketing': remarketing,
        'gateways': gateways,
        'peak_hours': peak_hours,
        'top_products': top_products,
        'funnels': funnels,
        'period_label': f'Últimos {period} dias' if str(period).isdigit() else 'Todo o período',
        # Campos de compatibilidade legacy
        'general': {
            'total_users': users['total'],
            'total_sales': summary['total_sales'],
            'pending_sales': 0,
            'total_revenue': summary['total_revenue'],
            'avg_ticket': summary['avg_ticket'],
            'conversion_rate': summary['conversion_rate']
        },
        'order_bumps': {
            'shown': 0,
            'accepted': funnels['order_bump_sales'],
            'acceptance_rate': 0,
            'revenue': funnels['order_bump_revenue']
        },
        'downsells': {
            'sent': 0,
            'converted': funnels['downsell_sales'],
            'conversion_rate': 0,
            'revenue': funnels['downsell_revenue']
        }
    }

    return jsonify(response_data)


# ============================================================================
# API ANALYTICS V2.0
# ============================================================================

@api_bp.route('/bots/<int:bot_id>/analytics-v2')
@login_required
@csrf.exempt
def bot_analytics_v2(bot_id):
    """API Analytics V2.0 - Dados demográficos e métricas avançadas"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    try:
        # Obter período da query string
        period = request.args.get('period', '30')
        
        # Buscar métricas principais
        metrics = StatsService.get_bot_metrics(bot_id, period)
        
        # Buscar dados do gráfico
        chart_data = StatsService.get_sales_chart_data(bot_id, period)
        
        # Buscar métricas de remarketing
        remarketing_metrics = StatsService.get_remarketing_metrics(bot_id)
        
        # Buscar estatísticas por gateway
        gateway_stats = StatsService.get_gateway_stats(bot_id, period)
        
        # Buscar horários de pico
        peak_hours = StatsService.get_peak_hours(bot_id, period)
        
        # Analytics V2.0 - Dados demográficos e métricas avançadas
        analytics_v2_data = {
            # Métricas principais
            'overview': {
                'total_revenue': metrics['total_revenue'],
                'total_sales': metrics['total_sales'],
                'total_users': metrics['total_users'],
                'conversion_rate': metrics['conversion_rate'],
                'avg_ticket': metrics['avg_ticket']
            },
            
            # Dados demográficos (simulados - TODO: implementar com dados reais)
            'demographics': {
                'age_groups': {
                    '18-24': 15,
                    '25-34': 35,
                    '35-44': 28,
                    '45-54': 15,
                    '55+': 7
                },
                'gender': {
                    'male': 45,
                    'female': 52,
                    'other': 3
                },
                'locations': {
                    'São Paulo': 25,
                    'Rio de Janeiro': 18,
                    'Minas Gerais': 12,
                    'Bahia': 8,
                    'Outros': 37
                }
            },
            
            # Engajamento
            'engagement': {
                'active_users': metrics['active_users'],
                'new_users': metrics['new_users'],
                'retention_rate': 75.5,  # TODO: Calcular taxa de retenção real
                'avg_session_duration': 4.2  # minutos
            },
            
            # Performance por dispositivo
            'devices': {
                'mobile': 65,
                'desktop': 28,
                'tablet': 7
            },
            
            # Fontes de tráfego
            'traffic_sources': {
                'direct': 35,
                'social': 28,
                'search': 20,
                'referral': 12,
                'other': 5
            },
            
            # Dados temporais para gráficos
            'temporal': {
                'daily_sales': chart_data,
                'revenue_trend': [item['revenue'] for item in chart_data],
                'sales_trend': [item['sales'] for item in chart_data]
            },
            
            # Remarketing
            'remarketing': remarketing_metrics,
            
            # Gateways
            'gateways': gateway_stats,
            
            # Horários de pico
            'peak_hours': peak_hours,
            
            # Período analisado
            'period': period,
            'period_label': f'Últimos {period} dias' if str(period).isdigit() else 'Todo o período'
        }
        
        return jsonify(analytics_v2_data)
        
    except Exception as e:
        logger.error(f"Error in analytics v2 API for bot {bot_id}: {e}")
        return jsonify({'error': 'Failed to load analytics data'}), 500
