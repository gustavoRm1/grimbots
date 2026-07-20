import logging
import requests
from typing import Dict, Optional, Any
from .gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)

SUPREMUSPAY_API = "http://141.11.128.204/api/v1"


class SupremusPayGateway(PaymentGateway):

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        logger.info("SupremusPay Gateway inicializado")

    def _request(self, method: str, path: str, json_data: dict = None) -> Optional[dict]:
        url = f"{SUPREMUSPAY_API}{path}"
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json_data,
                timeout=30
            )
            logger.debug(f"SupremusPay {method} {path} -> {resp.status_code}")
            if resp.status_code in (200, 201):
                return resp.json()
            logger.warning(f"SupremusPay {method} {path} -> {resp.status_code}: {resp.text[:200]}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"SupremusPay timeout {method} {path}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"SupremusPay connection error {method} {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"SupremusPay error {method} {path}: {e}")
            return None

    def generate_pix(
        self,
        amount: float,
        description: str,
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            amount_cents = int(amount * 100)
            cdata = customer_data or {}
            client_name = cdata.get("name", "Cliente Grimbots")
            client_email = cdata.get("email", "cliente@grimbots.online")
            client_document = cdata.get("cpf") or cdata.get("document", "")
            client_phone = cdata.get("phone", "")

            payload = {
                "external_id": str(payment_id)[:100],
                "amount": amount_cents,
                "client_name": client_name,
                "client_email": client_email,
                "client_document": client_document,
                "client_phone": client_phone,
                "product_name": description or "Produto Grimbots"
            }

            logger.info(f"SupremusPay: Gerando PIX - Amount: {amount}, PaymentID: {payment_id}")

            data = self._request("POST", "/charges", json_data=payload)
            if not data:
                return {
                    'transaction_id': None,
                    'pix_code': None,
                    'qr_code_url': None,
                    'payment_id': payment_id,
                    'qr_code_base64': None,
                    'expires_at': None,
                    'status': 'error',
                    'error': 'Falha na comunicação com o gateway'
                }

            pix_code = data.get("pix_code") or ""
            transaction_id = data.get("identifier") or data.get("transaction_id") or ""
            charge_id = data.get("id")

            if not pix_code:
                logger.warning(f"SupremusPay: Sem pix_code na resposta")
                return {
                    'transaction_id': transaction_id or str(charge_id),
                    'pix_code': None,
                    'status': 'error',
                    'error': 'pix_code nao retornado pela API'
                }

            logger.info(f"SupremusPay: PIX gerado - ID: {transaction_id or charge_id}")

            return {
                'transaction_id': transaction_id or str(charge_id),
                'pix_code': pix_code,
                'qr_code_url': f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={pix_code}",
                'payment_id': payment_id,
                'qr_code_base64': data.get("pix_qr_image"),
                'expires_at': None,
                'status': 'pending',
                'error': None
            }

        except Exception as e:
            logger.error(f"SupremusPay generate_pix error: {e}")
            return {
                'transaction_id': None,
                'pix_code': None,
                'qr_code_url': None,
                'payment_id': payment_id,
                'qr_code_base64': None,
                'expires_at': None,
                'status': 'error',
                'error': str(e)
            }

    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        if not transaction_id:
            logger.error("SupremusPay: transaction_id vazio")
            return None

        data = self._request("GET", f"/charges/{transaction_id}")
        if not data:
            return None

        status_map = {
            "PENDING": "pending",
            "COMPLETED": "paid",
            "EXPIRED": "failed",
            "CANCELED": "failed",
            "REFUNDED": "refunded"
        }
        raw_status = data.get("status", "").upper()
        status = status_map.get(raw_status, "failed")

        amount_raw = data.get("amount_cents") or data.get("amount")
        amount = float(amount_raw) / 100.0 if amount_raw else None

        return {
            'transaction_id': transaction_id,
            'status': status,
            'gateway_transaction_id': transaction_id,
            'amount': amount,
            'payer_name': data.get("client_name"),
            'payer_document': data.get("client_document"),
            'end_to_end_id': None
        }

    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if "event" in data and "data" in data:
                event = data.get("event", "")
                charge = data.get("data", {})
            else:
                event = data.get("status", "")
                charge = data

            status_map = {
                "COMPLETED": "paid",
                "PENDING": "pending",
                "EXPIRED": "failed",
                "CANCELED": "failed",
                "REFUNDED": "refunded"
            }
            status = status_map.get(event.upper(), "pending")

            payment_id = charge.get("identifier") or charge.get("external_id") or ""
            transaction_id = charge.get("id") or charge.get("transaction_id") or ""
            amount_raw = charge.get("amount_cents") or charge.get("amount")
            amount = float(amount_raw) / 100.0 if amount_raw else None

            logger.info(f"SupremusPay Webhook: PaymentID: {payment_id}, Event: {event}, Status: {status}")

            return {
                'payment_id': payment_id,
                'status': status,
                'gateway_transaction_id': str(transaction_id),
                'amount': amount,
                'payer_name': charge.get("client_name"),
                'payer_document': charge.get("client_document"),
                'end_to_end_id': None
            }

        except Exception as e:
            logger.error(f"SupremusPay Webhook error: {e}")
            return None

    def verify_credentials(self) -> bool:
        if not self.api_key or len(self.api_key) < 10:
            logger.warning("SupremusPay: API key invalida (muito curta)")
            return False

        data = self._request("GET", "/charges?per_page=1")
        if data is not None:
            logger.info("SupremusPay: Credenciais validas")
            return True

        logger.warning("SupremusPay: Falha na verificacao de credenciais")
        return False

    def get_gateway_name(self) -> str:
        return "supremuspay"

    def get_gateway_type(self) -> str:
        return "supremuspay"

    def get_webhook_url(self) -> str:
        from flask import current_app
        return f"{current_app.config.get('BASE_URL', 'https://app.grimbots.online')}/webhook/payment/supremuspay"

    def cancel_transaction(self, transaction_id: str) -> Dict[str, Any]:
        logger.warning(f"SupremusPay: cancel_transaction nao implementado - ID: {transaction_id}")
        return {
            'transaction_id': transaction_id,
            'status': 'error',
            'gateway_transaction_id': transaction_id,
            'amount': None,
            'payer_name': None,
            'payer_document': None,
            'end_to_end_id': None,
            'error': 'Metodo nao implementado'
        }
