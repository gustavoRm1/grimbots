"""
Bots Blueprint - Rotas relacionadas a bots individuais
=====================================================
Contém rotas para estatísticas, configurações e gestão de bots
"""

import logging
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from internal_logic.core.extensions import db
from internal_logic.core.models import Bot
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
    """Página de estatísticas detalhadas do bot"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Obter período da query string (default: 30 dias)
    period = request.args.get('period', '30')
    
    try:
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
        
        # Estruturar dados conforme esperado pelo template atual
        stats_data = {
            'general': {
                'total_users': metrics['total_users'],
                'total_sales': metrics['total_sales'],
                'pending_sales': 0,  # TODO: Implementar contagem de pagamentos pendentes
                'total_revenue': metrics['total_revenue'],
                'avg_ticket': metrics['avg_ticket'],
                'conversion_rate': metrics['conversion_rate']
            },
            'order_bumps': {
                'shown': 0,  # TODO: Implementar contagem de order bumps mostrados
                'accepted': 0,  # TODO: Implementar contagem de order bumps aceitos
                'acceptance_rate': 0,  # TODO: Calcular taxa de aceitação
                'revenue': 0.0  # TODO: Implementar receita de order bumps
            },
            'downsells': {
                'sent': 0,  # TODO: Implementar contagem de downsells enviados
                'converted': 0,  # TODO: Implementar contagem de downsells convertidos
                'conversion_rate': 0,  # TODO: Calcular taxa de conversão
                'revenue': 0.0  # TODO: Implementar receita de downsells
            },
            'remarketing': remarketing_metrics,
            'chart': {
                'daily_sales': chart_data,
                'period': period
            },
            'period_label': f'Últimos {period} dias' if str(period).isdigit() else 'Todo o período'
        }
        
        return render_template('bot_stats.html', bot=bot, stats=stats_data)
        
    except Exception as e:
        logger.error(f"Error loading stats page for bot {bot_id}: {e}")
        # Retornar página com dados vazios em caso de erro
        empty_stats = {
            'general': {
                'total_users': 0,
                'total_sales': 0,
                'pending_sales': 0,
                'total_revenue': 0.0,
                'avg_ticket': 0.0,
                'conversion_rate': 0.0
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
            'remarketing': StatsService._get_empty_remarketing_metrics(),
            'chart': {'daily_sales': [], 'period': period},
            'period_label': f'Últimos {period} dias'
        }
        return render_template('bot_stats.html', bot=bot, stats=empty_stats)


@bots_bp.route('/<int:bot_id>/stats/api')
@login_required
def bot_stats_api(bot_id):
    """API para estatísticas do bot (usada pelo frontend via AJAX)"""
    bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
    
    # Obter período da query string
    period = request.args.get('period', '30')
    
    try:
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
        
        # Retornar JSON conforme estrutura esperada pelo template
        return jsonify({
            'general': {
                'total_users': metrics['total_users'],
                'total_sales': metrics['total_sales'],
                'pending_sales': 0,  # TODO: Implementar contagem de pagamentos pendentes
                'total_revenue': metrics['total_revenue'],
                'avg_ticket': metrics['avg_ticket'],
                'conversion_rate': metrics['conversion_rate']
            },
            'order_bumps': {
                'shown': 0,  # TODO: Implementar contagem de order bumps mostrados
                'accepted': 0,  # TODO: Implementar contagem de order bumps aceitos
                'acceptance_rate': 0,  # TODO: Calcular taxa de aceitação
                'revenue': 0.0  # TODO: Implementar receita de order bumps
            },
            'downsells': {
                'sent': 0,  # TODO: Implementar contagem de downsells enviados
                'converted': 0,  # TODO: Implementar contagem de downsells convertidos
                'conversion_rate': 0,  # TODO: Calcular taxa de conversão
                'revenue': 0.0  # TODO: Implementar receita de downsells
            },
            'remarketing': remarketing_metrics,
            'chart': {
                'daily_sales': chart_data,
                'period': period
            },
            'period_label': f'Últimos {period} dias' if str(period).isdigit() else 'Todo o período'
        })
        
    except Exception as e:
        logger.error(f"Error in stats API for bot {bot_id}: {e}")
        return jsonify({'error': 'Failed to load statistics'}), 500
