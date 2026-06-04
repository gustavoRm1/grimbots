"""
Payment Gateway Service
=======================
Operacoes de gateway de pagamento: verificacao de credenciais e processamento de webhooks.
Extraido do BotManager para isolamento e testabilidade.

Dependencias:
- GatewayFactory (factory pattern para gateways)
- Zero dependencia de BotManager
"""

import logging
from typing import Optional, Dict, Any

from gateways import GatewayFactory

logger = logging.getLogger(__name__)


def verify_gateway(gateway_type: str, credentials: Dict[str, Any]) -> bool:
    """Verifica credenciais de um gateway de pagamento usando Factory Pattern

    Args:
        gateway_type: Tipo do gateway (syncpay, pushynpay, paradise, etc)
        credentials: Credenciais do gateway

    Returns:
        True se credenciais forem validas
    """
    try:
        try:
            payment_gateway = GatewayFactory.create_gateway(
                gateway_type=gateway_type,
                credentials=credentials
            )
        except Exception as factory_error:
            logger.warning(f"Falha ao inicializar Factory para {gateway_type} (dado corrompido): {factory_error}")
            return False

        if not payment_gateway:
            logger.error(f"Erro ao criar gateway {gateway_type} para verificacao")
            return False

        is_valid = payment_gateway.verify_credentials()

        if is_valid:
            logger.info(f"Crendenciais {gateway_type} verificadas com sucesso")
        else:
            logger.error(f"Crendenciais {gateway_type} invalidas")

        return is_valid

    except Exception as e:
        logger.error(f"Erro ao verificar gateway {gateway_type}: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_payment_webhook(gateway_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Processa webhook de pagamento usando Factory Pattern

    Args:
        gateway_type: Tipo do gateway (syncpay, pushynpay, etc)
        data: Dados do webhook

    Returns:
        Dados processados do pagamento
    """
    try:
        dummy_credentials = {}

        if gateway_type == 'syncpay':
            dummy_credentials = {'client_id': 'dummy', 'client_secret': 'dummy'}
        elif gateway_type == 'pushynpay':
            dummy_credentials = {'api_key': 'dummy'}
        elif gateway_type == 'paradise':
            dummy_credentials = {
                'api_key': 'sk_dummy',
                'product_hash': 'prod_dummy',
                'offer_hash': 'dummyhash'
            }
        elif gateway_type == 'wiinpay':
            dummy_credentials = {
                'api_key': 'dummy',
                'split_user_id': 'dummy-user-id'
            }
        elif gateway_type == 'atomopay':
            dummy_credentials = {
                'api_token': 'dummy_token',
                'offer_hash': 'dummy_offer',
                'product_hash': 'dummy_product'
            }

        payment_gateway = GatewayFactory.create_gateway(
            gateway_type=gateway_type,
            credentials=dummy_credentials
        )

        if not payment_gateway:
            logger.error(f"Erro ao criar gateway {gateway_type} para webhook")
            return None

        return payment_gateway.process_webhook(data)

    except Exception as e:
        logger.error(f"Erro ao processar webhook {gateway_type}: {e}")
        import traceback
        traceback.print_exc()
        return None
