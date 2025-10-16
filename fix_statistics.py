#!/usr/bin/env python3
"""
Script para CORRIGIR estatísticas duplicadas
Recalcula os valores corretos a partir dos pagamentos reais
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Bot, User, Payment
from sqlalchemy import func

def fix_statistics():
    """Recalcula estatísticas corretas"""
    
    with app.app_context():
        print("=" * 80)
        print("CORREÇÃO DE ESTATÍSTICAS")
        print("=" * 80)
        
        # Para cada bot
        bots = Bot.query.all()
        
        for bot in bots:
            # Calcular valores REAIS dos pagamentos
            real_sales = db.session.query(func.count(Payment.id)).filter(
                Payment.bot_id == bot.id,
                Payment.status == 'paid'
            ).scalar() or 0
            
            real_revenue = db.session.query(func.sum(Payment.amount)).filter(
                Payment.bot_id == bot.id,
                Payment.status == 'paid'
            ).scalar() or 0.0
            
            print(f"\n🤖 Bot: {bot.name}")
            print(f"   ANTES:")
            print(f"      Total Sales: {bot.total_sales}")
            print(f"      Total Revenue: R$ {bot.total_revenue:.2f}")
            print(f"   REAL (do banco):")
            print(f"      Total Sales: {real_sales}")
            print(f"      Total Revenue: R$ {real_revenue:.2f}")
            
            # Atualizar com valores corretos
            bot.total_sales = real_sales
            bot.total_revenue = real_revenue
            
            print(f"   ✅ Corrigido!")
        
        # Para cada usuário
        print("\n" + "=" * 80)
        users = User.query.all()
        
        for user in users:
            # Calcular valores REAIS dos pagamentos de TODOS os bots do usuário
            real_sales = db.session.query(func.count(Payment.id)).join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid'
            ).scalar() or 0
            
            real_revenue = db.session.query(func.sum(Payment.amount)).join(Bot).filter(
                Bot.user_id == user.id,
                Payment.status == 'paid'
            ).scalar() or 0.0
            
            print(f"\n👤 User: {user.email}")
            print(f"   ANTES:")
            print(f"      Total Sales: {user.total_sales}")
            print(f"      Total Revenue: R$ {user.total_revenue:.2f}")
            print(f"   REAL (do banco):")
            print(f"      Total Sales: {real_sales}")
            print(f"      Total Revenue: R$ {real_revenue:.2f}")
            
            # Atualizar com valores corretos
            user.total_sales = real_sales
            user.total_revenue = real_revenue
            
            print(f"   ✅ Corrigido!")
        
        # Salvar no banco
        db.session.commit()
        
        print("\n" + "=" * 80)
        print("✅ ESTATÍSTICAS CORRIGIDAS COM SUCESSO!")
        print("=" * 80)
        
        # Mostrar resumo final
        print("\n📊 RESUMO FINAL:")
        for bot in bots:
            print(f"   {bot.name}: {bot.total_sales} vendas, R$ {bot.total_revenue:.2f}")
        
        for user in users:
            print(f"   {user.email}: {user.total_sales} vendas, R$ {user.total_revenue:.2f}")

if __name__ == '__main__':
    fix_statistics()

