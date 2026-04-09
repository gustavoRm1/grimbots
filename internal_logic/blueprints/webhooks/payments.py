"""
Webhooks Payment Blueprint
===========================
Recebe webhooks de gateways de pagamento (Paradise, SyncPay, etc.)
Responde 200 imediatamente e delega processamento para fila RQ ou service.
"""

import json
import logging
from datetime import datetime
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
        success = _process_payment_webhook_sync(gateway_type, data)
        if success:
            return jsonify({'status': 'processed'}), 200
        else:
            return jsonify({'error': 'payment_not_found_or_not_updated'}), 404
    except Exception as e:
        logger.error(f" Erro ao processar webhook: {e}")
        return jsonify({'error': 'Internal error'}), 500


def _process_payment_webhook_sync(gateway_type: str, data: dict) -> bool:
    """
    Processamento síncrono com integridade garantida.
    Retorna True se o pagamento foi atualizado com sucesso, False caso contrário.
    """
    # STEP 2: LOG DO ADAPTER
    from gateway_factory import GatewayFactory
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
        print(f"[AUDIT] Step 2: Tradução Adapter: {result}")
    
    if result:
        gateway_transaction_id = result.get('gateway_transaction_id')
        
        # AUDITORIA: Print console para ver exatamente o que o Adapter retornou
        print(f"DEBUG WEBHOOK: Result do Adapter: {result}")
        
        # DEBUG: Log do resultado processado
        logger.debug(f"WEBHOOK DEBUG: Resultado processado:")
        logger.debug(f"   Gateway Transaction ID: {gateway_transaction_id}")
        logger.debug(f"   Status: {result.get('status')}")
        logger.debug(f"   Gateway Hash: {result.get('gateway_hash')}")
        
        # MAPEAMENTO DE STATUS - DOCUMENTAÇÃO PARADISE
        webhook_status = result.get('status', '').lower()
        original_status = result.get('status')
        print(f"[AUDIT] Step 3: Status Paradise recebido: '{original_status}' | Mapeando para: '{webhook_status}' se for 'approved'")

        # BUSCA ROBUSTA COM FALLBACK GLOBAL - DOCUMENTAÇÃO OFICIAL
        # Paradise envia: external_id = nosso UUID
        external_id = result.get('payment_id') or data.get('external_id')
        payment = None
        
        print(f"[AUDIT] Step 3: Buscando no DB por external_id: {external_id}")
        
        # Tentativa 1: Busca filtrada (se tiver gateway com user_id)
        if gateway and external_id:
            # Busca com filtros de usuário/bot (otimizada)
            user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
            if user_bot_ids:
                payment = Payment.query.filter(
                    Payment.bot_id.in_(user_bot_ids),
                    Payment.payment_id == str(external_id)
                ).first()
                if payment:
                    print(f"[AUDIT] Step 4: Resultado busca filtrada: <Payment ID={payment.id} | Status={payment.status}>")
        
        # Tentativa 2: Busca global por external_id (FAIL-OVER - se a filtrada falhar)
        if not payment and external_id:
            payment = Payment.query.filter_by(payment_id=str(external_id)).first()
            if payment:
                print(f"[AUDIT] Step 4: Resultado busca global: <Payment ID={payment.id} | Status={payment.status}>")
                print(f"[AUDIT] AVISO: Busca filtrada falhou, mas encontrou via global (external_id único)")
            else:
                print(f"[AUDIT] Step 4: Resultado busca global: <None>")

        # Tentativa 3: gateway_transaction_id (último fallback)
        if not payment and gateway_transaction_id:
            payment = Payment.query.filter_by(gateway_transaction_id=str(gateway_transaction_id)).first()
            if payment:
                print(f"[AUDIT] Step 4: Resultado busca final: <Payment ID={payment.id} | Status={payment.status}>")
                print(f"[AUDIT] AVISO: Encontrado apenas via gateway_transaction_id")

        # STEP 5: TENTANDO ATUALIZAÇÃO
        if payment:
            print(f"[AUDIT] Step 5: Tentando Commit...")
            print(f"[AUDIT] Step 5: Status atual: '{payment.status}' | Status webhook: '{webhook_status}'")
            
            # ACEITA MÚLTIPLOS STATUS - Paradise envia 'approved', outros gateways enviam 'paid'
            status_recebido = str(result.get('status', '')).lower()
            if status_recebido in ['paid', 'approved', 'confirmed', 'completed']:
                if payment.status != 'paid':
                    payment.status = 'paid'
                    payment.paid_at = datetime.utcnow()
                    from internal_logic.core.extensions import db
                    
                    try:
                        db.session.add(payment)
                        db.session.commit()
                        print(f"[SUCCESS] Pagamento {payment.id} atualizado para PAID via status: {status_recebido}")
                        print(f"[AUDIT] Step 6: Commit OK! Payment {payment.id} atualizado para PAID")
                    
                    # Processar entrega
                    from internal_logic.services.payment_processor import process_payment_confirmation
                    process_payment_confirmation(payment, gateway_type)
                    print(f"[AUDIT] Step 6: Entrega processada para Payment {payment.id}")
                    
                    return True  # SUCESSO
                    
                except Exception as commit_error:
                    print(f"[AUDIT] Step 6: Commit FALHOU: {commit_error}")
                    db.session.rollback()
                    return False
            else:
                print(f"[AUDIT] Step 5: Status não é 'paid', não atualizando")
                return False
        else:
            print(f"[AUDIT] Step 4: NENHUM pagamento encontrado!")
            return False
    
    return jsonify({'status': 'processed'}), 200
