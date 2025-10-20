"""
Sistema de Monitoramento e Alertas
===================================
Configura healthcheck e alertas automáticos para detectar problemas.

EXECUTAR:
---------
cd /root/grimbots
source venv/bin/activate
python setup_monitoring.py
"""

import os
import sys

HEALTHCHECK_SCRIPT = """#!/usr/bin/env python3
\"\"\"
Healthcheck Automático - Verifica se os bots estão funcionando
Executa a cada 5 minutos via cron
\"\"\"

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Bot
from datetime import datetime, timedelta
import requests
import logging

logging.basicConfig(
    filename='/var/log/grimbots_health.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ✅ WEBHOOK PARA ALERTAS (Configure com seu Discord/Slack/Telegram)
ALERT_WEBHOOK = os.getenv('ALERT_WEBHOOK_URL', '')

def send_alert(message, level='ERROR'):
    \"\"\"Envia alerta via webhook\"\"\"
    if not ALERT_WEBHOOK:
        return
    
    emoji = '🔴' if level == 'ERROR' else '⚠️' if level == 'WARNING' else 'ℹ️'
    
    try:
        # Discord webhook format
        payload = {
            'content': f'{emoji} **[GRIMBOTS {level}]**\\n{message}',
            'username': 'GrimBots Monitor'
        }
        requests.post(ALERT_WEBHOOK, json=payload, timeout=5)
    except:
        pass

def check_bot_health(bot):
    \"\"\"Verifica saúde de um bot específico\"\"\"
    try:
        url = f'https://api.telegram.org/bot{bot.token}/getMe'
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            return True, 'OK'
        else:
            return False, data.get('description', 'Erro desconhecido')
    except Exception as e:
        return False, str(e)

def main():
    with app.app_context():
        active_bots = Bot.query.filter_by(is_active=True, is_running=True).all()
        
        issues_found = []
        
        for bot in active_bots:
            # Verificar se bot responde
            is_healthy, message = check_bot_health(bot)
            
            if not is_healthy:
                issue = f'Bot {bot.name} (@{bot.username}): {message}'
                issues_found.append(issue)
                logger.error(issue)
            
            # Verificar se teve interações recentes (se é um bot com tráfego)
            if bot.total_users > 10:  # Só verificar bots com tráfego
                recent_cutoff = datetime.now() - timedelta(minutes=30)
                
                from models import BotUser
                recent_users = BotUser.query.filter(
                    BotUser.bot_id == bot.id,
                    BotUser.last_interaction >= recent_cutoff
                ).count()
                
                # Se não tem interações há 30min mas tinha tráfego antes, algo pode estar errado
                if recent_users == 0 and bot.total_users > 50:
                    issue = f'Bot {bot.name}: Sem interações há 30min (possível problema)'
                    issues_found.append(issue)
                    logger.warning(issue)
        
        # Enviar alertas se houver problemas
        if issues_found:
            alert_message = '\\n'.join(issues_found)
            send_alert(alert_message, 'ERROR')
            logger.error(f'HEALTHCHECK FAILED: {len(issues_found)} problemas encontrados')
            sys.exit(1)
        else:
            logger.info(f'HEALTHCHECK OK: {len(active_bots)} bots operacionais')
            sys.exit(0)

if __name__ == '__main__':
    main()
"""

CRON_SETUP = """# GrimBots Healthcheck - Executa a cada 5 minutos
*/5 * * * * cd /root/grimbots && /root/grimbots/venv/bin/python /root/grimbots/healthcheck.py
"""

def setup_monitoring():
    """Configura sistema de monitoramento"""
    
    print("=" * 80)
    print("🔧 CONFIGURAÇÃO DE MONITORAMENTO")
    print("=" * 80)
    print()
    
    # 1. Criar script de healthcheck
    print("1. Criando script de healthcheck...")
    with open('healthcheck.py', 'w') as f:
        f.write(HEALTHCHECK_SCRIPT)
    os.chmod('healthcheck.py', 0o755)
    print("   ✅ healthcheck.py criado")
    print()
    
    # 2. Instruções para cron
    print("2. Configurar CRON para executar healthcheck:")
    print()
    print("   Execute no servidor:")
    print("   " + "-" * 70)
    print("   crontab -e")
    print()
    print("   Adicione a linha:")
    print("   " + "-" * 70)
    print(CRON_SETUP)
    print("   " + "-" * 70)
    print()
    
    # 3. Configurar webhook de alertas
    print("3. Configurar webhook de alertas (RECOMENDADO):")
    print()
    print("   A) DISCORD:")
    print("      • Vá em Server Settings → Integrations → Webhooks")
    print("      • Crie webhook para canal #alertas")
    print("      • Copie a URL")
    print()
    print("   B) TELEGRAM:")
    print("      • Fale com @BotFather, crie bot de alertas")
    print("      • Use https://api.telegram.org/bot<TOKEN>/getUpdates")
    print("      • Pegue seu chat_id")
    print("      • Webhook: https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=")
    print()
    print("   C) SLACK:")
    print("      • Crie Incoming Webhook em Slack Apps")
    print()
    print("   Depois, configure no servidor:")
    print("   " + "-" * 70)
    print("   echo 'export ALERT_WEBHOOK_URL=\"sua_webhook_url\"' >> ~/.bashrc")
    print("   source ~/.bashrc")
    print("   " + "-" * 70)
    print()
    
    # 4. Testar healthcheck
    print("4. Testar healthcheck manualmente:")
    print("   " + "-" * 70)
    print("   cd /root/grimbots")
    print("   source venv/bin/activate")
    print("   python healthcheck.py")
    print("   " + "-" * 70)
    print()
    
    # 5. Logs
    print("5. Ver logs de monitoramento:")
    print("   " + "-" * 70)
    print("   tail -f /var/log/grimbots_health.log")
    print("   " + "-" * 70)
    print()
    
    print("=" * 80)
    print("✅ SETUP DE MONITORAMENTO CONCLUÍDO")
    print("=" * 80)
    print()
    print("📌 PRÓXIMOS PASSOS:")
    print("   1. Configure o cron (item 2 acima)")
    print("   2. Configure webhook de alertas (item 3 acima)")
    print("   3. Teste o healthcheck (item 4 acima)")
    print()
    print("⚠️ COM ISSO ATIVO, você receberá alertas automáticos quando:")
    print("   • Bot ficar offline")
    print("   • Bot parar de receber mensagens")
    print("   • Qualquer erro crítico acontecer")
    print()

if __name__ == '__main__':
    setup_monitoring()

