#!/usr/bin/env python3
"""
Script para verificar se o Celery está funcionando e processando tasks
"""

import os
import sys
import subprocess
import logging

# Adicionar o diretório raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_celery_processes():
    """Verifica se processos Celery estão rodando"""
    logger.info("================================================================================")
    logger.info("🔍 VERIFICANDO PROCESSOS CELERY")
    logger.info("================================================================================")
    
    try:
        # Verificar processos Celery
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        celery_processes = [line for line in result.stdout.split('\n') if 'celery' in line.lower() and 'grep' not in line.lower()]
        
        if celery_processes:
            logger.info(f"✅ {len(celery_processes)} processo(s) Celery encontrado(s):")
            for proc in celery_processes:
                logger.info(f"   {proc}")
        else:
            logger.error("❌ Nenhum processo Celery encontrado!")
            logger.error("   Execute: systemctl start grimbots-celery.service")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar processos Celery: {e}")
        return False

def check_celery_service():
    """Verifica se o serviço Celery está ativo"""
    logger.info("\n================================================================================")
    logger.info("🔍 VERIFICANDO SERVIÇO CELERY")
    logger.info("================================================================================")
    
    try:
        # Verificar status do serviço
        result = subprocess.run(['systemctl', 'is-active', 'grimbots-celery.service'], capture_output=True, text=True)
        is_active = result.stdout.strip() == 'active'
        
        if is_active:
            logger.info("✅ Serviço Celery está ativo")
        else:
            logger.error("❌ Serviço Celery NÃO está ativo!")
            logger.error("   Execute: systemctl start grimbots-celery.service")
            return False
        
        # Verificar status detalhado
        result = subprocess.run(['systemctl', 'status', 'grimbots-celery.service'], capture_output=True, text=True)
        logger.info(f"\n📊 Status do serviço:\n{result.stdout}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar serviço Celery: {e}")
        return False

def check_celery_tasks():
    """Verifica tasks ativas no Celery"""
    logger.info("\n================================================================================")
    logger.info("🔍 VERIFICANDO TASKS ATIVAS NO CELERY")
    logger.info("================================================================================")
    
    try:
        # Verificar tasks ativas
        result = subprocess.run(['celery', '-A', 'celery_app', 'inspect', 'active'], capture_output=True, text=True)
        
        if 'No nodes' in result.stdout:
            logger.error("❌ Nenhum worker Celery encontrado!")
            logger.error("   Execute: systemctl start grimbots-celery.service")
            return False
        
        logger.info(f"📊 Tasks ativas:\n{result.stdout}")
        
        # Verificar tasks reservadas
        result = subprocess.run(['celery', '-A', 'celery_app', 'inspect', 'reserved'], capture_output=True, text=True)
        logger.info(f"📊 Tasks reservadas:\n{result.stdout}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar tasks Celery: {e}")
        logger.error("   Verifique se o Celery está configurado corretamente")
        return False

def check_celery_logs():
    """Verifica logs recentes do Celery"""
    logger.info("\n================================================================================")
    logger.info("🔍 VERIFICANDO LOGS RECENTES DO CELERY")
    logger.info("================================================================================")
    
    try:
        # Verificar logs do journalctl
        result = subprocess.run(['journalctl', '-u', 'grimbots-celery.service', '-n', '50', '--no-pager'], capture_output=True, text=True)
        
        if result.stdout:
            logger.info(f"📊 Últimos 50 logs do Celery:\n{result.stdout}")
        else:
            logger.warning("⚠️ Nenhum log encontrado")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao verificar logs do Celery: {e}")
        return False

def main():
    """Função principal"""
    logger.info("================================================================================")
    logger.info("🚀 VERIFICAÇÃO COMPLETA DO CELERY")
    logger.info("================================================================================")
    
    # Verificar processos
    processes_ok = check_celery_processes()
    
    # Verificar serviço
    service_ok = check_celery_service()
    
    # Verificar tasks (só se serviço estiver OK)
    if service_ok:
        tasks_ok = check_celery_tasks()
    else:
        tasks_ok = False
    
    # Verificar logs
    logs_ok = check_celery_logs()
    
    # Resumo
    logger.info("\n================================================================================")
    logger.info("📊 RESUMO DA VERIFICAÇÃO")
    logger.info("================================================================================")
    logger.info(f"Processos: {'✅' if processes_ok else '❌'}")
    logger.info(f"Serviço: {'✅' if service_ok else '❌'}")
    logger.info(f"Tasks: {'✅' if tasks_ok else '❌'}")
    logger.info(f"Logs: {'✅' if logs_ok else '❌'}")
    
    if processes_ok and service_ok and tasks_ok:
        logger.info("\n✅ Celery está funcionando corretamente!")
    else:
        logger.error("\n❌ Celery NÃO está funcionando corretamente!")
        logger.error("   Execute os comandos abaixo para corrigir:")
        logger.error("   systemctl restart grimbots-celery.service")
        logger.error("   systemctl status grimbots-celery.service")

if __name__ == "__main__":
    main()

