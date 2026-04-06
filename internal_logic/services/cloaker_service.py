"""
Cloaker Service - GrimBots
==========================
Serviço profissional de cloaking para proteção contra revisores de anúncios e crawlers.

Recursos:
- Regra de Ouro: UTM x FBCLID (bloqueia UTMs sem fbclid)
- Detecção de 17+ crawlers (Facebook, Google, TikTok, etc)
- Safe page camuflada com status 200 (estratégia sênior)
- Auditoria completa de eventos
"""

import logging
import json
import re
from typing import Tuple, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CloakerService:
    """
    🔐 Serviço de Cloaking de Elite
    
    Protege pools de redirecionamento contra:
    - Revisores manuais de anúncios (Facebook, Google, TikTok)
    - Crawlers automatizos (17+ padrões)
    - Bots de compliance
    - IA de revisão de anúncios (2026)
    
    Estratégia Sênior: Retorna status 200 para safe page
    (faz bots acreditarem que a página é legítima)
    """
    
    # 17+ Padrões de crawlers/revisores
    CRAWLER_PATTERNS = [
        # Facebook
        'facebookexternalhit',
        'facebot',
        'fb_iab',
        'fb_ias',
        # Google
        'googlebot',
        'google-adsbot',
        'adsbot-google',
        'mediapartners-google',
        # TikTok
        'bytedance',
        'tiktok',
        # Microsoft
        'bingbot',
        'msnbot',
        # Outros
        'telegrambot',
        'whatsapp',
        'twitterbot',
        'linkedinbot',
        'pingdom',
        'GTmetrix',
        'semrush',
        'ahrefs',
        'mj12bot',
        'dotbot',
        'rogerbot',
    ]
    
    # Safe page HTML - Landing page legítima camuflada
    SAFE_PAGE_HTML = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Promoção Especial - Oferta Limitada</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 500px;
        }
        h1 { color: #333; margin-bottom: 20px; font-size: 28px; }
        p { color: #666; margin-bottom: 30px; line-height: 1.6; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 40px;
            border: none;
            border-radius: 50px;
            font-size: 18px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }
        .countdown {
            font-size: 14px;
            color: #999;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎉 Oferta Especial</h1>
        <p>Aproveite nossa promoção exclusiva por tempo limitado. Clique abaixo para participar.</p>
        <a href="#" class="btn">Quero Participar</a>
        <p class="countdown">⏰ Oferta termina em 2h 34m</p>
    </div>
</body>
</html>'''
    
    @classmethod
    def validate_access(cls, request, pool) -> Tuple[bool, str, Dict[str, Any]]:
        """
        🔐 Validação de acesso ao redirecionamento (Elite Edition)
        
        Regras:
        1. Detecção de crawlers (17+ padrões)
        2. Regra de Ouro: UTM sem FBCLID = bloqueio
        3. Validação do parâmetro grim (formato chave ou chave=valor)
        
        Args:
            request: Objeto request do Flask
            pool: Instância de RedirectPool
            
        Returns:
            tuple: (allowed: bool, reason: str, log_data: dict)
        """
        # Cloaker desativado → sempre permitir
        if not getattr(pool, 'meta_cloaker_enabled', False):
            return True, 'cloaker_disabled', {'check': 'disabled'}
        
        # Coletar dados da requisição
        user_agent = request.headers.get('User-Agent', '').lower()
        grim_param = request.args.get('grim', '').strip()
        fbclid = request.args.get('fbclid', '').strip()
        utm_source = request.args.get('utm_source', '').strip()
        utm_medium = request.args.get('utm_medium', '').strip()
        utm_campaign = request.args.get('utm_campaign', '').strip()
        referrer = request.headers.get('Referer', '').lower()
        
        # Verificar se UTMs estão presentes (qualquer um)
        has_utms = any([utm_source, utm_medium, utm_campaign])
        has_fbclid = bool(fbclid)
        
        # ═══════════════════════════════════════════════════════════
        # 1. DETECÇÃO DE CRAWLERS (17+ padrões)
        # ═══════════════════════════════════════════════════════════
        if cls._is_crawler(user_agent, referrer):
            cls._log_access_denied(request, pool, 'crawler_detected', grim_param, '', fbclid)
            return False, 'crawler_detected', {
                'check': 'crawler',
                'user_agent': user_agent[:100]
            }
        
        # ═══════════════════════════════════════════════════════════
        # 2. REGRA DE OURO: UTM x FBCLID
        # Se há UTMs mas não há fbclid → bloquear (revisor manual)
        # ═══════════════════════════════════════════════════════════
        if has_utms and not has_fbclid:
            cls._log_access_denied(request, pool, 'missing_fbclid_with_utm', grim_param, '', fbclid)
            return False, 'missing_fbclid_with_utm', {
                'check': 'utm_fbclid',
                'has_utms': True,
                'has_fbclid': False,
                'utm_source': utm_source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign
            }
        
        # ═══════════════════════════════════════════════════════════
        # 3. VALIDAÇÃO DO PARÂMETRO GRIM
        # Suporta: ?grim=valor ou ?grim (chave pura)
        # ═══════════════════════════════════════════════════════════
        expected_grim = getattr(pool, 'meta_cloaker_param_value', '') or ''
        
        # Se não houver valor configurado, permitir (configuração incompleta)
        if not expected_grim:
            return True, 'grim_not_configured', {
                'check': 'configured',
                'grim_received': grim_param,
                'fbclid_present': has_fbclid
            }
        
        # Validar grim (suporta chave pura ou chave=valor)
        grim_valid = cls._validate_grim(grim_param, expected_grim, request)
        
        if not grim_valid:
            cls._log_access_denied(request, pool, 'invalid_grim', grim_param, expected_grim, fbclid)
            return False, 'invalid_grim', {
                'check': 'grim_mismatch',
                'grim_received': grim_param,
                'fbclid_present': has_fbclid
            }
        
        # ═══════════════════════════════════════════════════════════
        # 4. ACESSO PERMITIDO
        # ═══════════════════════════════════════════════════════════
        cls._log_access_granted(request, pool, fbclid, utm_source)
        
        return True, 'valid_grim', {
            'check': 'passed',
            'grim_matched': True,
            'fbclid_present': has_fbclid,
            'utm_source': utm_source
        }
    
    @classmethod
    def _is_crawler(cls, user_agent: str, referrer: str) -> bool:
        """
        🤖 Detecta crawlers/revisores por User-Agent e Referrer
        
        17+ padrões de detecção
        """
        combined = f"{user_agent} {referrer}"
        
        for pattern in cls.CRAWLER_PATTERNS:
            if pattern.lower() in combined:
                logger.debug(f"🤖 Crawler detectado: {pattern}")
                return True
        
        return False
    
    @classmethod
    def _validate_grim(cls, grim_received: str, expected_grim: str, request) -> bool:
        """
        🔑 Valida o parâmetro grim nos dois formatos:
        - Formato 1: ?grim=valor (chave=valor)
        - Formato 2: ?grim (chave pura, verifica se existe no query string)
        """
        # Se expected_grim contém '=' é formato chave=valor
        if '=' in expected_grim:
            expected_key, expected_val = expected_grim.split('=', 1)
            received_key, received_val = grim_received.split('=', 1) if '=' in grim_received else (grim_received, '')
            return received_key.strip() == expected_key.strip() and received_val.strip() == expected_val.strip()
        
        # Formato chave pura: verificar se grim existe no query string
        if expected_grim and grim_received:
            return grim_received == expected_grim
        
        # Verificar se 'grim' está presente como chave pura na URL
        if 'grim' in request.args:
            return True
        
        return False
    
    @classmethod
    def get_safe_page(cls) -> Tuple[str, int]:
        """
        🛡️ Retorna a safe page camuflada
        
        Estratégia Sênior: Status 200 (não 403/404)
        Faz bots acreditarem que é uma página legítima
        
        Returns:
            tuple: (html_content, status_code)
        """
        return cls.SAFE_PAGE_HTML, 200
    
    @classmethod
    def increment_blocked_counter(cls, pool_id: int) -> bool:
        """
        ➕ Incrementa contador de acessos bloqueados atomicamente
        
        Args:
            pool_id: ID do RedirectPool
            
        Returns:
            bool: True se sucesso
        """
        try:
            from internal_logic.core.extensions import db
            from sqlalchemy import text
            
            sql = text("""
                UPDATE redirect_pools 
                SET total_blocked_accesses = COALESCE(total_blocked_accesses, 0) + 1,
                    updated_at = NOW()
                WHERE id = :pool_id
            """)
            
            db.session.execute(sql, {'pool_id': pool_id})
            db.session.commit()
            
            logger.debug(f"🛡️ Bloqueio registrado: pool={pool_id}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Falha ao registrar bloqueio: {e}")
            try:
                from internal_logic.core.extensions import db
                db.session.rollback()
            except:
                pass
            return False
    
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
        
        # Incrementar contador de bloqueios
        cls.increment_blocked_counter(getattr(pool, 'id', 0))
    
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
