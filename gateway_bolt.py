"""
Gateway Bolt Pagamentos - Implementação Isolada
Base URL: https://api.sistema.boltpagamentos.com/functions/v1
"""

import os
import base64
import logging
from typing import Dict, Any, Optional, List

import requests

from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class BoltGateway(PaymentGateway):
    def __init__(self, api_key: str, company_id: str):
        self.secret_key = api_key
        self.company_id = company_id
        self.base_url = os.environ.get('BOLT_API_URL', 'https://api.sistema.boltpagamentos.com/functions/v1')

    def get_gateway_name(self) -> str:
        return "Bolt Pagamentos"

    def get_gateway_type(self) -> str:
        return "bolt"

    def get_webhook_url(self) -> str:
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        if webhook_base:
            return f"{webhook_base}/webhooks/bolt"
        return ""

    def _build_headers(self) -> Dict[str, str]:
        if not self.secret_key:
            raise ValueError("Bolt secret_key (api_key) não configurada")
        if not self.company_id:
            raise ValueError("Bolt company_id não configurado")

        credentials_string = f"{self.secret_key}:{self.company_id}"
        credentials_base64 = base64.b64encode(credentials_string.encode('utf-8')).decode('utf-8')

        return {
            'Authorization': f'Basic {credentials_base64}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def verify_credentials(self) -> bool:
        try:
            if not self.secret_key or len(str(self.secret_key).strip()) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] Secret Key inválida ou vazia")
                return False
            if not self.company_id or len(str(self.company_id).strip()) < 5:
                logger.error(f"❌ [{self.get_gateway_name()}] Company ID inválido ou vazio")
                return False

            # Não existe endpoint de health documentado. Validação local apenas.
            return True
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False

    def _create_transaction(
        self,
        payment_method: str,
        amount: float,
        description: str,
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None

            method = str(payment_method or '').strip().upper()
            if method not in {'PIX', 'CARD', 'BOLETO'}:
                logger.error(f"❌ [{self.get_gateway_name()}] paymentMethod inválido: {payment_method}")
                return None

            amount_cents = int(round(float(amount) * 100))
            if amount_cents <= 0:
                logger.error(f"❌ [{self.get_gateway_name()}] amount_cents inválido: {amount_cents}")
                return None

            payload: Dict[str, Any] = {
                'paymentMethod': method,
                'amount': amount_cents,
                'postbackUrl': self.get_webhook_url(),
                'description': (description or '')[:500] or None,
                'items': [
                    {
                        'title': (description or 'Produto')[:100],
                        'unitPrice': amount_cents,
                        'quantity': 1,
                        'externalRef': (payment_id or '')[:100],
                    }
                ],
            }

            if not payload.get('postbackUrl'):
                logger.error(f"❌ [{self.get_gateway_name()}] WEBHOOK_URL não configurado (postbackUrl vazio)")
                return None

            if not payload['description']:
                payload.pop('description', None)

            if customer_data:
                customer_name = customer_data.get('name') or customer_data.get('customer_name')
                customer_email = customer_data.get('email') or customer_data.get('customer_email')
                customer_phone = customer_data.get('phone') or customer_data.get('customer_phone')
                customer_document = customer_data.get('cpf') or customer_data.get('document') or customer_data.get('customer_document')

                customer: Dict[str, Any] = {}
                if customer_name:
                    customer['name'] = str(customer_name)[:255]
                if customer_email:
                    customer['email'] = str(customer_email)[:255]
                if customer_phone:
                    customer['phone'] = ''.join(filter(str.isdigit, str(customer_phone)))[:20]
                if customer_document:
                    doc_number = ''.join(filter(str.isdigit, str(customer_document)))
                    if doc_number:
                        customer['document'] = doc_number[:30]

                if customer:
                    payload['customer'] = customer

            url = f"{self.base_url}/transactions"
            headers = self._build_headers()

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code not in (200, 201):
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar transação: {response.status_code} | {response.text}")
                return None

            data = response.json() if response.content else {}

            transaction_id = data.get('id')
            remote_method = data.get('paymentMethod')
            pix = data.get('pix') or {}

            # Não promover status local aqui. Retornar sempre pending.
            result: Dict[str, Any] = {
                'transaction_id': transaction_id,
                'payment_id': payment_id,
                'amount': amount_cents,
                'status': 'pending',
                'payment_method': remote_method or method,
                'raw_data': data,
            }

            if method == 'PIX' and isinstance(pix, dict):
                result['pix_code'] = pix.get('qrcodeText')
                result['qr_code_url'] = pix.get('qrcode')

            return result

        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar transação: {e}", exc_info=True)
            return None

    def generate_pix(
        self,
        amount: float,
        description: str,
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        result = self._create_transaction(
            payment_method='PIX',
            amount=amount,
            description=description,
            payment_id=payment_id,
            customer_data=customer_data,
        )
        if not result:
            return None

        pix_code = (result.get('pix_code') or '').strip() if result.get('pix_code') else ''
        qr_code_url = (result.get('qr_code_url') or '').strip() if result.get('qr_code_url') else ''

        # Alguns retornos do Bolt podem vir com o EMV (copia e cola) em outro campo.
        if not pix_code:
            raw_data = result.get('raw_data') or {}
            pix = raw_data.get('pix') if isinstance(raw_data, dict) else None
            if isinstance(pix, dict):
                for key in ('qrcodeText', 'qrCodeText', 'copyPaste', 'emv'):
                    candidate = pix.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        pix_code = candidate.strip()
                        break

        # Fallback adicional: quando o gateway entrega o EMV no campo qr_code_url.
        if not pix_code and qr_code_url and len(qr_code_url) > 50:
            pix_code = qr_code_url

        return {
            'pix_code': pix_code or '',
            'qr_code_url': qr_code_url or '',
            'transaction_id': result.get('transaction_id'),
            'payment_id': payment_id,
            'gateway_hash': None,
            'reference': payment_id,
            'status': 'pending',
        }

    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if not isinstance(data, dict):
                return None

            event_id = data.get('id')
            payload = data.get('data') if isinstance(data.get('data'), dict) else {}

            transaction_id = payload.get('id') or data.get('objectId')
            payment_method = payload.get('paymentMethod')
            bolt_status = str(payload.get('status') or '').strip().lower()

            allowed_statuses = {
                'waiting_payment',
                'paid',
                'refused',
                'canceled',
                'refunded',
                'chargedback',
                'failed',
                'expired',
                'in_analisys',
                'in_protest',
            }

            if bolt_status and bolt_status not in allowed_statuses:
                logger.warning(
                    f"⚠️ [{self.get_gateway_name()}] Status Bolt desconhecido recebido: {bolt_status}"
                )
                # Blindagem: tratar como pending.
                bolt_status = ''

            amount = payload.get('amount')
            external_ref = None
            items = payload.get('items')
            if isinstance(items, list) and items:
                first_item = items[0] if isinstance(items[0], dict) else {}
                external_ref = first_item.get('externalRef')

            # 🔐 Regra blindada: somente status == 'paid' promove.
            # Para qualquer outro status, retornamos 'pending' e NÃO expomos raw_status/raw_statuses
            # para evitar que o GatewayAdapter reclassifique como failed/cancelled/etc.
            normalized_status = 'paid' if bolt_status == 'paid' else 'pending'

            return {
                'payment_id': external_ref,
                'status': normalized_status,
                'amount': amount,
                'gateway_transaction_id': transaction_id,
                'external_reference': external_ref,
                'payment_method': payment_method,
                'raw_data': {
                    'event_id': event_id,
                    'payload': data,
                    'bolt_status': bolt_status,
                },
            }
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}", exc_info=True)
            return None

    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        try:
            if not transaction_id:
                return None

            url = f"{self.base_url}/transactions/{transaction_id}"
            headers = self._build_headers()

            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao consultar transação {transaction_id}: {response.status_code} | {response.text}")
                return None

            data = response.json() if response.content else {}
            bolt_status = str(data.get('status') or '').strip().lower()
            if bolt_status and bolt_status not in {
                'waiting_payment',
                'paid',
                'refused',
                'canceled',
                'refunded',
                'chargedback',
                'failed',
                'expired',
                'in_analisys',
                'in_protest',
            }:
                logger.warning(
                    f"⚠️ [{self.get_gateway_name()}] Status Bolt desconhecido em get_payment_status: {bolt_status} | transaction_id={transaction_id}"
                )
                bolt_status = ''
            normalized_status = 'paid' if bolt_status == 'paid' else 'pending'

            return {
                'payment_id': None,
                'status': normalized_status,
                'amount': data.get('amount'),
                'gateway_transaction_id': data.get('id') or transaction_id,
                'external_reference': None,
                'payment_method': data.get('paymentMethod'),
                'raw_data': {
                    'bolt_status': bolt_status,
                    'payload': data,
                },
            }

        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            return None

    def list_transactions(
        self,
        page: int = 1,
        limit: int = 10,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/transactions"
            headers = self._build_headers()

            params: Dict[str, Any] = {
                'page': max(1, int(page or 1)),
                'limit': max(1, min(100, int(limit or 10))),
            }
            if status:
                params['status'] = status
            if payment_method:
                params['paymentMethod'] = payment_method
            if start_date:
                params['startDate'] = start_date
            if end_date:
                params['endDate'] = end_date

            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code != 200:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao listar transações: {response.status_code} | {response.text}")
                return None

            data = response.json() if response.content else {}
            items = data.get('data') if isinstance(data.get('data'), list) else []

            normalized: List[Dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                bolt_status = str(item.get('status') or '').strip().lower()
                if bolt_status and bolt_status not in {
                    'waiting_payment',
                    'paid',
                    'refused',
                    'canceled',
                    'refunded',
                    'chargedback',
                    'failed',
                    'expired',
                    'in_analisys',
                    'in_protest',
                }:
                    logger.warning(
                        f"⚠️ [{self.get_gateway_name()}] Status Bolt desconhecido em list_transactions: {bolt_status}"
                    )
                    bolt_status = ''
                normalized_status = 'paid' if bolt_status == 'paid' else 'pending'
                normalized.append({
                    'gateway_transaction_id': item.get('id'),
                    'status': normalized_status,
                    'amount': item.get('amount'),
                    'payment_method': item.get('paymentMethod'),
                    'raw_data': {
                        'bolt_status': bolt_status,
                        'payload': item,
                    },
                })

            return {
                'data': normalized,
                'pagination': data.get('pagination') or {},
                'raw_data': data,
            }
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao listar transações: {e}")
            return None
