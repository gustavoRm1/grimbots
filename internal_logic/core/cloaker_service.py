"""
🔐 CLOAKER SERVICE V2.0
Módulo de Defesa e Camuflagem contra crawlers/bots

Extraído de: app.py (linhas 6377-6467, 6540-6570, 6631-6666)
Responsabilidade: Validação multicamadas, detecção de crawlers, safe page
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from flask import Request
import logging

logger = logging.getLogger(__name__)


@dataclass
class CloakerValidationResult:
    """Resultado da validação do Cloaker"""
    allowed: bool
    reason: str
    score: int
    details: Dict[str, Any]
    should_log: bool = True


class CloakerService:
    """
    🔐 CLOAKER V2.0 - À PROVA DE BURRICE HUMANA + PROTEÇÃO FACEBOOK
    
    REGRAS DE SEGURANÇA:
    1. Parâmetro grim obrigatório e válido
    2. fbclid OBRIGATÓRIO se tiver UTMs (tráfego de campanha = precisa de ID do Facebook)
    3. Permite testes diretos sem fbclid (se não tiver UTMs)
    4. Aceita qualquer ordem de parâmetros
    5. SEM validação de User-Agent (Facebook pode usar qualquer UA)
    """
    
    # Lista completa de padrões de crawlers/bots
    CRAWLER_PATTERNS: List[str] = [
        'facebookexternalhit',
        'facebot',
        'telegrambot',
        'whatsapp',
        'python-requests',
        'curl',
        'wget',
        'bot',
        'crawler',
        'spider',
        'scraper',
        'googlebot',
        'bingbot',
        'slurp',
        'duckduckbot',
        'baiduspider',
        'yandexbot',
        'sogou',
        'exabot',
        'ia_archiver'
    ]
    
    # Parâmetros UTM que indicam tráfego de campanha
    UTM_PARAMS: List[str] = [
        'utm_source',
        'utm_campaign',
        'utm_medium',
        'utm_content',
        'utm_term'
    ]
    
    def __init__(self, pool_config: Optional[Dict[str, Any]] = None):
        """
        Inicializa o serviço Cloaker
        
        Args:
            pool_config: Configurações do pool (meta_cloaker_enabled, meta_cloaker_param_value, etc.)
        """
        self.pool_config = pool_config or {}
        self.cloaker_enabled = self.pool_config.get('meta_cloaker_enabled', False)
        self.param_name = self.pool_config.get('meta_cloaker_param_name', 'grim')
        self.expected_value = (self.pool_config.get('meta_cloaker_param_value') or '').strip()
    
    def validate_access(self, request: Request) -> CloakerValidationResult:
        """
        Validação principal do Cloaker V2.0
        
        Args:
            request: Objeto Request do Flask
            
        Returns:
            CloakerValidationResult com allowed=True/False e metadados
        """
        # Verificar se cloaker está habilitado
        if not self.cloaker_enabled:
            return CloakerValidationResult(
                allowed=True,
                reason='cloaker_disabled',
                score=100,
                details={'message': 'Cloaker desativado para este pool'}
            )
        
        # Verificar se valor esperado está configurado
        if not self.expected_value:
            logger.error("🚨 CLOAKER MISCONFIGURED: meta_cloaker_param_value vazio")
            return CloakerValidationResult(
                allowed=False,
                reason='cloaker_misconfigured',
                score=0,
                details={'error': 'Valor do parâmetro grim não configurado'}
            )
        
        start_time = time.time()
        
        # ✅ CLOAKER V2.0: Busca o parâmetro grim de DUAS FORMAS
        actual_value = self._extract_grim_value(request)
        
        # Verificar presença de parâmetros UTM
        has_utm_params = self._has_utm_params(request)
        
        # Extrair fbclid
        fbclid = request.args.get('fbclid', '').strip()
        
        # Construir detalhes
        details = {
            'param_name': self.param_name,
            'expected_value': self.expected_value,
            'actual_value': actual_value,
            'has_utm_params': has_utm_params,
            'fbclid_present': bool(fbclid),
            'fbclid_value': fbclid[:50] if fbclid else None,
            'request_url': request.url,
            'user_agent': request.headers.get('User-Agent', ''),
            'latency_ms': 0
        }
        
        # VALIDAÇÃO CRÍTICA 1: grim deve estar presente e correto
        if actual_value != self.expected_value:
            details['validation_step'] = 'invalid_grim'
            details['latency_ms'] = int((time.time() - start_time) * 1000)
            
            return CloakerValidationResult(
                allowed=False,
                reason='invalid_grim',
                score=0,
                details=details
            )
        
        # VALIDAÇÃO CRÍTICA 2: fbclid OBRIGATÓRIO se tiver UTMs
        if has_utm_params and not fbclid:
            details['validation_step'] = 'missing_fbclid_with_utm'
            details['latency_ms'] = int((time.time() - start_time) * 1000)
            
            return CloakerValidationResult(
                allowed=False,
                reason='missing_fbclid_with_utm',
                score=0,
                details=details
            )
        
        # ✅ SUCESSO: grim válido + (fbclid presente OU sem UTMs para testes)
        reason = 'grim_valid_and_fbclid_present' if fbclid else 'grim_valid_test_access'
        details['validation_step'] = reason
        details['latency_ms'] = int((time.time() - start_time) * 1000)
        
        return CloakerValidationResult(
            allowed=True,
            reason=reason,
            score=100,
            details=details
        )
    
    def _extract_grim_value(self, request: Request) -> str:
        """
        Extrai o valor do parâmetro grim em DUAS FORMAS:
        - FORMA 1: ?grim=testecamu01 (padrão)
        - FORMA 2: ?testecamu01 (Facebook format - parâmetro sem valor)
        
        Args:
            request: Objeto Request do Flask
            
        Returns:
            Valor do grim ou string vazia
        """
        # FORMA 1: Parâmetro tradicional ?grim=valor
        actual_value = (request.args.get(self.param_name) or '').strip()
        
        # FORMA 2: Facebook format ?valor (parâmetro sem =)
        if not actual_value:
            if self.expected_value in request.args:
                # No formato Facebook, o próprio nome do parâmetro é o valor
                actual_value = self.expected_value
        
        return actual_value
    
    def _has_utm_params(self, request: Request) -> bool:
        """
        Verifica se há parâmetros UTM na URL
        
        Args:
            request: Objeto Request do Flask
            
        Returns:
            True se houver qualquer parâmetro UTM
        """
        return any(request.args.get(param) for param in self.UTM_PARAMS)
    
    def is_crawler(self, user_agent: Optional[str]) -> bool:
        """
        Detecta se o User-Agent é um crawler/bot
        
        Args:
            user_agent: String do User-Agent
            
        Returns:
            True se for crawler/bot
        """
        if not user_agent:
            return False
        
        ua_lower = user_agent.lower()
        
        is_crawler = any(pattern in ua_lower for pattern in self.CRAWLER_PATTERNS)
        
        if is_crawler:
            logger.info(f"🤖 CRAWLER DETECTADO: {user_agent[:50]}...")
        
        return is_crawler
    
    def get_fake_404_html(self, pool_name: str = '', slug: str = '') -> str:
        """
        Retorna HTML da Safe Page / White Page (fake 404)
        
        Esta página é exibida quando o Cloaker bloqueia um acesso,
        enganando crawlers/bots que não têm JavaScript habilitado.
        
        Args:
            pool_name: Nome do pool para personalização
            slug: Slug do pool
            
        Returns:
            HTML completo da página de bloqueio
        """
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 - Página Não Encontrada</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            max-width: 600px;
        }}
        h1 {{
            font-size: 6rem;
            font-weight: 700;
            margin-bottom: 1rem;
            opacity: 0.9;
        }}
        h2 {{
            font-size: 1.5rem;
            font-weight: 400;
            margin-bottom: 2rem;
            opacity: 0.8;
        }}
        p {{
            font-size: 1rem;
            opacity: 0.6;
            line-height: 1.6;
        }}
        .icon {{
            font-size: 4rem;
            margin-bottom: 1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🔒</div>
        <h1>404</h1>
        <h2>Página Não Encontrada</h2>
        <p>O conteúdo que você está procurando não está disponível ou pode ter sido movido.</p>
        <p style="margin-top: 2rem; font-size: 0.8rem; opacity: 0.4;">
            {pool_name or 'Sistema'} • Ref: {slug or 'N/A'}
        </p>
    </div>
</body>
</html>"""
    
    def log_validation_event(self, result: CloakerValidationResult, slug: str, pool_id: int) -> None:
        """
        Log estruturado em JSON para auditoria de eventos do Cloaker
        
        Args:
            result: Resultado da validação
            slug: Slug do pool
            pool_id: ID do pool
        """
        import json
        
        log_data = {
            'event_type': 'cloaker_validation',
            'slug': slug,
            'pool_id': pool_id,
            'allowed': result.allowed,
            'reason': result.reason,
            'score': result.score,
            'details': result.details,
            'timestamp': time.time()
        }
        
        if result.allowed:
            logger.info(f"✅ CLOAKER ALLOW | {json.dumps(log_data, default=str)}")
        else:
            logger.warning(f"🛡️ CLOAKER BLOCK | {json.dumps(log_data, default=str)}")


# Instância singleton para uso global
_cloaker_service: Optional[CloakerService] = None


def get_cloaker_service(pool_config: Optional[Dict[str, Any]] = None) -> CloakerService:
    """
    Factory para obter instância do CloakerService
    
    Args:
        pool_config: Configurações do pool (opcional)
        
    Returns:
        Instância de CloakerService
    """
    global _cloaker_service
    
    if pool_config is not None:
        return CloakerService(pool_config)
    
    if _cloaker_service is None:
        _cloaker_service = CloakerService()
    
    return _cloaker_service
