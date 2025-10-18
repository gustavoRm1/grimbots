#!/usr/bin/env python3
"""
Script de teste: Verifica se configurações estão carregando corretamente
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Bot, BotConfig

def test_config_load():
    """Testa carregamento de configurações"""
    print("=" * 60)
    print("🔍 TESTE: Carregamento de Configurações")
    print("=" * 60)
    print()
    
    with app.app_context():
        try:
            # Listar todos os bots
            bots = Bot.query.all()
            
            if not bots:
                print("⚠️  Nenhum bot encontrado no banco!")
                return False
            
            print(f"📊 Total de bots: {len(bots)}")
            print()
            
            for bot in bots:
                print(f"🤖 Bot: {bot.name} (ID: {bot.id})")
                print(f"   Username: @{bot.username}")
                print(f"   Ativo: {bot.is_active}")
                print(f"   Rodando: {bot.is_running}")
                
                if bot.config:
                    print(f"   ✅ Config existe (ID: {bot.config.id})")
                    
                    # Testar to_dict()
                    try:
                        config_dict = bot.config.to_dict()
                        print(f"   ✅ to_dict() funcionou")
                        print(f"      - welcome_message: {len(config_dict.get('welcome_message', ''))} chars")
                        print(f"      - welcome_media_url: {'Sim' if config_dict.get('welcome_media_url') else 'Não'}")
                        print(f"      - welcome_media_type: {config_dict.get('welcome_media_type', 'N/A')}")
                        print(f"      - main_buttons: {len(config_dict.get('main_buttons', []))} botões")
                        print(f"      - redirect_buttons: {len(config_dict.get('redirect_buttons', []))} botões")
                        print(f"      - downsells_enabled: {config_dict.get('downsells_enabled')}")
                        print(f"      - downsells: {len(config_dict.get('downsells', []))} itens")
                        print(f"      - upsells_enabled: {config_dict.get('upsells_enabled')}")
                        print(f"      - upsells: {len(config_dict.get('upsells', []))} itens")
                        
                        # Mostrar primeiro botão se existir
                        if config_dict.get('main_buttons'):
                            btn = config_dict['main_buttons'][0]
                            print(f"      - Botão 1: {btn.get('text')} - R$ {btn.get('price', 0):.2f}")
                            if btn.get('order_bump', {}).get('enabled'):
                                print(f"        → Order Bump ativo: R$ {btn['order_bump'].get('price', 0):.2f}")
                        
                        # Mostrar primeiro downsell se existir
                        if config_dict.get('downsells'):
                            ds = config_dict['downsells'][0]
                            print(f"      - Downsell 1: R$ {ds.get('price', 0):.2f} | Delay: {ds.get('delay_minutes', 0)}min")
                        
                    except Exception as e:
                        print(f"   ❌ Erro ao converter to_dict(): {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"   ❌ Bot NÃO tem config!")
                
                print()
            
            print("=" * 60)
            print("✅ TESTE CONCLUÍDO")
            print("=" * 60)
            return True
            
        except Exception as e:
            print()
            print("=" * 60)
            print("❌ ERRO NO TESTE!")
            print("=" * 60)
            print(f"Erro: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = test_config_load()
    sys.exit(0 if success else 1)

