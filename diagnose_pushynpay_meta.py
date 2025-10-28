"""
Diagnóstico: Por que Meta Pixel não está sendo enviado para PushynPay?
Autor: Senior QI 500
"""

from app import app, db
from models import Payment, Bot, PoolBot, RedirectPool
from datetime import datetime, timedelta

with app.app_context():
    # 1. Buscar últimas vendas PushynPay
    print("=" * 80)
    print("🔍 DIAGNÓSTICO META PIXEL - PUSHYNPAY")
    print("=" * 80)
    
    recent_payments = Payment.query.filter(
        Payment.gateway_type == 'pushynpay',
        Payment.status == 'paid',
        Payment.created_at >= datetime.now() - timedelta(days=7)
    ).order_by(Payment.id.desc()).limit(10).all()
    
    print(f"\n📊 TOTAL DE VENDAS PUSHYNPAY (últimos 7 dias): {len(recent_payments)}")
    
    if not recent_payments:
        print("\n❌ NENHUMA VENDA ENCONTRADA!")
        print("   Possíveis causas:")
        print("   1. Não há vendas do PushynPay no período")
        print("   2. Gateway não está sendo usado")
        print("   3. Vendas não estão sendo marcadas como 'paid'")
        exit(0)
    
    print("\n📋 ÚLTIMAS 10 VENDAS:")
    for p in recent_payments:
        print(f"\n{'=' * 80}")
        print(f"Payment ID: {p.payment_id}")
        print(f"Bot ID: {p.bot_id}")
        print(f"Status: {p.status}")
        print(f"Amount: R$ {p.amount:.2f}")
        print(f"Meta Purchase Sent: {p.meta_purchase_sent}")
        print(f"Meta Event ID: {p.meta_event_id}")
        print(f"Created At: {p.created_at}")
        
        # Verificar bot
        bot = Bot.query.get(p.bot_id)
        if bot:
            print(f"Bot: {bot.name}")
            
            # Verificar pool associado
            pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
            if pool_bot:
                pool = pool_bot.pool
                print(f"\n📊 POOL ASSOCIADO:")
                print(f"   Pool ID: {pool.id}")
                print(f"   Pool Name: {pool.name}")
                print(f"   Meta Tracking Enabled: {pool.meta_tracking_enabled}")
                print(f"   Meta Pixel ID: {pool.meta_pixel_id is not None}")
                print(f"   Meta Access Token: {pool.meta_access_token is not None}")
                print(f"   Meta Events Purchase: {pool.meta_events_purchase}")
                
                if not pool.meta_tracking_enabled:
                    print(f"\n⚠️ PROBLEMA: Meta tracking está DESABILITADO!")
                if not pool.meta_pixel_id:
                    print(f"\n⚠️ PROBLEMA: Meta Pixel ID não configurado!")
                if not pool.meta_access_token:
                    print(f"\n⚠️ PROBLEMA: Access Token não configurado!")
                if not pool.meta_events_purchase:
                    print(f"\n⚠️ PROBLEMA: Evento Purchase está DESABILITADO!")
            else:
                print(f"\n❌ PROBLEMA CRÍTICO: Bot não está em NENHUM POOL!")
                print(f"   Meta Pixel busca configuração do POOL, não do bot!")
                print(f"   Solução: Adicione este bot a um pool em Redirecionadores")
        else:
            print(f"\n❌ Bot não encontrado!")
    
    print("\n" + "=" * 80)
    print("✅ RESUMO:")
    print("=" * 80)
    
    paid_count = len(recent_payments)
    sent_count = sum(1 for p in recent_payments if p.meta_purchase_sent)
    
    print(f"Total de vendas: {paid_count}")
    print(f"Meta Pixel enviado: {sent_count}")
    print(f"Meta Pixel NÃO enviado: {paid_count - sent_count}")
    
    if sent_count == 0:
        print("\n⚠️ PROBLEMA ENCONTRADO!")
        print("   Nenhum Meta Pixel foi enviado!")
        print("\n🔍 Possíveis causas:")
        print("   1. Webhook não está sendo recebido")
        print("   2. Pool não tem Meta Pixel configurado")
        print("   3. Meta tracking está desabilitado")
        print("   4. Evento Purchase está desabilitado")
    
    print("\n" + "=" * 80)
    print("💡 PRÓXIMOS PASSOS:")
    print("=" * 80)
    print("1. Verifique se o webhook do PushynPay está configurado corretamente")
    print("2. Configure o Meta Pixel no Pool associado ao bot")
    print("3. Habilite Meta Tracking no Pool")
    print("4. Habilite Evento Purchase no Pool")

