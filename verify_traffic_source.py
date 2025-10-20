"""
VERIFICAÇÃO DE FONTE DE TRÁFEGO
================================
Descobre ONDE está o problema: tráfego pago ou sistema técnico

EXECUTAR:
---------
python verify_traffic_source.py
"""

import sys
from datetime import datetime, timedelta
from app import app, db
from models import RedirectPool, PoolBot, Bot, BotUser
from sqlalchemy import func

def verify_traffic():
    """Verifica se problema é tráfego ou técnico"""
    
    with app.app_context():
        print("=" * 80)
        print("🔍 VERIFICAÇÃO DE FONTE DE TRÁFEGO")
        print("=" * 80)
        print()
        
        # Últimas 24 horas
        cutoff_24h = datetime.now() - timedelta(hours=24)
        cutoff_1h = datetime.now() - timedelta(hours=1)
        
        # 1. ESTATÍSTICAS DOS POOLS
        print("📊 ESTATÍSTICAS DOS POOLS (cliques no redirecionador)")
        print("─" * 80)
        
        pools = RedirectPool.query.all()
        total_redirects = 0
        
        for pool in pools:
            print(f"\n🔗 Pool: {pool.name} (/go/{pool.slug})")
            print(f"   Total de redirects (histórico): {pool.total_redirects}")
            
            # Redirects por bot no pool
            pool_bots = PoolBot.query.filter_by(pool_id=pool.id).all()
            pool_redirects = sum(pb.total_redirects for pb in pool_bots)
            total_redirects += pool_redirects
            
            print(f"   Redirects dos bots: {pool_redirects}")
        
        print(f"\n✅ TOTAL DE REDIRECTS (todos os pools): {total_redirects}")
        print()
        
        # 2. USUÁRIOS QUE CHEGARAM NOS BOTS
        print("─" * 80)
        print("👥 USUÁRIOS QUE CHEGARAM NOS BOTS")
        print("─" * 80)
        
        users_24h = BotUser.query.filter(
            BotUser.first_interaction >= cutoff_24h,
            BotUser.archived == False
        ).count()
        
        users_1h = BotUser.query.filter(
            BotUser.first_interaction >= cutoff_1h,
            BotUser.archived == False
        ).count()
        
        print(f"\n📅 Últimas 24 horas: {users_24h} usuários")
        print(f"⏰ Última 1 hora: {users_1h} usuários")
        print()
        
        # 3. COMPARAÇÃO
        print("─" * 80)
        print("🎯 ANÁLISE COMPARATIVA")
        print("─" * 80)
        print()
        
        print(f"📊 Você disse: ~1000 pessoas entraram no redirecionador")
        print(f"📊 Sistema registrou: {total_redirects} redirects (histórico total)")
        print(f"📊 Bots capturaram: {users_24h} usuários (últimas 24h)")
        print()
        
        # 4. DIAGNÓSTICO
        print("─" * 80)
        print("💡 DIAGNÓSTICO")
        print("─" * 80)
        print()
        
        if total_redirects < 500:
            print("🔴 PROBLEMA: Poucos redirects no sistema!")
            print()
            print("   Causa provável:")
            print("   ❌ Link dos anúncios NÃO está apontando para o pool")
            print("   ❌ Você está usando link direto do bot (não passa pelo pool)")
            print()
            print("   ✅ SOLUÇÃO:")
            print(f"   1. Use este link nos anúncios:")
            for pool in pools:
                print(f"      https://seu-dominio.com/go/{pool.slug}")
                print(f"      OU: https://t.me/seu_bot?start=red1")
            print()
            print("   2. Verificar se domínio está configurado")
            print("   3. Verificar se Facebook/Google não está bloqueando links")
            print()
        
        elif total_redirects >= 800 and users_24h < 200:
            print("🔴 PROBLEMA: Muitos redirects mas poucos usuários!")
            print()
            print("   Causa provável:")
            print("   ❌ Pool está redirecionando mas bots não estão processando")
            print("   ❌ Deep linking quebrado (JÁ CORRIGIDO)")
            print("   ❌ Usuários clicam mas não abrem no Telegram")
            print()
            print("   ✅ SOLUÇÃO:")
            print("   1. Aplicar fix de deep linking: git pull && pm2 restart all")
            print("   2. Verificar logs: pm2 logs | grep 'Novo usuário'")
            print("   3. Teste manual: clicar no link e ver se abre bot")
            print()
        
        elif users_24h > 100 and users_24h < 200:
            print("⚠️  SISTEMA FUNCIONANDO, MAS...")
            print()
            print("   ✅ Bots estão capturando usuários normalmente")
            print("   ⚠️  Mas você esperava mais (1000)")
            print()
            print("   Possíveis causas:")
            print("   1. 📊 Você está medindo IMPRESSÕES (não cliques)")
            print("      → Ver relatório de cliques reais no Facebook/Google")
            print()
            print("   2. 🔗 Múltiplos links diferentes nos anúncios")
            print("      → Apenas um está correto (pool), outros diretos")
            print()
            print("   3. 🚫 Facebook/Google bloqueando links do Telegram")
            print("      → Taxa de bloqueio ~70-80% é NORMAL")
            print("      → Use domínio próprio com redirect")
            print()
            print("   4. 📱 Pessoas clicam mas não abrem Telegram")
            print("      → Taxa de abandono ~50% é normal")
            print()
        
        else:
            print("✅ SISTEMA FUNCIONANDO PERFEITAMENTE!")
            print()
            print(f"   {users_24h} usuários em 24h é um número sólido.")
            print()
            print("   Se você esperava 1000, provavelmente:")
            print("   • Está medindo impressões (não cliques)")
            print("   • Ou usando CTR muito otimista")
            print()
            print("   Cálculo realista:")
            print("   1000 impressões × 3% CTR = 30 cliques")
            print("   30 cliques × 50% abrem Telegram = 15 usuários")
            print()
        
        # 5. VERIFICAR LINKS USADOS
        print("─" * 80)
        print("🔗 LINKS CORRETOS PARA USAR NOS ANÚNCIOS")
        print("─" * 80)
        print()
        
        for pool in pools:
            print(f"Pool: {pool.name}")
            print(f"   Link 1 (se tiver domínio):")
            print(f"      https://seu-dominio.com/go/{pool.slug}")
            print()
            print(f"   Link 2 (direto, com deep linking):")
            # Pegar primeiro bot do pool
            pool_bots = PoolBot.query.filter_by(pool_id=pool.id).limit(1).all()
            if pool_bots:
                bot = pool_bots[0].bot
                print(f"      https://t.me/{bot.username}?start={pool.slug}")
            print()
        
        # 6. TESTE RÁPIDO
        print("─" * 80)
        print("🧪 TESTE RÁPIDO")
        print("─" * 80)
        print()
        print("Execute este comando e CLIQUE no link que está nos anúncios:")
        print()
        print("   pm2 logs | grep 'Novo usuário'")
        print()
        print("Se aparecer 'Novo usuário' em 5 segundos:")
        print("   ✅ Sistema está OK")
        print("   ⚠️  Problema é no TRÁFEGO (não técnico)")
        print()
        print("Se NÃO aparecer:")
        print("   ❌ Link está errado ou quebrado")
        print("   ❌ Verificar qual link está nos anúncios")
        print()

if __name__ == '__main__':
    try:
        verify_traffic()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

