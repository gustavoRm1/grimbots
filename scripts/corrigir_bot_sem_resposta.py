#!/usr/bin/env python3
"""
🔧 SCRIPT DE CORREÇÃO: Bot que não responde ao /start

Este script:
1. Diagnostica o problema
2. Tenta reiniciar o bot automaticamente
3. Verifica se o problema foi resolvido
"""

import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import Bot, BotConfig

def corrigir_bot(bot_id=None, bot_username=None):
    """Corrige bot que não responde ao /start"""
    
    with app.app_context():
        # Buscar bot
        if bot_id:
            bot = Bot.query.get(bot_id)
        elif bot_username:
            bot = Bot.query.filter_by(username=bot_username).first()
        else:
            print("❌ ERRO: Forneça bot_id ou bot_username")
            return
        
        if not bot:
            print(f"❌ Bot não encontrado (ID: {bot_id}, Username: {bot_username})")
            return
        
        print("=" * 70)
        print(f"🔧 CORREÇÃO DO BOT: {bot.name} (@{bot.username})")
        print("=" * 70)
        print()
        
        # 1. Verificar se está ativo
        if not bot.is_active:
            print("⚠️ Bot está marcado como inativo (is_active=False)")
            resposta = input("   Deseja ativar o bot? (s/N): ")
            if resposta.lower() == 's':
                bot.is_active = True
                db.session.commit()
                print("   ✅ Bot ativado")
            else:
                print("   ❌ Bot não foi ativado - correção abortada")
                return
        print()
        
        # 2. Parar o bot se estiver rodando incorretamente
        from app import bot_manager
        bot_data = bot_manager.bot_state.get_bot_data(bot.id)
        if bot_data and bot_data.get('status') == 'running':
            print("🛑 Parando bot antes de reiniciar...")
            try:
                bot_manager.stop_bot(bot.id)
                print("   ✅ Bot parado")
            except Exception as e:
                print(f"   ⚠️ Erro ao parar bot: {e}")
        print()
        
        # 3. Atualizar status no banco
        print("📝 Atualizando status no banco...")
        bot.is_running = False
        db.session.commit()
        print("   ✅ Status atualizado")
        print()
        
        # 4. Reiniciar o bot
        print("🚀 Reiniciando bot...")
        try:
            if not bot.config:
                print("   ⚠️ Configuração não encontrada - criando configuração padrão...")
                config = BotConfig(bot_id=bot.id)
                db.session.add(config)
                db.session.commit()
                bot.config = config
            
            config_dict = bot.config.to_dict()
            bot_manager.start_bot(bot.id, bot.token, config_dict)
            
            # Atualizar status
            bot.is_running = True
            from models import get_brazil_time
            bot.last_started = get_brazil_time()
            db.session.commit()
            
            print("   ✅ Bot reiniciado com sucesso!")
            print()
            
            # 5. Verificar status no Redis
            print("2️⃣ STATUS NO REDIS:")
            # Tentar acessar a instância global do BotManager
            try:
                from app import bot_manager
                bot_data = bot_manager.bot_state.get_bot_data(bot.id)
                if bot_data and bot_data.get('status') == 'running':
                    print(f"   • ✅ Bot está ativo no Redis")
                    print(f"   • Status: {bot_data.get('status')}")
                    print(f"   • Started at: {bot_data.get('started_at')}")
                else:
                    print(f"   • ❌ Bot NÃO está ativo no Redis (não está rodando)")
            except Exception as e:
                print(f"   • ⚠️ Não foi possível verificar status no Redis: {e}")
                print(f"   • Isso é normal se o script não estiver rodando no mesmo processo do app")
            print()
            
        except Exception as e:
            print(f"   ❌ Erro ao reiniciar bot: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print()
        print("=" * 70)
        print("✅ CORREÇÃO CONCLUÍDA")
        print("=" * 70)
        print()
        print("📋 PRÓXIMOS PASSOS:")
        print("   1. Aguarde alguns segundos para o bot inicializar completamente")
        print("   2. Teste enviando /start no Telegram")
        print("   3. Verifique os logs se ainda não funcionar:")
        print("      tail -f logs/app.log | grep bot")
        print()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Corrige bot que não responde ao /start')
    parser.add_argument('--bot-id', type=int, help='ID do bot')
    parser.add_argument('--username', type=str, help='Username do bot (sem @)')
    parser.add_argument('--auto', action='store_true', help='Aplicar correção automaticamente (sem perguntas)')
    
    args = parser.parse_args()
    
    if not args.bot_id and not args.username:
        print("❌ ERRO: Forneça --bot-id ou --username")
        sys.exit(1)
    
    corrigir_bot(bot_id=args.bot_id, bot_username=args.username)

