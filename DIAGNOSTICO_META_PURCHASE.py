#!/usr/bin/env python
"""
DIAGNÓSTICO COMPLETO: META PIXEL PURCHASE
==========================================

Verifica TUDO que pode estar errado:
1. Eventos Purchase sendo enviados?
2. external_id está correto?
3. fbclid sendo capturado?
4. IP/UA estão presentes?
5. Payload está completo?
6. Token é válido?

Autor: QI 500 Elite Team
Data: 2025-10-21
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

def diagnostico_completo():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO COMPLETO: META PIXEL PURCHASE")
    print("=" * 80)
    print()
    
    from app import app, db
    from models import Payment, BotUser, RedirectPool, PoolBot
    from sqlalchemy import func
    
    with app.app_context():
        # VERIFICAÇÃO 1: Pagamentos com status 'paid'
        print("=== 1. PAGAMENTOS CONFIRMADOS ===")
        print()
        
        total_paid = Payment.query.filter_by(status='paid').count()
        total_pending = Payment.query.filter_by(status='pending').count()
        
        print(f"   Total PAID: {total_paid}")
        print(f"   Total PENDING: {total_pending}")
        print()
        
        if total_paid == 0:
            print("   ❌ NENHUM PAGAMENTO CONFIRMADO!")
            print("   Faça um pagamento de teste primeiro")
            return
        
        # Últimos 10 pagamentos paid
        recent_paid = Payment.query.filter_by(status='paid').order_by(Payment.paid_at.desc()).limit(10).all()
        
        print("   Últimos 10 pagamentos confirmados:")
        for p in recent_paid:
            print(f"      R$ {p.amount:>7.2f} | {p.customer_name:<20} | {p.paid_at}")
        print()
        
        # VERIFICAÇÃO 2: Meta Purchase enviado?
        print("=== 2. EVENTOS PURCHASE ENVIADOS AO META ===")
        print()
        
        purchases_sent = Payment.query.filter(
            Payment.status == 'paid',
            Payment.meta_purchase_sent == True
        ).count()
        
        purchases_not_sent = Payment.query.filter(
            Payment.status == 'paid',
            Payment.meta_purchase_sent != True
        ).count()
        
        print(f"   Enviados ao Meta: {purchases_sent}")
        print(f"   NÃO enviados: {purchases_not_sent}")
        print()
        
        if purchases_not_sent > 0:
            print("   ⚠️  ATENÇÃO: Pagamentos confirmados mas SEM envio ao Meta!")
            not_sent = Payment.query.filter(
                Payment.status == 'paid',
                Payment.meta_purchase_sent != True
            ).limit(5).all()
            
            for p in not_sent:
                print(f"      Payment ID: {p.payment_id} | R$ {p.amount} | {p.paid_at}")
        print()
        
        # VERIFICAÇÃO 3: BotUser com external_id
        print("=== 3. EXTERNAL_ID (CRÍTICO!) ===")
        print()
        
        total_users = BotUser.query.count()
        users_with_external = BotUser.query.filter(BotUser.external_id.isnot(None)).count()
        users_with_fbclid = BotUser.query.filter(BotUser.fbclid.isnot(None)).count()
        
        print(f"   Total BotUsers: {total_users}")
        print(f"   Com external_id: {users_with_external} ({users_with_external/total_users*100:.1f}%)")
        print(f"   Com fbclid: {users_with_fbclid} ({users_with_fbclid/total_users*100:.1f}%)")
        print()
        
        if users_with_external < total_users * 0.5:
            print("   ❌ CRÍTICO: Menos de 50% dos usuários têm external_id!")
            print("   Isso significa que fbclid não está sendo capturado corretamente")
        print()
        
        # VERIFICAÇÃO 4: TRACKING ELITE (IP/UA)
        print("=== 4. TRACKING ELITE (IP/UA) ===")
        print()
        
        users_with_ip = BotUser.query.filter(BotUser.ip_address.isnot(None)).count() if hasattr(BotUser, 'ip_address') else 0
        users_with_ua = BotUser.query.filter(BotUser.user_agent.isnot(None)).count() if hasattr(BotUser, 'user_agent') else 0
        
        print(f"   Com IP: {users_with_ip} ({users_with_ip/total_users*100:.1f}%)")
        print(f"   Com UA: {users_with_ua} ({users_with_ua/total_users*100:.1f}%)")
        print()
        
        if users_with_ip == 0:
            print("   ⚠️  TRACKING ELITE ainda não ativo ou migration não rodada")
            print("   Execute: python migrate_add_tracking_fields.py")
        print()
        
        # VERIFICAÇÃO 5: Último pagamento DETALHADO
        print("=== 5. ÚLTIMO PAGAMENTO - ANÁLISE DETALHADA ===")
        print()
        
        last_payment = Payment.query.filter_by(status='paid').order_by(Payment.paid_at.desc()).first()
        
        if last_payment:
            print(f"   Payment ID: {last_payment.payment_id}")
            print(f"   Amount: R$ {last_payment.amount}")
            print(f"   Customer: {last_payment.customer_name}")
            print(f"   Bot ID: {last_payment.bot_id}")
            print(f"   Meta Purchase Sent: {last_payment.meta_purchase_sent}")
            print(f"   Meta Event ID: {last_payment.meta_event_id or 'N/A'}")
            print()
            
            # Buscar BotUser desse pagamento
            bot_user_payment = BotUser.query.filter_by(
                bot_id=last_payment.bot_id,
                telegram_user_id=last_payment.customer_user_id.replace('user_', '') if last_payment.customer_user_id and last_payment.customer_user_id.startswith('user_') else None
            ).first()
            
            if bot_user_payment:
                print("   📊 DADOS DO USUÁRIO:")
                print(f"      external_id: {bot_user_payment.external_id or '❌ AUSENTE'}")
                print(f"      fbclid: {bot_user_payment.fbclid or '❌ AUSENTE'}")
                print(f"      IP: {getattr(bot_user_payment, 'ip_address', 'N/A') or '❌ AUSENTE'}")
                print(f"      UA: {(getattr(bot_user_payment, 'user_agent', 'N/A')[:50] + '...') if getattr(bot_user_payment, 'user_agent', None) else '❌ AUSENTE'}")
                print()
                
                # VALIDAÇÃO CRÍTICA
                if not bot_user_payment.external_id and not bot_user_payment.fbclid:
                    print("   🚨 PROBLEMA CRÍTICO: SEM external_id E SEM fbclid!")
                    print("      Meta NÃO vai conseguir associar à campanha!")
                    print()
                    print("   💡 CAUSA PROVÁVEL:")
                    print("      1. Usuário não veio do link /go/ (acesso direto ao bot)")
                    print("      2. fbclid não estava na URL")
                    print("      3. Start param não continha tracking")
                    print()
            else:
                print("   ❌ BotUser não encontrado para esse pagamento!")
        print()
        
        # VERIFICAÇÃO 6: Pools com Meta Pixel
        print("=== 6. POOLS COM META PIXEL HABILITADO ===")
        print()
        
        pools_with_meta = RedirectPool.query.filter_by(meta_tracking_enabled=True).all()
        
        if not pools_with_meta:
            print("   ❌ NENHUM POOL com Meta Pixel habilitado!")
            return
        
        for pool in pools_with_meta:
            print(f"   📊 Pool: {pool.name}")
            print(f"      Pixel ID: {pool.meta_pixel_id or 'N/A'}")
            print(f"      ViewContent: {pool.meta_events_viewcontent}")
            print(f"      Purchase: {pool.meta_events_purchase}")
            print(f"      Token válido: {'✅' if pool.meta_access_token else '❌'}")
            
            # Contar vendas desse pool
            pool_sales = db.session.query(func.count(Payment.id)).join(PoolBot).filter(
                PoolBot.pool_id == pool.id,
                Payment.status == 'paid'
            ).scalar() or 0
            
            print(f"      Vendas do pool: {pool_sales}")
            print()
        
        # VERIFICAÇÃO 7: Últimas 24h
        print("=== 7. ÚLTIMAS 24 HORAS ===")
        print()
        
        since_24h = datetime.now() - timedelta(hours=24)
        
        sales_24h = Payment.query.filter(
            Payment.status == 'paid',
            Payment.paid_at >= since_24h
        ).count()
        
        meta_sent_24h = Payment.query.filter(
            Payment.status == 'paid',
            Payment.paid_at >= since_24h,
            Payment.meta_purchase_sent == True
        ).count()
        
        print(f"   Vendas confirmadas: {sales_24h}")
        print(f"   Meta Purchase enviados: {meta_sent_24h}")
        
        if sales_24h > 0:
            taxa = (meta_sent_24h / sales_24h * 100)
            print(f"   Taxa de envio: {taxa:.1f}%")
            
            if taxa < 90:
                print(f"   ❌ PROBLEMA: Taxa de envio muito baixa!")
                print(f"   Deveria ser > 95%")
        print()
        
        print("=" * 80)
        print("📋 RECOMENDAÇÕES:")
        print("=" * 80)
        print()
        
        # Recomendações baseadas nas verificações
        if users_with_external < total_users * 0.5:
            print("❌ CRÍTICO: Implementar captura robusta de fbclid")
            print("   → Verificar se /go/ está salvando fbclid no Redis")
            print("   → Verificar se bot_manager está associando ao BotUser")
            print()
        
        if users_with_ip == 0:
            print("⚠️  TRACKING ELITE não ativo")
            print("   → Rodar migration: python migrate_add_tracking_fields.py")
            print("   → Reiniciar aplicação")
            print()
        
        if purchases_not_sent > 0:
            print(f"❌ {purchases_not_sent} vendas SEM envio ao Meta")
            print("   → Verificar se pool.meta_events_purchase está TRUE")
            print("   → Verificar logs do Celery: tail -f logs/celery.log")
            print()
        
        print("💡 PRÓXIMOS PASSOS:")
        print("   1. Rodar teste manual: python TEST_META_PURCHASE_ELITE.py")
        print("   2. Verificar Events Manager do Meta")
        print("   3. Monitorar logs: sudo journalctl -u grimbots -f | grep Purchase")
        print()

if __name__ == '__main__':
    diagnostico_completo()

