#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 REENVIAR VENDAS DE HOJE PARA META COM GRIM CORRETO

Este script re-envia eventos Purchase para vendas pagas HOJE que já foram enviadas,
mas com o external_id CORRETO (grim) para que apareçam no Gerenciador da Meta.

USO:
    python3 reenviar_vendas_hoje_meta_grim.py
"""

import os
import sys
from datetime import datetime, timedelta
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, BotUser, PoolBot, RedirectPool

def reenviar_vendas_hoje_com_grim():
    """
    Re-envia eventos Purchase para vendas de HOJE com external_id correto (grim)
    """
    with app.app_context():
        print("=" * 80)
        print("🔧 REENVIAR VENDAS DE HOJE PARA META COM GRIM CORRETO")
        print("=" * 80)
        
        # Buscar vendas pagas de HOJE (desde 00:00:00)
        hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        vendas_hoje = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= hoje_inicio,
            Payment.meta_purchase_sent == True  # Já foram enviadas
        ).order_by(Payment.created_at.desc()).all()
        
        print(f"\n📊 Vendas pagas de HOJE (desde {hoje_inicio.strftime('%Y-%m-%d %H:%M:%S')}): {len(vendas_hoje)}")
        
        if not vendas_hoje:
            print("✅ Nenhuma venda encontrada para reenvio")
            return
        
        reenviadas = 0
        erro = 0
        sem_grim = 0
        
        for payment in vendas_hoje:
            try:
                # Buscar BotUser associado
                telegram_user_id = None
                if payment.customer_user_id:
                    if payment.customer_user_id.startswith('user_'):
                        telegram_user_id = int(payment.customer_user_id.replace('user_', ''))
                    elif payment.customer_user_id.isdigit():
                        telegram_user_id = int(payment.customer_user_id)
                
                bot_user = None
                if telegram_user_id:
                    bot_user = BotUser.query.filter_by(
                        bot_id=payment.bot_id,
                        telegram_user_id=telegram_user_id
                    ).first()
                
                # ✅ Buscar pool primeiro (para usar como fallback)
                pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
                if not pool_bot:
                    logger.error(f"❌ Payment {payment.payment_id}: bot não está em nenhum pool")
                    erro += 1
                    continue
                
                pool = pool_bot.pool
                
                # Verificar se BotUser tem external_id válido (grim)
                external_id_correto = None
                origem_grim = None
                
                if bot_user and bot_user.external_id:
                    # Verificar se é grim (não é fbclid e não é sintético)
                    external_id_value = bot_user.external_id
                    
                    # ✅ GRIM: Geralmente é curto (ex: "testecamu01") e não parece ser fbclid
                    # fbclid geralmente tem formato: IwARxxxxx... ou é muito longo (> 50 chars)
                    # ID sintético geralmente começa com "click_" ou "purchase_"
                    is_fbclid = external_id_value.startswith('IwAR') or len(external_id_value) > 50
                    is_sintetico = external_id_value.startswith('click_') or external_id_value.startswith('purchase_')
                    
                    if not is_fbclid and not is_sintetico:
                        external_id_correto = external_id_value
                        origem_grim = 'BotUser.external_id'
                        logger.info(f"✅ Payment {payment.payment_id}: grim encontrado no BotUser: {external_id_correto}")
                    else:
                        logger.warning(f"⚠️ Payment {payment.payment_id}: external_id é fbclid ou sintético: {external_id_value[:30]}...")
                
                # ✅ FALLBACK: Usar grim do pool se não encontrou no BotUser
                if not external_id_correto and pool.meta_cloaker_param_value:
                    external_id_correto = pool.meta_cloaker_param_value
                    origem_grim = 'Pool.meta_cloaker_param_value'
                    logger.info(f"✅ Payment {payment.payment_id}: usando grim do pool (fallback): {external_id_correto}")
                
                if not external_id_correto:
                    sem_grim += 1
                    logger.warning(f"⚠️ Payment {payment.payment_id}: não encontrou grim válido - pulando")
                    print(f"   ⚠️ Payment {payment.payment_id}: sem grim válido (BotUser e Pool sem grim)")
                    continue
                
                # ✅ RE-ENVIAR Purchase com external_id correto
                
                if not pool.meta_tracking_enabled or not pool.meta_pixel_id or not pool.meta_access_token:
                    logger.error(f"❌ Payment {payment.payment_id}: pool sem Meta Pixel configurado")
                    erro += 1
                    continue
                
                if not pool.meta_events_purchase:
                    logger.error(f"❌ Payment {payment.payment_id}: evento Purchase desabilitado no pool")
                    erro += 1
                    continue
                
                # Importar função de envio
                from celery_app import send_meta_event
                from utils.encryption import decrypt
                from utils.meta_pixel import MetaPixelAPI
                import time
                import uuid
                
                # Gerar NOVO event_id único (para evitar deduplicação)
                timestamp_ms = int(time.time() * 1000)
                unique_suffix = uuid.uuid4().hex[:8]
                event_id = f"purchase_re_{payment.payment_id}_{timestamp_ms}_{unique_suffix}"
                
                # Descriptografar access token
                try:
                    access_token = decrypt(pool.meta_access_token)
                except Exception as e:
                    logger.error(f"❌ Erro ao descriptografar access_token: {e}")
                    erro += 1
                    continue
                
                # Preparar event_data com external_id CORRETO
                event_data = {
                    'event_name': 'Purchase',
                    'event_time': int(time.time()),
                    'event_id': event_id,
                    'action_source': 'website',
                    'user_data': {
                        'external_id': external_id_correto,  # ✅ GRIM CORRETO!
                        'client_ip_address': bot_user.ip_address if bot_user else None,
                        'client_user_agent': bot_user.user_agent if bot_user else None
                    },
                    'custom_data': {
                        'currency': 'BRL',
                        'value': float(payment.amount),
                        'content_id': str(pool.id),
                        'content_name': payment.product_name or payment.bot.name,
                        'content_type': 'product',
                        'payment_id': payment.payment_id,
                        'is_downsell': payment.is_downsell or False,
                        'is_upsell': payment.is_upsell or False,
                        'is_remarketing': payment.is_remarketing or False,
                        'utm_source': payment.utm_source,
                        'utm_campaign': payment.utm_campaign,
                        'campaign_code': payment.campaign_code
                    }
                }
                
                # ✅ ENFILEIRAR COM PRIORIDADE ALTA
                try:
                    task = send_meta_event.apply_async(
                        args=[
                            pool.meta_pixel_id,
                            access_token,
                            event_data,
                            pool.meta_test_event_code
                        ],
                        priority=1
                    )
                    
                    logger.info(f"📤 Purchase RE-ENVIADO: R$ {payment.amount} | " +
                               f"Payment: {payment.payment_id} | " +
                               f"Grim: {external_id_correto} (origem: {origem_grim}) | " +
                               f"Event ID: {event_id} | " +
                               f"Task: {task.id}")
                    
                    # Aguardar resultado
                    try:
                        result = task.get(timeout=10)
                        if result and result.get('events_received', 0) > 0:
                            reenviadas += 1
                            logger.info(f"✅ Purchase RE-ENVIADO com sucesso: {payment.payment_id} | Events Received: {result.get('events_received', 0)} | Grim: {external_id_correto}")
                            print(f"   ✅ Payment {payment.payment_id}: RE-ENVIADO | Grim: {external_id_correto} (origem: {origem_grim}) | Valor: R$ {payment.amount:.2f}")
                        else:
                            erro += 1
                            logger.error(f"❌ Purchase RE-ENVIO falhou: {payment.payment_id} | Result: {result}")
                            print(f"   ❌ Payment {payment.payment_id}: FALHOU ao re-enviar")
                    except Exception as e:
                        erro += 1
                        logger.error(f"❌ Erro ao obter resultado do reenvio: {e}")
                        print(f"   ❌ Payment {payment.payment_id}: Erro ao re-enviar: {e}")
                        
                except Exception as e:
                    erro += 1
                    logger.error(f"❌ Erro ao enfileirar reenvio: {e}", exc_info=True)
                    print(f"   ❌ Payment {payment.payment_id}: Erro ao enfileirar: {e}")
                    
            except Exception as e:
                erro += 1
                logger.error(f"❌ Erro ao processar payment {payment.payment_id}: {e}", exc_info=True)
                print(f"   ❌ Payment {payment.payment_id}: Erro: {e}")
        
        print("\n" + "=" * 80)
        print("📊 RESUMO DO REENVIO:")
        print(f"   ✅ Re-enviadas com sucesso: {reenviadas}")
        print(f"   ⚠️ Sem grim válido: {sem_grim}")
        print(f"   ❌ Erros: {erro}")
        print(f"   📊 Total processadas: {len(vendas_hoje)}")
        print("=" * 80)
        
        if reenviadas > 0:
            print("\n💡 IMPORTANTE:")
            print("   - Os eventos foram re-enviados com external_id CORRETO (grim)")
            print("   - Podem levar até 30 minutos para aparecer no Gerenciador da Meta")
            print("   - Verifique em: https://business.facebook.com/events_manager/")
            print("=" * 80)

if __name__ == '__main__':
    reenviar_vendas_hoje_com_grim()

