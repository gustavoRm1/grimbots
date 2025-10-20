"""
Health Check Task
Verifica saúde do sistema periodicamente

Implementado por: QI 540
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def check_health_task():
    """
    Verifica saúde do sistema
    
    Executado a cada 1 minuto pelo Celery Beat
    """
    try:
        # Importar aqui para evitar circular import
        from app import db, Bot
        import redis
        
        issues = []
        
        # 1. Verificar Redis
        try:
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
        except Exception as e:
            issues.append(f"🔴 Redis offline: {e}")
            logger.error(f"Health check: Redis falhou - {e}")
        
        # 2. Verificar Database
        try:
            db.session.execute('SELECT 1')
        except Exception as e:
            issues.append(f"🔴 Database offline: {e}")
            logger.error(f"Health check: Database falhou - {e}")
        
        # 3. Verificar bots mortos
        try:
            dead_bots = Bot.query.filter(
                Bot.is_running == True,
                Bot.last_health_check < datetime.now() - timedelta(minutes=10)
            ).all()
            
            if dead_bots:
                for bot in dead_bots:
                    issues.append(f"⚠️ Bot @{bot.username} sem health check há 10+ min")
                    logger.warning(f"Health check: Bot @{bot.username} pode estar offline")
        except Exception as e:
            logger.error(f"Health check: Erro ao verificar bots - {e}")
        
        # Log resultado
        if not issues:
            logger.info("✅ Health check: Sistema OK")
        else:
            logger.warning(f"⚠️ Health check: {len(issues)} problemas encontrados")
        
        return {
            'status': 'ok' if not issues else 'warning',
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"💥 Health check falhou: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

