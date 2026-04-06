#!/usr/bin/env python3
"""
Cron Jobs - GrimBots SRE Architecture
Script CLI para executar jobs periódicos via crontab.

Substitui o APScheduler removido.
Uso: python scripts/cron_jobs.py <job_name>

Jobs disponíveis:
  - reconcile_paradise
  - reconcile_pushynpay
  - reconcile_atomopay
  - reconcile_aguia
  - reconcile_bolt
  - check_expired_subscriptions
  - reset_error_count
  - update_ranking
  - health_check_pools
  - remarketing_campaigns
  - reconcile_all  (roda todos os reconciliadores)
"""

import sys
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Adicionar raiz do projeto ao path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# ✅ INJEÇÃO SEGURA: Criar app usando Factory Pattern
from internal_logic.core.config import Config
from internal_logic.core.extensions import create_app

app = create_app()


def run_with_context(func, job_name):
    """Executa função com contexto Flask e tratamento de erros"""
    try:
        with app.app_context():
            logger.info(f"🚀 Iniciando job: {job_name}")
            start_time = datetime.now()
            func()
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Job {job_name} concluído em {elapsed:.1f}s")
    except Exception as e:
        logger.error(f"❌ Erro no job {job_name}: {e}", exc_info=True)
        sys.exit(1)


def reconcile_paradise():
    """Reconciliação Paradise - executar a cada 5 minutos"""
    from app import reconcile_paradise_payments
    run_with_context(reconcile_paradise_payments, "reconcile_paradise")


def reconcile_pushynpay():
    """Reconciliação PushynPay - executar a cada 1 minuto"""
    from app import reconcile_pushynpay_payments
    run_with_context(reconcile_pushynpay_payments, "reconcile_pushynpay")


def reconcile_atomopay():
    """Reconciliação Atomopay - executar a cada 1 minuto"""
    from app import reconcile_atomopay_payments
    run_with_context(reconcile_atomopay_payments, "reconcile_atomopay")


def reconcile_aguia():
    """Reconciliação ÁguiaPags - executar a cada 1 minuto"""
    from app import reconcile_aguia_payments
    run_with_context(reconcile_aguia_payments, "reconcile_aguia")


def reconcile_bolt():
    """Reconciliação Bolt - executar a cada 1 minuto"""
    from app import reconcile_bolt_payments
    run_with_context(reconcile_bolt_payments, "reconcile_bolt")


def reconcile_all():
    """Executa todos os reconciliadores em sequência"""
    jobs = [
        reconcile_paradise,
        reconcile_pushynpay,
        reconcile_atomopay,
        reconcile_aguia,
        reconcile_bolt,
    ]
    
    logger.info("🚀 Iniciando reconciliação completa de todos os gateways")
    for job in jobs:
        try:
            job()
        except Exception as e:
            logger.error(f"❌ Job {job.__name__} falhou: {e}")
            # Continua com o próximo, não interrompe
    logger.info("✅ Reconciliação completa finalizada")


def check_expired_subscriptions():
    """Verifica e remove assinaturas expiradas - executar a cada 5 minutos"""
    from app import check_expired_subscriptions as _check
    run_with_context(_check, "check_expired_subscriptions")


def reset_error_count():
    """Reseta error_count alto após 7 dias - executar a cada 24 horas"""
    from app import reset_high_error_count_subscriptions
    run_with_context(reset_high_error_count_subscriptions, "reset_error_count")


def update_ranking():
    """Atualiza taxas premium do ranking - executar a cada 1 hora"""
    from app import update_ranking_premium_rates
    run_with_context(update_ranking_premium_rates, "update_ranking")


def health_check_pools():
    """Health check de pools - executar a cada 15 segundos (ou 1 min via cron)"""
    from app import health_check_all_pools
    run_with_context(health_check_all_pools, "health_check_pools")


def remarketing_campaigns():
    """Verifica campanhas agendadas - executar a cada 1 minuto"""
    from app import check_scheduled_remarketing_campaigns
    run_with_context(check_scheduled_remarketing_campaigns, "remarketing_campaigns")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUso: python scripts/cron_jobs.py <job_name>")
        print("\nExemplo: python scripts/cron_jobs.py reconcile_all")
        sys.exit(1)
    
    job_name = sys.argv[1]
    
    jobs = {
        'reconcile_paradise': reconcile_paradise,
        'reconcile_pushynpay': reconcile_pushynpay,
        'reconcile_atomopay': reconcile_atomopay,
        'reconcile_aguia': reconcile_aguia,
        'reconcile_bolt': reconcile_bolt,
        'reconcile_all': reconcile_all,
        'check_expired_subscriptions': check_expired_subscriptions,
        'reset_error_count': reset_error_count,
        'update_ranking': update_ranking,
        'health_check_pools': health_check_pools,
        'remarketing_campaigns': remarketing_campaigns,
    }
    
    if job_name not in jobs:
        logger.error(f"❌ Job desconhecido: {job_name}")
        print(f"\nJobs disponíveis: {', '.join(jobs.keys())}")
        sys.exit(1)
    
    # Executar job
    jobs[job_name]()


if __name__ == '__main__':
    main()
