"""
Meta Token Validator
====================
Valida access_token do Meta CAPI usando endpoint debug_token.
Extraído de celery_app.py para ser usado por múltiplos clientes CAPI.
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)

META_API_VERSION = "v19.0"
DEBUG_TOKEN_URL = f"https://graph.facebook.com/{META_API_VERSION}/debug_token"
REQUEST_TIMEOUT = 10


def validate_meta_token(access_token: str) -> bool:
    """
    Valida token de acesso do Meta usando endpoint debug_token.

    Usa endpoint oficial de debug do Meta com validação robusta.
    """
    try:
        params = {
            'input_token': access_token,
            'access_token': access_token,
        }

        response = requests.get(DEBUG_TOKEN_URL, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            token_data = data.get('data', {})

            is_valid = token_data.get('is_valid', False)
            expires_at = token_data.get('expires_at', 0)

            if expires_at > 0 and expires_at < time.time():
                return False

            return is_valid
        else:
            return False

    except Exception as e:
        logger.error(f"Erro ao validar token Meta: {e}")
        return False


REQUIRED_EVENT_FIELDS = ['event_name', 'event_time', 'action_source']


def validate_event_data(event_data: dict) -> tuple[bool, Optional[str]]:
    """Valida campos obrigatórios do event_data para Meta CAPI.

    Returns:
        (True, None) se válido
        (False, mensagem_de_erro) se inválido
    """
    for field in REQUIRED_EVENT_FIELDS:
        if not event_data.get(field):
            return False, f"Campo obrigatório ausente: {field}"

    user_data = event_data.get('user_data')
    if user_data is not None and not isinstance(user_data, dict):
        return False, "user_data deve ser dict"

    return True, None
