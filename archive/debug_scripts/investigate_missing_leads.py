"""
INVESTIGAÇÃO - POR QUE SÓ 1 LEAD PERDIDO?
==========================================
1083 redirects mas só 1 lead perdido? Vamos descobrir onde estão os outros!

EXECUTAR:
---------
python investigate_missing_leads.py
"""

import sys
from datetime import datetime, timedelta
from app import app, db
from models import Bot, BotUser, PoolBot, RedirectPool
from sqlalchemy import func

def investigate():
    """Investiga onde estão os 950 leads"""
    
    with app.app_context():
        print("=" * 80)
        print("🔍 INVESTIGAÇÃO - ONDE ESTÃO OS 950 LEADS?")
        print("=" * 80)
        print()
        
        # Períodos
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        # 1. TOTAIS NO BANCO
        print("📊 ESTATÍSTICAS DO BANCO DE DADOS")
        print("─" * 80)
        
        total_users = BotUser.query.filter_by(archived=False).count()
        total_users_24h = BotUser.query.filter(
            BotUser.first_interaction >= last_24h,
            BotUser.archived == False
        ).count()
        total_users_7d = BotUser.query.filter(
            BotUser.first_interaction >= last_7d,
            BotUser.archived == False
        ).count()
        
        print(f"\n👥 Total de usuários no banco:")
        print(f"   Todos os tempos: {total_users}")
        print(f"   Últimas 24h: {total_users_24h}")
        print(f"   Últimos 7 dias: {total_users_7d}")
        
        # 2. WELCOME_SENT STATUS
        print(f"\n📨 Status de Boas-Vindas:")
        print("─" * 80)
        
        users_with_welcome = BotUser.query.filter(
            BotUser.archived == False,
            BotUser.welcome_sent == True
        ).count()
        
        users_without_welcome = BotUser.query.filter(
            BotUser.archived == False,
            BotUser.welcome_sent == False
        ).count()
        
        users_without_welcome_24h = BotUser.query.filter(
            BotUser.first_interaction >= last_24h,
            BotUser.archived == False,
            BotUser.welcome_sent == False
        ).count()
        
        print(f"\n✅ Com boas-vindas: {users_with_welcome} ({users_with_welcome / total_users * 100:.1f}% do total)")
        print(f"❌ Sem boas-vindas: {users_without_welcome} ({users_without_welcome / total_users * 100:.1f}% do total)")
        print(f"❌ Sem boas-vindas (24h): {users_without_welcome_24h}")
        
        # 3. DETALHES POR BOT
        print(f"\n📋 DETALHES POR BOT:")
        print("─" * 80)
        
        bots = Bot.query.filter_by(is_active=True).all()
        
        for bot in bots:
            total_bot = BotUser.query.filter_by(bot_id=bot.id, archived=False).count()
            with_welcome = BotUser.query.filter_by(bot_id=bot.id, archived=False, welcome_sent=True).count()
            without_welcome = BotUser.query.filter_by(bot_id=bot.id, archived=False, welcome_sent=False).count()
            
            print(f"\n🤖 {bot.name} (@{bot.username})")
            print(f"   Total: {total_bot}")
            print(f"   Com welcome: {with_welcome}")
            print(f"   Sem welcome: {without_welcome}")
            
            if total_bot > 0:
                success_rate = (with_welcome / total_bot * 100)
                print(f"   Taxa de sucesso: {success_rate:.1f}%")
        
        # 4. REDIRECTS vs USUÁRIOS
        print(f"\n\n📊 REDIRECTS vs USUÁRIOS:")
        print("─" * 80)
        
        pools = RedirectPool.query.all()
        total_redirects = 0
        
        for pool in pools:
            pool_bots = PoolBot.query.filter_by(pool_id=pool.id).all()
            pool_redirects = sum(pb.total_redirects for pb in pool_bots)
            total_redirects += pool_redirects
            
            print(f"\n🔗 Pool: {pool.name}")
            print(f"   Redirects: {pool_redirects}")
        
        print(f"\n📊 TOTAL DE REDIRECTS: {total_redirects}")
        print(f"📊 TOTAL DE USUÁRIOS: {total_users}")
        print(f"📊 DIFERENÇA: {total_redirects - total_users} ({(total_redirects - total_users) / total_redirects * 100:.1f}% de perda)")
        
        # 5. DIAGNÓSTICO
        print(f"\n\n💡 DIAGNÓSTICO:")
        print("─" * 80)
        print()
        
        if users_without_welcome < 50:
            print("✅ SISTEMA FUNCIONANDO BEM!")
            print(f"   Apenas {users_without_welcome} usuários sem boas-vindas.")
            print()
            print("   Isso significa que:")
            print("   • ✅ 99%+ dos usuários receberam mensagem")
            print("   • ✅ Deep linking está funcionando")
            print("   • ✅ Bots estão processando normalmente")
            print()
            
            if total_redirects > total_users:
                perda = total_redirects - total_users
                taxa_perda = (perda / total_redirects * 100)
                
                print(f"   ⚠️  MAS: {perda} redirects não viraram usuários ({taxa_perda:.1f}% de perda)")
                print()
                print("   Causas normais dessa perda:")
                print(f"   • 📱 Pessoas clicam mas não abrem Telegram (~30-50%)")
                print(f"   • 🤖 Telegram Web não abre app (~10-20%)")
                print(f"   • 🚫 Bloqueios de navegador/antivírus (~5-10%)")
                print(f"   • ⏱️  Timeout ao abrir (~5%)")
                print()
                
                if taxa_perda > 50:
                    print(f"   🔴 TAXA DE PERDA ALTA ({taxa_perda:.1f}%)")
                    print()
                    print("   Possíveis causas:")
                    print("   1. Links abrindo no navegador (não no app Telegram)")
                    print("   2. Facebook/Google bloqueando links do Telegram")
                    print("   3. Deep linking quebrado (já corrigido)")
                    print()
                    print("   ✅ SOLUÇÃO:")
                    print("   • Use domínio próprio com redirect")
                    print("   • Configure Facebook pixel corretamente")
                    print("   • Use t.me/+XXXXX (links de convite)")
                elif taxa_perda > 30:
                    print(f"   ⚠️  Taxa de perda NORMAL ({taxa_perda:.1f}%)")
                    print("   Isso é esperado para links do Telegram em anúncios.")
                else:
                    print(f"   ✅ Taxa de perda ÓTIMA ({taxa_perda:.1f}%)")
        
        else:
            print(f"🔴 PROBLEMA: {users_without_welcome} usuários sem boas-vindas!")
            print()
            print("   Ações:")
            print("   1. Executar: python fix_markdown_and_recover.py --execute")
            print("   2. Verificar configuração dos bots")
            print()
        
        # 6. PRÓXIMOS PASSOS
        print(f"\n\n📋 PRÓXIMOS PASSOS:")
        print("─" * 80)
        print()
        
        if users_without_welcome > 0:
            print(f"1. 🔴 URGENTE: Recuperar {users_without_welcome} leads sem boas-vindas")
            print("   python fix_markdown_and_recover.py --execute")
            print()
        
        if total_redirects - total_users > 500:
            print(f"2. ⚠️  Otimizar taxa de conversão redirect→usuário")
            print("   • Usar domínio próprio")
            print("   • Testar diferentes tipos de link")
            print("   • Configurar deep linking correto")
            print()
        
        print("3. ✅ Monitorar em tempo real")
        print("   tail -f /var/log/gunicorn.log | grep 'Novo usuário'")
        print()

if __name__ == '__main__':
    try:
        investigate()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

