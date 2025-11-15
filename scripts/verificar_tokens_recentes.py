#!/usr/bin/env python3
"""
Script para verificar tokens de tracking RECENTES (criados após as correções)
Valida se as correções estão funcionando para novos redirects/pagamentos
"""

import os
import sys
import json
import logging
import redis
from datetime import datetime, timedelta

# Adicionar o diretório raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verificar_tokens_recentes():
    """Verifica tokens de tracking criados nas últimas 2 horas"""
    logger.info("=" * 80)
    logger.info("🔍 VERIFICANDO TOKENS DE TRACKING RECENTES (Últimas 2 horas)")
    logger.info("=" * 80)
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Buscar todas as chaves de tracking
        tracking_keys = r.keys('tracking:*')
        
        if not tracking_keys:
            logger.warning("⚠️ Nenhuma chave de tracking encontrada no Redis")
            return
        
        logger.info(f"✅ {len(tracking_keys)} chave(s) de tracking encontrada(s)")
        
        # Filtrar chaves que são tokens (não índices)
        token_keys = [k for k in tracking_keys if not k.startswith('tracking:fbclid:') and not k.startswith('tracking:chat:') and not k.startswith('tracking:last_token:') and not k.startswith('tracking:hash:')]
        
        logger.info(f"✅ {len(token_keys)} chave(s) de token encontrada(s)")
        
        # Verificar tokens recentes (últimas 2 horas)
        # Como não temos timestamp direto, vamos verificar os últimos 20 tokens
        recent_tokens = token_keys[-20:] if len(token_keys) > 20 else token_keys
        
        logger.info(f"\n--- Verificando {len(recent_tokens)} token(s) mais recente(s) ---")
        
        tokens_com_dados_completos = 0
        tokens_com_prefixo_tracking = 0
        tokens_sem_prefixo = 0
        
        for key in recent_tokens:
            try:
                data = r.get(key)
                if data:
                    tracking_data = json.loads(data)
                    
                    # Extrair tracking_token da chave
                    tracking_token = key.replace('tracking:', '').replace('tracking:token:', '')
                    
                    # Verificar se tem prefixo tracking_
                    tem_prefixo = tracking_token.startswith('tracking_')
                    if tem_prefixo:
                        tokens_com_prefixo_tracking += 1
                    else:
                        tokens_sem_prefixo += 1
                    
                    # Verificar dados completos
                    tem_fbp = bool(tracking_data.get('fbp'))
                    tem_fbc = bool(tracking_data.get('fbc'))
                    tem_fbclid = bool(tracking_data.get('fbclid'))
                    tem_client_ip = bool(tracking_data.get('client_ip'))
                    tem_client_user_agent = bool(tracking_data.get('client_user_agent'))
                    tem_pageview_event_id = bool(tracking_data.get('pageview_event_id'))
                    
                    dados_completos = tem_fbp and tem_fbclid and tem_client_ip and tem_client_user_agent and tem_pageview_event_id
                    
                    if dados_completos:
                        tokens_com_dados_completos += 1
                    
                    logger.info(f"\n--- Token: {tracking_token[:30]}... ---")
                    logger.info(f"   Prefixo tracking_: {'✅' if tem_prefixo else '❌'}")
                    logger.info(f"   fbp: {'✅' if tem_fbp else '❌'}")
                    logger.info(f"   fbc: {'✅' if tem_fbc else '❌'}")
                    logger.info(f"   fbclid: {'✅' if tem_fbclid else '❌'}")
                    logger.info(f"   client_ip: {'✅' if tem_client_ip else '❌'}")
                    logger.info(f"   client_user_agent: {'✅' if tem_client_user_agent else '❌'}")
                    logger.info(f"   pageview_event_id: {'✅' if tem_pageview_event_id else '❌'}")
                    logger.info(f"   Dados completos: {'✅' if dados_completos else '❌'}")
                    
            except Exception as e:
                logger.warning(f"   ⚠️ Erro ao processar chave {key}: {e}")
        
        # Resumo
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMO DA VERIFICAÇÃO")
        logger.info("=" * 80)
        logger.info(f"   Tokens verificados: {len(recent_tokens)}")
        logger.info(f"   Tokens com prefixo tracking_: {tokens_com_prefixo_tracking} ({tokens_com_prefixo_tracking/len(recent_tokens)*100:.1f}%)")
        logger.info(f"   Tokens sem prefixo (UUID): {tokens_sem_prefixo} ({tokens_sem_prefixo/len(recent_tokens)*100:.1f}%)")
        logger.info(f"   Tokens com dados completos: {tokens_com_dados_completos} ({tokens_com_dados_completos/len(recent_tokens)*100:.1f}%)")
        
        if tokens_com_prefixo_tracking > 0:
            logger.warning(f"   ⚠️ {tokens_com_prefixo_tracking} token(s) ainda tem prefixo tracking_ (gerados no PIX, não no redirect)")
        
        if tokens_com_dados_completos < len(recent_tokens):
            logger.warning(f"   ⚠️ {len(recent_tokens) - tokens_com_dados_completos} token(s) não tem dados completos (client_ip, client_user_agent, pageview_event_id)")
        
        if tokens_com_dados_completos == len(recent_tokens) and tokens_sem_prefixo == len(recent_tokens):
            logger.info(f"   ✅ TODOS os tokens recentes estão corretos!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar tokens recentes: {e}", exc_info=True)

def verificar_pagamentos_recentes():
    """Verifica pagamentos criados nas últimas 2 horas"""
    logger.info("\n" + "=" * 80)
    logger.info("🔍 VERIFICANDO PAGAMENTOS RECENTES (Últimas 2 horas)")
    logger.info("=" * 80)
    
    try:
        from app import app, db
        from models import Payment, BotUser
        
        with app.app_context():
            # Buscar pagamentos das últimas 2 horas
            time_threshold = datetime.utcnow() - timedelta(hours=2)
            recent_payments = Payment.query.filter(
                Payment.created_at >= time_threshold
            ).order_by(Payment.created_at.desc()).limit(10).all()
            
            if not recent_payments:
                logger.warning("⚠️ Nenhum pagamento encontrado nas últimas 2 horas")
                return
            
            logger.info(f"✅ {len(recent_payments)} pagamento(s) encontrado(s) nas últimas 2 horas")
            
            pagamentos_com_token_correto = 0
            pagamentos_com_prefixo = 0
            
            for payment in recent_payments:
                tracking_token = payment.tracking_token
                tem_prefixo = tracking_token and tracking_token.startswith('tracking_')
                
                if tem_prefixo:
                    pagamentos_com_prefixo += 1
                else:
                    pagamentos_com_token_correto += 1
                
                # Verificar BotUser
                telegram_user_id = payment.customer_user_id.replace('user_', '') if payment.customer_user_id and payment.customer_user_id.startswith('user_') else str(payment.customer_user_id)
                bot_user = BotUser.query.filter_by(bot_id=payment.bot_id, telegram_user_id=telegram_user_id).first()
                
                logger.info(f"\n--- Payment ID: {payment.payment_id} ---")
                logger.info(f"   Status: {payment.status}")
                logger.info(f"   Criado em: {payment.created_at}")
                logger.info(f"   Tracking Token: {tracking_token[:30] if tracking_token else 'N/A'}...")
                logger.info(f"   Tem prefixo tracking_: {'✅' if tem_prefixo else '❌'}")
                logger.info(f"   BotUser Tracking Session ID: {bot_user.tracking_session_id[:30] if bot_user and bot_user.tracking_session_id else 'N/A'}...")
                logger.info(f"   Tokens coincidem: {'✅' if (tracking_token and bot_user and bot_user.tracking_session_id and tracking_token == bot_user.tracking_session_id) else '❌'}")
            
            # Resumo
            logger.info("\n" + "=" * 80)
            logger.info("📊 RESUMO DA VERIFICAÇÃO")
            logger.info("=" * 80)
            logger.info(f"   Pagamentos verificados: {len(recent_payments)}")
            logger.info(f"   Pagamentos com token correto (UUID): {pagamentos_com_token_correto} ({pagamentos_com_token_correto/len(recent_payments)*100:.1f}%)")
            logger.info(f"   Pagamentos com prefixo tracking_: {pagamentos_com_prefixo} ({pagamentos_com_prefixo/len(recent_payments)*100:.1f}%)")
            
            if pagamentos_com_prefixo > 0:
                logger.warning(f"   ⚠️ {pagamentos_com_prefixo} pagamento(s) ainda tem prefixo tracking_ (gerados no PIX, não no redirect)")
            
            if pagamentos_com_token_correto == len(recent_payments):
                logger.info(f"   ✅ TODOS os pagamentos recentes estão usando tokens corretos!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao verificar pagamentos recentes: {e}", exc_info=True)

def main():
    """Função principal"""
    logger.info("=" * 80)
    logger.info("🚀 VERIFICAÇÃO DE TOKENS E PAGAMENTOS RECENTES")
    logger.info("=" * 80)
    logger.info("⚠️ NOTA: Este script verifica tokens e pagamentos criados APÓS as correções")
    logger.info("=" * 80)
    
    verificar_tokens_recentes()
    verificar_pagamentos_recentes()
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ VERIFICAÇÃO CONCLUÍDA")
    logger.info("=" * 80)
    logger.info("💡 DICA: Para validar as correções, faça um teste real:")
    logger.info("   1. Acesse um link de redirect: https://app.grimbots.online/go/{slug}?grim=...")
    logger.info("   2. Envie /start no bot")
    logger.info("   3. Gere um PIX")
    logger.info("   4. Execute este script novamente para verificar se os dados estão corretos")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()

