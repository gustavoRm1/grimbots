#!/usr/bin/env python3
"""
🔥 DIAGNÓSTICO COMPLETO META PURCHASE TRACKING
Execute: python diagnostico_meta_purchase.py
"""

import sys
import os

# Adicionar diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, PoolBot, RedirectPool, Bot
from datetime import datetime, timedelta
from sqlalchemy import func, text

def print_section(title):
    print("\n" + "="*60)
    print(f"📊 {title}")
    print("="*60 + "\n")

def analyze_database():
    """Análise completa do banco de dados"""
    print_section("1. ANÁLISE DO BANCO DE DADOS")
    
    with app.app_context():
        # Estatísticas gerais
        days_ago = datetime.utcnow() - timedelta(days=7)
        
        total_payments = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= days_ago
        ).count()
        
        with_delivery_token = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= days_ago,
            Payment.delivery_token.isnot(None)
        ).count()
        
        with_meta_purchase_sent = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= days_ago,
            Payment.meta_purchase_sent == True
        ).count()
        
        delivery_token_but_no_purchase = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= days_ago,
            Payment.delivery_token.isnot(None),
            db.or_(Payment.meta_purchase_sent == False, Payment.meta_purchase_sent == None)
        ).count()
        
        missing_delivery_token = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= days_ago,
            Payment.delivery_token.is_(None)
        ).count()
        
        print(f"📊 Payments 'paid' dos últimos 7 dias: {total_payments}")
        print(f"  ✅ Com delivery_token: {with_delivery_token}")
        print(f"  ✅ Com meta_purchase_sent: {with_meta_purchase_sent}")
        print(f"  ❌ CRÍTICO: delivery_token mas SEM purchase: {delivery_token_but_no_purchase}")
        print(f"  ⚠️ Sem delivery_token: {missing_delivery_token}")
        
        if total_payments > 0:
            purchase_rate = (with_meta_purchase_sent / total_payments) * 100
            print(f"\n📈 Taxa de envio de Purchase: {purchase_rate:.2f}%")
        
        # Análise por pool
        print_section("2. ANÁLISE POR POOL")
        
        pools = db.session.query(
            RedirectPool.id,
            RedirectPool.name,
            RedirectPool.meta_tracking_enabled,
            RedirectPool.meta_pixel_id,
            RedirectPool.meta_access_token,
            RedirectPool.meta_events_purchase,
            func.count(func.distinct(PoolBot.bot_id)).label('bots_count'),
            func.count(func.distinct(Payment.id)).label('payments_count'),
            func.count(func.distinct(db.case((Payment.meta_purchase_sent == True, Payment.id), else_=None))).label('purchases_sent')
        ).outerjoin(
            PoolBot, PoolBot.pool_id == RedirectPool.id
        ).outerjoin(
            Payment, 
            db.and_(
                Payment.bot_id == PoolBot.bot_id,
                Payment.status == 'paid',
                Payment.created_at >= days_ago
            )
        ).group_by(
            RedirectPool.id,
            RedirectPool.name,
            RedirectPool.meta_tracking_enabled,
            RedirectPool.meta_pixel_id,
            RedirectPool.meta_access_token,
            RedirectPool.meta_events_purchase
        ).all()
        
        print(f"{'Pool ID':<10} {'Nome':<30} {'Tracking':<10} {'Pixel ID':<10} {'Token':<10} {'Purchase':<10} {'Bots':<8} {'Payments':<10} {'Sent':<8}")
        print("-" * 130)
        
        pools_with_issues = []
        for pool in pools:
            has_pixel_id = '✅' if pool.meta_pixel_id else '❌'
            has_token = '✅' if pool.meta_access_token else '❌'
            tracking = '✅' if pool.meta_tracking_enabled else '❌'
            purchase_enabled = '✅' if pool.meta_events_purchase else '❌'
            
            print(f"{pool.id:<10} {pool.name[:28]:<30} {tracking:<10} {has_pixel_id:<10} {has_token:<10} {purchase_enabled:<10} {pool.bots_count:<8} {pool.payments_count:<10} {pool.purchases_sent:<8}")
            
            # Identificar problemas
            if pool.meta_tracking_enabled:
                if not pool.meta_pixel_id or not pool.meta_access_token:
                    pools_with_issues.append({
                        'pool_id': pool.id,
                        'pool_name': pool.name,
                        'issue': 'meta_tracking_enabled mas falta pixel_id ou access_token'
                    })
                elif not pool.meta_events_purchase:
                    pools_with_issues.append({
                        'pool_id': pool.id,
                        'pool_name': pool.name,
                        'issue': 'pixel configurado mas meta_events_purchase = false'
                    })
        
        # Payments problemáticos
        print_section("3. PAYMENTS PROBLEMÁTICOS (TOP 20)")
        
        problematic_payments = Payment.query.join(
            Bot, Bot.id == Payment.bot_id
        ).outerjoin(
            PoolBot, PoolBot.bot_id == Bot.id
        ).outerjoin(
            RedirectPool, RedirectPool.id == PoolBot.pool_id
        ).filter(
            Payment.status == 'paid',
            Payment.delivery_token.isnot(None),
            db.or_(Payment.meta_purchase_sent == False, Payment.meta_purchase_sent == None),
            Payment.created_at >= days_ago
        ).order_by(Payment.created_at.desc()).limit(20).all()
        
        print(f"{'Payment ID':<12} {'Amount':<10} {'Bot ID':<8} {'Pool ID':<10} {'Pool Name':<30} {'Issue':<50}")
        print("-" * 130)
        
        for payment in problematic_payments:
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
            issue = "?"
            
            if not pool_bot:
                issue = "Bot não está em pool"
            else:
                pool = pool_bot.pool
                if not pool.meta_tracking_enabled:
                    issue = "meta_tracking_enabled = false"
                elif not pool.meta_pixel_id or not pool.meta_access_token:
                    issue = "Falta pixel_id ou access_token"
                elif not pool.meta_events_purchase:
                    issue = "meta_events_purchase = false"
                else:
                    issue = "Config OK - verificar logs"
            
            pool_name = pool_bot.pool.name if pool_bot and pool_bot.pool else "N/A"
            pool_id = pool_bot.pool_id if pool_bot else "N/A"
            
            print(f"{payment.id:<12} R${payment.amount:<8.2f} {payment.bot_id:<8} {pool_id!s:<10} {pool_name[:28]:<30} {issue[:48]:<50}")
        
        # Bots sem pool
        print_section("4. BOTS SEM POOL")
        
        bots_without_pool = db.session.query(
            Bot.id,
            Bot.username,
            func.count(Payment.id).label('payments_count')
        ).join(
            Payment, Payment.bot_id == Bot.id
        ).outerjoin(
            PoolBot, PoolBot.bot_id == Bot.id
        ).filter(
            Payment.status == 'paid',
            Payment.created_at >= days_ago,
            PoolBot.id.is_(None)
        ).group_by(Bot.id, Bot.username).all()
        
        if bots_without_pool:
            print(f"{'Bot ID':<10} {'Username':<30} {'Payments':<10}")
            print("-" * 60)
            for bot in bots_without_pool:
                print(f"{bot.id:<10} {bot.username[:28]:<30} {bot.payments_count:<10}")
        else:
            print("✅ Todos os bots estão associados a pools")
        
        # Resumo de pools
        print_section("5. RESUMO DE POOLS")
        
        total_pools = RedirectPool.query.count()
        pools_fully_configured = RedirectPool.query.filter(
            RedirectPool.meta_tracking_enabled == True,
            RedirectPool.meta_pixel_id.isnot(None),
            RedirectPool.meta_access_token.isnot(None),
            RedirectPool.meta_events_purchase == True
        ).count()
        
        pools_with_tracking_enabled = RedirectPool.query.filter(
            RedirectPool.meta_tracking_enabled == True
        ).count()
        
        pools_with_purchase_disabled = RedirectPool.query.filter(
            RedirectPool.meta_tracking_enabled == True,
            RedirectPool.meta_pixel_id.isnot(None),
            RedirectPool.meta_access_token.isnot(None),
            RedirectPool.meta_events_purchase == False
        ).count()
        
        print(f"Total de pools: {total_pools}")
        print(f"Pools totalmente configurados: {pools_fully_configured}")
        print(f"Pools com tracking habilitado: {pools_with_tracking_enabled}")
        print(f"❌ CRÍTICO: Pools com pixel configurado mas purchase DESABILITADO: {pools_with_purchase_disabled}")
        
        if pools_with_issues:
            print("\n⚠️ POOLS COM PROBLEMAS:")
            for issue in pools_with_issues:
                print(f"  - Pool {issue['pool_id']} ({issue['pool_name']}): {issue['issue']}")
        
        # Resumo final
        print_section("6. RESUMO EXECUTIVO")
        
        print(f"📊 Total Payments (7 dias): {total_payments}")
        print(f"  ✅ Com delivery_token: {with_delivery_token}")
        print(f"  ✅ Purchase enviado: {with_meta_purchase_sent}")
        print(f"  ❌ PROBLEMA CRÍTICO: {delivery_token_but_no_purchase} payments têm delivery_token mas NÃO têm purchase enviado")
        print(f"\n📊 Pools:")
        print(f"  ✅ Total: {total_pools}")
        print(f"  ✅ Totalmente configurados: {pools_fully_configured}")
        print(f"  ❌ Com purchase desabilitado: {pools_with_purchase_disabled}")
        
        if delivery_token_but_no_purchase > 0:
            print(f"\n🔍 DIAGNÓSTICO:")
            print(f"  - Se {delivery_token_but_no_purchase} payments têm delivery_token mas não têm purchase,")
            print(f"    isso indica que leads ACESSARAM /delivery mas purchase NÃO foi enviado.")
            print(f"  - Possíveis causas:")
            print(f"    1. pool.meta_events_purchase = false (VERIFICAR ACIMA)")
            print(f"    2. Erro ao enfileirar no Celery (VERIFICAR LOGS)")
            print(f"    3. Validações falhando silenciosamente (VERIFICAR LOGS)")
        
        return {
            'total_payments': total_payments,
            'with_delivery_token': with_delivery_token,
            'with_meta_purchase_sent': with_meta_purchase_sent,
            'delivery_token_but_no_purchase': delivery_token_but_no_purchase,
            'pools_with_purchase_disabled': pools_with_purchase_disabled,
            'problematic_payments_count': len(problematic_payments),
            'bots_without_pool': len(bots_without_pool)
        }

if __name__ == '__main__':
    try:
        results = analyze_database()
        print("\n" + "="*60)
        print("✅ DIAGNÓSTICO COMPLETO")
        print("="*60)
        print("\n📋 Próximos passos:")
        print("1. Analise os dados acima")
        print("2. Verifique logs para payments problemáticos")
        print("3. Corrija configurações dos pools se necessário")
        print("")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

