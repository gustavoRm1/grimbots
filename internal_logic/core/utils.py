"""
Core Utilities
==============
Funções utilitárias compartilhadas do núcleo da aplicação.
"""

import ipaddress
import logging
from typing import Any

from flask import request

logger = logging.getLogger(__name__)


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


def normalize_ip_to_ipv6(ip_address: str) -> str:
    """
    Normaliza endereço IP para IPv6 quando possível
    
    Args:
        ip_address: Endereço IP em formato string
        
    Returns:
        Endereço IP normalizado (IPv6 quando possível, senão original)
    """
    if not ip_address:
        return ip_address
    
    try:
        # Tentar converter para objeto IP
        ip = ipaddress.ip_address(ip_address)
        
        # Se for IPv4, tentar converter para IPv4-mapped IPv6
        if isinstance(ip, ipaddress.IPv4Address):
            ipv6_mapped = ipaddress.IPv6Address(int(ipaddress.IPv6Address("::ffff:0:0")) + int(ip))
            return str(ipv6_mapped)
        
        # Se já for IPv6, retornar como está
        return str(ip)
    except ValueError:
        # Não é um endereço IP válido, retornar original
        return ip_address
    except Exception as e:
        logger.warning(f"⚠️ Erro ao normalizar IP {ip_address}: {e}")
        return ip_address


def get_user_ip(request_obj=None, normalize_to_ipv6: bool = True):
    """
    Obtém o IP real do usuário (considerando Cloudflare e proxies)
    
    Args:
        request_obj: Objeto request (opcional, usa flask.request por padrão)
        normalize_to_ipv6: Se deve normalizar para IPv6
        
    Returns:
        Endereço IP do usuário
    """
    # Usar request_obj fornecido ou request global
    req = request_obj or request
    
    if not req:
        return None
    
    # Headers prioritários do Cloudflare
    cf_headers = [
        'CF-Connecting-IP',  # Cloudflare
        'X-Forwarded-For',   # Proxy reverso geral
        'X-Real-IP',         # Nginx proxy
    ]
    
    ip_address = None
    
    for header in cf_headers:
        value = req.headers.get(header)
        if value:
            if header == 'X-Forwarded-For':
                # Pegar o primeiro IP da lista (IP original)
                ip_address = value.split(',')[0].strip()
            else:
                ip_address = value
            break
    
    # Se não encontrou nos headers, usar remote_addr
    if not ip_address:
        ip_address = req.remote_addr
    
    if normalize_to_ipv6 and ip_address:
        ip_address = normalize_ip_to_ipv6(ip_address)
    
    return ip_address
