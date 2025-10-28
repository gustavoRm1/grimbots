"""
Script para verificar se dados demográficos estão sendo salvos corretamente
"""

from app import app, db
from models import Payment, BotUser, Bot
from datetime import datetime, timedelta

def verificar_dados_demograficos():
    """Verifica se há vendas com dados demográficos"""
    
    with app.app_context():
        print("=" * 80)
        print("🔍 VERIFICAÇÃO DE DADOS DEMOGRÁFICOS")
        print("=" * 80)
        
        # 1. Verificar vendas recentes (últimas 24 horas)
        last_24h = datetime.now() - timedelta(hours=24)
        recent_payments = Payment.query.filter(
            Payment.created_at >= last_24h
        ).order_by(Payment.id.desc()).limit(10).all()
        
        print(f"\n📊 VENDAS RECENTES (Últimas 24h): {len(recent_payments)}")
        
        if not recent_payments:
            print("❌ Nenhuma venda recente encontrada!")
            print("\n💡 SOLUÇÃO:")
            print("1. Crie uma venda de teste via bot")
            print("2. Aguarde alguns minutos")
            print("3. Recarregue a página de analytics")
            return
        
        # 2. Verificar quais têm dados demográficos
        with_data = 0
        without_data = 0
        
        for payment in recent_payments:
            has_demographics = (
                getattr(payment, 'customer_city', None) is not None or
                getattr(payment, 'device_type', None) is not None
            )
            
            if has_demographics:
                with_data += 1
            else:
                without_data += 1
        
        print(f"\n✅ VENDAS COM DADOS DEMOGRÁFICOS: {with_data}")
        print(f"❌ VENDAS SEM DADOS DEMOGRÁFICOS: {without_data}")
        
        if without_data > 0:
            print("\n⚠️ PROBLEMA: Vendas sem dados demográficos!")
            print("\n🔍 VERIFICANDO BOTUSER...")
            
            # Verificar se BotUser tem os dados
            bot = Bot.query.filter_by(id=recent_payments[0].bot_id).first()
            if bot:
                bot_users = BotUser.query.filter_by(
                    bot_id=bot.id
                ).order_by(BotUser.id.desc()).limit(5).all()
                
                for bu in bot_users:
                    print(f"\n📱 User {bu.telegram_user_id}:")
                    print(f"   City: {getattr(bu, 'customer_city', None)}")
                    print(f"   Device: {getattr(bu, 'device_type', None)}")
                    print(f"   IP: {getattr(bu, 'ip_address', None)}")
        
        # 3. Exemplo de venda recente
        if recent_payments:
            p = recent_payments[0]
            print("\n" + "=" * 80)
            print("📋 EXEMPLO DE VENDA RECENTE:")
            print("=" * 80)
            print(f"ID: {p.id}")
            print(f"Customer: {p.customer_name}")
            print(f"Amount: R$ {p.amount}")
            print(f"Created: {p.created_at}")
            print(f"\nDADOS DEMOGRÁFICOS:")
            print(f"  City: {getattr(p, 'customer_city', None)}")
            print(f"  State: {getattr(p, 'customer_state', None)}")
            print(f"  Country: {getattr(p, 'customer_country', None)}")
            print(f"  Device: {getattr(p, 'device_type', None)}")
            print(f"  OS: {getattr(p, 'os_type', None)}")
            print(f"  Browser: {getattr(p, 'browser', None)}")
        
        print("\n" + "=" * 80)
        print("✅ VERIFICAÇÃO CONCLUÍDA")
        print("=" * 80)

if __name__ == '__main__':
    verificar_dados_demograficos()

