"""
Script de Diagnóstico - Meta Purchase Não Enviado

Execute: python scripts/diagnostico_meta_purchase.py
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def diagnostico_meta_purchase():
    """Diagnóstico completo do problema de Meta Purchase não enviado"""
    from app import app, db
    from models import Payment, PoolBot, RedirectPool, Bot
    
    with app.app_context():
        try:
            logger.info("=" * 80)
            logger.info("🔍 DIAGNÓSTICO COMPLETO - META PURCHASE NÃO ENVIADO")
            logger.info("=" * 80)
            
            # ✅ 1. Verificar payments recentes (últimas 24 horas)
            logger.info("\n1️⃣ VERIFICANDO PAYMENTS RECENTES (últimas 24 horas)...")
            agora = datetime.utcnow()
            vinte_quatro_horas_atras = agora - timedelta(hours=24)
            
            payments_recentes = Payment.query.filter(
                Payment.created_at >= vinte_quatro_horas_atras
            ).order_by(Payment.created_at.desc()).limit(50).all()
            
            logger.info(f"   Total de payments recentes: {len(payments_recentes)}")
            
            # ✅ 2. Verificar payments pagos que NÃO enviaram Purchase
            logger.info("\n2️⃣ VERIFICANDO PAYMENTS PAGOS SEM META PURCHASE...")
            payments_pagos_sem_purchase = []
            
            for payment in payments_recentes:
                if payment.status == 'paid' and not payment.meta_purchase_sent:
                    payments_pagos_sem_purchase.append(payment)
                    
                    # Verificar Pool
                    pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
                    if pool_bot:
                        pool = pool_bot.pool
                        logger.info(f"   ❌ Payment {payment.payment_id}:")
                        logger.info(f"      Status: {payment.status}")
                        logger.info(f"      Meta Purchase Enviado: {payment.meta_purchase_sent}")
                        logger.info(f"      Pool: {pool.name if pool else 'N/A'}")
                        logger.info(f"      Pool Meta Tracking: {pool.meta_tracking_enabled if pool else 'N/A'}")
                        logger.info(f"      Pool Meta Pixel ID: {pool.meta_pixel_id[:10] + '...' if pool and pool.meta_pixel_id else 'N/A'}")
                        logger.info(f"      Pool Meta Access Token: {'✅' if pool and pool.meta_access_token else '❌'}")
                        logger.info(f"      Pool Meta Events Purchase: {pool.meta_events_purchase if pool else 'N/A'}")
                        logger.info(f"      Tracking Token: {payment.tracking_token[:30] + '...' if payment.tracking_token else '❌'}")
                        logger.info(f"      Gateway: {payment.gateway_type}")
                        logger.info(f"      Gateway Transaction ID: {payment.gateway_transaction_id}")
                        logger.info(f"      Criado em: {payment.created_at}")
                        logger.info(f"      Pago em: {payment.paid_at}")
                        logger.info("")
                    else:
                        logger.error(f"   ❌ Payment {payment.payment_id}: Bot {payment.bot_id} NÃO está associado a nenhum Pool!")
                        logger.error(f"      Isso IMPEDE o envio do Meta Purchase!")
                        logger.error(f"      SOLUÇÃO: Associe o bot a um Pool no dashboard")
                        logger.info("")
            
            logger.info(f"   Total de payments pagos sem Purchase: {len(payments_pagos_sem_purchase)}")
            
            # ✅ 3. Verificar payments UmbrellaPay pendentes
            logger.info("\n3️⃣ VERIFICANDO PAYMENTS UMBRELLAPAY PENDENTES...")
            payments_umbrellapay_pendentes = Payment.query.filter(
                Payment.gateway_type == 'umbrellapag',
                Payment.status == 'pending',
                Payment.created_at >= vinte_quatro_horas_atras
            ).order_by(Payment.created_at.desc()).limit(20).all()
            
            logger.info(f"   Total de payments UmbrellaPay pendentes: {len(payments_umbrellapay_pendentes)}")
            
            for payment in payments_umbrellapay_pendentes:
                logger.info(f"   ⏳ Payment {payment.payment_id}:")
                logger.info(f"      Status: {payment.status}")
                logger.info(f"      Gateway Transaction ID: {payment.gateway_transaction_id}")
                logger.info(f"      Criado em: {payment.created_at}")
                logger.info(f"      Tempo pendente: {(agora - payment.created_at).total_seconds() / 60:.1f} minutos")
                logger.info("")
            
            # ✅ 4. Verificar configuração dos Pools
            logger.info("\n4️⃣ VERIFICANDO CONFIGURAÇÃO DOS POOLS...")
            pools = RedirectPool.query.all()
            
            logger.info(f"   Total de pools: {len(pools)}")
            
            for pool in pools:
                pool_bots = PoolBot.query.filter_by(pool_id=pool.id).all()
                logger.info(f"   Pool {pool.id} ({pool.name}):")
                logger.info(f"      Bots associados: {len(pool_bots)}")
                logger.info(f"      Meta Tracking Habilitado: {pool.meta_tracking_enabled}")
                logger.info(f"      Meta Pixel ID: {pool.meta_pixel_id[:10] + '...' if pool.meta_pixel_id else '❌'}")
                logger.info(f"      Meta Access Token: {'✅' if pool.meta_access_token else '❌'}")
                logger.info(f"      Meta Events Purchase: {pool.meta_events_purchase}")
                logger.info("")
            
            # ✅ 5. Verificar webhooks recentes
            logger.info("\n5️⃣ VERIFICANDO WEBHOOKS RECENTES...")
            from models import WebhookEvent
            
            webhooks_recentes = WebhookEvent.query.filter(
                WebhookEvent.gateway_type == 'umbrellapag',
                WebhookEvent.received_at >= vinte_quatro_horas_atras
            ).order_by(WebhookEvent.received_at.desc()).limit(20).all()
            
            logger.info(f"   Total de webhooks UmbrellaPay recebidos: {len(webhooks_recentes)}")
            
            for webhook in webhooks_recentes:
                logger.info(f"   🔔 Webhook {webhook.id}:")
                logger.info(f"      Transaction ID: {webhook.transaction_id}")
                logger.info(f"      Status: {webhook.status}")
                logger.info(f"      Recebido em: {webhook.received_at}")
                logger.info("")
            
            # ✅ 6. Resumo Final
            logger.info("\n" + "=" * 80)
            logger.info("📊 RESUMO DO DIAGNÓSTICO")
            logger.info("=" * 80)
            logger.info(f"   Payments recentes: {len(payments_recentes)}")
            logger.info(f"   Payments pagos sem Purchase: {len(payments_pagos_sem_purchase)}")
            logger.info(f"   Payments UmbrellaPay pendentes: {len(payments_umbrellapay_pendentes)}")
            logger.info(f"   Webhooks UmbrellaPay recebidos: {len(webhooks_recentes)}")
            logger.info(f"   Pools configurados: {len(pools)}")
            
            # ✅ 7. Problemas Identificados
            logger.info("\n" + "=" * 80)
            logger.info("🔍 PROBLEMAS IDENTIFICADOS")
            logger.info("=" * 80)
            
            problemas = []
            
            if len(payments_pagos_sem_purchase) > 0:
                problemas.append(f"❌ {len(payments_pagos_sem_purchase)} payment(s) pago(s) sem Meta Purchase enviado")
            
            if len(payments_umbrellapay_pendentes) > 0:
                problemas.append(f"⏳ {len(payments_umbrellapay_pendentes)} payment(s) UmbrellaPay pendente(s)")
            
            if len(webhooks_recentes) == 0:
                problemas.append(f"❌ Nenhum webhook UmbrellaPay recebido nas últimas 24 horas")
            
            for pool in pools:
                if pool.meta_tracking_enabled:
                    if not pool.meta_pixel_id:
                        problemas.append(f"❌ Pool {pool.id} ({pool.name}): Meta Tracking habilitado mas SEM Pixel ID")
                    if not pool.meta_access_token:
                        problemas.append(f"❌ Pool {pool.id} ({pool.name}): Meta Tracking habilitado mas SEM Access Token")
                    if not pool.meta_events_purchase:
                        problemas.append(f"❌ Pool {pool.id} ({pool.name}): Meta Tracking habilitado mas Purchase Event DESABILITADO")
            
            if problemas:
                for problema in problemas:
                    logger.error(f"   {problema}")
            else:
                logger.info("   ✅ Nenhum problema identificado!")
            
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no diagnóstico: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔍 DIAGNÓSTICO - META PURCHASE NÃO ENVIADO")
    logger.info("=" * 80)
    
    success = diagnostico_meta_purchase()
    
    if success:
        logger.info("=" * 80)
        logger.info("✅ DIAGNÓSTICO CONCLUÍDO!")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("=" * 80)
        logger.error("❌ DIAGNÓSTICO FALHOU!")
        logger.error("=" * 80)
        sys.exit(1)

