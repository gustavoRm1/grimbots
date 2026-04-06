"""
Core Utilities
==============
Funções utilitárias compartilhadas do núcleo da aplicação.
"""

from typing import Any


def strip_surrogate_chars(value: Any) -> Any:
    """
    Remove caracteres surrogate inválidos de strings para evitar UnicodeEncodeError.
    
    Args:
        value: Valor a ser sanitizado (string ou estrutura aninhada)
        
    Returns:
        Valor sanitizado
    """
    if isinstance(value, str):
        try:
            return value.encode('utf-8', 'replace').decode('utf-8', 'replace')
        except Exception:
            return value
    return value


def sanitize_payload(payload: Any) -> Any:
    """
    Sanitiza estruturas (dict/list) removendo surrogates de todas as strings.
    
    Args:
        payload: Payload a ser sanitizado (dict, list, ou valor primitivo)
        
    Returns:
        Payload sanitizado
    """
    if isinstance(payload, dict):
        return {key: sanitize_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str):
        return strip_surrogate_chars(payload)
    return payload
