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
    ✅ Retorna 200 IMEDIATAMENTE e processa em background
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
    
    logger.info(f"🔔 Webhook {gateway_type} recebido | content-type={request.content_type}")
    
    # ✅ QI 200: Enfileirar processamento na fila WEBHOOK
    try:
        from tasks_async import webhook_queue, process_webhook_async
        if webhook_queue:
            webhook_queue.enqueue(
                process_webhook_async,
                0,  # user_id 0 = Worker fará auto-resolve via transaction_id
                gateway_type,
                data
            )
            return jsonify({'status': 'queued'}), 200
    except Exception as e:
        logger.error(f"Erro ao enfileirar webhook: {e}")
    
    # ✅ FALLBACK: Processar síncrono se RQ não disponível
    try:
        from tasks_async import process_webhook_async
        process_webhook_async(0, gateway_type, data)
        return jsonify({'status': 'processed_sync'}), 200
    except Exception as e:
        logger.error(f"❌ Erro ao processar webhook: {e}")
        return jsonify({'error': 'Internal error'}), 500


def _process_payment_webhook_sync(gateway_type: str, data: dict):
    """Processamento síncrono de fallback quando RQ não está disponível."""
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
    
    gateway_instance = GatewayFactory.create_gateway(gateway_type, dummy_credentials, use_adapter=True)
    
    gateway = None
    result = None
    
    if gateway_instance:
        producer_hash = None
        if hasattr(gateway_instance, 'extract_producer_hash'):
            producer_hash = gateway_instance.extract_producer_hash(data)
            if producer_hash:
                gateway = Gateway.query.filter_by(
                    gateway_type=gateway_type,
                    producer_hash=producer_hash
                ).first()
        
        result = gateway_instance.process_webhook(data)
    
    if result:
        gateway_transaction_id = result.get('gateway_transaction_id')
        
        # Buscar pagamento
        payment_query = Payment.query
        if gateway:
            payment_query = payment_query.filter_by(gateway_type=gateway_type)
            user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
            if user_bot_ids:
                payment_query = payment_query.filter(Payment.bot_id.in_(user_bot_ids))
        
        payment = None
        if gateway_transaction_id:
            payment = payment_query.filter_by(gateway_transaction_id=str(gateway_transaction_id)).first()
        
        if not payment:
            gateway_hash = result.get('gateway_hash') or data.get('hash')
            if gateway_hash:
                payment = payment_query.filter_by(gateway_transaction_hash=str(gateway_hash)).first()
        
        if payment and result.get('status') == 'paid' and payment.status != 'paid':
            payment.status = 'paid'
            from internal_logic.core.extensions import db
            db.session.commit()
            
            # Processar entrega
            from internal_logic.services.payment_processor import process_payment_confirmation
            process_payment_confirmation(payment, gateway_type)
    
    return jsonify({'status': 'processed'}), 200
