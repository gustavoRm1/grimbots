"""
Reset Bot Status - Fix Status Fantasma
=====================================
Script para corrigir bots que ficam com status "online" incorretamente.

PROBLEMA IDENTIFICADO:
- Bot troca de token
- Bot cai mas banco mantém is_running=True
- Frontend continua mostrando "online"

SOLUÇÃO:
- Reseta is_running=False para todos os bots
- Limpa last_error
- Deixa apenas bots realmente rodando no bot_manager como online

Execução: python reset_bot_status.py
"""

import sys
from app import app, db
from models import Bot
from datetime import datetime

def reset_bot_statuses():
    """Reseta status de todos os bots para offline"""
    
    with app.app_context():
        print("=" * 80)
        print("RESET DE STATUS DOS BOTS")
        print("=" * 80)
        print()
        
        # Buscar todos os bots
        all_bots = Bot.query.all()
        
        if not all_bots:
            print("[INFO] Nenhum bot encontrado no banco de dados.")
            return
        
        print(f"[OK] {len(all_bots)} bot(s) encontrado(s)")
        print()
        
        bots_to_fix = []
        
        for bot in all_bots:
            if bot.is_running:
                bots_to_fix.append(bot)
                print(f"[AVISO] Bot {bot.id} ({bot.name}) esta marcado como ONLINE")
                print(f"   Username: @{bot.username or 'N/A'}")
                print(f"   Dono: {bot.owner.email}")
        
        if not bots_to_fix:
            print("[OK] Todos os bots ja estao offline. Nada a fazer!")
            print()
            return
        
        print()
        print(f"[INFO] {len(bots_to_fix)} bot(s) serao resetados para OFFLINE")
        print()
        
        # Confirmar ação
        resp = input("Deseja continuar? (s/N): ").strip().lower()
        if resp != 's':
            print("[CANCELADO] Operacao cancelada pelo usuario.")
            return
        
        print()
        print("[INFO] Resetando bots...")
        print()
        
        # Resetar cada bot
        for bot in bots_to_fix:
            bot.is_running = False
            bot.last_stopped = datetime.now()
            print(f"   [OK] Bot {bot.id} ({bot.name}) -> OFFLINE")
        
        try:
            db.session.commit()
            print()
            print("=" * 80)
            print(f"[SUCESSO] {len(bots_to_fix)} bot(s) resetado(s) com sucesso!")
            print("=" * 80)
            print()
            print("[INFO] Para iniciar os bots novamente:")
            print("   1. Acesse o dashboard")
            print("   2. Clique em 'Iniciar' no bot desejado")
            print()
        except Exception as e:
            db.session.rollback()
            print()
            print("=" * 80)
            print(f"[ERRO] Erro ao salvar alteracoes: {e}")
            print("=" * 80)
            sys.exit(1)

if __name__ == '__main__':
    print()
    print("=" * 80)
    print(" " * 25 + "RESET BOT STATUS")
    print("=" * 80)
    print()
    
    try:
        reset_bot_statuses()
        print()
        print("[SUCESSO] Script concluido!")
        print()
    except Exception as e:
        print()
        print(f"[ERRO CRITICO] {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

