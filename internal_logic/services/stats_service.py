"""
Stats Service - Lógica de Negócio para Estatísticas de Bots
============================================================
Implementação performática com queries SQL diretas para evitar problemas de schema
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import text, extract, func
from internal_logic.core.extensions import db
from internal_logic.core.models import Payment, BotUser

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
        Calcula métricas principais do bot usando SQL direto
        
        Args:
            bot_id: ID do bot
            period_days: Período em dias (int ou 'all')
            
        Returns:
            dict: Métricas calculadas
        """
        # REMOVIDO: try/except temporariamente para expor erros SQL
        # Filtro de período
        date_filter = StatsService.get_period_filter(period_days)
        date_filter_str = date_filter.strftime('%Y-%m-%d %H:%M:%S') if period_days != 'all' else None
        
        # Usar SQL direto via session (compatível SQLAlchemy 2.0)
        # Total de vendas pagas
        if date_filter_str:
            sales_query = text("""
                SELECT COUNT(*) as count 
                FROM payments 
                WHERE bot_id = :bot_id AND status = 'paid' AND created_at >= :date_filter
            """)
            total_sales = db.session.execute(sales_query, {"bot_id": bot_id, "date_filter": date_filter_str}).scalar()
        else:
            sales_query = text("SELECT COUNT(*) FROM payments WHERE bot_id = :bot_id AND status = 'paid'")
            total_sales = db.session.execute(sales_query, {"bot_id": bot_id}).scalar()
        
        # Receita total
        if date_filter_str:
            revenue_query = text("""
                SELECT COALESCE(SUM(amount), 0) as revenue 
                FROM payments 
                WHERE bot_id = :bot_id AND status = 'paid' AND created_at >= :date_filter
            """)
            total_revenue = db.session.execute(revenue_query, {"bot_id": bot_id, "date_filter": date_filter_str}).scalar()
        else:
            revenue_query = text("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE bot_id = :bot_id AND status = 'paid'")
            total_revenue = db.session.execute(revenue_query, {"bot_id": bot_id}).scalar()
        
        # Total de checkouts iniciados (todos os status)
        if date_filter_str:
            checkout_query = text("""
                SELECT COUNT(*) as count 
                FROM payments 
                WHERE bot_id = :bot_id AND created_at >= :date_filter
            """)
            total_checkouts = db.session.execute(checkout_query, {"bot_id": bot_id, "date_filter": date_filter_str}).scalar()
        else:
            checkout_query = text("SELECT COUNT(*) FROM payments WHERE bot_id = :bot_id")
            total_checkouts = db.session.execute(checkout_query, {"bot_id": bot_id}).scalar()
        
        # Taxa de conversão
        conversion_rate = (total_sales / total_checkouts * 100) if total_checkouts > 0 else 0.0
        
        # Ticket médio
        avg_ticket = (total_revenue / total_sales) if total_sales > 0 else 0.0
        
        # Métricas de hoje
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_str = today_start.strftime('%Y-%m-%d %H:%M:%S')
        today_end_str = (today_start + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        today_sales = db.session.execute(
            text("""SELECT COUNT(*) FROM payments 
               WHERE bot_id = :bot_id AND status = 'paid' 
               AND created_at >= :start_date AND created_at < :end_date"""),
            {"bot_id": bot_id, "start_date": today_start_str, "end_date": today_end_str}
        ).scalar()
        
        today_revenue = db.session.execute(
            text("""SELECT COALESCE(SUM(amount), 0) FROM payments 
               WHERE bot_id = :bot_id AND status = 'paid' 
               AND created_at >= :start_date AND created_at < :end_date"""),
            {"bot_id": bot_id, "start_date": today_start_str, "end_date": today_end_str}
        ).scalar()
        
        # Métricas de ontem
        yesterday_start_str = (today_start - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        yesterday_sales = db.session.execute(
            text("""SELECT COUNT(*) FROM payments 
               WHERE bot_id = :bot_id AND status = 'paid' 
               AND created_at >= :start_date AND created_at < :end_date"""),
            {"bot_id": bot_id, "start_date": yesterday_start_str, "end_date": today_start_str}
        ).scalar()
        
        yesterday_revenue = db.session.execute(
            text("""SELECT COALESCE(SUM(amount), 0) FROM payments 
               WHERE bot_id = :bot_id AND status = 'paid' 
               AND created_at >= :start_date AND created_at < :end_date"""),
            {"bot_id": bot_id, "start_date": yesterday_start_str, "end_date": today_start_str}
        ).scalar()
        
        # Variação percentual
        revenue_change = StatsService._calculate_percentage_change(today_revenue, yesterday_revenue)
        sales_change = StatsService._calculate_percentage_change(today_sales, yesterday_sales)
        
        # Métricas de usuários
        total_users = db.session.execute(
            text("SELECT COUNT(*) FROM bot_users WHERE bot_id = :bot_id"), 
            {"bot_id": bot_id}
        ).scalar()
        
        # Usuários ativos (com interação no período)
        if date_filter_str:
            active_users = db.session.execute(
                text("""SELECT COUNT(*) FROM bot_users 
                   WHERE bot_id = :bot_id AND last_interaction >= :date_filter"""),
                {"bot_id": bot_id, "date_filter": date_filter_str}
            ).scalar()
        else:
            active_users = 0
        
        # Novos usuários no período
        if date_filter_str:
            new_users = db.session.execute(
                text("""SELECT COUNT(*) FROM bot_users 
                   WHERE bot_id = :bot_id AND first_interaction >= :date_filter"""),
                {"bot_id": bot_id, "date_filter": date_filter_str}
            ).scalar()
        else:
            new_users = 0
        
        return {
            'total_sales': total_sales or 0,
            'total_revenue': float(total_revenue or 0.0),
            'avg_ticket': round(float(avg_ticket), 2),
            'conversion_rate': round(float(conversion_rate), 2),
            'today_sales': today_sales or 0,
            'today_revenue': float(today_revenue or 0.0),
            'revenue_change': round(float(revenue_change), 1),
            'sales_change': round(float(sales_change), 1),
            'total_users': total_users or 0,
            'active_users': active_users or 0,
            'new_users': new_users or 0
        }
    
    @staticmethod
    def get_sales_chart_data(bot_id, period_days=30):
        """
        Gera dados para gráfico de vendas diárias usando SQL direto
        
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
            date_filter_str = date_filter.strftime('%Y-%m-%d %H:%M:%S')
            
            # Query SQL para vendas por dia (via session - compatível SQLAlchemy 2.0)
            chart_query = text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as sales,
                    COALESCE(SUM(amount), 0) as revenue
                FROM payments 
                WHERE bot_id = :bot_id 
                    AND status = 'paid' 
                    AND created_at >= :date_filter
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            
            daily_data = db.session.execute(chart_query, {"bot_id": bot_id, "date_filter": date_filter_str}).fetchall()
            
            # Converter para dicionário para lookup rápido
            data_by_date = {str(row.date): {'sales': row.sales, 'revenue': float(row.revenue)} 
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
        Calcula métricas de remarketing do bot usando SQL direto
        
        Args:
            bot_id: ID do bot
            
        Returns:
            dict: Métricas de remarketing
        """
        try:
            # Usar SQL direto via session (compatível SQLAlchemy 2.0)
            # Campanhas do bot
            total_campaigns = db.session.execute(
                text("SELECT COUNT(*) FROM remarketing_campaigns WHERE bot_id = :bot_id"), 
                {"bot_id": bot_id}
            ).scalar()
            
            active_campaigns = db.session.execute(
                text("SELECT COUNT(*) FROM remarketing_campaigns WHERE bot_id = :bot_id AND status = 'active'"), 
                {"bot_id": bot_id}
            ).scalar()
            
            completed_campaigns = db.session.execute(
                text("SELECT COUNT(*) FROM remarketing_campaigns WHERE bot_id = :bot_id AND status = 'completed'"), 
                {"bot_id": bot_id}
            ).scalar()
            
            # Totais de campanhas
            campaign_totals = db.session.execute(
                text("""SELECT 
                    COALESCE(SUM(total_sent), 0) as total_sent,
                    COALESCE(SUM(total_clicks), 0) as total_clicks,
                    COALESCE(SUM(total_sales), 0) as total_sales,
                    COALESCE(SUM(revenue_generated), 0) as revenue_generated
                FROM remarketing_campaigns 
                WHERE bot_id = :bot_id"""),
                {"bot_id": bot_id}
            ).first()
            
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
    def _get_empty_metrics():
        """Retorna métricas vazias com valores zerados"""
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
        """Retorna métricas de remarketing vazias com valores zerados"""
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
    
    @staticmethod
    def _calculate_percentage_change(current, previous):
        """Calcula variação percentual com segurança"""
        if previous == 0 or previous is None:
            return 0.0
        return round(((current - previous) / previous) * 100, 1)
    
    @staticmethod
    def get_gateway_stats(bot_id, period_days=30):
        """
        Calcula estatísticas por gateway de pagamento
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
