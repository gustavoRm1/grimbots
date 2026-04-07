"""
Stats Service - Lógica de Negócio para Estatísticas de Bots
============================================================
Implementação performática com queries otimizadas SQLAlchemy
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import func, extract
from internal_logic.core.extensions import db
from internal_logic.core.models import Payment, BotUser, RemarketingCampaign

logger = logging.getLogger(__name__)


class StatsService:
    """Serviço responsável por calcular estatísticas de bots de forma performática"""
    
    @staticmethod
    def get_period_filter(period_days):
        """Converte dias em filtro de data"""
        if period_days == 'all':
            return datetime.min
        try:
            days = int(period_days)
            return datetime.utcnow() - timedelta(days=days)
        except (ValueError, TypeError):
            return datetime.utcnow() - timedelta(days=30)  # Default: 30 dias
    
    @staticmethod
    def get_bot_metrics(bot_id, period_days=30):
        """
        Calcula métricas principais do bot de forma otimizada
        
        Args:
            bot_id: ID do bot
            period_days: Período em dias (int ou 'all')
            
        Returns:
            dict: Métricas calculadas
        """
        try:
            # Filtro de período
            date_filter = StatsService.get_period_filter(period_days)
            
            # Query base para pagamentos do bot
            payment_base = Payment.query.filter(
                Payment.bot_id == bot_id,
                Payment.created_at >= date_filter if period_days != 'all' else True
            )
            
            # Métricas de vendas (apenas pagamentos confirmados)
            paid_payments = payment_base.filter(Payment.status == 'paid')
            
            # Total de vendas pagas
            total_sales = paid_payments.count()
            
            # Receita total (query otimizada com func.sum)
            total_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= date_filter if period_days != 'all' else True
            ).scalar() or 0.0
            
            # Total de checkouts iniciados (todos os status)
            total_checkouts = payment_base.count()
            
            # Taxa de conversão
            conversion_rate = (total_sales / total_checkouts * 100) if total_checkouts > 0 else 0.0
            
            # Ticket médio
            avg_ticket = (total_revenue / total_sales) if total_sales > 0 else 0.0
            
            # Métricas de hoje
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            today_sales = Payment.query.filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= today_start,
                Payment.created_at < today_end
            ).count()
            
            today_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= today_start,
                Payment.created_at < today_end
            ).scalar() or 0.0
            
            # Métricas de ontem
            yesterday_start = today_start - timedelta(days=1)
            
            yesterday_sales = Payment.query.filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= yesterday_start,
                Payment.created_at < today_start
            ).count()
            
            yesterday_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= yesterday_start,
                Payment.created_at < today_start
            ).scalar() or 0.0
            
            # Variação percentual
            revenue_change = StatsService._calculate_percentage_change(today_revenue, yesterday_revenue)
            sales_change = StatsService._calculate_percentage_change(today_sales, yesterday_sales)
            
            # Métricas de usuários
            total_users = BotUser.query.filter_by(bot_id=bot_id).count()
            
            active_users = BotUser.query.filter(
                BotUser.bot_id == bot_id,
                BotUser.last_interaction >= date_filter if period_days != 'all' else True
            ).count()
            
            new_users = BotUser.query.filter(
                BotUser.bot_id == bot_id,
                BotUser.created_at >= date_filter if period_days != 'all' else True
            ).count()
            
            return {
                'total_sales': total_sales,
                'total_revenue': float(total_revenue),
                'avg_ticket': round(float(avg_ticket), 2),
                'conversion_rate': round(float(conversion_rate), 2),
                'today_sales': today_sales,
                'today_revenue': float(today_revenue),
                'revenue_change': round(float(revenue_change), 1),
                'sales_change': round(float(sales_change), 1),
                'total_users': total_users,
                'active_users': active_users,
                'new_users': new_users
            }
            
        except Exception as e:
            logger.error(f"Error calculating bot metrics for bot {bot_id}: {e}")
            return StatsService._get_empty_metrics()
    
    @staticmethod
    def get_sales_chart_data(bot_id, period_days=30):
        """
        Gera dados para gráfico de vendas diárias
        
        Args:
            bot_id: ID do bot
            period_days: Período em dias
            
        Returns:
            list: Lista de dicionários com dados diários
        """
        try:
            # Determinar número de dias para o gráfico
            chart_days = min(int(period_days), 30) if str(period_days).isdigit() else 30
            date_filter = StatsService.get_period_filter(chart_days)
            
            # Query otimizada para vendas por dia
            daily_data = db.session.query(
                func.date(Payment.created_at).label('date'),
                func.count(Payment.id).label('sales'),
                func.sum(Payment.amount).label('revenue')
            ).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= date_filter
            ).group_by(func.date(Payment.created_at)).all()
            
            # Converter para dicionário para lookup rápido
            data_by_date = {str(row.date): {'sales': row.sales, 'revenue': float(row.revenue or 0)} 
                           for row in daily_data}
            
            # Preencher todos os dias do período (inclusive sem vendas)
            chart_data = []
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            for i in range(chart_days - 1, -1, -1):  # Do mais antigo para o mais recente
                day_date = today - timedelta(days=i)
                date_str = str(day_date.date())
                
                day_data = data_by_date.get(date_str, {'sales': 0, 'revenue': 0.0})
                
                chart_data.append({
                    'date': date_str,
                    'day': day_date.strftime('%d/%m'),
                    'sales': day_data['sales'],
                    'revenue': day_data['revenue']
                })
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Error generating sales chart data for bot {bot_id}: {e}")
            return []
    
    @staticmethod
    def get_remarketing_metrics(bot_id):
        """
        Calcula métricas de remarketing do bot
        
        Args:
            bot_id: ID do bot
            
        Returns:
            dict: Métricas de remarketing
        """
        try:
            # Campanhas do bot
            total_campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id).count()
            active_campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id, status='active').count()
            completed_campaigns = RemarketingCampaign.query.filter_by(bot_id=bot_id, status='completed').count()
            
            # Totais de campanhas (query otimizada)
            campaign_totals = db.session.query(
                func.sum(RemarketingCampaign.total_sent).label('total_sent'),
                func.sum(RemarketingCampaign.total_clicks).label('total_clicks'),
                func.sum(RemarketingCampaign.total_sales).label('total_sales'),
                func.sum(RemarketingCampaign.revenue_generated).label('revenue_generated')
            ).filter(RemarketingCampaign.bot_id == bot_id).first()
            
            total_sent = int(campaign_totals.total_sent or 0)
            total_clicks = int(campaign_totals.total_clicks or 0)
            campaign_sales = int(campaign_totals.total_sales or 0)
            campaign_revenue = float(campaign_totals.revenue_generated or 0.0)
            
            # Taxas
            click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0.0
            conversion_rate = (campaign_sales / total_sent * 100) if total_sent > 0 else 0.0
            avg_ticket = (campaign_revenue / campaign_sales) if campaign_sales > 0 else 0.0
            
            return {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'completed_campaigns': completed_campaigns,
                'total_sent': total_sent,
                'total_clicks': total_clicks,
                'sales': campaign_sales,
                'revenue': campaign_revenue,
                'click_rate': round(float(click_rate), 2),
                'conversion_rate': round(float(conversion_rate), 2),
                'avg_ticket': round(float(avg_ticket), 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating remarketing metrics for bot {bot_id}: {e}")
            return StatsService._get_empty_remarketing_metrics()
    
    @staticmethod
    def get_gateway_stats(bot_id, period_days=30):
        """
        Calcula estatísticas por gateway de pagamento
        
        Args:
            bot_id: ID do bot
            period_days: Período em dias
            
        Returns:
            list: Lista de estatísticas por gateway
        """
        try:
            date_filter = StatsService.get_period_filter(period_days)
            
            gateway_data = db.session.query(
                Payment.gateway_type,
                func.count(Payment.id).label('sales'),
                func.sum(Payment.amount).label('revenue')
            ).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= date_filter if period_days != 'all' else True
            ).group_by(Payment.gateway_type).all()
            
            return [{
                'type': row.gateway_type,
                'sales': row.sales,
                'revenue': float(row.revenue or 0)
            } for row in gateway_data]
            
        except Exception as e:
            logger.error(f"Error calculating gateway stats for bot {bot_id}: {e}")
            return []
    
    @staticmethod
    def get_peak_hours(bot_id, period_days=30):
        """
        Identifica horários de pico de vendas
        
        Args:
            bot_id: ID do bot
            period_days: Período em dias
            
        Returns:
            list: Lista de horários com mais vendas
        """
        try:
            date_filter = StatsService.get_period_filter(period_days)
            
            peak_data = db.session.query(
                extract('hour', Payment.created_at).label('hour'),
                func.count(Payment.id).label('sales')
            ).filter(
                Payment.bot_id == bot_id,
                Payment.status == 'paid',
                Payment.created_at >= date_filter if period_days != 'all' else True
            ).group_by(extract('hour', Payment.created_at))\
             .order_by(func.count(Payment.id).desc())\
             .limit(5).all()
            
            return [{
                'hour': int(row.hour),
                'hour_formatted': f"{int(row.hour):02d}h",
                'sales': row.sales
            } for row in peak_data]
            
        except Exception as e:
            logger.error(f"Error calculating peak hours for bot {bot_id}: {e}")
            return []
    
    @staticmethod
    def _calculate_percentage_change(current, previous):
        """Calcula variação percentual de forma segura"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100
    
    @staticmethod
    def _get_empty_metrics():
        """Retorna métricas vazias para fallback"""
        return {
            'total_sales': 0,
            'total_revenue': 0.0,
            'avg_ticket': 0.0,
            'conversion_rate': 0.0,
            'today_sales': 0,
            'today_revenue': 0.0,
            'revenue_change': 0.0,
            'sales_change': 0.0,
            'total_users': 0,
            'active_users': 0,
            'new_users': 0
        }
    
    @staticmethod
    def _get_empty_remarketing_metrics():
        """Retorna métricas de remarketing vazias para fallback"""
        return {
            'total_campaigns': 0,
            'active_campaigns': 0,
            'completed_campaigns': 0,
            'total_sent': 0,
            'total_clicks': 0,
            'sales': 0,
            'revenue': 0.0,
            'click_rate': 0.0,
            'conversion_rate': 0.0,
            'avg_ticket': 0.0
        }
