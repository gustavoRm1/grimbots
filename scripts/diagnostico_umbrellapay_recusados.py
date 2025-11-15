#!/usr/bin/env python3
"""
Script para diagnosticar pagamentos recusados pela UmbrellaPay
Analisa payload enviado, resposta do gateway, webhooks e logs
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta

# Adicionar o diretório raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def diagnosticar_pagamentos_recusados(transaction_ids):
    """Diagnostica pagamentos recusados pela UmbrellaPay"""
    logger.info("=" * 80)
    logger.info("🔍 DIAGNÓSTICO: PAGAMENTOS RECUSADOS UMBRELLAPAY")
    logger.info("=" * 80)
    
    try:
        from app import app, db
        from models import Payment, WebhookEvent
        
        with app.app_context():
            logger.info(f"\n📋 Analisando {len(transaction_ids)} transação(ões) recusada(s)...")
            
            for transaction_id in transaction_ids:
                logger.info("\n" + "=" * 80)
                logger.info(f"🔍 TRANSACTION ID: {transaction_id}")
                logger.info("=" * 80)
                
                # 1. Buscar Payment pelo gateway_transaction_id
                payment = Payment.query.filter_by(
                    gateway_transaction_id=transaction_id,
                    gateway_type='umbrellapag'
                ).first()
                
                if not payment:
                    logger.warning(f"⚠️ Payment não encontrado para transaction_id: {transaction_id}")
                    logger.info(f"   Tentando buscar por payment_id...")
                    # Tentar buscar por payment_id (se transaction_id for igual ao payment_id)
                    payment = Payment.query.filter_by(payment_id=transaction_id).first()
                
                if not payment:
                    logger.error(f"❌ Payment não encontrado para transaction_id: {transaction_id}")
                    logger.info(f"   Verificando se transaction_id está em outro campo...")
                    # Buscar em todos os campos relacionados
                    payment = Payment.query.filter(
                        (Payment.gateway_transaction_id.like(f"%{transaction_id}%")) |
                        (Payment.payment_id.like(f"%{transaction_id}%")) |
                        (Payment.gateway_transaction_hash.like(f"%{transaction_id}%"))
                    ).first()
                
                if not payment:
                    logger.error(f"❌ Payment NÃO ENCONTRADO para transaction_id: {transaction_id}")
                    logger.info(f"   Este transaction_id pode não estar no nosso banco de dados")
                    continue
                
                logger.info(f"✅ Payment encontrado: {payment.payment_id}")
                logger.info(f"   Status: {payment.status}")
                logger.info(f"   Gateway Type: {payment.gateway_type}")
                logger.info(f"   Gateway Transaction ID: {payment.gateway_transaction_id}")
                logger.info(f"   Gateway Transaction Hash: {payment.gateway_transaction_hash}")
                logger.info(f"   Valor: R$ {payment.amount:.2f}")
                logger.info(f"   Criado em: {payment.created_at}")
                logger.info(f"   Pago em: {payment.paid_at if payment.paid_at else 'N/A'}")
                
                # 2. Verificar dados do cliente
                logger.info(f"\n--- DADOS DO CLIENTE ---")
                logger.info(f"   Nome: {payment.customer_name}")
                logger.info(f"   Email: {payment.customer_email}")
                logger.info(f"   Telefone: {payment.customer_phone}")
                logger.info(f"   CPF: {payment.customer_document}")
                logger.info(f"   Customer User ID: {payment.customer_user_id}")
                
                # 3. Verificar webhooks recebidos
                logger.info(f"\n--- WEBHOOKS RECEBIDOS ---")
                webhooks = WebhookEvent.query.filter(
                    WebhookEvent.transaction_id == transaction_id,
                    WebhookEvent.gateway_type == 'umbrellapag'
                ).order_by(WebhookEvent.received_at.desc()).all()
                
                if webhooks:
                    logger.info(f"✅ {len(webhooks)} webhook(s) encontrado(s)")
                    for i, webhook in enumerate(webhooks, 1):
                        logger.info(f"\n   Webhook #{i}:")
                        logger.info(f"   Status: {webhook.status}")
                        logger.info(f"   Recebido em: {webhook.received_at}")
                        logger.info(f"   Payload: {json.dumps(webhook.payload, ensure_ascii=False, indent=2)}")
                else:
                    logger.warning(f"⚠️ Nenhum webhook encontrado para transaction_id: {transaction_id}")
                
                # 4. Verificar logs de geração de PIX
                logger.info(f"\n--- LOGS DE GERAÇÃO DE PIX ---")
                logger.info(f"   Para ver logs detalhados, execute:")
                logger.info(f"   tail -f logs/gunicorn.log | grep -iE '{transaction_id}|{payment.payment_id}|umbrellapay'")
                
                # 5. Verificar dados críticos para UmbrellaPay
                logger.info(f"\n--- VALIDAÇÃO DE DADOS CRÍTICOS ---")
                
                problemas = []
                
                # Validar CPF
                if not payment.customer_document:
                    problemas.append("❌ CPF ausente (obrigatório para UmbrellaPay)")
                elif len(payment.customer_document.replace('.', '').replace('-', '')) != 11:
                    problemas.append(f"⚠️ CPF com formato inválido: {payment.customer_document} (deve ter 11 dígitos)")
                
                # Validar Email
                if not payment.customer_email:
                    problemas.append("❌ Email ausente (obrigatório para UmbrellaPay)")
                elif '@' not in payment.customer_email:
                    problemas.append(f"⚠️ Email com formato inválido: {payment.customer_email}")
                
                # Validar Telefone
                if not payment.customer_phone:
                    problemas.append("⚠️ Telefone ausente (recomendado para UmbrellaPay)")
                else:
                    phone_digits = ''.join(filter(str.isdigit, payment.customer_phone))
                    if len(phone_digits) < 10 or len(phone_digits) > 11:
                        problemas.append(f"⚠️ Telefone com formato inválido: {payment.customer_phone} (deve ter 10-11 dígitos)")
                
                # Validar Nome
                if not payment.customer_name:
                    problemas.append("❌ Nome ausente (obrigatório para UmbrellaPay)")
                elif len(payment.customer_name) < 3:
                    problemas.append(f"⚠️ Nome muito curto: {payment.customer_name} (mínimo 3 caracteres)")
                
                # Validar Valor
                if payment.amount <= 0:
                    problemas.append(f"❌ Valor inválido: R$ {payment.amount:.2f} (deve ser > 0)")
                
                if problemas:
                    logger.warning(f"⚠️ {len(problemas)} problema(s) identificado(s):")
                    for problema in problemas:
                        logger.warning(f"   {problema}")
                else:
                    logger.info(f"✅ Todos os dados críticos estão válidos")
                
                # 6. Verificar se há logs de erro na geração
                logger.info(f"\n--- ANÁLISE DE POSSÍVEIS CAUSAS ---")
                logger.info(f"   Possíveis causas de recusa pela UmbrellaPay:")
                logger.info(f"   1. CPF inválido ou ausente")
                logger.info(f"   2. Email inválido ou ausente")
                logger.info(f"   3. Telefone inválido ou ausente")
                logger.info(f"   4. Nome muito curto ou ausente")
                logger.info(f"   5. Valor inválido (<= 0)")
                logger.info(f"   6. Dados duplicados (mesmo CPF/Email em múltiplas transações)")
                logger.info(f"   7. Limite de transações excedido")
                logger.info(f"   8. Problema na API da UmbrellaPay (temporário)")
                
                # 7. Comparar com pagamentos aprovados recentes
                logger.info(f"\n--- COMPARAÇÃO COM PAGAMENTOS APROVADOS ---")
                pagamentos_aprovados = Payment.query.filter(
                    Payment.gateway_type == 'umbrellapag',
                    Payment.status == 'paid',
                    Payment.created_at >= payment.created_at - timedelta(days=1)
                ).limit(5).all()
                
                if pagamentos_aprovados:
                    logger.info(f"✅ {len(pagamentos_aprovados)} pagamento(s) aprovado(s) nas últimas 24h")
                    logger.info(f"   Comparando estrutura de dados...")
                    
                    # Comparar estrutura
                    aprovado = pagamentos_aprovados[0]
                    logger.info(f"\n   Pagamento Aprovado (exemplo):")
                    logger.info(f"   CPF: {aprovado.customer_document}")
                    logger.info(f"   Email: {aprovado.customer_email}")
                    logger.info(f"   Telefone: {aprovado.customer_phone}")
                    logger.info(f"   Nome: {aprovado.customer_name}")
                    
                    logger.info(f"\n   Pagamento Recusado:")
                    logger.info(f"   CPF: {payment.customer_document}")
                    logger.info(f"   Email: {payment.customer_email}")
                    logger.info(f"   Telefone: {payment.customer_phone}")
                    logger.info(f"   Nome: {payment.customer_name}")
                    
                    # Verificar diferenças
                    diferencas = []
                    if aprovado.customer_document and not payment.customer_document:
                        diferencas.append("❌ CPF ausente no recusado (presente no aprovado)")
                    if aprovado.customer_email and not payment.customer_email:
                        diferencas.append("❌ Email ausente no recusado (presente no aprovado)")
                    if aprovado.customer_phone and not payment.customer_phone:
                        diferencas.append("⚠️ Telefone ausente no recusado (presente no aprovado)")
                    
                    if diferencas:
                        logger.warning(f"⚠️ Diferenças encontradas:")
                        for diff in diferencas:
                            logger.warning(f"   {diff}")
                    else:
                        logger.info(f"✅ Estrutura de dados similar ao aprovado")
                else:
                    logger.warning(f"⚠️ Nenhum pagamento aprovado encontrado para comparação")
            
            logger.info("\n" + "=" * 80)
            logger.info("✅ DIAGNÓSTICO CONCLUÍDO")
            logger.info("=" * 80)
            logger.info("\n💡 PRÓXIMOS PASSOS:")
            logger.info("   1. Verificar logs detalhados de geração de PIX")
            logger.info("   2. Comparar payload enviado com documentação UmbrellaPay")
            logger.info("   3. Verificar se há padrão nos dados dos recusados")
            logger.info("   4. Validar formato de CPF, Email, Telefone")
            logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro durante diagnóstico: {e}", exc_info=True)

def main():
    """Função principal"""
    # IDs de transação fornecidos pelo usuário
    transaction_ids = [
        "294c13fe-b631-4a38-b3df-208854b9824c",
        "9a795667-b704-490e-b90d-a828ab729f24",
        "f785b4e5-4381-4016-8e92-e3ff8951b970",
        "11a9bc7c-2709-4bb9-9a8d-b3fba524c55a",
        "589c5f63-e676-4575-b7d7-85cff2686f01",
        "e56243e3-5a2c-4260-8540-16bb897a88aa",
        "958f6f40-a7e3-4e75-b5a4-ffcc68f85ac2",
        "722664db-384a-4342-94cf-603c0eea2702"
    ]
    
    logger.info("=" * 80)
    logger.info("🚀 INICIANDO DIAGNÓSTICO: PAGAMENTOS RECUSADOS UMBRELLAPAY")
    logger.info("=" * 80)
    logger.info(f"📋 Transaction IDs a analisar: {len(transaction_ids)}")
    
    diagnosticar_pagamentos_recusados(transaction_ids)

if __name__ == "__main__":
    main()

