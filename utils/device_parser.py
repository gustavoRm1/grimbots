"""
Parser de User-Agent para extrair informações de device
Autor: Senior QI 502 + QI 500
"""

import re
from typing import Dict, Optional

def parse_user_agent(user_agent: str) -> Dict[str, Optional[str]]:
    """
    Extrai informações de device, OS e browser do user-agent
    
    Args:
        user_agent: String do User-Agent completo
    
    Returns:
        Dict com device_type, os_type, browser
    """
    if not user_agent:
        return {
            'device_type': 'unknown',
            'os_type': 'Unknown',
            'browser': 'Unknown'
        }
    
    device_type = 'desktop'
    os_type = 'Unknown'
    browser = 'Unknown'
    
    user_agent_lower = user_agent.lower()
    
    # ✅ DETECTAR DEVICE TYPE
    mobile_indicators = ['mobile', 'android', 'iphone', 'ipod', 'ipad', 'blackberry', 'windows phone']
    
    if any(indicator in user_agent_lower for indicator in mobile_indicators):
        device_type = 'mobile'
    
    # ✅ DETECTAR OS TYPE
    if 'iphone' in user_agent_lower:
        os_type = 'iOS'
    elif 'ipad' in user_agent_lower:
        os_type = 'iPadOS'
    elif 'android' in user_agent_lower:
        os_type = 'Android'
    elif 'windows' in user_agent_lower:
        os_type = 'Windows'
    elif 'linux' in user_agent_lower:
        os_type = 'Linux'
    elif 'mac' in user_agent_lower:
        os_type = 'macOS'
    elif 'ipad' in user_agent_lower:
        os_type = 'iPadOS'
    
    # ✅ DETECTAR BROWSER
    if 'chrome' in user_agent_lower and 'edg' not in user_agent_lower:
        browser = 'Chrome'
    elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
        browser = 'Safari'
    elif 'firefox' in user_agent_lower:
        browser = 'Firefox'
    elif 'edge' in user_agent_lower or 'edg' in user_agent_lower:
        browser = 'Edge'
    elif 'opera' in user_agent_lower or 'opr' in user_agent_lower:
        browser = 'Opera'
    elif 'brave' in user_agent_lower:
        browser = 'Brave'
    
    return {
        'device_type': device_type,
        'os_type': os_type,
        'browser': browser
    }

def parse_ip_to_location(ip_address: str) -> Dict[str, Optional[str]]:
    """
    Tenta inferir localização baseado no IP
    
    Args:
        ip_address: Endereço IP
    
    Returns:
        Dict com city, state, country
    """
    # TODO: Implementar integração com API de geolocalização
    # Opções: MaxMind GeoIP2, ipinfo.io, ip-api.com
    
    return {
        'city': 'Unknown',
        'state': 'Unknown',
        'country': 'BR'
    }

