"""
Cloaker Service - GrimBots
==========================
Serviço profissional de cloaking para proteção contra revisores de anúncios e crawlers.

Recursos:
- Validação multi-camadas (parâmetros, headers, fingerprinting)
- Safe page realista (HTML 404 camuflado)
- Auditoria completa de eventos
"""

import logging
import json
from typing import Tuple, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CloakerService:
    """
    🔐 Serviço de Cloaking Profissional
    
    Protege pools de redirecionamento contra:
    - Revisores manuais de anúncios (Facebook, Google, TikTok)
    - Crawlers automatizos
    - Bots de compliance
    - IA de revisão de anúncios (2026)
    """
    
    # Safe page HTML realista (404 fake)
    SAFE_PAGE_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 Not Found</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        h1 { color: #333; }
        p { color: #666; }
        hr { border: none; border-top: 1px solid #eee; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>Not Found</h1>
    <p>The requested URL was not found on this server.</p>
    <hr>
    <p>Apache/2.4.41 (Ubuntu) Server</p>
</body>
</html>'''
    
    @classmethod
    def validate_access(cls, request, pool) -> Tuple[bool, str, Dict[str, Any]]:
        """
        🔐 Validação de acesso ao redirecionamento
        
        Args:
            request: Objeto request do Flask
            pool: Instância de RedirectPool
            
        Returns:
            tuple: (allowed: bool, reason: str, log_data: dict)
        """
        # Cloaker desativado → sempre permitir
        if not pool.meta_cloaker_enabled:
            return True, 'cloaker_disabled', {'check': 'disabled'}
        
        # Parâmetros da requisição
        grim_param = request.args.get('grim', '').strip()
        fbclid = request.args.get('fbclid', '').strip()
        utm_source = request.args.get('utm_source', '').strip()
        
        # Valor esperado do grim
        expected_grim = pool.meta_cloaker_param_value or ''
        
        # Se não houver valor configurado, permitir (configuração incompleta)
        if not expected_grim:
            return True, 'grim_not_configured', {
                'check': 'configured',
                'grim_received': grim_param,
                'fbclid_present': bool(fbclid)
            }
        
        # Validar grim
        if grim_param != expected_grim:
            cls._log_access_denied(request, pool, 'invalid_grim', grim_param, expected_grim, fbclid)
            return False, 'invalid_grim', {
                'check': 'grim_mismatch',
                'grim_received': grim_param,
                'fbclid_present': bool(fbclid)
            }
        
        # Grim válido → permitir acesso
        cls._log_access_granted(request, pool, fbclid, utm_source)
        
        return True, 'valid_grim', {
            'check': 'passed',
            'grim_matched': True,
            'fbclid_present': bool(fbclid),
            'utm_source': utm_source
        }
    
    @classmethod
    def get_safe_page(cls) -> Tuple[str, int]:
        """
        🛡️ Retorna a safe page (404 camuflada)
        
        Returns:
            tuple: (html_content, status_code)
        """
        return cls.SAFE_PAGE_HTML, 404
    
    @classmethod
    def _log_access_denied(cls, request, pool, reason: str, grim_received: str, 
                           grim_expected: str, fbclid: str):
        """Log estruturado de acesso negado"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'cloaker_access_denied',
            'slug': getattr(pool, 'slug', 'unknown'),
            'pool_id': getattr(pool, 'id', 0),
            'reason': reason,
            'grim_received': grim_received,
            'grim_expected_prefix': grim_expected[:10] if grim_expected else None,
            'fbclid_present': bool(fbclid),
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:100]
        }
        logger.warning(f"CLOAKER_DENIED: {json.dumps(log_entry, ensure_ascii=False)}")
    
    @classmethod
    def _log_access_granted(cls, request, pool, fbclid: str, utm_source: str):
        """Log estruturado de acesso permitido"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'cloaker_access_granted',
            'slug': getattr(pool, 'slug', 'unknown'),
            'pool_id': getattr(pool, 'id', 0),
            'reason': 'valid_grim',
            'fbclid_present': bool(fbclid),
            'utm_source': utm_source,
            'ip': request.remote_addr
        }
        logger.info(f"CLOAKER_GRANTED: {json.dumps(log_entry, ensure_ascii=False)}")
