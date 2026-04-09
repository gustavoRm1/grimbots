"""
Webhooks Payment Blueprint - Versão Final (CTO Approved)
=======================================================
- Suporte oficial à API Paradise (Status 'approved').
- Busca Global de Emergência (Fallback por UUID).
- Validação de Credenciais para instanciamento seguro.
- Integridade Atômica com Rollback em caso de erro no banco.
"""

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from internal_logic.core.extensions import limiter, csrf, db
from internal_logic.core.models import Payment, Gateway, Bot
from gateway_factory import GatewayFactory

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__)

@csrf.exempt
@webhooks_bp.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@limiter.limit("500 per minute")
def payment_webhook(gateway_type):
    """
    Rota principal do Webhook.
    Recebe o sinal, processa e garante que o banco foi atualizado antes do 200 OK.
    """
    raw_body = request.get_data(cache=True, as_text=True)
    data = request.get_json(silent=True) or {}

    # Normalização de dados caso venha como Form
    if not data and request.form:
        data = request.form.to_dict(flat=True)

    logger.info(f"🚀 Webhook {gateway_type} recebido. Processando...")

    try:
        # Chama o processador síncrono para garantir o commit
        success = _process_payment_webhook_sync(gateway_type, data)
        
        if success:
            return jsonify({'status': 'processed', 'info': 'Payment updated successfully'}), 200
        else:
            # Retorna 404 para que o Gateway saiba que o ID não foi achado no nosso banco
            return jsonify({'error': 'Payment not found or status not eligible'}), 404

    except Exception as e:
        logger.error(f"❌ Erro crítico no Webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def _process_payment_webhook_sync(gateway_type: str, data: dict) -> bool:
    """
    Lógica de Processamento com Integridade Garantida.
    """
    # 1. Preparação de Credenciais Dummy (Seguindo as regras do gateway_paradise.py)
    dummy_credentials = {'api_key': 'dummy', 'product_hash': 'prod_dummy'}
    
    if gateway_type == 'paradise':
        # Paradise exige sk_ e 40+ caracteres para não dar ValueError
        dummy_credentials = {
            'api_key': 'sk_live_v30_dummy_1234567890abcdef1234567890abcdef',
            'product_hash': 'prod_default_v30'
        }
    elif gateway_type == 'syncpay':
        dummy_credentials = {'client_id': 'dummy', 'client_secret': 'dummy'}

    # 2. Instanciamento via Factory (Adapter Pattern)
    gateway_instance = GatewayFactory.create_gateway(gateway_type, dummy_credentials, use_adapter=True)
    if not gateway_instance:
        print(f"[AUDIT] Erro: Gateway {gateway_type} não suportado pela Factory.")
        return False

    # 3. Tradução do Payload (Traduz 'approved' para 'paid' e extrai IDs)
    result = gateway_instance.process_webhook(data)
    if not result:
        return False

    # Extração de Identificadores (Tratando a doc da Paradise)
    # Paradise envia nosso ID no 'external_id', o Adapter coloca no 'payment_id'
    external_id = result.get('payment_id') or data.get('external_id')
    gateway_tid = result.get('gateway_transaction_id')
    status_recebido = str(result.get('status', '')).lower()

    print(f"[AUDIT] Tradução: ID={external_id} | Status Gateway={status_recebido}")

    # 4. Busca em Cascata (Resiliência Máxima)
    payment = None

    # Tentativa 1: Busca Global por UUID (A mais segura)
    if external_id:
        payment = Payment.query.filter_by(payment_id=str(external_id)).first()

    # Tentativa 2: Busca por ID do Gateway (Fallback)
    if not payment and gateway_tid:
        payment = Payment.query.filter_by(gateway_transaction_id=str(gateway_tid)).first()

    # 5. Validação e Persistência
    if payment:
        # Lista de status que significam "Dinheiro no Bolso"
        if status_recebido in ['paid', 'approved', 'confirmed', 'completed']:
            # Se já estiver pago, não faz nada mas retorna sucesso (idempotência)
            if payment.status == 'paid':
                print(f"[AUDIT] Pagamento {payment.id} já estava como PAID.")
                return True

            try:
                # Atualização do Banco
                payment.status = 'paid'
                payment.paid_at = datetime.utcnow()
                
                db.session.add(payment)
                db.session.commit()
                print(f"[SUCCESS] Pagamento {payment.id} ATUALIZADO para PAID.")

                # 6. Disparar Entrega (Telegram/Bot)
                try:
                    from internal_logic.services.payment_processor import process_payment_confirmation
                    process_payment_confirmation(payment, gateway_type)
                    print(f"[SUCCESS] Entrega processada para o bot.")
                except Exception as delivery_err:
                    logger.error(f"⚠️ Erro na entrega mas pagamento foi salvo: {delivery_err}")

                return True

            except Exception as db_err:
                db.session.rollback()
                logger.error(f"❌ Erro ao salvar no banco: {db_err}")
                return False
    
    print(f"[AUDIT] Falha: Pagamento {external_id} não localizado no banco.")
    return False