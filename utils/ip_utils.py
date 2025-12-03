"""
Utilities para manipulação de endereços IP
Suporte para IPv4 e IPv6 conforme recomendação Meta
"""
import ipaddress
import logging

logger = logging.getLogger(__name__)


def normalize_ip_to_ipv6(ip_address: str) -> str:
    """
    Normaliza endereço IP para IPv6 quando possível
    
    Meta recomenda IPv6 para melhor matching e durabilidade.
    Se o IP for IPv4, tenta converter para IPv6 mapeado (IPv4-mapped IPv6).
    
    Args:
        ip_address: Endereço IP (IPv4 ou IPv6)
    
    Returns:
        Endereço IPv6 ou IPv4 original se conversão falhar
    """
    if not ip_address:
        return ip_address
    
    try:
        # Tentar parsear como IPv6
        ip = ipaddress.ip_address(ip_address.strip())
        
        # Se já é IPv6, retornar como está
        if isinstance(ip, ipaddress.IPv6Address):
            logger.debug(f"✅ IP já é IPv6: {ip_address}")
            return str(ip)
        
        # Se é IPv4, converter para IPv6 mapeado (IPv4-mapped IPv6)
        if isinstance(ip, ipaddress.IPv4Address):
            ipv6_mapped = ipaddress.IPv6Address(f"::ffff:{ip}")
            logger.debug(f"✅ IPv4 convertido para IPv6 mapeado: {ip_address} -> {ipv6_mapped}")
            return str(ipv6_mapped)
        
    except ValueError as e:
        logger.warning(f"⚠️ Erro ao normalizar IP {ip_address}: {e}")
        return ip_address
    
    return ip_address


def get_user_ip_with_ipv6_support(request_obj=None):
    """
    Obtém o IP real do usuário com suporte para IPv6
    
    Prioridade:
    1. CF-Connecting-IP (Cloudflare - mais confiável, pode ser IPv6)
    2. True-Client-IP (Cloudflare alternativo)
    3. X-Forwarded-For (proxies genéricos - primeiro IP)
    4. X-Real-IP (nginx e outros)
    5. request.remote_addr (fallback direto)
    
    Retorna IPv6 quando possível (conforme recomendação Meta)
    """
    if request_obj is None:
        from flask import request
        request_obj = request
    
    ip_address = None
    
    # ✅ PRIORIDADE 1: Cloudflare CF-Connecting-IP (mais confiável, pode ser IPv6)
    cf_ip = request_obj.headers.get('CF-Connecting-IP')
    if cf_ip:
        ip_address = cf_ip.strip()
        logger.debug(f"✅ IP capturado do CF-Connecting-IP: {ip_address}")
    
    # ✅ PRIORIDADE 2: Cloudflare True-Client-IP (alternativo)
    if not ip_address:
        true_client_ip = request_obj.headers.get('True-Client-IP')
        if true_client_ip:
            ip_address = true_client_ip.strip()
            logger.debug(f"✅ IP capturado do True-Client-IP: {ip_address}")
    
    # ✅ PRIORIDADE 3: X-Forwarded-For (proxies genéricos - usar primeiro IP)
    if not ip_address:
        x_forwarded_for = request_obj.headers.get('X-Forwarded-For')
        if x_forwarded_for:
            # X-Forwarded-For pode ter múltiplos IPs separados por vírgula
            # O primeiro IP é o IP real do cliente
            first_ip = x_forwarded_for.split(',')[0].strip()
            if first_ip:
                ip_address = first_ip
                logger.debug(f"✅ IP capturado do X-Forwarded-For: {ip_address}")
    
    # ✅ PRIORIDADE 4: X-Real-IP (nginx e outros)
    if not ip_address:
        x_real_ip = request_obj.headers.get('X-Real-IP')
        if x_real_ip:
            ip_address = x_real_ip.strip()
            logger.debug(f"✅ IP capturado do X-Real-IP: {ip_address}")
    
    # ✅ PRIORIDADE 5: request.remote_addr (fallback direto)
    if not ip_address:
        if request_obj.remote_addr:
            ip_address = request_obj.remote_addr
            logger.debug(f"✅ IP capturado do remote_addr: {ip_address}")
    
    # ✅ NORMALIZAR PARA IPv6 (conforme recomendação Meta)
    if ip_address:
        ip_address = normalize_ip_to_ipv6(ip_address)
    
    return ip_address

