#!/usr/bin/env python3
"""
Script de Validação Completa - Meta Pixel
Valida todos os itens do checklist automaticamente
"""

import os
import sys
import subprocess
import logging
import json
import redis
from datetime import datetime, timedelta

# Adicionar o diretório raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_celery():
    """Verifica se Celery está rodando"""
    logger.info("=" * 80)
    logger.info("1️⃣ VERIFICANDO CELERY")
    logger.info("=" * 80)
    
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        celery_processes = [line for line in result.stdout.split('\n') if 'celery' in line.lower() and 'grep' not in line.lower() and 'python' in line.lower()]
        
        if celery_processes:
            logger.info(f"✅ {len(celery_processes)} processo(s) Celery encontrado(s)")
            return True
        else:
            logger.error("❌ Nenhum processo Celery encontrado!")
            return False
    except Exception as e:
        logger.error(f"❌ Erro ao verificar Celery: {e}")
        return False

def check_redis():
    """Verifica se Redis está rodando e acessível"""
    logger.info("\n" + "=" * 80)
    logger.info("2️⃣ VERIFICANDO REDIS")
    logger.info("=" * 80)
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        
        # Contar chaves de tracking
        tracking_keys = r.keys('tracking:*')
        logger.info(f"✅ Redis está rodando")
        logger.info(f"   Chaves de tracking encontradas: {len(tracking_keys)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar Redis: {e}")
        return False

def check_recent_payments():
    """Verifica pagamentos recentes e seus tracking tokens"""
    logger.info("\n" + "=" * 80)
    logger.info("3️⃣ VERIFICANDO PAGAMENTOS RECENTES")
    logger.info("=" * 80)
    
    try:
        from app import app, db
        from models import Payment, BotUser
        
        with app.app_context():
            # Buscar pagamentos das últimas 24 horas
            time_threshold = datetime.utcnow() - timedelta(hours=24)
            recent_payments = Payment.query.filter(
                Payment.created_at >= time_threshold
            ).order_by(Payment.created_at.desc()).limit(10).all()
            
            if not recent_payments:
                logger.warning("⚠️ Nenhum pagamento encontrado nas últimas 24 horas")
                return False
            
            logger.info(f"✅ {len(recent_payments)} pagamento(s) encontrado(s) nas últimas 24 horas")
            
            for payment in recent_payments:
                logger.info(f"\n--- Payment ID: {payment.payment_id} ---")
                logger.info(f"   Status: {payment.status}")
                logger.info(f"   Valor: R$ {payment.amount:.2f}")
                logger.info(f"   Tracking Token: {payment.tracking_token[:30] if payment.tracking_token else 'N/A'}...")
                logger.info(f"   Meta Purchase Sent: {payment.meta_purchase_sent}")
                
                # Verificar BotUser
                telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else str(payment.customer_user_id)
                bot_user = BotUser.query.filter_by(bot_id=payment.bot_id, telegram_user_id=telegram_user_id).first()
                
                if bot_user:
                    logger.info(f"   BotUser Tracking Session ID: {bot_user.tracking_session_id[:30] if bot_user.tracking_session_id else 'N/A'}...")
                else:
                    logger.warning(f"   ⚠️ BotUser não encontrado")
            
            return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar pagamentos: {e}", exc_info=True)
        return False

def check_tracking_data():
    """Verifica dados de tracking no Redis"""
    logger.info("\n" + "=" * 80)
    logger.info("4️⃣ VERIFICANDO DADOS DE TRACKING NO REDIS")
    logger.info("=" * 80)
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Buscar algumas chaves de tracking recentes
        tracking_keys = r.keys('tracking:*')
        
        if not tracking_keys:
            logger.warning("⚠️ Nenhuma chave de tracking encontrada no Redis")
            return False
        
        logger.info(f"✅ {len(tracking_keys)} chave(s) de tracking encontrada(s)")
        
        # Verificar algumas chaves aleatórias
        sample_keys = tracking_keys[:5]
        
        for key in sample_keys:
            try:
                data = r.get(key)
                if data:
                    tracking_data = json.loads(data)
                    logger.info(f"\n--- Chave: {key} ---")
                    logger.info(f"   fbp: {'✅' if tracking_data.get('fbp') else '❌'}")
                    logger.info(f"   fbc: {'✅' if tracking_data.get('fbc') else '❌'}")
                    logger.info(f"   fbc_origin: {tracking_data.get('fbc_origin', 'N/A')}")
                    logger.info(f"   fbclid: {'✅' if tracking_data.get('fbclid') else '❌'}")
                    logger.info(f"   client_ip: {'✅' if tracking_data.get('client_ip') else '❌'}")
                    logger.info(f"   client_user_agent: {'✅' if tracking_data.get('client_user_agent') else '❌'}")
                    logger.info(f"   pageview_event_id: {'✅' if tracking_data.get('pageview_event_id') else '❌'}")
            except Exception as e:
                logger.warning(f"   ⚠️ Erro ao processar chave {key}: {e}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar tracking data: {e}", exc_info=True)
        return False

def check_meta_events_logs():
    """Verifica logs de eventos Meta"""
    logger.info("\n" + "=" * 80)
    logger.info("5️⃣ VERIFICANDO LOGS DE EVENTOS META")
    logger.info("=" * 80)
    
    try:
        # Verificar logs do Gunicorn
        log_file = 'logs/gunicorn.log'
        if os.path.exists(log_file):
            result = subprocess.run(['tail', '-100', log_file], capture_output=True, text=True)
            logs = result.stdout
            
            # Contar eventos
            pageview_count = logs.count('[META PAGEVIEW]')
            viewcontent_count = logs.count('[META VIEWCONTENT]')
            purchase_count = logs.count('[META PURCHASE]')
            
            logger.info(f"✅ Logs encontrados:")
            logger.info(f"   PageView: {pageview_count} evento(s)")
            logger.info(f"   ViewContent: {viewcontent_count} evento(s)")
            logger.info(f"   Purchase: {purchase_count} evento(s)")
            
            # Verificar últimos eventos
            if '[META PURCHASE]' in logs:
                logger.info(f"\n   ✅ Últimos eventos Purchase encontrados nos logs")
            else:
                logger.warning(f"   ⚠️ Nenhum evento Purchase encontrado nos logs recentes")
            
            return True
        else:
            logger.warning(f"⚠️ Arquivo de log não encontrado: {log_file}")
            return False
    except Exception as e:
        logger.error(f"❌ Erro ao verificar logs: {e}", exc_info=True)
        return False

def check_celery_tasks():
    """Verifica tasks do Celery"""
    logger.info("\n" + "=" * 80)
    logger.info("6️⃣ VERIFICANDO TASKS DO CELERY")
    logger.info("=" * 80)
    
    try:
        # Verificar tasks ativas
        result = subprocess.run(['celery', '-A', 'celery_app', 'inspect', 'active'], capture_output=True, text=True)
        
        if 'No nodes' in result.stdout:
            logger.error("❌ Nenhum worker Celery encontrado!")
            return False
        
        logger.info(f"✅ Workers Celery encontrados")
        logger.info(f"   {result.stdout[:200]}...")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar tasks Celery: {e}")
        return False

def main():
    """Função principal"""
    logger.info("=" * 80)
    logger.info("🚀 CHECKLIST DE VALIDAÇÃO - META PIXEL")
    logger.info("=" * 80)
    
    results = {
        'celery': check_celery(),
        'celery_tasks': check_celery_tasks(),
        'redis': check_redis(),
        'recent_payments': check_recent_payments(),
        'tracking_data': check_tracking_data(),
        'meta_events_logs': check_meta_events_logs()
    }
    
    # Resumo
    logger.info("\n" + "=" * 80)
    logger.info("📊 RESUMO DA VALIDAÇÃO")
    logger.info("=" * 80)
    
    for check, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"{status} {check}: {'OK' if result else 'FALHOU'}")
    
    total_checks = len(results)
    passed_checks = sum(1 for r in results.values() if r)
    
    logger.info(f"\n✅ {passed_checks}/{total_checks} verificações passaram")
    
    if passed_checks == total_checks:
        logger.info("\n✅ TODAS AS VERIFICAÇÕES PASSARAM!")
    else:
        logger.warning(f"\n⚠️ {total_checks - passed_checks} verificação(ões) falharam")

if __name__ == "__main__":
    main()

