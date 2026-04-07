"""
API Blueprint - Endpoints de API para frontend
==============================================
Contém todas as rotas de API usadas pelo frontend via AJAX
"""

import logging
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFProtect

from internal_logic.core.models import Bot
from internal_logic.services.stats_service import StatsService

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
        response_data = {
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
            'daily_chart': chart_data,  # ✅ CORREÇÃO: JavaScript espera 'daily_chart'
            'period_label': f'Últimos {period} dias' if str(period).isdigit() else 'Todo o período',
            'gateways': gateway_stats,
            'peak_hours': peak_hours
        }
        
        # ✅ LOG: Imprimir resposta para debugging
        logger.info(f"🔍 API RESPONSE for bot {bot_id}:")
        logger.info(f"  total_sales: {response_data['general']['total_sales']}")
        logger.info(f"  total_revenue: {response_data['general']['total_revenue']}")
        logger.info(f"  daily_chart length: {len(response_data['daily_chart'])}")
        logger.info(f"  chart_data sample: {response_data['daily_chart'][:3] if response_data['daily_chart'] else 'EMPTY'}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error in stats API for bot {bot_id}: {e}")
        return jsonify({'error': 'Failed to load statistics'}), 500


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
