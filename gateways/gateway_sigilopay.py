import logging
import re
import random
import hashlib
import time
import csv
import os
import requests
from typing import Dict, Optional, Any
from .gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)

# ===== KYC: Cache de identidades do CSV (mesmo padrão Paradise) =====
_VALID_IDENTITIES_CACHE = []
_VALID_CPFS_FALLBACK = [
    '56657477007', '06314127513', '25214446772',
    '27998261321', '09553238602', '48317801896',
    '21540970817', '21996866900', '15721994746'
]


def _load_identities_if_needed():
    global _VALID_IDENTITIES_CACHE
    if not _VALID_IDENTITIES_CACHE:
        try:
            csv_path = os.path.join(os.path.dirname(__file__), 'cpf_nome_formatado.csv')
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        _VALID_IDENTITIES_CACHE.append({'cpf': row[0].strip(), 'nome': row[1].strip()})
            logger.info(f"KYC SigiloPay: {len(_VALID_IDENTITIES_CACHE)} identidades carregadas")
        except Exception as e:
            logger.error(f"KYC SigiloPay erro: {e}")


def _sortear_identidade() -> tuple:
    """Retorna (nome, cpf_somente_digitos)."""
    _load_identities_if_needed()
    if _VALID_IDENTITIES_CACHE:
        identity = random.choice(_VALID_IDENTITIES_CACHE)
        return identity['nome'], re.sub(r'\D', '', identity['cpf'])
    cpf = random.choice(_VALID_CPFS_FALLBACK)
    return "Cliente Padrão", cpf


class SigiloPayGateway(PaymentGateway):

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://app.sigilopay.com.br/api/v1"

        self.headers = {
            "x-public-key": self.api_key,
            "x-secret-key": self.secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        logger.info("SigiloPay Gateway inicializado")

    def generate_pix(
        self,
        amount: float,
        description: str,
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            logger.info(f"SigiloPay: Gerando PIX - Amount: {amount}, PaymentID: {payment_id}")

            amount_cents = int(amount * 100)

            real_name, real_cpf = _sortear_identidade()
            timestamp_ms = int(time.time() * 1000)
            unique_hash = hashlib.md5(f"{payment_id}_{timestamp_ms}".encode()).hexdigest()[:8]

            first_name = real_name.split()[0].lower() if ' ' in real_name else real_name.lower()
            cpf_last4 = real_cpf[-4:]
            unique_email = f"{first_name}{cpf_last4}@gmail.com"
            unique_name = real_name[:30] if len(real_name) > 30 else real_name

            digits = re.sub(r'\D', '', f"11{unique_hash}{cpf_last4}")
            unique_phone = "+" + digits[:13]

            formatted_cpf = f"{real_cpf[:3]}.{real_cpf[3:6]}.{real_cpf[6:9]}-{real_cpf[9:]}"

            client = {
                "name": unique_name,
                "email": unique_email,
                "cpf": formatted_cpf,
                "phone": unique_phone
            }

            prod_id = str(payment_id)[:20] or "prod-grimbots"

            payload = {
                "identifier": str(payment_id),
                "amount": amount_cents,
                "client": client,
                "products": [
                    {
                        "id": prod_id,
                        "name": description or "Produto Digital Grimbots",
                        "price": amount_cents,
                        "title": description or "Produto Digital Grimbots",
                        "value": amount_cents,
                        "amount": 1
                    }
                ],
                "callbackUrl": self.get_webhook_url()
            }

            logger.debug(f"SigiloPay Payload: {payload}")

            url = f"{self.base_url}/gateway/pix/receive"
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)

            logger.info(f"SigiloPay Resposta: Status {response.status_code}")

            if response.status_code not in [200, 201]:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"SigiloPay: Erro na resposta - {error_msg}")
                return {
                    'transaction_id': None,
                    'pix_code': None,
                    'qr_code_url': None,
                    'payment_id': payment_id,
                    'qr_code_base64': None,
                    'expires_at': None,
                    'status': 'error',
                    'error': f'Erro na API: {error_msg}'
                }

            try:
                response_data = response.json()
                logger.debug(f"SigiloPay Resposta JSON: {response_data}")

                transaction_id = response_data.get("transactionId")
                pix = response_data.get("pix", {})
                pix_code = pix.get("code")
                pix_image = pix.get("image")

                if not transaction_id:
                    error_msg = "transactionId nao encontrado na resposta"
                    logger.error(f"SigiloPay: {error_msg}")
                    return {
                        'transaction_id': None,
                        'pix_code': pix_code,
                        'status': 'error',
                        'error': error_msg
                    }

                if not pix_code:
                    error_msg = "pix.code nao encontrado na resposta"
                    logger.error(f"SigiloPay: {error_msg}")
                    return {
                        'transaction_id': transaction_id,
                        'pix_code': None,
                        'status': 'error',
                        'error': error_msg
                    }

                logger.info(f"SigiloPay: PIX gerado - TransactionID: {transaction_id}")

                return {
                    'transaction_id': transaction_id,
                    'pix_code': pix_code,
                    'qr_code_url': f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={pix_code}",
                    'payment_id': payment_id,
                    'qr_code_base64': pix_image,
                    'expires_at': None,
                    'status': 'pending',
                    'error': None
                }

            except ValueError as e:
                error_msg = f"Erro ao parsear JSON: {str(e)}"
                logger.error(f"SigiloPay: {error_msg}")
                return {
                    'transaction_id': None,
                    'pix_code': None,
                    'qr_code_url': None,
                    'payment_id': payment_id,
                    'qr_code_base64': None,
                    'expires_at': None,
                    'status': 'error',
                    'error': error_msg
                }

        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout na requisicao a API SigiloPay: {str(e)}"
            logger.error(f"SigiloPay: {error_msg}")
            return {
                'transaction_id': None,
                'pix_code': None,
                'qr_code_url': None,
                'payment_id': payment_id,
                'qr_code_base64': None,
                'expires_at': None,
                'status': 'error',
                'error': error_msg
            }

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Erro de conexao com a API SigiloPay: {str(e)}"
            logger.error(f"SigiloPay: {error_msg}")
            return {
                'transaction_id': None,
                'pix_code': None,
                'qr_code_url': None,
                'payment_id': payment_id,
                'qr_code_base64': None,
                'expires_at': None,
                'status': 'error',
                'error': error_msg
            }

        except Exception as e:
            error_msg = f"Erro inesperado na API SigiloPay: {str(e)}"
            logger.error(f"SigiloPay: {error_msg}")
            return {
                'transaction_id': None,
                'pix_code': None,
                'qr_code_url': None,
                'payment_id': payment_id,
                'qr_code_base64': None,
                'expires_at': None,
                'status': 'error',
                'error': error_msg
            }

    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        try:
            if not transaction_id:
                logger.error("SigiloPay: transaction_id vazio na consulta de status")
                return None

            url = f"{self.base_url}/gateway/transactions"
            params = {"id": transaction_id}

            logger.info(f"SigiloPay: Consultando status - TransactionID: {transaction_id}")

            resp = requests.get(url, params=params, headers=self.headers, timeout=15)

            if resp.status_code != 200:
                logger.warning(f"SigiloPay CHECK {resp.status_code}: {resp.text[:200]}")
                return None

            try:
                data = resp.json()
            except ValueError:
                logger.warning(f"SigiloPay: Resposta nao e JSON valido: {resp.text[:200]}")
                return None

            status_raw = data.get("status", "").upper()
            amount = data.get("amount")

            if amount:
                amount = amount / 100.0

            logger.info(f"SigiloPay: Status bruto: {status_raw}")

            status = None
            if status_raw == "PAID":
                status = "paid"
            elif status_raw == "PENDING":
                status = "pending"
            elif status_raw in ["REFUNDED", "CHARGED_BACK"]:
                status = "refunded"
            elif status_raw == "CANCELED":
                status = "failed"
            else:
                status = "failed"

            return {
                'transaction_id': transaction_id,
                'status': status,
                'gateway_transaction_id': transaction_id,
                'amount': amount,
                'payer_name': None,
                'payer_document': None,
                'end_to_end_id': None
            }

        except requests.exceptions.Timeout:
            logger.error(f"SigiloPay: Timeout na consulta de status - TransactionID: {transaction_id}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"SigiloPay: Erro de conexao na consulta de status - TransactionID: {transaction_id}")
            return None
        except Exception as e:
            logger.error(f"SigiloPay: Erro na consulta de status: {e} - TransactionID: {transaction_id}")
            return None

    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            event = data.get("event")
            transaction = data.get("transaction", {})
            token = data.get("token")

            payment_id = transaction.get("identifier")
            transaction_id = transaction.get("id")

            if not payment_id or not event:
                logger.warning(f"SigiloPay Webhook: Payload incompleto - event: {event}, payment_id: {payment_id}")
                return None

            status_mapping = {
                "TRANSACTION_PAID": "paid",
                "TRANSACTION_REFUNDED": "refunded",
                "TRANSACTION_CHARGED_BACK": "refunded",
                "TRANSACTION_CANCELED": "failed",
                "TRANSACTION_CREATED": "pending"
            }

            status = status_mapping.get(event, "pending")

            logger.info(f"SigiloPay Webhook: Processado - PaymentID: {payment_id}, Event: {event}, Status: {status}")

            amount_raw = transaction.get('amount')
            amount = float(amount_raw) / 100.0 if amount_raw is not None else None

            client_info = data.get('client') or transaction.get('client') or {}
            payer_name = client_info.get('name') if isinstance(client_info, dict) else None
            payer_doc = None
            if isinstance(client_info, dict):
                payer_doc = client_info.get('cpf') or client_info.get('cnpj')
            end_to_end = None
            if isinstance(transaction.get('pixInformation'), dict):
                end_to_end = transaction['pixInformation'].get('endToEndId')

            return {
                'payment_id': payment_id,
                'status': status,
                'gateway_transaction_id': transaction_id,
                'amount': amount,
                'payer_name': payer_name,
                'payer_document': payer_doc,
                'end_to_end_id': end_to_end
            }

        except Exception as e:
            logger.error(f"SigiloPay Webhook: Erro ao processar: {e}")
            return None

    def verify_credentials(self) -> bool:
        if not self.api_key or len(self.api_key) < 5:
            logger.warning("SigiloPay: x-public-key invalida (muito curta ou vazia)")
            return False

        if not self.secret_key or len(self.secret_key) < 5:
            logger.warning("SigiloPay: x-secret-key invalida (muito curta ou vazia)")
            return False

        logger.info("SigiloPay: Credenciais validas (verificacao de formato)")
        return True

    def get_gateway_name(self) -> str:
        return "sigilopay"

    def get_gateway_type(self) -> str:
        return "sigilopay"

    def get_webhook_url(self) -> str:
        from flask import current_app
        return f"{current_app.config.get('BASE_URL', 'https://app.grimbots.online')}/webhook/payment/sigilopay"

    def cancel_transaction(self, transaction_id: str) -> Dict[str, Any]:
        logger.warning(f"SigiloPay: cancel_transaction nao implementado - TransactionID: {transaction_id}")
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


def create_sigilopay_gateway(api_key: str, secret_key: str) -> SigiloPayGateway:
    return SigiloPayGateway(api_key=api_key, secret_key=secret_key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        gateway = create_sigilopay_gateway("test_public_key", "test_secret_key")
        logger.info("Gateway SigiloPay criado com sucesso")
        result = gateway.generate_pix(10.50, "Teste", "test_payment_123")
        logger.info(f"Teste result: {result}")
    except Exception as e:
        logger.error(f"Erro no teste: {str(e)}")
