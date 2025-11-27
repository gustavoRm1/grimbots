#!/usr/bin/env python3
"""
Script para verificar se os jobs de assinaturas estão rodando no APScheduler
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, scheduler

def main():
    with app.app_context():
        print("=" * 70)
        print("📋 VERIFICAÇÃO DE JOBS DE ASSINATURAS")
        print("=" * 70)
        print()
        
        # Verificar se scheduler está rodando
        if not scheduler.running:
            print("⚠️ APScheduler não está rodando neste processo!")
            print("   Isso é normal se o scheduler está rodando em outro processo (Gunicorn).")
            print()
            print("✅ Verifique os logs do Gunicorn para confirmar que os jobs foram registrados:")
            print("   ./scripts/verificar_jobs_logs.sh")
            print()
            print("   Ou manualmente:")
            print("   tail -100 logs/gunicorn.log | grep 'Job.*registrado'")
            print("   tail -100 logs/error.log | grep 'Job.*registrado'")
            print()
            print("   As seguintes mensagens devem aparecer:")
            print("   - '✅ Job check_expired_subscriptions registrado'")
            print("   - '✅ Job check_pending_subscriptions_in_groups registrado'")
            print("   - '✅ Job retry_failed_subscription_removals registrado'")
            print()
            return True  # Não é erro se scheduler está em outro processo
        
        jobs = scheduler.get_jobs()
        subscription_jobs = [
            j for j in jobs 
            if 'subscription' in j.id.lower() or 'expired' in j.id.lower() or 'pending' in j.id.lower() or 'retry_failed' in j.id.lower()
        ]
        
        if not subscription_jobs:
            print("❌ NENHUM JOB DE ASSINATURA ENCONTRADO!")
            print()
            print("⚠️ Os seguintes jobs devem estar rodando:")
            print("  1. check_expired_subscriptions (a cada 5 minutos)")
            print("  2. check_pending_subscriptions_in_groups (a cada 30 minutos)")
            print("  3. retry_failed_subscription_removals (a cada 30 minutos)")
            print()
            print("Verifique se os jobs foram adicionados em app.py")
            return False
        
        print(f"✅ Encontrados {len(subscription_jobs)} job(s) de assinatura:")
        print()
        
        expected_jobs = {
            'check_expired_subscriptions': '5 minutos',
            'check_pending_subscriptions_in_groups': '30 minutos',
            'retry_failed_subscription_removals': '30 minutos'
        }
        
        found_jobs = set()
        
        for job in subscription_jobs:
            print(f"  ✅ {job.id}")
            # Tentar obter próxima execução (pode variar conforme versão do APScheduler)
            try:
                if hasattr(job, 'next_run_time'):
                    next_run = job.next_run_time
                elif hasattr(job, 'next_run_time'):
                    next_run = job.next_run_time()
                else:
                    next_run = "N/A"
                
                if next_run:
                    print(f"     Próxima execução: {next_run}")
                else:
                    print(f"     Próxima execução: Agendado")
            except Exception:
                print(f"     Próxima execução: Agendado")
            
            print(f"     Trigger: {job.trigger}")
            print()
            found_jobs.add(job.id)
        
        missing_jobs = set(expected_jobs.keys()) - found_jobs
        if missing_jobs:
            print("⚠️ JOBS FALTANDO:")
            for job_id in missing_jobs:
                print(f"  ❌ {job_id} (esperado a cada {expected_jobs[job_id]})")
            print()
        
        print("=" * 70)
        if len(found_jobs) == len(expected_jobs):
            print("✅ TODOS OS JOBS ESTÃO RODANDO CORRETAMENTE!")
            return True
        else:
            print("⚠️ ALGUNS JOBS ESTÃO FALTANDO!")
            print()
            print("💡 Dica: Se o scheduler está em outro processo, verifique os logs:")
            print("   ./scripts/verificar_jobs_logs.sh")
            print("   ou:")
            print("   tail -100 logs/gunicorn.log | grep 'Job.*registrado'")
            return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)


