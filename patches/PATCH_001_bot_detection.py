"""
PATCH 001: BOT DETECTION VIA USER-AGENT
Severidade: CRITICAL
Prioridade: P0
Tempo Estimado: 24h

Adiciona validação de User-Agent para bloquear bots conhecidos
(facebookexternalhit, twitterbot, etc.)
"""

# ============================================================================
# CÓDIGO ATUAL (app.py:2611-2640)
# ============================================================================

"""
if pool.meta_cloaker_enabled:
    param_name = pool.meta_cloaker_param_name or 'grim'
    expected_value = pool.meta_cloaker_param_value
    
    if not expected_value or not expected_value.strip():
        logger.error(f"🔥 BUG: Cloaker ativo no pool '{slug}' mas sem valor configurado!")
    else:
        expected_value = expected_value.strip()
        actual_value = (request.args.get(param_name) or '').strip()
        
        if actual_value != expected_value:
            logger.warning(f"🛡️ Cloaker bloqueou acesso ao pool '{slug}'")
            return render_template('cloaker_block.html', 
                                 pool_name=pool.name,
                                 slug=slug), 403
"""

# ============================================================================
# CÓDIGO NOVO (SUBSTITUIR)
# ============================================================================

# ADICIONAR FUNÇÃO DE VALIDAÇÃO (antes do route /go/<slug>)

def validate_cloaker_access(request, pool):
    """
    Valida acesso ao pool baseado em cloaker
    
    Validações:
    1. Parâmetro de segurança (obrigatório)
    2. User-Agent (bloqueia bots conhecidos)
    
    Returns:
        dict: {
            'allowed': bool,
            'reason': str,
            'details': dict
        }
    """
    import json
    import uuid
    from datetime import datetime
    
    # ========================================================================
    # VALIDAÇÃO 1: PARÂMETRO DE SEGURANÇA
    # ========================================================================
    
    param_name = pool.meta_cloaker_param_name or 'grim'
    expected_value = pool.meta_cloaker_param_value
    
    # Verificar se cloaker está configurado corretamente
    if not expected_value or not expected_value.strip():
        logger.error(f"🔥 Cloaker ativo no pool '{pool.slug}' mas sem valor configurado!")
        return {
            'allowed': False,
            'reason': 'cloaker_misconfigured',
            'details': {
                'message': 'Cloaker configuration error',
                'param_name': param_name
            }
        }
    
    # Normalizar valores
    expected_value = expected_value.strip()
    actual_value = (request.args.get(param_name) or '').strip()
    
    # Verificar parâmetro
    if actual_value != expected_value:
        return {
            'allowed': False,
            'reason': 'invalid_parameter',
            'details': {
                'param_name': param_name,
                'param_expected': bool(expected_value),
                'param_provided': bool(actual_value),
                'param_match': False
            }
        }
    
    # ========================================================================
    # VALIDAÇÃO 2: USER-AGENT (BOT DETECTION)
    # ========================================================================
    
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Lista de padrões de bots conhecidos
    bot_patterns = [
        # Meta / Facebook
        'facebookexternalhit',
        'facebot',
        'facebook',
        
        # Outras redes sociais
        'twitterbot',
        'twitter',
        'linkedinbot',
        'pinterestbot',
        'whatsapp',
        'telegrambot',
        
        # Search engines
        'googlebot',
        'bingbot',
        'baiduspider',
        'yandexbot',
        
        # Crawlers gerais
        'bot',
        'crawler',
        'spider',
        'scraper',
        
        # Ferramentas
        'python-requests',
        'curl',
        'wget',
        'scrapy',
        'httpie',
        'postman',
        'insomnia'
    ]
    
    # Verificar se User-Agent contém algum padrão de bot
    detected_pattern = None
    for pattern in bot_patterns:
        if pattern in user_agent:
            detected_pattern = pattern
            break
    
    if detected_pattern:
        return {
            'allowed': False,
            'reason': 'bot_detected',
            'details': {
                'pattern_detected': detected_pattern,
                'user_agent': user_agent[:100]  # Primeiros 100 chars
            }
        }
    
    # ========================================================================
    # TODAS AS VALIDAÇÕES PASSARAM
    # ========================================================================
    
    return {
        'allowed': True,
        'reason': 'authorized',
        'details': {
            'param_name': param_name,
            'param_match': True,
            'bot_detected': False
        }
    }


def log_cloaker_event(event_type, slug, validation_result, request, pool):
    """
    Log estruturado em JSON para eventos do cloaker
    """
    import json
    import uuid
    from datetime import datetime
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'request_id': str(uuid.uuid4()),
        'event_type': event_type,
        'slug': slug,
        'pool_id': pool.id,
        'pool_name': pool.name,
        'result': 'ALLOW' if validation_result['allowed'] else 'BLOCK',
        'reason': validation_result['reason'],
        'details': validation_result['details'],
        'ip_short': request.remote_addr.rsplit('.', 1)[0] + '.x',
        'user_agent': request.headers.get('User-Agent', 'unknown')[:200],
        'http_method': request.method,
        'referer': request.headers.get('Referer', '')[:200],
        'query_string': request.query_string.decode('utf-8')[:500]
    }
    
    logger.info(f"CLOAKER_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")


# SUBSTITUIR NO ROUTE /go/<slug> (linha 2611):

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
    # ✅ CLOAKER + ANTICLONE: VALIDAÇÃO DE SEGURANÇA (NOVO)
    # ============================================================================
    
    if pool.meta_cloaker_enabled:
        # Validar acesso
        validation_result = validate_cloaker_access(request, pool)
        
        # Log do evento
        log_cloaker_event(
            event_type='cloaker_validation',
            slug=slug,
            validation_result=validation_result,
            request=request,
            pool=pool
        )
        
        # Se bloqueado, retornar página de bloqueio
        if not validation_result['allowed']:
            logger.warning(
                f"🛡️ Cloaker bloqueou acesso ao pool '{slug}' | "
                f"Motivo: {validation_result['reason']} | "
                f"IP: {request.remote_addr} | "
                f"UA: {request.headers.get('User-Agent', 'unknown')[:100]}"
            )
            
            return render_template(
                'cloaker_block.html',
                pool_name=pool.name,
                slug=slug,
                reason=validation_result['reason']
            ), 403
        
        # Se autorizado, logar sucesso
        logger.info(
            f"✅ Cloaker autorizou acesso ao pool '{slug}' | "
            f"IP: {request.remote_addr} | "
            f"UA: {request.headers.get('User-Agent', 'unknown')[:100]}"
        )
    
    # ... continuar com código existente de seleção de bot ...
    
    # No final, logar latência
    latency_ms = (time.time() - start_time) * 1000
    if latency_ms > 500:
        logger.warning(f"HIGH_LATENCY: /go/{slug} took {latency_ms:.0f}ms")


# ============================================================================
# TESTES PARA VALIDAR O PATCH
# ============================================================================

"""
# Test 1: Bot deve ser bloqueado
curl -A "facebookexternalhit/1.1" \
  "https://app.grimbots.online/go/testslug?grim=abc123"
# Esperado: 403

# Test 2: Usuário legítimo deve passar
curl -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  "https://app.grimbots.online/go/testslug?grim=abc123"
# Esperado: 302

# Test 3: Sem parâmetro deve bloquear
curl -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  "https://app.grimbots.online/go/testslug"
# Esperado: 403
"""

# ============================================================================
# CHECKLIST DE APLICAÇÃO
# ============================================================================

"""
[ ] 1. Fazer backup do app.py atual
[ ] 2. Adicionar função validate_cloaker_access() antes do route /go/<slug>
[ ] 3. Adicionar função log_cloaker_event() antes do route /go/<slug>
[ ] 4. Substituir código do cloaker no route /go/<slug>
[ ] 5. Testar localmente com curl
[ ] 6. Executar pytest tests/test_cloaker.py
[ ] 7. Deploy em staging
[ ] 8. Validar logs estruturados
[ ] 9. Deploy em produção
[ ] 10. Monitorar logs por 24h
"""

