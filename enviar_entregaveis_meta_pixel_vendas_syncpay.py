"""
📦 ENVIAR ENTREGÁVEIS E META PIXEL - VENDAS SYNCPAY ESPECÍFICAS

Este script envia entregáveis e Meta Pixel Purchase Events para vendas
que já foram atualizadas para 'paid' mas não receberam entregável/Meta Pixel.

Vendas específicas:
1. R$ 14,90 - Payment ID: BOT30_1762422998_174b9cda
2. R$ 33,80 - Payment ID: BOT34_1762422931_94f37ccd
3. R$ 33,80 - Payment ID: BOT37_1762422186_5bd30537

Autor: QI 600 + QI 602
"""

from app import app, db
from models import Payment, get_brazil_time
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ PAYMENT IDs DAS VENDAS ATUALIZADAS
PAYMENT_IDS = [
    'BOT30_1762422998_174b9cda',
    'BOT34_1762422931_94f37ccd',
    'BOT37_1762422186_5bd30537'
]

def send_delivery_and_meta_pixel(payment: Payment) -> bool:
    """Envia entregável e Meta Pixel para um payment"""
    try:
        logger.info(f"\n{'='*80}")
        logger.info(f"📦 PROCESSANDO: {payment.payment_id}")
        logger.info(f"   Bot ID: {payment.bot_id}")
        logger.info(f"   Amount: R$ {payment.amount:.2f}")
        logger.info(f"   Status: {payment.status}")
        
        if payment.status != 'paid':
            logger.warning(f"⚠️ Payment não está como 'paid', pulando...")
            return False
        
        # ✅ 1. ENVIAR ENTREGÁVEL
        logger.info(f"📦 Enviando entregável...")
        delivery_sent = False
        
        try:
            from models import Bot
            bot = Bot.query.filter_by(id=payment.bot_id).first()
            if bot and bot.token:
                chat_id = int(payment.customer_user_id) if payment.customer_user_id else None
                
                if chat_id:
                    try:
                        import requests
                        
                        # Verificar se bot tem config e access_link
                        has_access_link = bot.config and bot.config.access_link
                        
                        if has_access_link:
                            access_link = bot.config.access_link
                            delivery_message = f"""✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name or 'Produto'}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

Aproveite! 🚀"""
                        else:
                            delivery_message = f"""✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name or 'Produto'}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

Seu acesso será enviado em breve! 🚀"""
                        
                        # Enviar mensagem via API do Telegram
                        url = f"https://api.telegram.org/bot{bot.token}/sendMessage"
                        payload = {
                            'chat_id': chat_id,
                            'text': delivery_message,
                            'parse_mode': 'HTML'
                        }
                        
                        response = requests.post(url, json=payload, timeout=10)
                        
                        if response.status_code == 200:
                            logger.info(f"✅ Entregável enviado para chat {chat_id}")
                            delivery_sent = True
                        else:
                            logger.warning(f"⚠️ Erro ao enviar entregável: {response.status_code} - {response.text}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao enviar entregável: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                else:
                    logger.warning(f"⚠️ customer_user_id não encontrado: {payment.customer_user_id}")
            else:
                logger.warning(f"⚠️ Bot {payment.bot_id} não encontrado ou sem token")
        except Exception as e:
            logger.error(f"❌ Erro ao enviar entregável: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # ✅ 2. ENVIAR META PIXEL PURCHASE EVENT
        logger.info(f"📊 Enviando Meta Pixel Purchase Event...")
        meta_sent = False
        
        try:
            from models import Bot, RedirectPool, PoolBot
            bot = Bot.query.filter_by(id=payment.bot_id).first()
            
            if bot:
                # Buscar pool que tem este bot
                # Estratégia 1: Buscar via PoolBot
                pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
                if pool_bot:
                    pool = RedirectPool.query.filter_by(
                        id=pool_bot.pool_id,
                        meta_tracking_enabled=True
                    ).first()
                else:
                    # Estratégia 2: Buscar pool do usuário do bot (fallback)
                    pool = RedirectPool.query.filter_by(
                        user_id=bot.user_id,
                        meta_tracking_enabled=True
                    ).first()
                
                if pool and pool.meta_pixel_id and pool.meta_access_token:
                    from utils.meta_pixel import MetaPixelAPI
                    from utils.encryption import decrypt
                    import time
                    
                    # Descriptografar access token
                    try:
                        access_token = decrypt(pool.meta_access_token)
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao descriptografar access_token: {e}")
                        access_token = None
                    
                    if access_token:
                        # Gerar event_id único
                        event_id = f"purchase_{payment.id}_{int(time.time())}"
                        
                        # Buscar tracking data do Redis
                        tracking_data = None
                        
                        if payment.customer_user_id:
                            # Tentar buscar por chat_id no Redis
                            try:
                                import redis
                                redis_client = redis.Redis(
                                    host=os.environ.get('REDIS_HOST', 'localhost'),
                                    port=int(os.environ.get('REDIS_PORT', 6379)),
                                    db=0,
                                    decode_responses=True
                                )
                                
                                chat_key = f"chat:{payment.customer_user_id}"
                                tracking_json = redis_client.get(chat_key)
                                
                                if tracking_json:
                                    tracking_data = json.loads(tracking_json)
                                    logger.info(f"✅ Tracking data recuperado do Redis por chat_id")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao buscar tracking no Redis: {e}")
                        
                        # Se não encontrou, tentar buscar por BotUser
                        if not tracking_data and payment.customer_user_id:
                            try:
                                from models import BotUser
                                bot_user = BotUser.query.filter_by(
                                    bot_id=payment.bot_id,
                                    user_id=int(payment.customer_user_id)
                                ).first()
                                
                                if bot_user and bot_user.external_id:
                                    try:
                                        import redis
                                        redis_client = redis.Redis(
                                            host=os.environ.get('REDIS_HOST', 'localhost'),
                                            port=int(os.environ.get('REDIS_PORT', 6379)),
                                            db=0,
                                            decode_responses=True
                                        )
                                        
                                        fbclid_key = f"tracking:{bot_user.external_id}"
                                        tracking_json = redis_client.get(fbclid_key)
                                        
                                        if tracking_json:
                                            tracking_data = json.loads(tracking_json)
                                            logger.info(f"✅ Tracking data recuperado do Redis por external_id")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Erro ao buscar tracking por external_id: {e}")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao buscar BotUser: {e}")
                        
                        # Extrair dados do tracking
                        fbp = tracking_data.get('fbp') if tracking_data else None
                        fbc = tracking_data.get('fbc') if tracking_data else None
                        ip_address = tracking_data.get('ip') if tracking_data else None
                        user_agent = tracking_data.get('ua') if tracking_data else None
                        external_id = tracking_data.get('fbclid') if tracking_data else None
                        campaign_code = tracking_data.get('campaign_code') if tracking_data else None
                        utm_source = tracking_data.get('utm_source') if tracking_data else None
                        utm_campaign = tracking_data.get('utm_campaign') if tracking_data else None
                        
                        # Enviar Purchase Event
                        result = MetaPixelAPI.send_purchase_event(
                            pixel_id=pool.meta_pixel_id,
                            access_token=access_token,
                            event_id=event_id,
                            value=float(payment.amount),
                            currency='BRL',
                            customer_user_id=str(payment.customer_user_id) if payment.customer_user_id else None,
                            content_id=str(payment.id),
                            content_name=payment.product_name or 'Produto',
                            is_downsell=payment.is_downsell or False,
                            is_upsell=payment.is_upsell or False,
                            is_remarketing=payment.is_remarketing or False,
                            order_bump_value=float(payment.order_bump_value) if payment.order_bump_value else 0,
                            client_ip=ip_address,
                            client_user_agent=user_agent,
                            fbp=fbp,
                            fbc=fbc,
                            utm_source=utm_source,
                            utm_campaign=utm_campaign,
                            campaign_code=campaign_code
                        )
                        
                        if result.get('success'):
                            logger.info(f"✅ Meta Pixel Purchase Event enviado com sucesso")
                            logger.info(f"   Event ID: {event_id}")
                            
                            # Marcar como enviado
                            payment.meta_purchase_sent = True
                            payment.meta_purchase_sent_at = get_brazil_time()
                            payment.meta_event_id = event_id
                            db.session.commit()
                            meta_sent = True
                        else:
                            logger.warning(f"⚠️ Falha ao enviar Meta Pixel: {result.get('error')}")
                    else:
                        logger.warning(f"⚠️ Access token não disponível para pool {pool.id}")
                else:
                    logger.info(f"ℹ️ Meta Pixel não configurado para este bot/pool")
            else:
                logger.warning(f"⚠️ Bot {payment.bot_id} não encontrado")
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar Meta Pixel: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return delivery_sent or meta_sent
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar {payment.payment_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Função principal"""
    with app.app_context():
        print("\n" + "=" * 80)
        print("📦 ENVIAR ENTREGÁVEIS E META PIXEL - VENDAS SYNCPAY")
        print("=" * 80)
        
        print(f"\n📋 Processando {len(PAYMENT_IDS)} vendas...")
        
        total_found = 0
        total_delivery_sent = 0
        total_meta_sent = 0
        total_errors = 0
        
        for i, payment_id in enumerate(PAYMENT_IDS, 1):
            print(f"\n{'='*80}")
            print(f"🔍 Processando venda {i}/{len(PAYMENT_IDS)}")
            print(f"{'='*80}")
            print(f"Payment ID: {payment_id}")
            
            # Buscar payment
            payment = Payment.query.filter_by(payment_id=payment_id).first()
            
            if not payment:
                logger.error(f"❌ Payment não encontrado: {payment_id}")
                total_errors += 1
                continue
            
            total_found += 1
            logger.info(f"✅ Payment encontrado: {payment.payment_id}")
            logger.info(f"   Status: {payment.status}")
            
            if send_delivery_and_meta_pixel(payment):
                if payment.meta_purchase_sent:
                    total_meta_sent += 1
                total_delivery_sent += 1
        
        # Resumo final
        print("\n" + "=" * 80)
        print("📊 RESUMO FINAL")
        print("=" * 80)
        print(f"✅ Total encontrado: {total_found}/{len(PAYMENT_IDS)}")
        print(f"✅ Entregáveis enviados: {total_delivery_sent}")
        print(f"✅ Meta Pixel enviados: {total_meta_sent}")
        print(f"❌ Total com erro: {total_errors}")
        print("=" * 80)

if __name__ == '__main__':
    main()

