#!/usr/bin/env python3
"""
Cron Script para Processamento de Campanhas Agendadas de Remarketing

Uso:
    python cron_scheduled_remarketing.py --check     # Apenas verifica campanhas pendentes
    python cron_scheduled_remarketing.py --execute   # Verifica e executa campanhas agendadas

Deploy no VPS:
    1. Copie este arquivo para ~/grimbots/cron_scheduled_remarketing.py
    2. Torne executável: chmod +x ~/grimbots/cron_scheduled_remarketing.py
    3. Adicione ao crontab: crontab -e
    4. Adicione a linha: */5 * * * * cd ~/grimbots && python3 cron_scheduled_remarketing.py --execute >> logs/cron_remarketing.log 2>&1
"""

import sys
import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Adicionar o diretório do projeto ao path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from app import app, db
from models import RemarketingCampaign, Bot
from tasks_async import task_queue, task_process_broadcast_campaign
from sqlalchemy import and_


def get_brazil_time():
    """Retorna hora atual no timezone de Brasília"""
    from datetime import datetime
    import pytz
    return datetime.now(pytz.timezone('America/Sao_Paulo'))


def check_scheduled_campaigns():
    """
    Verifica campanhas agendadas que estão prontas para execução
    Retorna: (count, list of campaigns)
    """
    now = get_brazil_time()
    
    with app.app_context():
        # Buscar campanhas agendadas cujo horário chegou
        scheduled = db.session.query(RemarketingCampaign, Bot).join(
            Bot, RemarketingCampaign.bot_id == Bot.id
        ).filter(
            and_(
                RemarketingCampaign.status == 'scheduled',
                RemarketingCampaign.scheduled_at <= now,
                RemarketingCampaign.group_id.isnot(None)  # Apenas campanhas multi-bot
            )
        ).all()
        
        return len(scheduled), scheduled


def execute_scheduled_campaigns(campaigns_data):
    """
    Enfileira campanhas agendadas para execução no worker
    """
    executed = 0
    failed = 0
    
    with app.app_context():
        for campaign, bot in campaigns_data:
            try:
                # Preparar dados da campanha
                campaign_data = {
                    'name': campaign.name,
                    'message': campaign.message,
                    'media_url': campaign.media_url,
                    'media_type': campaign.media_type,
                    'audio_enabled': campaign.audio_enabled,
                    'audio_url': campaign.audio_url,
                    'buttons': campaign.buttons,
                    'days_since_last_contact': campaign.days_since_last_contact,
                    'audience_segment': campaign.target_audience,
                    'user_id': bot.user_id,
                    'exclude_buyers': campaign.exclude_buyers,
                    'group_id': campaign.group_id
                }
                
                # Atualizar status para 'queued' (aguardando processamento)
                campaign.status = 'queued'
                campaign.started_at = get_brazil_time()
                db.session.commit()
                
                # Enfileirar no worker (processamento assíncrono)
                job = task_queue.enqueue(
                    task_process_broadcast_campaign,
                    campaign_data=campaign_data,
                    bot_ids=[campaign.bot_id],  # Campanha individual agendada
                    group_id=campaign.group_id,
                    job_timeout='2h',
                    job_id=f"remarketing_scheduled_{campaign.id}_{int(get_brazil_time().timestamp())}"
                )
                
                print(f"✅ Campanha #{campaign.id} ({bot.name}) enfileirada | Job: {job.get_id()}")
                executed += 1
                
            except Exception as e:
                print(f"❌ Erro ao processar campanha #{campaign.id}: {e}")
                failed += 1
                campaign.status = 'failed'
                db.session.commit()
                continue
    
    return executed, failed


def main():
    parser = argparse.ArgumentParser(
        description='Cron para processamento de campanhas agendadas de remarketing'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Apenas verifica campanhas pendentes sem executar'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Verifica e executa campanhas agendadas'
    )
    
    args = parser.parse_args()
    
    if not args.check and not args.execute:
        parser.print_help()
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Cron Remarketing - {get_brazil_time().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Verificar campanhas
    count, campaigns = check_scheduled_campaigns()
    
    if count == 0:
        print("ℹ️ Nenhuma campanha agendada para execução.")
        sys.exit(0)
    
    print(f"📋 Encontradas {count} campanha(s) agendada(s) para execução:\n")
    
    for campaign, bot in campaigns:
        print(f"  • #{campaign.id} | Bot: {bot.name} | "
              f"Agendada: {campaign.scheduled_at.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print()
    
    # Executar se solicitado
    if args.execute:
        print("🚀 Executando campanhas...\n")
        executed, failed = execute_scheduled_campaigns(campaigns)
        
        print(f"\n{'='*60}")
        print(f"Resumo: {executed} executada(s), {failed} falha(s)")
        print(f"{'='*60}\n")
        
        sys.exit(0 if failed == 0 else 1)
    else:
        print("⏭️  Modo check: Nenhuma ação executada (use --execute para rodar)\n")
        sys.exit(0)


if __name__ == '__main__':
    main()
