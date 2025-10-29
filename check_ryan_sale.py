"""Script para verificar dados demográficos da venda do Ryan"""
from app import app, db
from models import Payment, BotUser

with app.app_context():
    # Buscar venda do Ryan
    payment = Payment.query.filter(
        Payment.customer_name.like('%Ryan%'),
        Payment.status == 'paid'
    ).order_by(Payment.id.desc()).first()
    
    if not payment:
        print("❌ Nenhuma venda encontrada para Ryan")
        exit(1)
    
    print(f"\n✅ VENDA ENCONTRADA:")
    print(f"   ID: {payment.id}")
    print(f"   Payment ID: {payment.payment_id}")
    print(f"   Nome: {payment.customer_name}")
    print(f"   Username: {payment.customer_username}")
    print(f"   Telegram User ID: {payment.customer_user_id}")
    print(f"   Valor: R$ {payment.amount}")
    print(f"   Status: {payment.status}")
    print(f"   Data: {payment.created_at}")
    print(f"   Bot ID: {payment.bot_id}")
    
    print(f"\n📊 DADOS DEMOGRÁFICOS NO PAYMENT:")
    print(f"   City: {payment.customer_city or '❌ NULL'}")
    print(f"   State: {payment.customer_state or '❌ NULL'}")
    print(f"   Country: {payment.customer_country or '❌ NULL'}")
    print(f"   Age: {payment.customer_age or '❌ NULL'}")
    print(f"   Gender: {payment.customer_gender or '❌ NULL'}")
    
    print(f"\n📱 DADOS DE DEVICE NO PAYMENT:")
    print(f"   Device Type: {payment.device_type or '❌ NULL'}")
    print(f"   OS Type: {payment.os_type or '❌ NULL'}")
    print(f"   Browser: {payment.browser or '❌ NULL'}")
    
    # Buscar BotUser correspondente
    bot_user = BotUser.query.filter_by(
        telegram_user_id=payment.customer_user_id,
        bot_id=payment.bot_id
    ).first()
    
    if bot_user:
        print(f"\n👤 BOTUSER ENCONTRADO:")
        print(f"   ID: {bot_user.id}")
        print(f"   Telegram User ID: {bot_user.telegram_user_id}")
        print(f"   First Name: {bot_user.first_name}")
        print(f"   Username: {bot_user.username}")
        
        print(f"\n📊 DADOS DEMOGRÁFICOS NO BOTUSER:")
        print(f"   City: {bot_user.customer_city or '❌ NULL'}")
        print(f"   State: {bot_user.customer_state or '❌ NULL'}")
        print(f"   Country: {bot_user.customer_country or '❌ NULL'}")
        print(f"   Age: {bot_user.customer_age or '❌ NULL'}")
        print(f"   Gender: {bot_user.customer_gender or '❌ NULL'}")
        
        print(f"\n📱 DADOS DE DEVICE NO BOTUSER:")
        print(f"   Device Type: {bot_user.device_type or '❌ NULL'}")
        print(f"   OS Type: {bot_user.os_type or '❌ NULL'}")
        print(f"   Browser: {bot_user.browser or '❌ NULL'}")
        print(f"   IP Address: {bot_user.ip_address or '❌ NULL'}")
        print(f"   User Agent: {bot_user.user_agent[:100] if bot_user.user_agent else '❌ NULL'}...")
        
        # Verificar se precisa copiar
        needs_update = (
            (not payment.customer_city and bot_user.customer_city) or
            (not payment.device_type and bot_user.device_type)
        )
        
        if needs_update:
            print(f"\n⚠️ NECESSITA ATUALIZAÇÃO!")
            print(f"   Copiando dados do BotUser para Payment...")
            
            if not payment.customer_city and bot_user.customer_city:
                payment.customer_city = bot_user.customer_city
                print(f"   ✅ City: {bot_user.customer_city}")
            if not payment.customer_state and bot_user.customer_state:
                payment.customer_state = bot_user.customer_state
                print(f"   ✅ State: {bot_user.customer_state}")
            if not payment.customer_country and bot_user.customer_country:
                payment.customer_country = bot_user.customer_country
                print(f"   ✅ Country: {bot_user.customer_country}")
            if not payment.device_type and bot_user.device_type:
                payment.device_type = bot_user.device_type
                print(f"   ✅ Device Type: {bot_user.device_type}")
            if not payment.os_type and bot_user.os_type:
                payment.os_type = bot_user.os_type
                print(f"   ✅ OS Type: {bot_user.os_type}")
            if not payment.browser and bot_user.browser:
                payment.browser = bot_user.browser
                print(f"   ✅ Browser: {bot_user.browser}")
            
            db.session.commit()
            print(f"\n✅ Payment atualizado com sucesso!")
        else:
            if not bot_user.customer_city and not bot_user.device_type:
                print(f"\n❌ PROBLEMA: BotUser também não tem dados demográficos!")
                print(f"   Isso significa que a geolocalização não foi capturada na criação do BotUser.")
            else:
                print(f"\n✅ Dados já estão corretos ou não há dados disponíveis no BotUser")
    else:
        print(f"\n❌ BOTUSER NÃO ENCONTRADO!")
        print(f"   Telegram User ID: {payment.customer_user_id}")
        print(f"   Bot ID: {payment.bot_id}")
        print(f"\n   Isso pode acontecer se:")
        print(f"   - O usuário não passou pelo fluxo /go/red1 (redirecionador)")
        print(f"   - O BotUser foi deletado ou arquivado")
    
    # Verificar quantas vendas têm dados demográficos
    total_paid = Payment.query.filter_by(bot_id=payment.bot_id, status='paid').count()
    with_city = Payment.query.filter_by(bot_id=payment.bot_id, status='paid').filter(Payment.customer_city.isnot(None)).count()
    with_device = Payment.query.filter_by(bot_id=payment.bot_id, status='paid').filter(Payment.device_type.isnot(None)).count()
    
    print(f"\n📈 ESTATÍSTICAS DO BOT:")
    print(f"   Total de vendas pagas: {total_paid}")
    print(f"   Com cidade: {with_city} ({with_city*100//total_paid if total_paid > 0 else 0}%)")
    print(f"   Com device: {with_device} ({with_device*100//total_paid if total_paid > 0 else 0}%)")

