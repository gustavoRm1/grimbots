"""
FIX MARKDOWN + RECUPERAÇÃO COMPLETA
====================================
Corrige problema de Markdown e busca TODOS os leads perdidos (não só 24h)

EXECUTAR:
---------
python fix_markdown_and_recover.py --execute
"""

import sys
import time
import requests
import logging
import argparse
import re
from datetime import datetime, timedelta
from app import app, db
from models import Bot, BotUser, BotConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def escape_markdown_v1(text):
    """Escapa caracteres especiais do Markdown (sem quebrar)"""
    if not text:
        return text
    # Remover formatação problemática
    text = text.replace('*', '')
    text = text.replace('_', '')
    text = text.replace('[', '')
    text = text.replace(']', '')
    text = text.replace('`', '')
    return text

def send_telegram_message_safe(bot_token, chat_id, text, buttons=None):
    """Envia mensagem SEM Markdown (modo seguro)"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': text,
        # NÃO usar parse_mode (enviar texto puro)
    }
    
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
        response = requests.post(url, json=payload, timeout=15)
        result = response.json()
        return result.get('ok', False), result
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return False, {'error': str(e)}

def recover_all_lost_leads(hours_back=None, dry_run=True):
    """
    Recupera TODOS os leads perdidos (não só 24h)
    
    Args:
        hours_back: Se None, pega TODOS. Se número, pega últimas X horas
        dry_run: Se True, apenas simula
    """
    
    with app.app_context():
        print("=" * 80)
        print("🚨 RECUPERAÇÃO COMPLETA DE LEADS")
        print("=" * 80)
        
        if hours_back:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            print(f"\n📅 Período: Últimas {hours_back} horas")
            print(f"⏰ Desde: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            cutoff_time = None
            print(f"\n📅 Período: TODOS OS TEMPOS (histórico completo)")
        
        if dry_run:
            print(f"⚠️  MODO DRY RUN - Apenas simulação\n")
        else:
            print(f"🔴 MODO EXECUÇÃO - Mensagens serão enviadas!\n")
        
        # Buscar usuários que NUNCA receberam boas-vindas
        query = BotUser.query.filter(
            BotUser.welcome_sent == False,
            BotUser.archived == False
        )
        
        if cutoff_time:
            query = query.filter(BotUser.first_interaction >= cutoff_time)
        
        lost_users = query.order_by(BotUser.first_interaction.desc()).all()
        
        print(f"📊 LEADS PERDIDOS ENCONTRADOS: {len(lost_users)}")
        
        if len(lost_users) == 0:
            print("\n✅ Nenhum lead perdido! Sistema está OK.")
            return
        
        # Mostrar amostra
        print(f"\n📋 Primeiros 10 leads perdidos:")
        for i, user in enumerate(lost_users[:10], 1):
            bot = Bot.query.get(user.bot_id)
            bot_name = bot.name if bot else f"Bot {user.bot_id}"
            print(f"   {i}. {user.first_name} (@{user.username or 'sem username'}) - {bot_name} - {user.first_interaction}")
        
        if len(lost_users) > 10:
            print(f"   ... e mais {len(lost_users) - 10} leads")
        
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
            
            # Limpar mensagem (sem Markdown problemático)
            welcome_msg = config.welcome_message or "Olá! Bem-vindo!"
            welcome_msg = escape_markdown_v1(welcome_msg)  # Remover formatação
            
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
                
                # Tentar enviar (modo seguro - sem Markdown)
                try:
                    success, result = send_telegram_message_safe(
                        bot.token,
                        user.telegram_user_id,
                        welcome_msg,
                        buttons
                    )
                    
                    if success:
                        # Marcar como enviado
                        user.welcome_sent = True
                        user.welcome_sent_at = datetime.now()
                        db.session.commit()
                        
                        print(f"         ✅ Enviado e marcado como welcome_sent=True")
                        total_sent += 1
                    else:
                        error_desc = result.get('description', 'Erro desconhecido')
                        
                        # Verificar se bloqueou
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
                    
                    # Rate limiting
                    time.sleep(0.05)
                    
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
        
        if not dry_run and len(lost_users) > 0:
            recovery_rate = (total_sent / len(lost_users) * 100) if len(lost_users) > 0 else 0
            print(f"\n💰 Taxa de recuperação: {recovery_rate:.1f}%")
            print(f"💸 Leads recuperados: {total_sent}")
            
            if total_sent > 0:
                print(f"\n🎉 SUCESSO! {total_sent} leads recuperados e de volta ao funil!")
        
        print("\n" + "=" * 80 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Recuperar TODOS os leads perdidos')
    parser.add_argument('--hours', type=int, default=None, help='Horas para trás (padrão: TODOS)')
    parser.add_argument('--execute', action='store_true', help='Executar de verdade (padrão: dry-run)')
    args = parser.parse_args()
    
    try:
        recover_all_lost_leads(
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

