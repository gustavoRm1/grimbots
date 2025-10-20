"""
Recuperação Emergencial de Leads
=================================
Envia mensagem de boas-vindas para usuários que não receberam durante o crash.

IMPORTANTE: 
- Só funciona para usuários que FORAM salvos no banco (antes do crash)
- Usuários que tentaram /start DURANTE o crash não foram salvos

EXECUTAR:
---------
cd /root/grimbots
source venv/bin/activate
python recover_leads_emergency.py
"""

from app import app, db
from models import Bot, BotUser, BotConfig
from datetime import datetime, timedelta
import sys
import time
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_telegram_message(bot_token, chat_id, text, parse_mode='Markdown'):
    """Envia mensagem via Telegram API"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return None

def send_media_message(bot_token, chat_id, media_url, media_type, caption=None):
    """Envia foto ou vídeo via Telegram API"""
    if media_type == 'photo':
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {'chat_id': chat_id, 'photo': media_url}
    else:
        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        payload = {'chat_id': chat_id, 'video': media_url}
    
    if caption:
        payload['caption'] = caption
        payload['parse_mode'] = 'Markdown'
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        logger.error(f"Erro ao enviar mídia: {e}")
        return None

def recover_leads_for_bot(bot_id, dry_run=True):
    """Recupera leads de um bot específico"""
    
    with app.app_context():
        bot = Bot.query.get(bot_id)
        if not bot:
            print(f"❌ Bot {bot_id} não encontrado")
            return
        
        config = bot.config
        if not config:
            print(f"❌ Bot {bot.name} não tem configuração")
            return
        
        print(f"\n{'='*80}")
        print(f"🤖 Bot: {bot.name} (@{bot.username})")
        print(f"{'='*80}\n")
        
        # Buscar usuários que interagiram recentemente (últimas 2 horas)
        # Mas que não têm vendas associadas (não converteram ainda)
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        potential_lost_leads = BotUser.query.filter(
            BotUser.bot_id == bot_id,
            BotUser.first_interaction >= cutoff_time,
            BotUser.last_interaction >= cutoff_time
        ).all()
        
        print(f"📊 Usuários que interagiram nas últimas 2 horas: {len(potential_lost_leads)}")
        
        if len(potential_lost_leads) == 0:
            print("✅ Nenhum lead para recuperar")
            return
        
        if dry_run:
            print("\n⚠️ MODO DRY RUN - Apenas simulação")
            print("   Execute com --execute para enviar mensagens reais\n")
        
        # Preparar mensagem de recuperação
        welcome_text = config.welcome_message or "Olá! Bem-vindo ao nosso bot 🤖"
        
        sent_count = 0
        failed_count = 0
        
        for user in potential_lost_leads:
            print(f"👤 {user.first_name} (@{user.username or 'sem username'})")
            
            if dry_run:
                print(f"   [DRY RUN] Enviaria mensagem de boas-vindas")
                continue
            
            try:
                # Enviar mídia se configurada
                if config.welcome_media_url:
                    result = send_media_message(
                        bot.token,
                        user.telegram_user_id,
                        config.welcome_media_url,
                        config.welcome_media_type or 'video',
                        welcome_text
                    )
                else:
                    result = send_telegram_message(
                        bot.token,
                        user.telegram_user_id,
                        welcome_text
                    )
                
                if result and result.get('ok'):
                    print(f"   ✅ Mensagem enviada")
                    sent_count += 1
                else:
                    print(f"   ❌ Falha: {result.get('description') if result else 'Sem resposta'}")
                    failed_count += 1
                
                # Rate limiting (não bombardear)
                time.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")
                failed_count += 1
        
        print(f"\n{'='*80}")
        print(f"📊 RESULTADO:")
        print(f"{'='*80}")
        print(f"✅ Enviadas: {sent_count}")
        print(f"❌ Falhadas: {failed_count}")
        print(f"📊 Total: {len(potential_lost_leads)}")
        print()

def main():
    """Função principal"""
    
    import argparse
    parser = argparse.ArgumentParser(description='Recuperar leads perdidos')
    parser.add_argument('--bot-id', type=int, help='ID do bot (ou todos se omitido)')
    parser.add_argument('--execute', action='store_true', help='Executar de verdade (não dry-run)')
    args = parser.parse_args()
    
    with app.app_context():
        print("\n" + "="*80)
        print("🚨 RECUPERAÇÃO EMERGENCIAL DE LEADS")
        print("="*80)
        
        if not args.execute:
            print("\n⚠️ MODO DRY RUN - Use --execute para enviar mensagens reais\n")
        else:
            print("\n🔴 MODO EXECUÇÃO - Mensagens serão enviadas!\n")
            input("Pressione ENTER para continuar ou CTRL+C para cancelar...")
        
        if args.bot_id:
            recover_leads_for_bot(args.bot_id, dry_run=not args.execute)
        else:
            # Todos os bots ativos
            bots = Bot.query.filter_by(is_active=True).all()
            print(f"\n📋 Processando {len(bots)} bots ativos...\n")
            
            for bot in bots:
                recover_leads_for_bot(bot.id, dry_run=not args.execute)
        
        print("\n" + "="*80)
        print("✅ PROCESSO CONCLUÍDO")
        print("="*80 + "\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

