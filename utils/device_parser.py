"""
Parser de User-Agent para extrair informações de device
Autor: Senior QI 502 + QI 500
"""

import re
from typing import Dict, Optional

def parse_user_agent(user_agent: str) -> Dict[str, Optional[str]]:
    """
    Extrai informações de device, OS, browser e modelo do dispositivo do user-agent
    
    Args:
        user_agent: String do User-Agent completo
    
    Returns:
        Dict com device_type, os_type, browser, device_model
    """
    if not user_agent:
        return {
            'device_type': 'unknown',
            'os_type': 'Unknown',
            'browser': 'Unknown',
            'device_model': None
        }
    
    device_type = 'desktop'
    os_type = 'Unknown'
    browser = 'Unknown'
    device_model = None
    
    user_agent_lower = user_agent.lower()
    
    # ✅ DETECTAR DEVICE TYPE
    mobile_indicators = ['mobile', 'android', 'iphone', 'ipod', 'ipad', 'blackberry', 'windows phone']
    
    if any(indicator in user_agent_lower for indicator in mobile_indicators):
        device_type = 'mobile'
    
    # ✅ DETECTAR iOS E MODELO DE iPhone
    if 'iphone' in user_agent_lower:
        os_type = 'iOS'
        device_type = 'mobile'
        # Extrair modelo do iPhone do User-Agent
        # Exemplos: "iPhone14,2" → iPhone 13 Pro, "iPhone15,3" → iPhone 14 Pro Max
        iphone_model_match = re.search(r'iphone(\d+),(\d+)', user_agent_lower)
        if iphone_model_match:
            identifier = f"{iphone_model_match.group(1)},{iphone_model_match.group(2)}"
            device_model = _get_iphone_model(identifier)
        else:
            # Fallback: tentar identificar por outros padrões
            if 'iphone os 17' in user_agent_lower or 'iphone os 18' in user_agent_lower:
                device_model = 'iPhone 15 Pro'
            elif 'iphone os 16' in user_agent_lower:
                device_model = 'iPhone 14 Pro'
            elif 'iphone os 15' in user_agent_lower:
                device_model = 'iPhone 13'
            else:
                device_model = 'iPhone'
    
    # ✅ DETECTAR iPad
    elif 'ipad' in user_agent_lower:
        os_type = 'iPadOS'
        device_type = 'mobile'
        device_model = 'iPad'
    
    # ✅ DETECTAR ANDROID E MODELO
    elif 'android' in user_agent_lower:
        os_type = 'Android'
        device_type = 'mobile'
        device_model = _get_android_model(user_agent)
    
    # ✅ DETECTAR WINDOWS
    elif 'windows' in user_agent_lower:
        os_type = 'Windows'
        if 'mobile' in user_agent_lower:
            device_type = 'mobile'
    
    # ✅ DETECTAR LINUX
    elif 'linux' in user_agent_lower:
        os_type = 'Linux'
    
    # ✅ DETECTAR macOS
    elif 'mac' in user_agent_lower:
        os_type = 'macOS'
        device_type = 'desktop'
    
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
        'browser': browser,
        'device_model': device_model
    }


def _get_iphone_model(identifier: str) -> str:
    """
    Converte identificador do iPhone em nome do modelo
    
    Fonte: https://www.theiphonewiki.com/wiki/Models
    """
    iphone_models = {
        # iPhone 15 série
        '15,4': 'iPhone 15',
        '15,5': 'iPhone 15 Plus',
        '16,1': 'iPhone 15 Pro',
        '16,2': 'iPhone 15 Pro Max',
        # iPhone 14 série
        '14,7': 'iPhone 14',
        '14,8': 'iPhone 14 Plus',
        '15,2': 'iPhone 14 Pro',
        '15,3': 'iPhone 14 Pro Max',
        # iPhone 13 série
        '14,2': 'iPhone 13',
        '14,3': 'iPhone 13 mini',
        '14,4': 'iPhone 13 Pro',
        '14,5': 'iPhone 13 Pro Max',
        # iPhone 12 série
        '13,1': 'iPhone 12 mini',
        '13,2': 'iPhone 12',
        '13,3': 'iPhone 12 Pro',
        '13,4': 'iPhone 12 Pro Max',
        # iPhone 11 série
        '12,1': 'iPhone 11',
        '12,3': 'iPhone 11 Pro',
        '12,5': 'iPhone 11 Pro Max',
        # iPhone XS/XS Max/XR
        '11,2': 'iPhone XS',
        '11,4': 'iPhone XS Max',
        '11,8': 'iPhone XR',
        # iPhone X
        '10,3': 'iPhone X',
        '10,6': 'iPhone X',
    }
    return iphone_models.get(identifier, 'iPhone')


def _get_android_model(user_agent: str) -> str:
    """
    Extrai modelo do Android do User-Agent
    
    Exemplos de padrões:
    - "SM-S918B" (Samsung Galaxy S23 Ultra)
    - "22111317G" (Xiaomi 13)
    - "Pixel 7" (Google Pixel)
    - "CPH2451" (OnePlus)
    """
    user_agent_upper = user_agent.upper()
    
    # Samsung
    samsung_match = re.search(r'SM-([A-Z0-9]+)', user_agent_upper)
    if samsung_match:
        model_code = samsung_match.group(1)
        return _get_samsung_model(model_code)
    
    # Xiaomi/Redmi - padrão comum: números seguidos de letra
    xiaomi_match = re.search(r'(\d{8}[A-Z])|(MI\s+\d+)|(REDMI\s+\w+)', user_agent_upper)
    if xiaomi_match:
        model = xiaomi_match.group(0)
        if 'MI ' in model or 'REDMI' in model:
            return model.replace('MI ', 'Xiaomi ').replace('REDMI', 'Redmi')
        # Códigos numéricos do Xiaomi são difíceis de mapear sem base de dados
        return 'Xiaomi'
    
    # Google Pixel
    if 'PIXEL' in user_agent_upper:
        pixel_match = re.search(r'PIXEL\s+(\d+)', user_agent_upper)
        if pixel_match:
            return f'Pixel {pixel_match.group(1)}'
        return 'Pixel'
    
    # OnePlus
    if 'ONEPLUS' in user_agent_upper or re.search(r'CPH\d+', user_agent_upper):
        oneplus_match = re.search(r'(ONE\s*PLUS\s*\w+)|(CPH\d+)', user_agent_upper)
        if oneplus_match:
            model = oneplus_match.group(0)
            if 'CPH' in model:
                return 'OnePlus'
            return model.replace('ONE PLUS', 'OnePlus').replace(' ', '')
        return 'OnePlus'
    
    # Motorola
    if 'MOTO' in user_agent_upper:
        moto_match = re.search(r'MOTO\s+(\w+)', user_agent_upper)
        if moto_match:
            return f'Moto {moto_match.group(1)}'
        return 'Motorola'
    
    # LG
    if 'LM-' in user_agent_upper:
        lg_match = re.search(r'LM-([A-Z0-9]+)', user_agent_upper)
        if lg_match:
            return 'LG'
    
    # Se não identificou, tenta extrair qualquer padrão de modelo comum
    model_match = re.search(r'(\w+\s*\d+[A-Z]?)', user_agent_upper)
    if model_match and len(model_match.group(1)) < 30:
        return model_match.group(1)
    
    return 'Android'


def _get_samsung_model(code: str) -> str:
    """
    Mapeia código Samsung para nome do modelo
    
    Fonte aproximada baseada em padrões comuns
    """
    # Samsung Galaxy S23 série
    if code.startswith('S918'):
        return 'Galaxy S23 Ultra'
    if code.startswith('S911'):
        return 'Galaxy S23'
    if code.startswith('S916'):
        return 'Galaxy S23+'
    
    # Samsung Galaxy S22 série
    if code.startswith('S908'):
        return 'Galaxy S22 Ultra'
    if code.startswith('S901'):
        return 'Galaxy S22'
    if code.startswith('S906'):
        return 'Galaxy S22+'
    
    # Samsung Galaxy S21 série
    if code.startswith('G998'):
        return 'Galaxy S21 Ultra'
    if code.startswith('G991'):
        return 'Galaxy S21'
    if code.startswith('G996'):
        return 'Galaxy S21+'
    
    # Samsung Galaxy Note
    if code.startswith('N98'):
        return 'Galaxy Note'
    
    # Samsung Galaxy A série (modelos populares)
    if code.startswith('A54'):
        return 'Galaxy A54'
    if code.startswith('A34'):
        return 'Galaxy A34'
    if code.startswith('A14'):
        return 'Galaxy A14'
    
    # Samsung Galaxy M série
    if code.startswith('M54'):
        return 'Galaxy M54'
    if code.startswith('M34'):
        return 'Galaxy M34'
    
    # Se não encontrou, retorna código genérico
    return f'Samsung {code}'

def parse_ip_to_location(ip_address: str) -> Dict[str, Optional[str]]:
    """
    Tenta inferir localização baseado no IP usando ip-api.com (GRATUITA)
    
    Args:
        ip_address: Endereço IP
    
    Returns:
        Dict com city, state, country
    """
    if not ip_address:
        return {
            'city': 'Unknown',
            'state': 'Unknown',
            'country': 'BR'
        }
    
    try:
        import requests
        import time
        
        # API gratuita ip-api.com (15 req/min = suficiente)
        # https://ip-api.com/docs/api:json
        response = requests.get(
            f'http://ip-api.com/json/{ip_address}',
            timeout=2,  # Max 2 segundos para não bloquear
            headers={'User-Agent': 'GrimbotsAnalytics/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return {
                    'city': data.get('city', 'Unknown'),
                    'state': data.get('regionName', 'Unknown'),
                    'country': data.get('countryCode', 'BR')
                }
        
        # Rate limit ou erro - esperar e retornar default
        return {
            'city': 'Unknown',
            'state': 'Unknown',
            'country': 'BR'
        }
        
    except Exception as e:
        # Em caso de erro, retornar defaults
        return {
            'city': 'Unknown',
            'state': 'Unknown',
            'country': 'BR'
        }

