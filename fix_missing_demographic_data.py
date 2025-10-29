"""Script para atualizar dados demográficos faltantes em Payments
Copiar dados do BotUser para Payment se ainda não existirem"""
from app import app, db
from models import Payment, BotUser

def fix_missing_demographic_data():
    """Atualiza Payments que não têm dados demográficos, copiando do BotUser"""
    with app.app_context():
        # Buscar todos os payments pagos sem dados demográficos
        payments = Payment.query.filter(
            Payment.status == 'paid'
        ).all()
        
        updated_count = 0
        missing_botuser_count = 0
        
        for payment in payments:
            # Verificar se precisa atualizar
            needs_update = (
                not payment.customer_city or
                not payment.device_type or
                (not payment.customer_age and not payment.customer_gender)  # Age e gender podem ser opcionais
            )
            
            if not needs_update:
                continue
            
            # Buscar BotUser correspondente
            bot_user = BotUser.query.filter_by(
                telegram_user_id=payment.customer_user_id,
                bot_id=payment.bot_id
            ).first()
            
            if not bot_user:
                missing_botuser_count += 1
                continue
            
            # Copiar dados do BotUser para Payment
            updated = False
            if not payment.customer_city and bot_user.customer_city:
                payment.customer_city = bot_user.customer_city
                updated = True
            if not payment.customer_state and bot_user.customer_state:
                payment.customer_state = bot_user.customer_state
                updated = True
            if not payment.customer_country and bot_user.customer_country:
                payment.customer_country = bot_user.customer_country
                updated = True
            if not payment.customer_age and bot_user.customer_age:
                payment.customer_age = bot_user.customer_age
                updated = True
            if not payment.customer_gender and bot_user.customer_gender:
                payment.customer_gender = bot_user.customer_gender
                updated = True
            if not payment.device_type and bot_user.device_type:
                payment.device_type = bot_user.device_type
                updated = True
            if not payment.os_type and bot_user.os_type:
                payment.os_type = bot_user.os_type
                updated = True
            if not payment.browser and bot_user.browser:
                payment.browser = bot_user.browser
                updated = True
            
            if updated:
                updated_count += 1
                print(f"✅ Payment {payment.id} atualizado (Cliente: {payment.customer_name})")
        
        if updated_count > 0:
            db.session.commit()
            print(f"\n✅ Total atualizado: {updated_count} payments")
        
        if missing_botuser_count > 0:
            print(f"⚠️ {missing_botuser_count} payments sem BotUser correspondente")
        
        print(f"\n✅ Processo concluído!")

if __name__ == '__main__':
    fix_missing_demographic_data()

