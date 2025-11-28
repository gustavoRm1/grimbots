#!/usr/bin/env python3
"""
🔍 SCRIPT DE DIAGNÓSTICO SIMPLIFICADO: Bot que não responde ao /start

Versão simplificada que não depende do app completo (evita problemas de SocketIO no Windows)
"""

import sys
import os
import requests

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar apenas o necessário (sem app completo)
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Criar app mínimo para acessar banco
app = Flask(__name__)

# Carregar configuração do banco (mesma lógica do app.py)
from dotenv import load_dotenv
load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'sqlite:///grimbots.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Importar modelos (sem dependências do app completo)
from models import Bot, BotConfig

def diagnosticar_bot(bot_id=None, bot_username=None):
    """Diagnostica problema de bot que não responde ao /start"""
    
    with app.app_context():
        # Buscar bot
        if bot_id:
            bot = Bot.query.get(bot_id)
        elif bot_username:
            # Remover @ se presente
            username = bot_username.lstrip('@')
            bot = Bot.query.filter_by(username=username).first()
        else:
            print("❌ ERRO: Forneça bot_id ou bot_username")
            return
        
        if not bot:
            print(f"❌ Bot não encontrado (ID: {bot_id}, Username: {bot_username})")
            return
        
        print("=" * 70)
        print(f"🔍 DIAGNÓSTICO DO BOT: {bot.name} (@{bot.username})")
        print("=" * 70)
        print()
        
        # 1. Verificar status no banco
        print("1️⃣ STATUS NO BANCO DE DADOS:")
        print(f"   • ID: {bot.id}")
        print(f"   • is_running: {'✅ SIM' if bot.is_running else '❌ NÃO'}")
        print(f"   • is_active: {'✅ SIM' if bot.is_active else '❌ NÃO'}")
        print(f"   • last_started: {bot.last_started}")
        print(f"   • last_stopped: {bot.last_stopped}")
        if bot.last_error:
            print(f"   • last_error: {bot.last_error[:200]}")
        print()
        
        # 2. Verificar webhook no Telegram
        print("2️⃣ CONFIGURAÇÃO DO WEBHOOK (Telegram API):")
        try:
            webhook_url = f"https://api.telegram.org/bot{bot.token}/getWebhookInfo"
            response = requests.get(webhook_url, timeout=10)
            if response.status_code == 200:
                webhook_info = response.json()
                if webhook_info.get('ok'):
                    result = webhook_info.get('result', {})
                    webhook_url_telegram = result.get('url', '')
                    pending_update_count = result.get('pending_update_count', 0)
                    last_error_date = result.get('last_error_date')
                    last_error_message = result.get('last_error_message')
                    
                    if webhook_url_telegram:
                        print(f"   • ✅ Webhook configurado: {webhook_url_telegram}")
                    else:
                        print(f"   • ❌ Webhook NÃO configurado (URL vazia)")
                    
                    if pending_update_count > 0:
                        print(f"   • ⚠️ Updates pendentes: {pending_update_count}")
                    
                    if last_error_date:
                        print(f"   • ❌ Último erro do webhook: {last_error_message}")
                        print(f"   • Data do erro: {last_error_date}")
                else:
                    print(f"   • ❌ Erro ao consultar webhook: {webhook_info}")
            else:
                print(f"   • ❌ Erro HTTP ao consultar webhook: {response.status_code}")
        except Exception as e:
            print(f"   • ❌ Erro ao consultar webhook: {e}")
        print()
        
        # 3. Verificar configuração
        print("3️⃣ CONFIGURAÇÃO DO BOT:")
        if bot.config:
            config_dict = bot.config.to_dict()
            welcome_message = config_dict.get('welcome_message', '')
            flow_enabled = config_dict.get('flow_enabled', False)
            
            if welcome_message:
                print(f"   • ✅ Welcome message configurada ({len(welcome_message)} caracteres)")
                print(f"   • Preview: {welcome_message[:100]}...")
            else:
                print(f"   • ⚠️ Welcome message NÃO configurada")
            
            if flow_enabled:
                flow_steps = config_dict.get('flow_steps', [])
                flow_start_step_id = config_dict.get('flow_start_step_id')
                print(f"   • ✅ Fluxo visual ativo ({len(flow_steps)} steps)")
                if flow_start_step_id:
                    print(f"   • Step inicial: {flow_start_step_id}")
                else:
                    print(f"   • ⚠️ Nenhum step marcado como inicial")
            else:
                print(f"   • Fluxo visual desativado (usando welcome_message)")
        else:
            print(f"   • ❌ Configuração não encontrada!")
        print()
        
        # 4. Verificar getMe (validação do token)
        print("4️⃣ VALIDAÇÃO DO TOKEN:")
        try:
            getme_url = f"https://api.telegram.org/bot{bot.token}/getMe"
            response = requests.get(getme_url, timeout=10)
            if response.status_code == 200:
                getme_result = response.json()
                if getme_result.get('ok'):
                    bot_info = getme_result.get('result', {})
                    print(f"   • ✅ Token válido")
                    print(f"   • Bot: {bot_info.get('first_name')} (@{bot_info.get('username')})")
                    print(f"   • Bot ID: {bot_info.get('id')}")
                else:
                    print(f"   • ❌ Token INVÁLIDO: {getme_result}")
            else:
                print(f"   • ❌ Erro HTTP ao validar token: {response.status_code}")
        except Exception as e:
            print(f"   • ❌ Erro ao validar token: {e}")
        print()
        
        # 5. Diagnóstico e recomendações
        print("=" * 70)
        print("💡 DIAGNÓSTICO E RECOMENDAÇÕES:")
        print("=" * 70)
        
        problemas = []
        solucoes = []
        
        # Verificar se está rodando
        if not bot.is_running:
            problemas.append("Bot marcado como não rodando no banco")
            solucoes.append("Execute: python scripts/corrigir_bot_simples.py --username " + bot.username)
        
        # Verificar webhook
        try:
            webhook_url = f"https://api.telegram.org/bot{bot.token}/getWebhookInfo"
            response = requests.get(webhook_url, timeout=10)
            if response.status_code == 200:
                webhook_info = response.json()
                if webhook_info.get('ok'):
                    result = webhook_info.get('result', {})
                    webhook_url_telegram = result.get('url', '')
                    if not webhook_url_telegram:
                        problemas.append("Webhook não configurado no Telegram")
                        solucoes.append("Reinicie o bot - o webhook será configurado automaticamente")
                    elif result.get('last_error_message'):
                        problemas.append(f"Webhook com erro: {result.get('last_error_message')}")
                        solucoes.append("Verifique se o servidor está acessível e reinicie o bot")
        except:
            pass
        
        # Verificar configuração
        if not bot.config or not bot.config.welcome_message:
            if not bot.config:
                problemas.append("Configuração do bot não existe")
                solucoes.append("Crie a configuração do bot pelo painel")
            elif not bot.config.welcome_message:
                try:
                    config_dict = bot.config.to_dict()
                    if not config_dict.get('flow_enabled'):
                        problemas.append("Welcome message não configurada e fluxo desativado")
                        solucoes.append("Configure welcome_message ou ative o fluxo visual no painel")
                except:
                    pass
        
        if problemas:
            print("\n⚠️ PROBLEMAS IDENTIFICADOS:")
            for i, problema in enumerate(problemas, 1):
                print(f"   {i}. {problema}")
            
            print("\n✅ SOLUÇÕES RECOMENDADAS:")
            for i, solucao in enumerate(solucoes, 1):
                print(f"   {i}. {solucao}")
        else:
            print("\n✅ Nenhum problema crítico identificado no banco!")
            print("   O bot pode estar funcionando corretamente.")
            print("   Verifique se está rodando no servidor (active_bots).")
        
        print()
        print("=" * 70)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Diagnostica bot que não responde ao /start')
    parser.add_argument('--bot-id', type=int, help='ID do bot')
    parser.add_argument('--username', type=str, help='Username do bot (com ou sem @)')
    
    args = parser.parse_args()
    
    if not args.bot_id and not args.username:
        print("❌ ERRO: Forneça --bot-id ou --username")
        sys.exit(1)
    
    diagnosticar_bot(bot_id=args.bot_id, bot_username=args.username)


