"""Script para fazer parsing retroativo de dados demográficos dos BotUsers"""
from app import app, db
from models import BotUser
from utils.device_parser import parse_user_agent, parse_ip_to_location

def fix_demographic_parsing():
    """Faz parsing retroativo de device e geolocalização dos BotUsers"""
    with app.app_context():
        # Buscar todos os BotUsers sem device_type ou customer_city
        bot_users = BotUser.query.filter(
            db.or_(
                BotUser.device_type.is_(None),
                BotUser.customer_city.is_(None)
            )
        ).all()
        
        updated_count = 0
        ipv6_skipped = 0
        parse_error_count = 0
        
        print(f"🔍 Encontrados {len(bot_users)} BotUsers para processar...\n")
        
        for bot_user in bot_users:
            updated_device = False
            updated_location = False
            
            # 1. Parsear Device (User-Agent)
            if not bot_user.device_type and bot_user.user_agent:
                try:
                    device_info = parse_user_agent(bot_user.user_agent)
                    if device_info.get('device_type'):
                        bot_user.device_type = device_info.get('device_type')
                        bot_user.os_type = device_info.get('os_type')
                        bot_user.browser = device_info.get('browser')
                        updated_device = True
                except Exception as e:
                    parse_error_count += 1
                    print(f"⚠️ Erro ao parsear device para BotUser {bot_user.id}: {e}")
            
            # 2. Parsear Geolocalização (IP)
            if not bot_user.customer_city and bot_user.ip_address:
                # Verificar se é IPv6 (a API ip-api.com pode não suportar bem IPv6)
                ip = bot_user.ip_address.strip()
                is_ipv6 = ':' in ip
                
                if is_ipv6:
                    # Tentar extrair IPv4 de IPv6 mapeado ou pular
                    if ip.startswith('::ffff:'):
                        # IPv6 mapeado para IPv4
                        ip = ip.replace('::ffff:', '')
                        is_ipv6 = False
                    else:
                        ipv6_skipped += 1
                        print(f"⚠️ BotUser {bot_user.id}: IPv6 puro detectado, pode não ser suportado: {ip[:30]}...")
                        # Tentar mesmo assim, mas pode falhar
                
                # Tentar parsear mesmo com IPv6 (pode falhar, mas tentamos)
                if True:
                    try:
                        location_info = parse_ip_to_location(ip)
                        if location_info.get('city') and location_info.get('city') != 'Unknown':
                            bot_user.customer_city = location_info.get('city')
                            bot_user.customer_state = location_info.get('state')
                            bot_user.customer_country = location_info.get('country', 'BR')
                            updated_location = True
                    except Exception as e:
                        parse_error_count += 1
                        print(f"⚠️ Erro ao parsear geolocalização para BotUser {bot_user.id}: {e}")
            
            if updated_device or updated_location:
                updated_count += 1
                if updated_count % 10 == 0:
                    db.session.commit()
                    print(f"✅ Processados {updated_count} BotUsers...")
        
        # Commit final
        if updated_count > 0:
            db.session.commit()
            print(f"\n✅ Total atualizado: {updated_count} BotUsers")
        
        if ipv6_skipped > 0:
            print(f"⚠️ {ipv6_skipped} BotUsers com IPv6 puro (pode não ser suportado pela API)")
        
        if parse_error_count > 0:
            print(f"⚠️ {parse_error_count} erros durante o parsing")
        
        print(f"\n✅ Processo concluído!")
        
        # Agora copiar dados atualizados para Payments
        print(f"\n🔄 Copiando dados atualizados para Payments...")
        from models import Payment
        
        payments_updated = 0
        payments = Payment.query.filter(
            Payment.status == 'paid'
        ).all()
        
        for payment in payments:
            bot_user = BotUser.query.filter_by(
                telegram_user_id=payment.customer_user_id,
                bot_id=payment.bot_id
            ).first()
            
            if not bot_user:
                continue
            
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
                payments_updated += 1
                if payments_updated % 10 == 0:
                    db.session.commit()
        
        if payments_updated > 0:
            db.session.commit()
            print(f"✅ {payments_updated} Payments atualizados!")
        
        print(f"\n✨ Tudo concluído!")

if __name__ == '__main__':
    fix_demographic_parsing()

