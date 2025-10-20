"""
RECUPERAÇÃO EMERGENCIAL - TODOS OS LEADS PERDIDOS
==================================================
Envia mensagem de boas-vindas para TODOS os usuários que:
1. Estão no banco mas nunca receberam mensagem (welcome_sent=False)
2. OU foram criados recentemente mas sem interação completa

EXECUTAR IMEDIATAMENTE:
-----------------------
cd /root/grimbots
source venv/bin/activate
python emergency_recover_all_lost_leads.py --execute

ATENÇÃO: Use --dry-run primeiro para ver quantos serão recuperados
"""

import sys
import time
import requests
import logging
import argparse
from datetime import datetime, timedelta
from app import app, db
from models import Bot, BotUser, BotConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_telegram_message(bot_token, chat_id, text, buttons=None):
    """Envia mensagem via API do Telegram"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    if buttons:
        keyboard = {'inline_keyboard': []}
        row = []
        for btn in buttons:
            if 'url' in btn:
                row.append({'text': btn['text'], 'url': btn['url']})
            elif 'callback_data' in btn:
                row.append({'text': btn['text'], 'callback_data': btn['callback_data']})
            
            if len(row) == 2:  # 2 botões por linha
                keyboard['inline_keyboard'].append(row)
                row = []
        
        if row:  # Adicionar última linha
            keyboard['inline_keyboard'].append(row)
        
        payload['reply_markup'] = keyboard
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        result = response.json()
        return result.get('ok', False), result
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return False, {'error': str(e)}

def send_media_message(bot_token, chat_id, media_url, media_type, caption=None, buttons=None):
    """Envia mídia (foto/vídeo) via Telegram"""
    if media_type == 'photo':
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {'chat_id': chat_id, 'photo': media_url}
    else:
        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        payload = {'chat_id': chat_id, 'video': media_url}
    
    if caption:
        payload['caption'] = caption
        payload['parse_mode'] = 'Markdown'
    
    if buttons:
        keyboard = {'inline_keyboard': []}
        row = []
        for btn in buttons:
            if 'url' in btn:
                row.append({'text': btn['text'], 'url': btn['url']})
            elif 'callback_data' in btn:
                row.append({'text': btn['text'], 'callback_data': btn['callback_data']})
            
            if len(row) == 2:
                keyboard['inline_keyboard'].append(row)
                row = []
        
        if row:
            keyboard['inline_keyboard'].append(row)
        
        payload['reply_markup'] = keyboard
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        return result.get('ok', False), result
    except Exception as e:
        logger.error(f"Erro ao enviar mídia: {e}")
        return False, {'error': str(e)}

def recover_lost_leads(hours_back=24, dry_run=True):
    """
    Recupera leads perdidos das últimas X horas
    
    Args:
        hours_back: Quantas horas para trás procurar
        dry_run: Se True, apenas simula (não envia mensagens)
    """
    
    with app.app_context():
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        print("=" * 80)
        print(f"🚨 RECUPERAÇÃO EMERGENCIAL DE LEADS")
        print("=" * 80)
        print(f"\n📅 Período: Últimas {hours_back} horas")
        print(f"⏰ Desde: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if dry_run:
            print(f"⚠️  MODO DRY RUN - Apenas simulação\n")
        else:
            print(f"🔴 MODO EXECUÇÃO - Mensagens serão enviadas!\n")
        
        # Buscar todos os usuários que NUNCA receberam boas-vindas
        # OU foram criados recentemente mas welcome_sent=False
        lost_users = BotUser.query.filter(
            BotUser.welcome_sent == False,
            BotUser.first_interaction >= cutoff_time,
            BotUser.archived == False
        ).order_by(BotUser.first_interaction.desc()).all()
        
        print(f"📊 LEADS PERDIDOS ENCONTRADOS: {len(lost_users)}")
        
        if len(lost_users) == 0:
            print("\n✅ Nenhum lead perdido! Sistema está OK.")
            return
        
        # Agrupar por bot
        leads_by_bot = {}
        for user in lost_users:
            if user.bot_id not in leads_by_bot:
                leads_by_bot[user.bot_id] = []
            leads_by_bot[user.bot_id].append(user)
        
        print(f"\n📋 Distribuição por bot:")
        for bot_id, users in leads_by_bot.items():
            bot = Bot.query.get(bot_id)
            bot_name = bot.name if bot else f"Bot {bot_id}"
            print(f"   • {bot_name}: {len(users)} leads")
        
        print("\n" + "=" * 80)
        print("🚀 INICIANDO RECUPERAÇÃO")
        print("=" * 80 + "\n")
        
        total_sent = 0
        total_failed = 0
        total_blocked = 0
        
        for bot_id, users in leads_by_bot.items():
            bot = Bot.query.get(bot_id)
            
            if not bot:
                print(f"⚠️  Bot {bot_id} não encontrado, pulando...")
                continue
            
            if not bot.is_active:
                print(f"⚠️  Bot {bot.name} está inativo, pulando...")
                continue
            
            config = bot.config
            if not config:
                print(f"⚠️  Bot {bot.name} sem configuração, pulando...")
                continue
            
            print(f"\n{'='*80}")
            print(f"🤖 Bot: {bot.name} (@{bot.username})")
            print(f"   Leads para recuperar: {len(users)}")
            print(f"{'='*80}\n")
            
            # Preparar mensagem e botões
            welcome_msg = config.welcome_message or "Olá! Bem-vindo!"
            welcome_media = config.welcome_media_url
            welcome_media_type = config.welcome_media_type or 'video'
            
            # Botões
            buttons = []
            main_buttons = config.get_main_buttons()
            redirect_buttons = config.get_redirect_buttons()
            
            for idx, btn in enumerate(main_buttons):
                if btn.get('text') and btn.get('price'):
                    buttons.append({
                        'text': btn['text'],
                        'callback_data': f"buy_{idx}"
                    })
            
            for btn in redirect_buttons:
                if btn.get('text') and btn.get('url'):
                    buttons.append({
                        'text': btn['text'],
                        'url': btn['url']
                    })
            
            # Enviar para cada usuário
            for idx, user in enumerate(users, 1):
                print(f"[{idx}/{len(users)}] {user.first_name} (@{user.username or 'sem username'}) | ID: {user.telegram_user_id}")
                
                if dry_run:
                    print(f"         [DRY RUN] Enviaria mensagem de boas-vindas")
                    continue
                
                # Tentar enviar
                try:
                    success = False
                    error_msg = None
                    
                    # Tentar com mídia se configurada
                    if welcome_media and '/c/' not in welcome_media:
                        success, result = send_media_message(
                            bot.token,
                            user.telegram_user_id,
                            welcome_media,
                            welcome_media_type,
                            welcome_msg,
                            buttons
                        )
                        
                        if not success:
                            # Falhou com mídia, tentar só texto
                            success, result = send_telegram_message(
                                bot.token,
                                user.telegram_user_id,
                                welcome_msg,
                                buttons
                            )
                    else:
                        # Sem mídia, direto texto
                        success, result = send_telegram_message(
                            bot.token,
                            user.telegram_user_id,
                            welcome_msg,
                            buttons
                        )
                    
                    if success:
                        # Marcar como enviado no banco
                        user.welcome_sent = True
                        user.welcome_sent_at = datetime.now()
                        db.session.commit()
                        
                        print(f"         ✅ Enviado e marcado como welcome_sent=True")
                        total_sent += 1
                    else:
                        error_desc = result.get('description', 'Erro desconhecido')
                        
                        # Verificar se bloqueou o bot
                        if 'blocked' in error_desc.lower() or 'bot was blocked' in error_desc.lower():
                            print(f"         🚫 Usuário bloqueou o bot")
                            total_blocked += 1
                            # Marcar como enviado para não tentar de novo
                            user.welcome_sent = True
                            user.welcome_sent_at = datetime.now()
                            db.session.commit()
                        else:
                            print(f"         ❌ Falhou: {error_desc}")
                            total_failed += 1
                    
                    # Rate limiting (não bombardear Telegram)
                    time.sleep(0.05)  # 50ms entre mensagens = 20 msg/s (dentro do limite)
                    
                except Exception as e:
                    print(f"         ❌ Erro: {e}")
                    total_failed += 1
                    time.sleep(0.1)
        
        # Relatório final
        print("\n" + "=" * 80)
        print("📊 RELATÓRIO FINAL")
        print("=" * 80)
        print(f"\n✅ Enviadas com sucesso: {total_sent}")
        print(f"❌ Falhadas: {total_failed}")
        print(f"🚫 Bloqueadas: {total_blocked}")
        print(f"📊 Total processado: {len(lost_users)}")
        
        if not dry_run:
            recovery_rate = (total_sent / len(lost_users) * 100) if len(lost_users) > 0 else 0
            print(f"\n💰 Taxa de recuperação: {recovery_rate:.1f}%")
            print(f"💸 Leads recuperados: {total_sent}")
            
            if total_sent > 0:
                print(f"\n🎉 SUCESSO! {total_sent} leads recuperados e de volta ao funil!")
        
        print("\n" + "=" * 80 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Recuperar leads perdidos')
    parser.add_argument('--hours', type=int, default=24, help='Horas para trás (padrão: 24)')
    parser.add_argument('--execute', action='store_true', help='Executar de verdade (padrão: dry-run)')
    args = parser.parse_args()
    
    try:
        recover_lost_leads(
            hours_back=args.hours,
            dry_run=not args.execute
        )
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

