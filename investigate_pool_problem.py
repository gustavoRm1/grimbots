"""
INVESTIGAÇÃO - POR QUE 83% DE PERDA NO POOL?
=============================================
Analisa o sistema de redirecionamento para encontrar a causa raiz.

1000 pessoas → Redirecionador
170 pessoas → Chegaram nos bots
830 pessoas → PERDIDAS (83%!)

EXECUTAR:
---------
cd /root/grimbots
source venv/bin/activate
python investigate_pool_problem.py
"""

import sys
import requests
from datetime import datetime, timedelta
from app import app, db
from models import RedirectPool, PoolBot, Bot, BotUser

def check_bot_health(bot):
    """Verifica se bot está respondendo"""
    try:
        url = f'https://api.telegram.org/bot{bot.token}/getMe'
        response = requests.get(url, timeout=10)
        data = response.json()
        return data.get('ok', False), data
    except Exception as e:
        return False, {'error': str(e)}

def investigate():
    """Investiga problema do pool"""
    
    with app.app_context():
        print("=" * 80)
        print("🔍 INVESTIGAÇÃO - PERDA DE LEADS NO REDIRECIONAMENTO")
        print("=" * 80)
        print()
        
        # 1. LISTAR TODOS OS POOLS
        pools = RedirectPool.query.all()
        
        if not pools:
            print("❌ PROBLEMA CRÍTICO: Nenhum pool encontrado!")
            print("   Isso explica por que os leads não estão chegando.")
            print()
            return
        
        print(f"📊 Pools encontrados: {len(pools)}")
        print()
        
        for pool in pools:
            print(f"\n{'='*80}")
            print(f"🔗 POOL: {pool.name} (ID: {pool.id})")
            print(f"   Slug: /go/{pool.slug}")
            print(f"   Status: {'✅ Ativo' if pool.is_active else '❌ Inativo'}")
            print(f"   Estratégia: {pool.distribution_strategy}")
            print(f"{'='*80}\n")
            
            # Bots do pool
            pool_bots = PoolBot.query.filter_by(pool_id=pool.id).all()
            
            if not pool_bots:
                print(f"   ❌ PROBLEMA: Pool não tem nenhum bot associado!")
                print(f"      Isso explica por que ninguém está chegando.\n")
                continue
            
            print(f"   Bots no pool: {len(pool_bots)}")
            print()
            
            online_count = 0
            offline_count = 0
            degraded_count = 0
            
            for pb in pool_bots:
                bot = pb.bot
                
                print(f"   🤖 {bot.name} (@{bot.username})")
                print(f"      Bot ID: {bot.id}")
                print(f"      Pool Status: {pb.status}")
                print(f"      Habilitado: {'✅ Sim' if pb.is_enabled else '❌ Não'}")
                print(f"      Peso: {pb.weight}")
                print(f"      Redirects: {pb.total_redirects}")
                print(f"      Falhas consecutivas: {pb.consecutive_failures}")
                
                # Circuit breaker ativo?
                if pb.circuit_breaker_until:
                    if pb.circuit_breaker_until > datetime.now():
                        print(f"      ⚠️  CIRCUIT BREAKER ATIVO até {pb.circuit_breaker_until}")
                        degraded_count += 1
                    else:
                        print(f"      ✅ Circuit breaker expirado (pode usar)")
                
                # Verificar saúde real do bot
                is_healthy, result = check_bot_health(bot)
                
                if is_healthy:
                    print(f"      ✅ Bot está ONLINE (respondendo)")
                    online_count += 1
                else:
                    error = result.get('description', result.get('error', 'Erro desconhecido'))
                    print(f"      ❌ Bot está OFFLINE: {error}")
                    offline_count += 1
                
                # Verificar se bot tem config
                if not bot.config:
                    print(f"      ⚠️  Bot sem configuração (não pode enviar mensagens)")
                
                # Verificar usuários do bot
                user_count = BotUser.query.filter_by(bot_id=bot.id, archived=False).count()
                print(f"      👥 Usuários no bot: {user_count}")
                
                # Usuários recentes (última 1h)
                recent_cutoff = datetime.now() - timedelta(hours=1)
                recent_users = BotUser.query.filter(
                    BotUser.bot_id == bot.id,
                    BotUser.first_interaction >= recent_cutoff
                ).count()
                print(f"      🆕 Novos usuários (última 1h): {recent_users}")
                
                print()
            
            # Resumo do pool
            print(f"   {'─'*70}")
            print(f"   📊 RESUMO DO POOL:")
            print(f"      Online: {online_count}")
            print(f"      Offline: {offline_count}")
            print(f"      Degraded: {degraded_count}")
            print(f"      Total: {len(pool_bots)}")
            
            if online_count == 0:
                print(f"\n   🔴 PROBLEMA CRÍTICO: Nenhum bot online!")
                print(f"      Todos os leads estão sendo perdidos porque não há")
                print(f"      nenhum bot disponível para receber.")
            elif online_count < len(pool_bots) * 0.5:
                print(f"\n   ⚠️  PROBLEMA: Menos de 50% dos bots estão online!")
                print(f"      Taxa de perda alta devido a poucos bots disponíveis.")
            else:
                print(f"\n   ✅ Saúde OK: {online_count}/{len(pool_bots)} bots online")
        
        # ANÁLISE GERAL
        print(f"\n\n{'='*80}")
        print("📊 ANÁLISE GERAL")
        print(f"{'='*80}\n")
        
        # Contar total de usuários únicos nas últimas 24h
        cutoff = datetime.now() - timedelta(hours=24)
        total_users_24h = BotUser.query.filter(
            BotUser.first_interaction >= cutoff,
            BotUser.archived == False
        ).count()
        
        print(f"👥 Usuários capturados (últimas 24h): {total_users_24h}")
        print(f"📊 Usuários esperados no pool: ~1000 (você mencionou)")
        print(f"💔 Taxa de perda: {((1000 - total_users_24h) / 1000 * 100):.1f}%")
        print()
        
        # POSSÍVEIS CAUSAS
        print(f"🔍 POSSÍVEIS CAUSAS DA PERDA:")
        print()
        
        # 1. Bots offline
        all_bots = Bot.query.filter_by(is_active=True).all()
        bots_online = sum(1 for b in all_bots if check_bot_health(b)[0])
        print(f"1. Bots offline:")
        print(f"   Total de bots ativos: {len(all_bots)}")
        print(f"   Bots respondendo: {bots_online}")
        if bots_online < len(all_bots):
            print(f"   ⚠️  {len(all_bots) - bots_online} bots OFFLINE")
        
        # 2. Deep linking quebrado
        users_with_start = BotUser.query.filter(
            BotUser.first_interaction >= cutoff
        ).count()
        users_with_welcome = BotUser.query.filter(
            BotUser.first_interaction >= cutoff,
            BotUser.welcome_sent == True
        ).count()
        
        print(f"\n2. Deep linking / Processamento:")
        print(f"   Usuários criados no banco: {users_with_start}")
        print(f"   Usuários que receberam mensagem: {users_with_welcome}")
        if users_with_start > users_with_welcome:
            print(f"   ⚠️  {users_with_start - users_with_welcome} usuários NÃO receberam mensagem!")
        
        # 3. Limite do Telegram
        print(f"\n3. Limites do Telegram:")
        print(f"   Limite por bot: ~30 msg/segundo")
        print(f"   Se 1000 pessoas em 1 minuto = 16.6/seg por bot")
        print(f"   ✅ Dentro do limite (se distribuído)")
        
        # 4. Circuit breaker
        breakers_active = PoolBot.query.filter(
            PoolBot.circuit_breaker_until > datetime.now()
        ).count()
        
        if breakers_active > 0:
            print(f"\n4. Circuit Breakers:")
            print(f"   ⚠️  {breakers_active} bots com circuit breaker ATIVO")
            print(f"      Esses bots estão temporariamente desabilitados")
        
        print(f"\n\n{'='*80}")
        print("💡 RECOMENDAÇÕES")
        print(f"{'='*80}\n")
        
        if offline_count > 0:
            print("1. 🔴 URGENTE: Verificar por que bots estão offline")
            print("   → Reiniciar: pm2 restart all")
            print("   → Ver logs: pm2 logs")
            print()
        
        if users_with_start > users_with_welcome:
            print("2. 🔴 URGENTE: Recuperar leads que não receberam mensagem")
            print("   → python emergency_recover_all_lost_leads.py --execute")
            print()
        
        if breakers_active > 0:
            print("3. ⚠️  Resetar circuit breakers")
            print("   → Acessar admin panel → Pool management → Reset breakers")
            print()
        
        print("4. ✅ Aplicar fix de deep linking (já feito)")
        print("   → git pull && pm2 restart all")
        print()
        
        print("5. 📊 Monitorar em tempo real")
        print("   → pm2 logs | grep 'Novo usuário'")
        print()

if __name__ == '__main__':
    try:
        investigate()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

