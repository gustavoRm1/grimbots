#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Diagnóstico: Meta Purchase não sendo enviado via Webhook

Este script analisa pagamentos recentes e identifica por que o Meta Purchase
não está sendo enviado, verificando todas as condições necessárias.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Adicionar raiz do projeto ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Carregar variáveis de ambiente ANTES de importar app
from dotenv import load_dotenv
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)

from flask import Flask
from models import Payment, PoolBot, RedirectPool, BotUser, db
import logging
import redis
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verificar_redis_connection():
    """Verifica conexão com Redis"""
    try:
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=False
        )
        redis_client.ping()
        return redis_client
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao Redis: {e}")
        return None


def diagnosticar_payment(payment, redis_client=None):
    """Diagnostica um payment específico"""
    logger.info("=" * 80)
    logger.info(f"🔍 DIAGNÓSTICO: Payment {payment.payment_id}")
    logger.info("=" * 80)
    
    problemas = []
    avisos = []
    sucessos = []
    
    # 1. Verificar status do payment
    logger.info(f"\n1️⃣ STATUS DO PAYMENT:")
    logger.info(f"   Status: {payment.status}")
    logger.info(f"   Meta Purchase Sent: {payment.meta_purchase_sent}")
    logger.info(f"   Meta Purchase Sent At: {payment.meta_purchase_sent_at}")
    logger.info(f"   Meta Event ID: {payment.meta_event_id}")
    
    if payment.status != 'paid':
        problemas.append(f"❌ Payment status não é 'paid': {payment.status}")
    else:
        sucessos.append("✅ Payment status é 'paid'")
    
    if payment.meta_purchase_sent:
        avisos.append(f"⚠️ Meta Purchase já foi marcado como enviado (meta_purchase_sent=True)")
        avisos.append(f"   Isso pode bloquear reenvio (linha 7439 de app.py)")
    
    # 2. Verificar Pool Bot
    logger.info(f"\n2️⃣ POOL BOT:")
    pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
    if not pool_bot:
        problemas.append("❌ Bot não está associado a nenhum pool (PoolBot não encontrado)")
        logger.error("   Isso bloqueia o Purchase na linha 7406-7409 de app.py")
        return problemas, avisos, sucessos
    else:
        sucessos.append("✅ Pool Bot encontrado")
        logger.info(f"   Pool Bot ID: {pool_bot.id}")
    
    pool = pool_bot.pool
    logger.info(f"   Pool ID: {pool.id}")
    logger.info(f"   Pool Nome: {pool.name}")
    
    # 3. Verificar configuração do Pool
    logger.info(f"\n3️⃣ CONFIGURAÇÃO DO POOL:")
    logger.info(f"   Meta Tracking Enabled: {pool.meta_tracking_enabled}")
    logger.info(f"   Meta Events Purchase: {pool.meta_events_purchase}")
    logger.info(f"   Meta Pixel ID: {pool.meta_pixel_id}")
    logger.info(f"   Meta Access Token: {'✅ Configurado' if pool.meta_access_token else '❌ Ausente'}")
    
    if not pool.meta_tracking_enabled:
        problemas.append("❌ Meta tracking DESABILITADO no pool (linha 7419-7422)")
    else:
        sucessos.append("✅ Meta tracking habilitado")
    
    if not pool.meta_events_purchase:
        problemas.append("❌ Evento Purchase DESABILITADO no pool (linha 7431-7434)")
    else:
        sucessos.append("✅ Evento Purchase habilitado")
    
    if not pool.meta_pixel_id:
        problemas.append("❌ Meta Pixel ID ausente no pool (linha 7424-7427)")
    else:
        sucessos.append(f"✅ Meta Pixel ID configurado: {pool.meta_pixel_id[:10]}...")
    
    if not pool.meta_access_token:
        problemas.append("❌ Meta Access Token ausente no pool (linha 7424-7427)")
    else:
        sucessos.append("✅ Meta Access Token configurado")
    
    # 4. Verificar tracking_token
    logger.info(f"\n4️⃣ TRACKING TOKEN:")
    logger.info(f"   Tracking Token: {payment.tracking_token}")
    
    if not payment.tracking_token:
        problemas.append("❌ Tracking token ausente no payment (linha 7511-7512)")
        avisos.append("   Isso indica que o usuário não veio do redirect ou token não foi salvo")
    else:
        sucessos.append(f"✅ Tracking token presente: {payment.tracking_token[:30]}...")
        
        # 5. Verificar dados no Redis
        if redis_client:
            logger.info(f"\n5️⃣ DADOS NO REDIS:")
            try:
                redis_key = f"tracking:{payment.tracking_token}"
                redis_data = redis_client.get(redis_key)
                
                if not redis_data:
                    problemas.append(f"❌ Tracking token NÃO encontrado no Redis: {redis_key}")
                    avisos.append("   Isso pode indicar que o token expirou ou nunca foi salvo")
                else:
                    sucessos.append("✅ Tracking token encontrado no Redis")
                    try:
                        tracking_data = json.loads(redis_data)
                        logger.info(f"   Campos no Redis: {list(tracking_data.keys())}")
                        
                        # Verificar campos críticos
                        campos_criticos = {
                            'fbclid': tracking_data.get('fbclid'),
                            'fbp': tracking_data.get('fbp'),
                            'fbc': tracking_data.get('fbc'),
                            'client_ip': tracking_data.get('client_ip') or tracking_data.get('ip'),
                            'client_user_agent': tracking_data.get('client_user_agent') or tracking_data.get('ua') or tracking_data.get('user_agent'),
                            'pageview_event_id': tracking_data.get('pageview_event_id')
                        }
                        
                        logger.info(f"\n   Campos críticos:")
                        for campo, valor in campos_criticos.items():
                            if valor:
                                logger.info(f"   ✅ {campo}: {str(valor)[:50]}...")
                                sucessos.append(f"✅ {campo} presente no Redis")
                            else:
                                logger.warning(f"   ❌ {campo}: Ausente")
                                if campo in ['client_ip', 'client_user_agent']:
                                    problemas.append(f"❌ {campo} ausente no Redis (linha 8028-8041 pode bloquear)")
                        
                        # Verificar TTL
                        ttl = redis_client.ttl(redis_key)
                        if ttl > 0:
                            logger.info(f"   TTL restante: {ttl} segundos ({ttl // 3600} horas)")
                            if ttl < 3600:
                                avisos.append(f"⚠️ TTL do token está baixo: {ttl} segundos (expira em {ttl // 60} minutos)")
                        else:
                            logger.warning(f"   ⚠️ TTL: {ttl} (token pode ter expirado)")
                    
                    except json.JSONDecodeError as e:
                        problemas.append(f"❌ Erro ao decodificar dados do Redis: {e}")
            except Exception as e:
                problemas.append(f"❌ Erro ao buscar dados do Redis: {e}")
        else:
            avisos.append("⚠️ Redis não disponível - não foi possível verificar tracking_data")
    
    # 6. Verificar BotUser
    logger.info(f"\n6️⃣ BOT USER:")
    bot_user = BotUser.query.filter_by(
        bot_id=payment.bot_id,
        telegram_user_id=payment.customer_user_id
    ).first()
    
    if not bot_user:
        avisos.append("⚠️ BotUser não encontrado (fallback de IP/UA não disponível)")
    else:
        sucessos.append("✅ BotUser encontrado")
        logger.info(f"   BotUser ID: {bot_user.id}")
        
        # Verificar IP e User-Agent no BotUser
        ip_bot_user = getattr(bot_user, 'ip_address', None)
        ua_bot_user = getattr(bot_user, 'user_agent', None)
        
        logger.info(f"   IP Address: {ip_bot_user if ip_bot_user else '❌ Ausente'}")
        logger.info(f"   User Agent: {ua_bot_user[:50] if ua_bot_user else '❌ Ausente'}...")
        
        if not ip_bot_user:
            avisos.append("⚠️ IP não está no BotUser (fallback não disponível para linha 8028-8034)")
        if not ua_bot_user:
            avisos.append("⚠️ User-Agent não está no BotUser (fallback não disponível para linha 8035-8041)")
    
    # 7. Verificar dados do Payment
    logger.info(f"\n7️⃣ DADOS DO PAYMENT:")
    logger.info(f"   FBP: {payment.fbp if hasattr(payment, 'fbp') and payment.fbp else '❌ Ausente'}")
    logger.info(f"   FBC: {payment.fbc if hasattr(payment, 'fbc') and payment.fbc else '❌ Ausente'}")
    logger.info(f"   FBCLID: {payment.fbclid if hasattr(payment, 'fbclid') and payment.fbclid else '❌ Ausente'}")
    logger.info(f"   Pageview Event ID: {payment.pageview_event_id if hasattr(payment, 'pageview_event_id') and payment.pageview_event_id else '❌ Ausente'}")
    
    # 8. Resumo
    logger.info(f"\n{'=' * 80}")
    logger.info(f"📊 RESUMO DO DIAGNÓSTICO:")
    logger.info(f"{'=' * 80}")
    
    if sucessos:
        logger.info(f"\n✅ SUCESSOS ({len(sucessos)}):")
        for sucesso in sucessos:
            logger.info(f"   {sucesso}")
    
    if avisos:
        logger.info(f"\n⚠️ AVISOS ({len(avisos)}):")
        for aviso in avisos:
            logger.warning(f"   {aviso}")
    
    if problemas:
        logger.error(f"\n❌ PROBLEMAS ({len(problemas)}):")
        for problema in problemas:
            logger.error(f"   {problema}")
    else:
        logger.info(f"\n✅ NENHUM PROBLEMA ENCONTRADO!")
        logger.info(f"   O Purchase deveria ser enviado normalmente.")
        logger.info(f"   Verifique os logs do webhook para ver se há erros durante o envio.")
    
    return problemas, avisos, sucessos


def main():
    """Função principal"""
    logger.info("=" * 80)
    logger.info("🔍 DIAGNÓSTICO: Meta Purchase não sendo enviado via Webhook")
    logger.info("=" * 80)
    
    # Carregar app
    from app import app
    
    with app.app_context():
        # Conectar ao Redis
        redis_client = verificar_redis_connection()
        if not redis_client:
            logger.warning("⚠️ Redis não disponível - algumas verificações serão puladas")
        
        # Buscar pagamentos recentes (últimas 24 horas)
        uma_hora_atras = datetime.utcnow() - timedelta(hours=1)
        pagamentos = Payment.query.filter(
            Payment.status == 'paid',
            Payment.created_at >= uma_hora_atras
        ).order_by(Payment.id.desc()).limit(10).all()
        
        if not pagamentos:
            logger.warning("⚠️ Nenhum pagamento 'paid' encontrado nas últimas 24 horas")
            logger.info("   Buscando pagamentos mais antigos...")
            pagamentos = Payment.query.filter(
                Payment.status == 'paid'
            ).order_by(Payment.id.desc()).limit(5).all()
        
        if not pagamentos:
            logger.error("❌ Nenhum pagamento 'paid' encontrado no banco de dados")
            return
        
        logger.info(f"\n📊 Encontrados {len(pagamentos)} pagamento(s) para diagnosticar\n")
        
        # Diagnosticar cada pagamento
        todos_problemas = []
        todos_avisos = []
        todos_sucessos = []
        
        for i, payment in enumerate(pagamentos, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"🔍 PAGAMENTO {i}/{len(pagamentos)}")
            logger.info(f"{'=' * 80}")
            
            problemas, avisos, sucessos = diagnosticar_payment(payment, redis_client)
            
            todos_problemas.extend(problemas)
            todos_avisos.extend(avisos)
            todos_sucessos.extend(sucessos)
        
        # Resumo geral
        logger.info(f"\n{'=' * 80}")
        logger.info(f"📊 RESUMO GERAL")
        logger.info(f"{'=' * 80}")
        logger.info(f"   Pagamentos analisados: {len(pagamentos)}")
        logger.info(f"   Problemas encontrados: {len(todos_problemas)}")
        logger.info(f"   Avisos: {len(todos_avisos)}")
        logger.info(f"   Sucessos: {len(todos_sucessos)}")
        
        if todos_problemas:
            logger.error(f"\n❌ PROBLEMAS MAIS COMUNS:")
            from collections import Counter
            problemas_count = Counter(todos_problemas)
            for problema, count in problemas_count.most_common(5):
                logger.error(f"   {problema} (x{count})")
        
        logger.info(f"\n{'=' * 80}")
        logger.info("✅ DIAGNÓSTICO CONCLUÍDO")
        logger.info(f"{'=' * 80}")


if __name__ == "__main__":
    main()

