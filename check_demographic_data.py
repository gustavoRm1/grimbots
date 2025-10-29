"""Script para verificar dados demográficos de uma venda recente"""
from app import app, db
from models import Payment, BotUser

with app.app_context():
    # Buscar venda mais recente do Ryan
    payment = Payment.query.filter(
        Payment.customer_name.like('%Ryan%'),
        Payment.status == 'paid'
    ).order_by(Payment.id.desc()).first()
    
    if not payment:
        print("❌ Nenhuma venda encontrada para Ryan")
    else:
        print(f"✅ Venda encontrada:")
        print(f"   ID: {payment.id}")
        print(f"   Nome: {payment.customer_name}")
        print(f"   Valor: R$ {payment.amount}")
        print(f"   Status: {payment.status}")
        print(f"   Data: {payment.created_at}")
        print(f"\n📊 DADOS DEMOGRÁFICOS NO PAYMENT:")
        print(f"   City: {payment.customer_city}")
        print(f"   State: {payment.customer_state}")
        print(f"   Country: {payment.customer_country}")
        print(f"   Age: {payment.customer_age}")
        print(f"   Gender: {payment.customer_gender}")
        print(f"\n📱 DADOS DE DEVICE NO PAYMENT:")
        print(f"   Device Type: {payment.device_type}")
        print(f"   OS Type: {payment.os_type}")
        print(f"   Browser: {payment.browser}")
        
        # Buscar BotUser correspondente
        bot_user = BotUser.query.filter_by(
            telegram_user_id=payment.customer_user_id,
            bot_id=payment.bot_id
        ).first()
        
        if bot_user:
            print(f"\n👤 DADOS DEMOGRÁFICOS NO BOTUSER:")
            print(f"   City: {bot_user.customer_city}")
            print(f"   State: {bot_user.customer_state}")
            print(f"   Country: {bot_user.customer_country}")
            print(f"   Age: {bot_user.customer_age}")
            print(f"   Gender: {bot_user.customer_gender}")
            print(f"\n📱 DADOS DE DEVICE NO BOTUSER:")
            print(f"   Device Type: {bot_user.device_type}")
            print(f"   OS Type: {bot_user.os_type}")
            print(f"   Browser: {bot_user.browser}")
            print(f"   IP Address: {bot_user.ip_address}")
            print(f"   User Agent: {bot_user.user_agent[:100] if bot_user.user_agent else None}...")
            
            # Verificar se precisa copiar dados
            if not payment.customer_city and bot_user.customer_city:
                print(f"\n⚠️ PROBLEMA DETECTADO: Payment não tem city mas BotUser tem!")
                print(f"   BotUser.city = {bot_user.customer_city}")
                print(f"   Payment.city = {payment.customer_city}")
        else:
            print(f"\n❌ BotUser não encontrado para telegram_user_id: {payment.customer_user_id}")
            
        # Verificar última venda geral
        last_payment = Payment.query.filter(
            Payment.status == 'paid',
            Payment.bot_id == payment.bot_id
        ).order_by(Payment.id.desc()).first()
        
        print(f"\n📊 ÚLTIMA VENDA GERAL DO BOT:")
        print(f"   ID: {last_payment.id}")
        print(f"   City: {last_payment.customer_city}")
        print(f"   Device: {last_payment.device_type}")

