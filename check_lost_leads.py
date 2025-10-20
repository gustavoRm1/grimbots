"""
Análise de Leads Perdidos Durante o Crash
==========================================
Verifica quantos /start aconteceram durante o período do erro
e quantos usuários foram realmente salvos.

EXECUTAR:
---------
cd /root/grimbots
source venv/bin/activate
python check_lost_leads.py
"""

from app import app, db
from models import Bot, BotUser
from datetime import datetime, timedelta
import sys

def analyze_lost_leads():
    """Analisa impacto do crash nos leads"""
    
    with app.app_context():
        print("=" * 80)
        print("🔍 ANÁLISE DE LEADS PERDIDOS")
        print("=" * 80)
        print()
        
        # Período do crash (ajustar conforme logs)
        # Oct 20 14:46:53 = hoje às 14:46
        crash_time = datetime(2025, 10, 20, 14, 46)
        now = datetime.now()
        
        print(f"📅 Período analisado:")
        print(f"   Início do crash: {crash_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Agora: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Duração: {(now - crash_time).total_seconds() / 60:.1f} minutos")
        print()
        
        # Listar todos os bots ativos
        active_bots = Bot.query.filter_by(is_active=True).all()
        
        print(f"🤖 Bots ativos: {len(active_bots)}")
        print()
        
        total_users_during_crash = 0
        
        for bot in active_bots:
            # Usuários que tentaram interagir durante o crash
            # (só conseguimos ver os que FORAM salvos ANTES do crash)
            users_before_crash = BotUser.query.filter(
                BotUser.bot_id == bot.id,
                BotUser.first_interaction < crash_time
            ).count()
            
            users_after_fix = BotUser.query.filter(
                BotUser.bot_id == bot.id,
                BotUser.first_interaction >= crash_time
            ).count()
            
            total_users = BotUser.query.filter_by(bot_id=bot.id).count()
            
            print(f"📊 {bot.name} (@{bot.username})")
            print(f"   Usuários antes do crash: {users_before_crash}")
            print(f"   Usuários após o fix: {users_after_fix}")
            print(f"   Total: {total_users}")
            
            if users_after_fix > 0:
                print(f"   ✅ Bot voltou a funcionar - {users_after_fix} novos usuários")
            
            print()
        
        print("=" * 80)
        print("⚠️ REALIDADE DURA:")
        print("=" * 80)
        print()
        print("❌ Usuários que enviaram /start durante o crash NÃO foram salvos.")
        print("❌ Telegram não guarda fila de mensagens quando bot falha.")
        print("❌ Não há como recuperar automaticamente.")
        print()
        print("=" * 80)
        print("💡 SOLUÇÃO DE RECUPERAÇÃO:")
        print("=" * 80)
        print()
        print("1. TRÁFEGO PAGO:")
        print("   • Aumente budget temporariamente (+30-50%)")
        print("   • Compense os leads perdidos com mais tráfego")
        print()
        print("2. REMARKETING NO FACEBOOK/GOOGLE:")
        print("   • Pessoas que clicaram no link mas não converteram")
        print("   • Use pixel/analytics para criar público")
        print()
        print("3. BROADCAST PARA USUÁRIOS ANTIGOS:")
        print("   • Se tinha usuários de antes do crash")
        print("   • Envie campanha de reengajamento")
        print()
        print("4. POSTS EM GRUPOS/CANAIS:")
        print("   • Se você tem grupos relacionados")
        print("   • Reposte o link do bot")
        print()
        print("5. MONITORE O SISTEMA:")
        print("   • Configure alertas (pm2-slack, discord webhook)")
        print("   • Nunca mais fique tanto tempo offline")
        print()

if __name__ == '__main__':
    try:
        analyze_lost_leads()
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

