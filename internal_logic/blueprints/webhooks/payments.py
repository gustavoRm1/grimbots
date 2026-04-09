"""
Webhooks Payment Blueprint
===========================
Recebe webhooks de gateways de pagamento (Paradise, SyncPay, etc.)
Responde 200 imediatamente e delega processamento para fila RQ ou service.
"""

import json
import logging
from flask import Blueprint, request, jsonify, current_app
from internal_logic.core.extensions import limiter, csrf
from internal_logic.core.models import Payment, Gateway, Bot
from gateway_factory import GatewayFactory

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__)


@csrf.exempt
@webhooks_bp.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@limiter.limit("500 per minute")
def payment_webhook(gateway_type):
    """
    Webhook para confirmação de pagamento - QI 200 FAST MODE
    """
    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True)
    payload_source = 'json'

    if data is None:
        payload_source = 'form'
        data = {}
        if request.form:
            data.update(request.form.to_dict(flat=True))

    if (not data) and raw_body:
        payload_source = 'raw'
        try:
            parsed = json.loads(raw_body)
            if isinstance(parsed, dict):
                data = parsed
            else:
                data = {'_raw_payload': parsed}
        except (ValueError, TypeError):
            data = {'_raw_body': raw_body}

    if not isinstance(data, dict):
        data = {'_raw_payload': data}

    data.setdefault('_content_type', request.content_type)
    data.setdefault('_payload_source', payload_source)
    
    # DEBUG: Log completo do payload recebido
    logger.debug(f"WEBHOOK DEBUG: {gateway_type} payload recebido:")
    logger.debug(f"   Raw Body: {raw_body[:500]}...")  # Primeiros 500 chars
    logger.debug(f"   Parsed Data: {data}")
    logger.debug(f"   Content-Type: {request.content_type}")
    
    logger.info(f" Webhook {gateway_type} recebido | content-type={request.content_type}")
    
    # ✅# QI 200: ENFILEIRAMENTO DESATIVADO - Processar sempre síncrono
    # try:
    #     from tasks_async import webhook_queue, process_webhook_async
    #     if webhook_queue:
    #         webhook_queue.enqueue(
    #             process_webhook_async,
    #             0,  # user_id 0 = Worker fará auto-resolve via transaction_id
    #             gateway_type,
    #             data
    #         )
    # PROCESSAMENTO SÍNCRONO DIRETO (usando GatewayFactory com adapter)
    try:
        _process_payment_webhook_sync(gateway_type, data)
        return jsonify({'status': 'processed_sync'}), 200
    except Exception as e:
        logger.error(f" Erro ao processar webhook: {e}")
        return jsonify({'error': 'Internal error'}), 500


def _process_payment_webhook_sync(gateway_type: str, data: dict):
    """Processamento síncrono de fallback quando RQ não está disponível."""
    # 1. Instanciar o Factory com credenciais dummy
    dummy_credentials = {}
    if gateway_type == 'syncpay':
        dummy_credentials = {'client_id': 'dummy', 'client_secret': 'dummy'}
    elif gateway_type == 'pushynpay':
        dummy_credentials = {'api_key': 'dummy'}
    elif gateway_type == 'paradise':
        dummy_credentials = {'api_key': 'dummy', 'product_hash': 'dummy'}
    elif gateway_type == 'wiinpay':
        dummy_credentials = {'api_key': 'dummy'}
    elif gateway_type == 'atomopay':
        dummy_credentials = {'api_token': 'dummy'}
    elif gateway_type == 'umbrellapag':
        dummy_credentials = {'api_key': 'dummy'}
    elif gateway_type == 'orionpay':
        dummy_credentials = {'api_key': 'dummy'}
    elif gateway_type == 'babylon':
        dummy_credentials = {'api_key': 'dummy'}
    elif gateway_type == 'bolt':
        dummy_credentials = {'api_key': 'dummy', 'company_id': 'dummy'}
    
    # 2. Criar gateway via Factory com adapter
    from gateway_factory import GatewayFactory
    gateway_instance = GatewayFactory.create_gateway(gateway_type, dummy_credentials, use_adapter=True)
    
    gateway = None
    result = None
    
    if gateway_instance:
        # 3. Extrair producer_hash se disponível
        producer_hash = None
        if hasattr(gateway_instance, 'extract_producer_hash'):
            producer_hash = gateway_instance.extract_producer_hash(data)
            if producer_hash:
                gateway = Gateway.query.filter_by(
                    gateway_type=gateway_type,
                    producer_hash=producer_hash
                ).first()
        
        # 4. Processar webhook via ADAPTER (ARQUITETURA LEGADA RESTAURADA)
        result = gateway_instance.process_webhook(data)
    
    if result:
        gateway_transaction_id = result.get('gateway_transaction_id')
        
        # AUDITORIA: Print console para ver exatamente o que o Adapter retornou
        print(f"DEBUG WEBHOOK: Result do Adapter: {result}")
        
        # DEBUG: Log do resultado processado
        logger.debug(f"WEBHOOK DEBUG: Resultado processado:")
        logger.debug(f"   Gateway Transaction ID: {gateway_transaction_id}")
        logger.debug(f"   Status: {result.get('status')}")
        logger.debug(f"   Gateway Hash: {result.get('gateway_hash')}")
        
        # Buscar pagamento - MELHORADO COM REFERENCE
        payment_query = Payment.query
        if gateway:
            payment_query = payment_query.filter_by(gateway_type=gateway_type)
            user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
            if user_bot_ids:
                payment_query = payment_query.filter(Payment.bot_id.in_(user_bot_ids))
        
        payment = None
        
        # Tentativa 1: gateway_transaction_id (PARADISE USA ESTE)
        if gateway_transaction_id:
            print(f"DEBUG WEBHOOK: Buscando Payment com ID: {gateway_transaction_id}")
            logger.debug(f"WEBHOOK DEBUG: Buscando por gateway_transaction_id={gateway_transaction_id}")
            payment = payment_query.filter_by(gateway_transaction_id=str(gateway_transaction_id)).first()
            if payment:
                print(f"DEBUG WEBHOOK: Payment encontrado via gateway_transaction_id! ID={payment.id}")
                logger.debug(f"WEBHOOK DEBUG: Pagamento encontrado via gateway_transaction_id! ID={payment.id}")
        
        # Tentativa 2: reference/pament_id (O PULO DO GATO - Paradise envia reference)
        if not payment:
            reference = result.get('payment_id') or result.get('reference') or data.get('reference')
            if reference:
                print(f"DEBUG WEBHOOK: Buscando por reference/payment_id: {reference}")
                logger.debug(f"WEBHOOK DEBUG: Buscando por reference={reference}")
                payment = payment_query.filter_by(payment_id=str(reference)).first()
                if payment:
                    print(f"DEBUG WEBHOOK: Payment encontrado via reference! ID={payment.id}")
                    logger.debug(f"WEBHOOK DEBUG: Pagamento encontrado via reference! ID={payment.id}")
        
        # Tentativa 3: payment_id no payload direto (fallback)
        if not payment and 'payment_id' in data:
            payment_id = data.get('payment_id')
            print(f"DEBUG WEBHOOK: Buscando por payment_id no payload: {payment_id}")
            logger.debug(f"WEBHOOK DEBUG: Buscando por payment_id={payment_id}")
            payment = payment_query.filter_by(payment_id=str(payment_id)).first()
            if payment:
                print(f"DEBUG WEBHOOK: Payment encontrado via payment_id! ID={payment.id}")
                logger.debug(f"WEBHOOK DEBUG: Pagamento encontrado via payment_id! ID={payment.id}")
        
        # Tentativa 4: gateway_hash (fallback)
        if not payment:
            gateway_hash = result.get('gateway_hash') or data.get('hash')
            if gateway_hash:
                print(f"DEBUG WEBHOOK: Buscando por gateway_hash: {gateway_hash}")
                logger.debug(f"WEBHOOK DEBUG: Buscando por gateway_hash={gateway_hash}")
                payment = payment_query.filter_by(gateway_transaction_hash=str(gateway_hash)).first()
                if payment:
                    print(f"DEBUG WEBHOOK: Payment encontrado via gateway_hash! ID={payment.id}")
                    logger.debug(f"WEBHOOK DEBUG: Pagamento encontrado via gateway_hash! ID={payment.id}")
        
        # AUDITORIA: Verificação final
        print(f"DEBUG WEBHOOK: Payment encontrado? {'SIM' if payment else 'NAO'}")
        
        # Se encontrou pagamento e status é 'paid'
        if payment:
            print(f"DEBUG WEBHOOK: Payment localizado - Status atual: {payment.status} | Status webhook: {result.get('status')}")
            logger.debug(f"WEBHOOK DEBUG: Pagamento localizado - Status atual: {payment.status}")
            
            if result.get('status') == 'paid' and payment.status != 'paid':
                print(f"DEBUG WEBHOOK: ATUALIZANDO pagamento {payment.id} para PAID!")
                logger.info(f"WEBHOOK DEBUG: ATUALIZANDO pagamento {payment.id} para PAID!")
                
                # FORÇAR ATUALIZAÇÃO COM COMMIT EXPLÍCITO
                payment.status = 'paid'
                payment.paid_at = datetime.utcnow()  # <--- CRÍTICO: Preencher paid_at
                from internal_logic.core.extensions import db
                db.session.add(payment)  # Garante que está na sessão
                db.session.commit()
                
                print(f"DEBUG WEBHOOK: COMMIT REALIZADO para Payment {payment.id}")
                logger.info(f"WEBHOOK DEBUG: COMMIT REALIZADO para Payment {payment.id}")
                
                # Processar entrega
                from internal_logic.services.payment_processor import process_payment_confirmation
                process_payment_confirmation(payment, gateway_type)
                logger.info(f"WEBHOOK DEBUG: Pagamento {payment.id} confirmado e entrega processada!")
            else:
                print(f"DEBUG WEBHOOK: Pagamento já está paid ou status não é paid")
                logger.debug(f"WEBHOOK DEBUG: Pagamento já está paid ou status não é paid")
        else:
            print(f"DEBUG WEBHOOK: NENHUM pagamento encontrado para o webhook!")
            logger.warning(f"WEBHOOK DEBUG: NENHUM pagamento encontrado para o webhook!")
    
    return jsonify({'status': 'processed'}), 200
