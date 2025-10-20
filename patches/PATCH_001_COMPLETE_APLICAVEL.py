"""
PATCH 001 - BOT DETECTION COMPLETO + LOGS JSON
Severidade: CRITICAL
Responsável: QI 300 #2 + QI 540
Tempo: 24 horas

INSTRUÇÕES DE APLICAÇÃO:
1. Backup: cp app.py app.py.backup.$(date +%s)
2. Adicionar funções ANTES do route /go/<slug> (linha ~2580)
3. Substituir validação do cloaker (linha 2611-2640)
4. Testar: python -m pytest tests/test_cloaker.py -v
5. Deploy: sudo systemctl restart grimbots
"""

# ============================================================================
# ADICIONAR ESTAS FUNÇÕES ANTES DO ROUTE /go/<slug> (linha ~2570)
# ============================================================================

import json
import uuid
import time
from datetime import datetime

def validate_cloaker_access(request, pool, slug):
    """
    Validação MULTICAMADAS do cloaker
    
    CAMADA 1: Parâmetro obrigatório
    CAMADA 2: User-Agent (bot detection)
    CAMADA 3: Header consistency
    CAMADA 4: Timing analysis (rate limiting via Redis)
    
    Returns:
        dict: {
            'allowed': bool,
            'reason': str,
            'score': int (0-100, < 40 = suspeito),
            'details': dict
        }
    """
    import redis
    
    score = 100  # Começa com score perfeito
    details = {}
    
    # ========================================================================
    # CAMADA 1: VALIDAÇÃO DE PARÂMETRO
    # ========================================================================
    
    param_name = pool.meta_cloaker_param_name or 'grim'
    expected_value = pool.meta_cloaker_param_value
    
    if not expected_value or not expected_value.strip():
        return {
            'allowed': False,
            'reason': 'cloaker_misconfigured',
            'score': 0,
            'details': {'error': 'Pool sem valor configurado'}
        }
    
    expected_value = expected_value.strip()
    actual_value = (request.args.get(param_name) or '').strip()
    
    if actual_value != expected_value:
        return {
            'allowed': False,
            'reason': 'invalid_parameter',
            'score': 0,
            'details': {
                'param_name': param_name,
                'param_expected': True,
                'param_provided': bool(actual_value)
            }
        }
    
    details['param_match'] = True
    
    # ========================================================================
    # CAMADA 2: BOT DETECTION VIA USER-AGENT
    # ========================================================================
    
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Lista COMPLETA de bots conhecidos
    bot_patterns = [
        # Meta / Facebook
        'facebookexternalhit', 'facebot', 'facebook', 'meta-externalagent',
        
        # Redes sociais
        'twitterbot', 'twitter', 'linkedinbot', 'pinterestbot', 
        'whatsapp', 'telegrambot', 'instagrambot',
        
        # Search engines
        'googlebot', 'bingbot', 'baiduspider', 'yandexbot', 'duckduckbot',
        'slurp', 'yahoo', 'teoma',
        
        # Crawlers gerais
        'bot', 'crawler', 'spider', 'scraper', 'scraping',
        
        # Ferramentas HTTP
        'python-requests', 'python-urllib', 'python-httpx',
        'curl', 'wget', 'httpie', 'postman', 'insomnia',
        
        # Frameworks
        'scrapy', 'beautifulsoup', 'selenium', 'puppeteer', 'playwright',
        'mechanize', 'httparty', 'axios', 'got', 'node-fetch',
        
        # Monitoring/Testing
        'pingdom', 'uptimerobot', 'newrelic', 'datadog', 'monitor',
        'check', 'nagios', 'zabbix',
        
        # Misc
        'headlesschrome', 'phantomjs', 'slackbot', 'discordbot',
        'ahrefsbot', 'semrushbot', 'mj12bot', 'dotbot'
    ]
    
    detected_pattern = None
    for pattern in bot_patterns:
        if pattern in user_agent:
            detected_pattern = pattern
            score -= 100  # Bot = score 0
            break
    
    if detected_pattern:
        return {
            'allowed': False,
            'reason': 'bot_detected_ua',
            'score': 0,
            'details': {
                'pattern': detected_pattern,
                'user_agent': user_agent[:200]
            }
        }
    
    details['bot_ua_check'] = 'passed'
    
    # ========================================================================
    # CAMADA 3: HEADER CONSISTENCY
    # ========================================================================
    
    # User-Agent de navegador DEVE ter Accept header apropriado
    if 'mozilla' in user_agent or 'chrome' in user_agent or 'safari' in user_agent:
        accept_header = request.headers.get('Accept', '')
        
        if not accept_header:
            score -= 30
            details['missing_accept'] = True
        elif 'text/html' not in accept_header:
            score -= 20
            details['suspicious_accept'] = accept_header[:100]
        
        # Accept-Language esperado para navegadores
        accept_language = request.headers.get('Accept-Language', '')
        if not accept_language:
            score -= 10
            details['missing_accept_language'] = True
    
    # ========================================================================
    # CAMADA 4: TIMING ANALYSIS (REDIS)
    # ========================================================================
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=1)
        ip = request.remote_addr
        current_time = time.time()
        
        # Chave para último acesso deste IP
        last_access_key = f"cloaker:last_access:{ip}"
        last_access = r.get(last_access_key)
        
        if last_access:
            time_diff = current_time - float(last_access)
            
            # Se menos de 100ms desde último request = muito rápido (bot)
            if time_diff < 0.1:  # 100ms
                score -= 40
                details['timing_suspicious'] = f'{time_diff*1000:.0f}ms'
            
            # Se menos de 500ms = suspeito
            elif time_diff < 0.5:
                score -= 20
                details['timing_fast'] = f'{time_diff*1000:.0f}ms'
        
        # Salvar timestamp atual
        r.setex(last_access_key, 60, str(current_time))
        
    except Exception as e:
        logger.warning(f"Timing analysis failed: {e}")
        # Não bloquear se Redis falhar
    
    # ========================================================================
    # DECISÃO FINAL
    # ========================================================================
    
    # Score < 40 = bloqueado
    if score < 40:
        return {
            'allowed': False,
            'reason': 'suspicious_behavior',
            'score': score,
            'details': details
        }
    
    # Score >= 40 = permitido
    return {
        'allowed': True,
        'reason': 'authorized',
        'score': score,
        'details': details
    }


def log_cloaker_event_json(event_type, slug, validation_result, request, pool, latency_ms=0):
    """
    Log estruturado em JSON por linha (JSONL)
    
    Formato padrão da indústria para análise automatizada
    """
    import json
    import uuid
    from datetime import datetime
    
    # Mascarar IP (LGPD/GDPR compliant)
    ip_full = request.remote_addr
    ip_parts = ip_full.split('.')
    ip_short = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.x" if len(ip_parts) == 4 else ip_full
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'request_id': str(uuid.uuid4()),
        'event_type': event_type,
        'slug': slug,
        'pool_id': pool.id,
        'pool_name': pool.name,
        'result': 'ALLOW' if validation_result['allowed'] else 'BLOCK',
        'reason': validation_result['reason'],
        'score': validation_result['score'],
        'details': validation_result['details'],
        'ip_short': ip_short,
        'user_agent': request.headers.get('User-Agent', 'unknown')[:200],
        'http_method': request.method,
        'referer': request.headers.get('Referer', '')[:200],
        'accept': request.headers.get('Accept', '')[:100],
        'accept_language': request.headers.get('Accept-Language', '')[:50],
        'query_string': request.query_string.decode('utf-8')[:500],
        'latency_ms': round(latency_ms, 2)
    }
    
    # Log em formato JSONL
    logger.info(f"CLOAKER_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")
    
    # Também salvar em arquivo separado para análise
    try:
        with open('logs/cloaker_events.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"Erro ao salvar log JSONL: {e}")


# ============================================================================
# SUBSTITUIR NO ROUTE /go/<slug> (linha 2611-2640)
# ============================================================================

@app.route('/go/<slug>')
def public_redirect(slug):
    """
    Endpoint PÚBLICO de redirecionamento com Load Balancing + Meta Pixel Tracking + Cloaker
    """
    from datetime import datetime
    import time
    
    start_time = time.time()
    
    # Buscar pool ativo
    pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first()
    
    if not pool:
        abort(404, f'Pool "{slug}" não encontrado ou inativo')
    
    # ============================================================================
    # ✅ CLOAKER + ANTICLONE: VALIDAÇÃO MULTICAMADAS (NOVO)
    # ============================================================================
    
    if pool.meta_cloaker_enabled:
        # Validar acesso com múltiplas camadas
        validation_result = validate_cloaker_access(request, pool, slug)
        
        # Calcular latência da validação
        validation_latency = (time.time() - start_time) * 1000
        
        # Log estruturado em JSON
        log_cloaker_event_json(
            event_type='cloaker_validation',
            slug=slug,
            validation_result=validation_result,
            request=request,
            pool=pool,
            latency_ms=validation_latency
        )
        
        # Se bloqueado, retornar página de bloqueio
        if not validation_result['allowed']:
            logger.warning(
                f"🛡️ CLOAKER BLOCK | Slug: {slug} | "
                f"Reason: {validation_result['reason']} | "
                f"Score: {validation_result['score']}/100 | "
                f"IP: {request.remote_addr}"
            )
            
            return render_template(
                'cloaker_block.html',
                pool_name=pool.name,
                slug=slug,
                reason=validation_result['reason']
            ), 403
        
        # Se autorizado, logar sucesso
        logger.info(
            f"✅ CLOAKER ALLOW | Slug: {slug} | "
            f"Score: {validation_result['score']}/100 | "
            f"IP: {request.remote_addr}"
        )
    
    # ... continuar com código existente de seleção de bot ...


# ============================================================================
# TESTES PARA VALIDAR
# ============================================================================

"""
# Teste 1: Bot deve ser bloqueado
curl -A "facebookexternalhit/1.1" \
  "https://app.grimbots.online/go/red1?grim=escalafull"
# Esperado: 403 + log JSON com reason: bot_detected_ua

# Teste 2: Usuário legítimo deve passar
curl -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  -H "Accept: text/html,application/xhtml+xml" \
  -H "Accept-Language: pt-BR,pt;q=0.9" \
  "https://app.grimbots.online/go/red1?grim=escalafull"
# Esperado: 302 + log JSON com score: 100

# Teste 3: Headers inconsistentes (score baixo mas não bloqueia)
curl -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  "https://app.grimbots.online/go/red1?grim=escalafull"
# Esperado: 302 + log JSON com score: 60-70

# Teste 4: Timing muito rápido
for i in {1..5}; do
  curl -s "https://app.grimbots.online/go/red1?grim=escalafull" > /dev/null &
done
# Esperado: Primeiros OK, últimos podem ter score baixo

# Teste 5: Verificar logs JSON
tail -10 logs/cloaker_events.jsonl | jq .
# Esperado: JSON válido por linha
"""

