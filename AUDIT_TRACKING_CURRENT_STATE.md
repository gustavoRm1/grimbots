# A) Redirect (/go/<slug>) – app.py

```python
@app.route('/go/<slug>')
@limiter.limit("10000 per hour")  # Override: endpoint público precisa de limite alto
def public_redirect(slug):
    """
    Endpoint PÚBLICO de redirecionamento com Load Balancing + Meta Pixel Tracking + Cloaker
    
    URL: /go/{slug} (ex: /go/red1)
    
    FUNCIONALIDADES:
    - Busca pool pelo slug
    - ✅ CLOAKER: Validação MULTICAMADAS (parâmetro + UA + headers + timing)
    - Seleciona bot online (estratégia configurada)
    - Health check em cache (não valida em tempo real)
    - Failover automático
    - Circuit breaker
    - Métricas de uso
    - ✅ META PIXEL: PageView tracking
    - ✅ NORMALIZAÇÃO: Corrige URLs malformadas com múltiplos "?" (ex: Utmify)
    """
    from datetime import datetime
    # time já está importado no topo do arquivo
    
    start_time = time.time()
    
    # ✅ OBSERVAÇÃO: Flask trata corretamente múltiplos "?" em URLs malformadas através do request.args
    # Se a Utmify gerar URLs com múltiplos "?", o Flask já parseia corretamente os parâmetros
    
    # Buscar pool ativo
    pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first()
    
    if not pool:
        abort(404, f'Pool "{slug}" não encontrado ou inativo')
    
    # ============================================================================
    # ✅ CLOAKER + ANTICLONE: VALIDAÇÃO MULTICAMADAS (PATCH_001 APLICADO)
    # ============================================================================
    # ✅ IMPORTANTE: O Cloaker funciona 100% INDEPENDENTE do Meta Pixel
    # - Pode ser usado sem pixel vinculado
    # - Validação acontece ANTES de qualquer verificação de pixel
    # - Não há dependência de meta_pixel_id, meta_tracking_enabled ou meta_access_token
    # - Se bloqueado, retorna template estático (não depende de pixel)
    # - Se autorizado, continua fluxo normalmente (com ou sem pixel)
    
    if pool.meta_cloaker_enabled:
        # Validação multicamadas
        validation_result = validate_cloaker_access(request, pool, slug)
        
        # Latência da validação
        validation_latency = (time.time() - start_time) * 1000
        
        # Log estruturado JSON
        log_cloaker_event_json(
            event_type='cloaker_validation',
            slug=slug,
            validation_result=validation_result,
            request=request,
            pool=pool,
            latency_ms=validation_latency
        )
        
        # Se bloqueado
        if not validation_result['allowed']:
            logger.warning(
                f"🛡️ BLOCK | Slug: {slug} | Reason: {validation_result['reason']} | "
                f"Score: {validation_result['score']}/100"
            )
            return render_template('cloaker_block.html', pool_name=pool.name, slug=slug), 403
        
        # Se autorizado
        logger.info(f"✅ ALLOW | Slug: {slug} | Score: {validation_result['score']}/100")
    
    # Selecionar bot usando estratégia configurada
    pool_bot = pool.select_bot()
    
    if not pool_bot:
        # Nenhum bot online - tentar bot degradado como fallback
        degraded = pool.pool_bots.filter_by(
            is_enabled=True,
            status='degraded'
        ).order_by(PoolBot.consecutive_failures.asc()).first()
        
        if degraded:
            pool_bot = degraded
            logger.warning(f"Pool {slug}: Usando bot degradado @{pool_bot.bot.username}")
        else:
            abort(503, 'Nenhum bot disponível no momento. Tente novamente em instantes.')
    
    # ✅ CORREÇÃO DEADLOCK: Usar UPDATE atômico ao invés de FOR UPDATE
    # UPDATE atômico evita deadlocks e é mais eficiente (1 query ao invés de SELECT + UPDATE)
    try:
        # Incrementar total_redirects de forma atômica (evita deadlocks)
        # Usar coalesce para tratar NULL (valores antigos podem ser NULL)
        db.session.execute(
            update(PoolBot)
            .where(PoolBot.id == pool_bot.id)
            .values(total_redirects=text('COALESCE(total_redirects, 0) + 1'))
        )
        db.session.execute(
            update(RedirectPool)
            .where(RedirectPool.id == pool.id)
            .values(total_redirects=text('COALESCE(total_redirects, 0) + 1'))
        )
        
        db.session.commit()
        
        # Refresh para obter valores atualizados (opcional, apenas se necessário para log)
        db.session.refresh(pool_bot)
        db.session.refresh(pool)
    except SQLAlchemyError as e:
        db.session.rollback()
        # ✅ Não abortar em caso de erro de métricas - redirect deve continuar funcionando
        # Métricas são secundárias, o redirect é crítico
        logger.warning(f"⚠️ Erro ao atualizar métricas de redirect (não crítico): {e}")
        # Continuar execução - redirect não deve falhar por causa de métricas
    
    # Log
    logger.info(f"Redirect: /go/{slug} → @{pool_bot.bot.username} | Estratégia: {pool.distribution_strategy} | Total: {pool_bot.total_redirects}")
    
    # ============================================================================
    # ✅ TRACKING ELITE: CAPTURA IP + USER-AGENT + SESSION (TOP 1%)
    # ============================================================================
    import uuid
    import redis
    from datetime import datetime
    
    # Capturar dados do request
    # ✅ CORREÇÃO CRÍTICA: Usar função get_user_ip() que prioriza Cloudflare headers
    user_ip_raw = get_user_ip(request)
    # ✅ VALIDAÇÃO: Tratar '0.0.0.0' e strings vazias como None (será atualizado pelo Parameter Builder)
    # '0.0.0.0' não é um IP válido para tracking, mas salvaremos como None e o Parameter Builder atualizará
    user_ip = user_ip_raw if user_ip_raw and user_ip_raw.strip() and user_ip_raw.strip() != '0.0.0.0' else None
    user_agent = request.headers.get('User-Agent', '')
    fbclid = request.args.get('fbclid', '')
    
    # ✅ CRÍTICO QI 300: Detectar crawlers e NÃO salvar tracking
    # Crawlers não têm cookies, não geram FBP/FBC válidos, e poluem o Redis
    def is_crawler(ua: str) -> bool:
        """Detecta se o User-Agent é um crawler/bot"""
        if not ua:
            return False
        ua_lower = ua.lower()
        crawler_patterns = [
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
            'facebot',
            'ia_archiver'
        ]
        return any(pattern in ua_lower for pattern in crawler_patterns)
    
    is_crawler_request = is_crawler(user_agent)
    if is_crawler_request:
        logger.info(f"🤖 CRAWLER DETECTADO: {user_agent[:50]}... | Tracking NÃO será salvo")
    
    grim_param = request.args.get('grim', '')
    import json
    from utils.tracking_service import TrackingService, TrackingServiceV4

    # GERAR IDENTIFICADORES ANTES DE QUALQUER DEPENDÊNCIA DO CLIENTE
    tracking_service_v4 = TrackingServiceV4()
    tracking_token = uuid.uuid4().hex  # sempre existe para correlacionar PageView → Purchase
    root_event_id = f"evt_{tracking_token}"  # ID canônico imutável por sessão/click
    pageview_context = {}
    external_id = None
    utm_data = {}
    fbp_cookie = None  # Inicializar para usar depois mesmo se Meta Pixel desabilitado
    fbc_cookie = None  # Inicializar para usar depois mesmo se Meta Pixel desabilitado
    fbc_origin = None
    pageview_ts = int(time.time())
    TRACKING_TOKEN_TTL = TrackingServiceV4.TRACKING_TOKEN_TTL_SECONDS
    
    # Capturar contexto e salvar tracking token MESMO antes do client-side pixel
    if pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token:
        # CRÍTICO V4.1: Capturar FBC do cookie OU dos params (JS pode ter enviado)
        # Prioridade: cookie > params (cookie é mais confiável)
        fbp_cookie = request.cookies.get('_fbp') or request.args.get('_fbp_cookie')
        fbc_cookie = request.cookies.get('_fbc') or request.args.get('_fbc_cookie')
        # Usar variável fbclid já capturada anteriormente (linha 4166)

    # CORREÇÃO: Inicializar utms sempre (mesmo se for crawler)
    # Se for crawler, utms será dict vazio (não salvará UTMs)
    utms = {}
    if not is_crawler_request:
        utms = {
            'utm_source': request.args.get('utm_source', ''),
            'utm_campaign': request.args.get('utm_campaign', ''),
            'utm_medium': request.args.get('utm_medium', ''),
            'utm_content': request.args.get('utm_content', ''),
            'utm_term': request.args.get('utm_term', ''),
            'utm_id': request.args.get('utm_id', '')
        }

    # ✅ CRÍTICO: Garantir que fbclid completo (até 255 chars) seja salvo - NUNCA truncar antes de salvar no Redis!
    fbclid_to_save = fbclid or None
    # === CANONICAL CLICK TIMESTAMP (META SAFE) ===
    if fbclid_to_save:
        try:
            click_ts = int(time.time())
            tracking_service_v4.redis.setex(
                f"meta:click_ts:{fbclid_to_save}",
                60 * 60 * 24 * 7,  # 7 dias
                click_ts
            )
        except Exception as e:
            logger.warning(f"⚠️ Falha ao salvar click_ts no Redis: {e}")
    if fbclid_to_save:
        logger.info(f" Redirect - Salvando fbclid completo no Redis: {fbclid_to_save[:50]}... (len={len(fbclid_to_save)})")
        if len(fbclid_to_save) > 255:
            logger.warning(f" Redirect - fbclid excede 255 chars ({len(fbclid_to_save)}), mas será salvo completo no Redis (sem truncar)")
        # Derivar campaign_code do próprio fbclid (garante contexto de campanha)
        utms.setdefault('campaign_code', fbclid_to_save)
        # ✅ FBC CANÔNICO ÚNICO: gerar somente na 1ª vez (quando não há cookie)
        if not fbc_cookie:
            fbc_cookie = f"fb.1.{click_ts}.{fbclid_to_save}"
            fbc_origin = "click"
            logger.info(f"✅ FBC canônico gerado no redirect (origem click): {fbc_cookie[:64]}...")
    elif grim_param:
        # Se não há fbclid, usar grim como campaign_code
        utms.setdefault('campaign_code', grim_param)
    
    # ✅ tracking_payload inicial (sempre definido) para merge com pageview_context
    tracking_payload = {
        'tracking_token': tracking_token,
        'fbclid': fbclid_to_save,
        'fbp': fbp_cookie,
        'fbc': fbc_cookie,
        'fbc_origin': fbc_origin,
        'pageview_event_id': root_event_id,
        'pageview_ts': pageview_ts,
        'client_ip': user_ip if user_ip else None,
        'client_user_agent': user_agent if user_agent and user_agent.strip() else None,
        'grim': grim_param or None,
        'event_source_url': request.url or f'https://{request.host}/go/{pool.slug}',
        'first_page': request.url or f'https://{request.host}/go/{pool.slug}',
        'pageview_sent': False,
        'pixel_id': pool.meta_pixel_id if pool and pool.meta_pixel_id else None,  # ✅ Pixel do redirect (fonte primária para Purchase)
        **{k: v for k, v in utms.items() if v}
    }

    # ✅ UPSERT CANÔNICO EM meta_tracking_sessions (PageView = nascimento da sessão)
    from models import MetaTrackingSession, get_brazil_time
    try:
        session_row = MetaTrackingSession.query.filter_by(tracking_token=tracking_token).first()
        now_ts = get_brazil_time()
        if not session_row:
            session_row = MetaTrackingSession(
                tracking_token=tracking_token,
                root_event_id=root_event_id,
                pageview_sent=True,
                pageview_sent_at=now_ts,
                fbclid=fbclid_to_save,
                fbc=fbc_cookie,
                fbp=fbp_cookie,
                user_external_id=None  # pode ser preenchido depois (telegram_user_id hash)
            )
            db.session.add(session_row)
        else:
            session_row.root_event_id = session_row.root_event_id or root_event_id
            session_row.pageview_sent = True
            session_row.pageview_sent_at = now_ts
            session_row.fbclid = session_row.fbclid or fbclid_to_save
            session_row.fbc = session_row.fbc or fbc_cookie
            session_row.fbp = session_row.fbp or fbp_cookie
        db.session.commit()
        tracking_payload['pageview_sent'] = True
    except Exception as e:
        # Proteção para ambientes onde a tabela ainda não existe (evita 500 e deixa o fluxo seguir)
        logger.error(f"[META TRACKING SESSION] Erro ao upsert meta_tracking_sessions (possível tabela ausente): {e}", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
    
    # ============================================================================
    # ✅ META PIXEL: PAGEVIEW TRACKING + UTM CAPTURE (NÍVEL DE POOL)
    # ============================================================================
    # CRÍTICO: Captura UTM e External ID para vincular eventos posteriores
    # ============================================================================
    # ✅ Verificar se Meta Pixel está habilitado antes de processar PageView
    if pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token:
        # ✅ CORREÇÃO CRÍTICA QI 500: Inicializar pageview_context antes do try para garantir que sempre exista
        pageview_context = {}
        try:
            external_id, utm_data, pageview_context = send_meta_pixel_pageview_event(
                pool,
                request,
                pageview_event_id=root_event_id if not is_crawler_request else None,
                tracking_token=tracking_token
            )
        except Exception as e:
            logger.error(f"Erro ao enviar PageView para Meta Pixel: {e}")
            # Não impedir o redirect se Meta falhar
            pageview_context = {}
        
        # ✅ CORREÇÃO CRÍTICA QI 500: MERGE sempre executa, independentemente de erros no PageView
        # Isso garante que o tracking_token seja sempre atualizado com os dados disponíveis
        # ✅ CRÍTICO: Sempre salvar pageview_context, mesmo se vazio, para garantir que pageview_event_id seja preservado
        # ✅ CORREÇÃO CRÍTICA QI 1000+: MERGE pageview_context com tracking_payload inicial
        # Isso garante que client_ip e client_user_agent sejam preservados (não sobrescreve)
        if tracking_token:
            try:
                # ✅ CORREÇÃO CRÍTICA: MERGE pageview_context com tracking_payload inicial
                # PROBLEMA IDENTIFICADO: pageview_context estava sobrescrevendo tracking_payload inicial
                # Isso fazia com que client_ip e client_user_agent fossem perdidos
                # SOLUÇÃO: Fazer merge (não sobrescrever)
                merged_context = None  # ✅ Inicializar para garantir que sempre existe
                if pageview_context:
                    # ✅ MERGE: Combinar dados iniciais com dados do PageView
                    # ✅ PRIORIDADE: pageview_context > tracking_payload (pageview_context é mais recente e tem dados do PageView)
                    merged_context = {
                        **tracking_payload,  # ✅ Dados iniciais (client_ip, client_user_agent, fbclid, fbp, etc.)
                        **pageview_context   # ✅ Dados do PageView (pageview_event_id, event_source_url, client_ip, client_user_agent, etc.) - SOBRESCREVE tracking_payload
                    }
                    merged_context['pageview_sent'] = True
                    
                    # ✅ CRÍTICO: GARANTIR que client_ip e client_user_agent sejam preservados (prioridade: pageview_context > tracking_payload)
                    # Se pageview_context tem valores válidos, usar (são mais recentes e vêm do PageView)
                    # Se pageview_context tem vazios/None mas tracking_payload tem valores válidos, usar tracking_payload (fallback)
                    if pageview_context.get('client_ip') and isinstance(pageview_context.get('client_ip'), str) and pageview_context.get('client_ip').strip():
                        # ✅ Prioridade 1: Usar client_ip do pageview_context (mais recente e vem do PageView)
                        merged_context['client_ip'] = pageview_context['client_ip']
                        logger.info(f"✅ Usando client_ip do pageview_context (mais recente): {pageview_context['client_ip']}")
                    elif tracking_payload.get('client_ip') and isinstance(tracking_payload.get('client_ip'), str) and tracking_payload.get('client_ip').strip():
                        # ✅ Prioridade 2: Se pageview_context não tem, usar tracking_payload (fallback)
                        merged_context['client_ip'] = tracking_payload['client_ip']
                        logger.info(f"✅ Usando client_ip do tracking_payload (fallback): {tracking_payload['client_ip']}")
                    
                    if pageview_context.get('client_user_agent') and isinstance(pageview_context.get('client_user_agent'), str) and pageview_context.get('client_user_agent').strip():
                        # ✅ Prioridade 1: Usar client_user_agent do pageview_context (mais recente e vem do PageView)
                        merged_context['client_user_agent'] = pageview_context['client_user_agent']
                        logger.info(f"✅ Usando client_user_agent do pageview_context (mais recente): {pageview_context['client_user_agent'][:50]}...")
                    elif tracking_payload.get('client_user_agent') and isinstance(tracking_payload.get('client_user_agent'), str) and tracking_payload.get('client_user_agent').strip():
                        # ✅ Prioridade 2: Se pageview_context não tem, usar tracking_payload (fallback)
                        merged_context['client_user_agent'] = tracking_payload['client_user_agent']
                        logger.info(f"✅ Usando client_user_agent do tracking_payload (fallback): {tracking_payload['client_user_agent'][:50]}...")
                    
                    # ✅ GARANTIR que pageview_event_id seja preservado (prioridade: pageview_context > tracking_payload)
                    if not merged_context.get('pageview_event_id') and tracking_payload.get('pageview_event_id'):
                        merged_context['pageview_event_id'] = tracking_payload['pageview_event_id']
                        logger.info(f"✅ Preservando pageview_event_id do tracking_payload inicial: {tracking_payload['pageview_event_id']}")
                    
                    logger.info(f"✅ Merge realizado: client_ip={'✅' if merged_context.get('client_ip') else '❌'}, client_user_agent={'✅' if merged_context.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if merged_context.get('pageview_event_id') else '❌'}")
                    
                    ok = tracking_service_v4.save_tracking_token(
                        tracking_token,
                        merged_context,  # ✅ Dados completos (não sobrescreve)
                        ttl=TRACKING_TOKEN_TTL
                    )
                else:
                    # Se pageview_context está vazio, salvar apenas o tracking_payload inicial (já tem tudo)
                    logger.warning(f"⚠️ pageview_context vazio - preservando tracking_payload inicial completo")
                    tracking_payload['pageview_sent'] = True
                    ok = tracking_service_v4.save_tracking_token(
                        tracking_token,
                        tracking_payload,  # ✅ Dados iniciais completos (client_ip, client_user_agent, pageview_event_id, etc.)
                        ttl=TRACKING_TOKEN_TTL
                    )
                
                if not ok:
                    logger.warning("Retry saving merged context once (redirect)")
                    # ✅ CORREÇÃO: Usar merged_context se foi criado (não é None), senão usar tracking_payload
                    retry_context = merged_context if merged_context else tracking_payload
                    tracking_service_v4.save_tracking_token(
                        tracking_token,
                        retry_context,
                        ttl=TRACKING_TOKEN_TTL
                    )
            except Exception as e:
                logger.warning(f"⚠️ Erro ao atualizar tracking_token {tracking_token} com merged context: {e}")
    else:
        # ✅ Meta Pixel desabilitado - nenhum tracking será executado
        logger.info(f"⚠️ [META PIXEL] Tracking desabilitado para pool {pool.name} - pulando todo processamento de Meta Pixel")
    
    # Emitir evento WebSocket para o dono do pool
    socketio.emit('pool_redirect', {
        'pool_id': pool.id,
        'pool_name': pool.name,
        'bot_username': pool_bot.bot.username,
        'total_redirects': pool.total_redirects
    }, room=f'user_{pool.user_id}')
    
    # ============================================================================
    # ✅ REDIRECT PARA TELEGRAM COM TRACKING TOKEN
    # ============================================================================
    # SOLUÇÃO DEFINITIVA: Usar APENAS tracking_token no start param (32 chars)
    # Todos os dados (fbclid, fbp, fbc, UTMs, etc.) já estão salvos no Redis
    # com a chave tracking:{tracking_token}
    # ============================================================================
    
    # ✅ CRÍTICO: Renderizar HTML próprio SEMPRE após cloaker validar
    # HTML carrega Meta Pixel JS (se habilitado) e scripts Utmify (se configurado) antes de redirecionar
    # ✅ SEGURANÇA: Cloaker já validou ANTES (linha 4116), então HTML é seguro
    # ✅ CORREÇÃO: Renderizar HTML sempre (mesmo sem Meta Pixel ou Utmify) para consistência e segurança
    has_meta_pixel = pool.meta_pixel_id and pool.meta_tracking_enabled
    has_utmify = pool.utmify_pixel_id and pool.utmify_pixel_id.strip()
    
    # ✅ SEMPRE renderizar HTML se não for crawler (após cloaker passar)
    if not is_crawler_request:
        # ✅ VALIDAÇÃO CRÍTICA: Garantir que pool_bot, bot e username existem antes de renderizar HTML
        if not pool_bot or not pool_bot.bot or not pool_bot.bot.username:
            logger.error(f"❌ Pool {slug}: pool_bot ou bot.username ausente - usando fallback redirect direto")
            # Fallback para redirect direto (comportamento atual)
            if tracking_token:
                tracking_param = tracking_token
            else:
                tracking_param = f"p{pool.id}"
            # Usar username do pool_bot se disponível, senão usar fallback
            bot_username_fallback = pool_bot.bot.username if pool_bot and pool_bot.bot and pool_bot.bot.username else 'bot'
            redirect_url = f"https://t.me/{bot_username_fallback}?start={tracking_param}"
            response = make_response(redirect(redirect_url, code=302))
            # ✅ Injetar _fbp/_fbc gerados no servidor (90 dias - padrão Meta)
            cookie_kwargs_fallback = {
                'max_age': 90 * 24 * 60 * 60,
                'httponly': False,
                'secure': True,
                'samesite': 'None',
            }
            if fbp_cookie:
                response.set_cookie('_fbp', fbp_cookie, **cookie_kwargs_fallback)
            if fbc_cookie:
                response.set_cookie('_fbc', fbc_cookie, **cookie_kwargs_fallback)
            return response
        
        # ✅ SEMPRE usar tracking_token no start param
        if tracking_token:
            tracking_param = tracking_token
            logger.info(f"✅ Tracking param: {tracking_token} ({len(tracking_token)} chars)")
        else:
            tracking_param = f"p{pool.id}"
            logger.info(f"⚠️ Tracking token ausente - usando fallback: {tracking_param}")
        
        # ✅ TRY/EXCEPT: Renderizar HTML com fallback seguro
        try:
            # ✅ Log detalhado do que será renderizado
            tracking_services = []
            if has_meta_pixel:
                tracking_services.append(f"Meta Pixel ({pool.meta_pixel_id[:10]}...)")
            if has_utmify:
                tracking_services.append(f"Utmify ({pool.utmify_pixel_id[:10]}...)")
            
            if tracking_services:
                logger.info(f"🌉 Renderizando HTML com tracking: {', '.join(tracking_services)}")
            else:
                logger.info(f"🌉 Renderizando HTML (sem tracking configurado, apenas redirect)")
            
            # ✅ SEGURANÇA: Sanitizar valores para JavaScript (prevenir XSS)
            import re
            def sanitize_js_value(value):
                """Remove caracteres perigosos para JavaScript"""
                if not value:
                    return ''
                value = str(value).replace("'", "").replace('"', '').replace('\n', '').replace('\r', '').replace('\\', '')
                # Permitir apenas alfanuméricos, underscore, hífen, ponto
                value = re.sub(r'[^a-zA-Z0-9_.-]', '', value)
                return value[:64]  # Limitar tamanho
            
            tracking_token_safe = sanitize_js_value(tracking_param)
            bot_username_safe = sanitize_js_value(pool_bot.bot.username)
            
            # ✅ CORREÇÃO: Passar pixel_id apenas se Meta Pixel está habilitado
            pixel_id_to_template = pool.meta_pixel_id if has_meta_pixel else None
            utmify_pixel_id_to_template = pool.utmify_pixel_id if has_utmify else None
            
            # ✅ LOG DIAGNÓSTICO: Verificar valores passados para template
            logger.info(f"📊 Template params - has_utmify: {has_utmify}, utmify_pixel_id_to_template: {'✅' if utmify_pixel_id_to_template else '❌'} ({utmify_pixel_id_to_template[:20] + '...' if utmify_pixel_id_to_template else 'None'})")
            logger.info(f"📊 Template params - has_meta_pixel: {has_meta_pixel}, pixel_id_to_template: {'✅' if pixel_id_to_template else '❌'}")
            
            response = make_response(render_template('telegram_redirect.html',
                bot_username=bot_username_safe,
                tracking_token=tracking_token_safe,
                pixel_id=pixel_id_to_template,  # ✅ None se Meta Pixel desabilitado
                utmify_pixel_id=utmify_pixel_id_to_template,  # ✅ Pixel ID da Utmify (pode estar sem Meta Pixel)
                fbclid=sanitize_js_value(fbclid) if fbclid else '',
                utm_source=sanitize_js_value(request.args.get('utm_source', '')),
                utm_campaign=sanitize_js_value(request.args.get('utm_campaign', '')),
                utm_medium=sanitize_js_value(request.args.get('utm_medium', '')),
                utm_content=sanitize_js_value(request.args.get('utm_content', '')),
                utm_term=sanitize_js_value(request.args.get('utm_term', '')),
                grim=sanitize_js_value(request.args.get('grim', ''))
            ))
            
            # ✅ CRÍTICO: Adicionar headers anti-cache para evitar cache de tracking_token
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            
            return response
        except Exception as e:
            # ✅ FALLBACK SEGURO: Se template falhar, redirect direto (comportamento atual)
            logger.error(f"❌ Erro ao renderizar template telegram_redirect.html: {e} | Usando fallback redirect direto", exc_info=True)
            # Continuar para redirect direto (linha 4382) - não retornar aqui, deixar código continuar
    
    # ✅ FALLBACK: Se não tem pixel_id ou é crawler ou Meta Pixel está desabilitado, usar fallback simples
    # ✅ CORREÇÃO: tracking_token pode ser None se Meta Pixel está desabilitado (comportamento esperado)
    if tracking_token and not is_crawler_request:
        # tracking_token tem 32 caracteres (uuid4.hex), bem abaixo do limite de 64
        tracking_param = tracking_token
        logger.info(f"✅ Tracking param: {tracking_token} ({len(tracking_token)} chars)")
    elif is_crawler_request:
        # ✅ Crawler: usar fallback (não tem tracking mesmo)
        tracking_param = f"p{pool.id}"
        logger.info(f"🤖 Crawler detectado - usando fallback: {tracking_param}")
    elif not pool.meta_tracking_enabled:
        # ✅ Meta Pixel desabilitado: usar fallback (não há tracking para fazer)
        tracking_param = f"p{pool.id}"
        logger.info(f"⚠️ Meta Pixel desabilitado - usando fallback: {tracking_param}")
    else:
        # ✅ ERRO CRÍTICO: tracking_token deveria existir mas está None
        # Isso indica um BUG - tracking_token só é None se is_crawler_request = True OU meta_tracking_enabled = False
        logger.error(f"❌ [REDIRECT] tracking_token é None mas não é crawler e Meta Pixel está habilitado - ISSO É UM BUG!")
        logger.error(f"   Pool: {pool.name} | Slug: {slug} | is_crawler_request: {is_crawler_request} | meta_tracking_enabled: {pool.meta_tracking_enabled}")
        logger.error(f"   tracking_token deveria ter sido gerado quando meta_tracking_enabled=True")
        # ✅ FALHAR: Não usar fallback que não tem tracking_data (quebra Purchase)
        raise ValueError(
            f"tracking_token ausente - não pode usar fallback sem tracking_data. "
            f"Pool: {pool.name} | Slug: {slug} | is_crawler_request: {is_crawler_request} | meta_tracking_enabled: {pool.meta_tracking_enabled}"
        )
    
    redirect_url = f"https://t.me/{pool_bot.bot.username}?start={tracking_param}"
    
    # ✅ CRÍTICO: Injetar cookies _fbp e _fbc no redirect response (apenas se Meta Pixel está habilitado)
    # Isso sincroniza o FBP gerado no servidor com o browser
    # Meta Pixel JS usará o mesmo FBP, garantindo matching perfeito
    response = make_response(redirect(redirect_url, code=302))
    
    # ✅ CORREÇÃO: Só injetar cookies se Meta Pixel está habilitado (fbp_cookie e fbc_cookie só são definidos nesse caso)
    if pool.meta_tracking_enabled and (fbp_cookie or fbc_cookie):
        # ✅ Injetar _fbp/_fbc gerados no servidor (90 dias - padrão Meta)
        cookie_kwargs = {
            'max_age': 90 * 24 * 60 * 60,
            'httponly': False,
            'secure': True,
            'samesite': 'None',
        }
        if fbp_cookie:
            response.set_cookie('_fbp', fbp_cookie, **cookie_kwargs)
            logger.info(f"✅ Cookie _fbp injetado: {fbp_cookie[:30]}...")
        if fbc_cookie:
            response.set_cookie('_fbc', fbc_cookie, **cookie_kwargs)
            logger.info(f"✅ Cookie _fbc injetado: {fbc_cookie[:30]}...")
    
    return response
```

---

# B) Telegram Bot — `_handle_start_command` (bot_manager.py)

```python
    def _handle_start_command(self, bot_id: int, token: str, config: Dict[str, Any], 
                             chat_id: int, message: Dict[str, Any], start_param: str = None):
        """
        Processa comando /start - FAST RESPONSE MODE (QI 200)
        
        ✅ REGRA ABSOLUTA QI 200: /start SEMPRE reinicia o funil
        - Ignora conversa ativa
        - Ignora histórico
        - Ignora steps anteriores
        - Zera tudo e começa do zero
        
        ✅ OTIMIZAÇÃO QI 200: Resposta <50ms
        - Envia mensagem IMEDIATAMENTE
        - Processa tarefas pesadas em background via RQ
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            config: Configuração do bot (será recarregada do banco)
            chat_id: ID do chat
            message: Dados da mensagem
            start_param: Parâmetro do deep link (ex: "acesso", "promo123", None se não houver)
        """
        try:
            # ✅ QI 200: PRIORIDADE MÁXIMA - Resetar funil ANTES de qualquer verificação
            user_from = message.get('from', {})
            telegram_user_id = str(user_from.get('id', ''))
            first_name = user_from.get('first_name', 'Usuário')
            
            logger.info(f"⭐ COMANDO /START recebido - Reiniciando funil FORÇADAMENTE (regra absoluta)")

            # ✅ EXTRAÇÃO FORÇADA DO START PARAM (fallback se não veio pelo argumento)
            if not start_param:
                try:
                    text_msg = message.get('text') if isinstance(message, dict) else None
                    if text_msg and isinstance(text_msg, str):
                        parts = text_msg.split()
                        if len(parts) > 1:
                            start_param = parts[1].strip()
                            logger.info(f"🔧 start_param recuperado do texto: '{start_param}'")
                except Exception as e:
                    logger.warning(f"⚠️ Falha ao extrair start_param do texto: {e}")

            # ============================================================================
            # ✅ HIDRATAÇÃO DE TRACKING (PRIORIDADE MÁXIMA - ANTES DE QUALQUER RESET)
            # ============================================================================
            logger.info(f"🔍 Tentando processar tracking para param: '{start_param}'")
            try:
                from app import app, db
                from models import BotUser
                if start_param:
                    with app.app_context():
                        bot_user_track = BotUser.query.filter_by(
                            bot_id=bot_id,
                            telegram_user_id=telegram_user_id,
                            archived=False
                        ).first()
                        if bot_user_track:
                            import json as _json
                            tracking_key = f"tracking:{start_param}"
                            redis_conn = get_redis_connection()
                            raw_payload = redis_conn.get(tracking_key) if redis_conn else None
                            if raw_payload:
                                payload = _json.loads(raw_payload)
                                bot_user_track.fbclid = payload.get('fbclid') or bot_user_track.fbclid
                                bot_user_track.fbp = payload.get('fbp') or bot_user_track.fbp
                                bot_user_track.fbc = payload.get('fbc') or bot_user_track.fbc
                                bot_user_track.last_fbclid = payload.get('fbclid') or bot_user_track.last_fbclid
                                bot_user_track.last_fbp = payload.get('fbp') or bot_user_track.last_fbp
                                bot_user_track.last_fbc = payload.get('fbc') or bot_user_track.last_fbc
                                bot_user_track.user_agent = payload.get('client_user_agent') or bot_user_track.user_agent
                                bot_user_track.ip_address = payload.get('client_ip') or bot_user_track.ip_address
                                bot_user_track.utm_source = payload.get('utm_source') or bot_user_track.utm_source
                                bot_user_track.utm_campaign = payload.get('utm_campaign') or bot_user_track.utm_campaign
                                bot_user_track.utm_content = payload.get('utm_content') or bot_user_track.utm_content
                                bot_user_track.utm_medium = payload.get('utm_medium') or bot_user_track.utm_medium
                                bot_user_track.utm_term = payload.get('utm_term') or bot_user_track.utm_term
                                bot_user_track.click_timestamp = datetime.now()
                                db.session.commit()
                                logger.info(f"🔗 TRACKING LINKED: User {bot_user_track.id} -> FBCLID: {bot_user_track.fbclid}")
            except Exception as e:
                logger.warning(f"⚠️ Falha na hidratação inicial de tracking via start_param={start_param}: {e}")
            
            # ============================================================================
            # ✅ PATCH QI 900 - ANTI-REPROCESSAMENTO DE /START
            # ============================================================================
            # PATCH 1: Bloquear múltiplos /start em sequência (intervalo de 5s)
            try:
                import redis
                import time as _time
                redis_conn = get_redis_connection()
                last_start_key = f"last_start:{chat_id}"
                last_start = redis_conn.get(last_start_key)
                now = int(_time.time())
                
                if last_start and now - int(last_start) < 5:
                    logger.info(f"⛔ Bloqueado /start duplicado em menos de 5s: chat_id={chat_id}")
                    return  # Sair sem processar
                
                # Registrar timestamp do /start atual (expira em 5s)
                redis_conn.set(last_start_key, now, ex=5)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar anti-duplicação de /start: {e} - continuando processamento")
            
            # PATCH 2: Se já enviou welcome, nunca mais envia
            try:
                from app import app, db
                from models import BotUser
                with app.app_context():
                    bot_user = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id,
                        archived=False
                    ).first()
                    
                    if bot_user and bot_user.welcome_sent:
                        logger.info(f"🔁 Flag welcome_sent resetada para permitir novo /start: chat_id={chat_id}")
                        bot_user.welcome_sent = False
                        bot_user.welcome_sent_at = None
                        db.session.commit()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar/resetar welcome_sent: {e} - continuando processamento")
            
            # ============================================================================
            # ✅ QI 500: Lock para evitar /start duplicado (lock adicional de segurança)
            # ============================================================================
            if not self._check_start_lock(chat_id):
                logger.warning(f"⚠️ /start duplicado bloqueado - já está processando")
                return  # Sair sem processar
            
            # ✅ QI 200: FAST RESPONSE MODE - Buscar apenas config mínima (1 query rápida)
            from app import app, db
            from models import Bot, BotUser
            
            # Buscar config do banco e fazer reset NO MESMO CONTEXTO (rápido - apenas 1 query)
            with app.app_context():
                # ✅ QI 500: RESET ABSOLUTO NO MESMO CONTEXTO (garante commit imediato)
                self._reset_user_funnel(bot_id, chat_id, telegram_user_id, db_session=db.session)
                
                bot = db.session.get(Bot, bot_id)
                if bot and bot.config:
                    config = bot.config.to_dict()
                else:
                    config = config or {}
                
                # ✅ QI 500: VERIFICAR welcome_sent APÓS reset (garantir que foi resetado)
                bot_user_check = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id,
                    archived=False
                ).first()
                
                if bot_user_check and bot_user_check.welcome_sent:
                    # Se ainda está True, forçar reset novamente (proteção extra)
                    logger.warning(f"⚠️ welcome_sent ainda True após reset - forçando reset novamente")
                    bot_user_check.welcome_sent = False
                    bot_user_check.welcome_sent_at = None
                    db.session.commit()
                
                # Enfileirar processamento pesado (tracking, Redis, device parsing, etc)
                try:
                    from tasks_async import task_queue, process_start_async
                    if task_queue:
                        task_queue.enqueue(
                            process_start_async,
                            bot_id=bot_id,
                            token=token,
                            config=config,
                            chat_id=chat_id,
                            message=message,
                            start_param=start_param
                        )
                except Exception as e:
                    logger.warning(f"Erro ao enfileirar task async: {e}")
            
            # ============================================================================
            # ✅ V8 ULTRA: Verificação centralizada de modo ativo
            # ============================================================================
            is_flow_active = checkActiveFlow(config)
            
            # ✅ CRÍTICO: Default é SEMPRE True para garantir que welcome seja enviado quando flow não está ativo
            should_send_welcome = True  # Default: enviar welcome (CRÍTICO para clientes sem fluxo)
            
            logger.info(f"🔍 Verificação de modo: is_flow_active={is_flow_active}, should_send_welcome={should_send_welcome}")
            
            # ✅ CRÍTICO: Se flow está ativo, NUNCA enviar welcome_message
            if is_flow_active:
                logger.info(f"🎯 FLUXO VISUAL ATIVO - Executando fluxo visual")
                logger.info(f"🚫 BLOQUEANDO welcome_message, main_buttons, redirect_buttons, welcome_audio")
                
                # ✅ CRÍTICO: Definir should_send_welcome = False ANTES de executar
                # Isso garante que mesmo se _execute_flow falhar, welcome não será enviado
                should_send_welcome = False
                
                try:
                    logger.info(f"🚀 Chamando _execute_flow...")
                    logger.info(f"🚀 Config flow_enabled: {config.get('flow_enabled')}")
                    logger.info(f"🚀 Config flow_steps count: {len(config.get('flow_steps', [])) if isinstance(config.get('flow_steps'), list) else 'N/A'}")
                    logger.info(f"🚀 Config flow_start_step_id: {config.get('flow_start_step_id')}")
                    
                    self._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
                    logger.info(f"✅ _execute_flow concluído sem exceções")
                    
                    # Marcar welcome_sent após fluxo iniciar
                    with app.app_context():
                        try:
                            bot_user_update = BotUser.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id
                            ).first()
                            if bot_user_update:
                                bot_user_update.welcome_sent = True
                                from models import get_brazil_time
                                bot_user_update.welcome_sent_at = get_brazil_time()
                                db.session.commit()
                                logger.info(f"✅ Fluxo iniciado - welcome_sent=True")
                        except Exception as e:
                            logger.error(f"Erro ao marcar welcome_sent: {e}")
                    
                    logger.info(f"✅ Fluxo visual executado com sucesso - should_send_welcome=False (confirmado)")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao executar fluxo: {e}", exc_info=True)
                    # ✅ CRÍTICO: Mesmo com erro, NÃO enviar welcome_message
                    # O fluxo visual está ativo, então não deve usar sistema tradicional
                    should_send_welcome = False
                    logger.warning(f"⚠️ Fluxo falhou mas welcome_message está BLOQUEADO (flow_enabled=True)")
                    logger.warning(f"⚠️ Usuário não receberá welcome_message nem mensagem do fluxo")
            else:
                # ✅ Fluxo não está ativo - usar welcome_message normalmente
                logger.info(f"📝 Fluxo visual desabilitado ou vazio - usando welcome_message normalmente")
                should_send_welcome = True
                logger.info(f"✅ should_send_welcome confirmado como True (fluxo não ativo)")
            
            # ============================================================================
            # ✅ QI 200: ENVIAR MENSAGEM IMEDIATAMENTE (<50ms)
            # Processamento pesado foi enfileirado para background
            # ============================================================================
            logger.info(f"🔍 DECISÃO FINAL: should_send_welcome={should_send_welcome} (is_flow_active={is_flow_active})")
            logger.info(f"🔍 Condição para enviar welcome: should_send_welcome={should_send_welcome}")
            
            if should_send_welcome:
                logger.info(f"✅ ENVIANDO welcome_message - fluxo visual NÃO está ativo ou está vazio")
                welcome_message = config.get('welcome_message', 'Olá! Bem-vindo!')
                welcome_media_url = config.get('welcome_media_url')
                welcome_media_type = config.get('welcome_media_type', 'video')
                welcome_audio_enabled = config.get('welcome_audio_enabled', False)
                welcome_audio_url = config.get('welcome_audio_url', '')
                main_buttons = config.get('main_buttons', [])
                redirect_buttons = config.get('redirect_buttons', [])
                
                # Preparar botões de venda (incluir índice para identificar qual botão tem order bump)
                buttons = []
                for index, btn in enumerate(main_buttons):
                    if btn.get('text') and btn.get('price'):
                        price = float(btn.get('price', 0))
                        button_text = self._format_button_text(btn['text'], price, btn.get('price_position'))
                        buttons.append({
                            'text': button_text,
                            'callback_data': f"buy_{index}"  # ✅ CORREÇÃO: Usar apenas o índice (max 10 bytes)
                        })
                
                # Adicionar botões de redirecionamento (com URL)
                for btn in redirect_buttons:
                    if btn.get('text') and btn.get('url'):
                        buttons.append({
                            'text': btn['text'],
                            'url': btn['url']  # Botão com URL abre direto no navegador
                        })
                
                # ✅ QI 500: Enviar tudo SEQUENCIALMENTE (garante ordem)
                # Verificar se URL de mídia é válida (não pode ser canal privado)
                valid_media = False
                if welcome_media_url:
                    # URLs de canais privados começam com /c/ - não funcionam
                    if '/c/' not in welcome_media_url and welcome_media_url.startswith('http'):
                        valid_media = True
                    else:
                        logger.info(f"⚠️ Mídia de canal privado detectada - enviando só texto")
                
                # ✅ QI 500: Usar função sequencial para garantir ordem
                # Texto sempre enviado (como caption se houver mídia, ou mensagem separada)
                result = self.send_funnel_step_sequential(
                    token=token,
                    chat_id=str(chat_id),
                    text=welcome_message,  # Sempre enviar texto (será caption se houver mídia)
                    media_url=welcome_media_url if valid_media else None,
                    media_type=welcome_media_type if valid_media else None,
                    buttons=buttons,
                    delay_between=0.2  # ✅ QI 500: Delay de 0.2s entre envios
                )
                
                if result:
                    logger.info(f"✅ Mensagem /start enviada com {len(buttons)} botão(ões)")
                    
                    # ✅ MARCAR COMO ENVIADO NO BANCO
                    with app.app_context():
                        try:
                            bot_user_update = BotUser.query.filter_by(
                                bot_id=bot_id,
                                telegram_user_id=telegram_user_id
                            ).first()
                            if bot_user_update:
                                bot_user_update.welcome_sent = True
                                from models import get_brazil_time
                                bot_user_update.welcome_sent_at = get_brazil_time()
                                db.session.commit()
                                logger.info(f"✅ Marcado como welcome_sent=True")
                        except Exception as e:
                            logger.error(f"Erro ao marcar welcome_sent: {e}")
                    
                    # ✅ Enviar áudio adicional se habilitado
                    if welcome_audio_enabled and welcome_audio_url:
                        logger.info(f"🎤 Enviando áudio complementar...")
                        audio_result = self.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message="",  # Sem caption
                            media_url=welcome_audio_url,
                            media_type='audio',
                            buttons=None  # Sem botões no áudio
                        )
                        if audio_result:
                            logger.info(f"✅ Áudio complementar enviado")
                        else:
                            logger.warning(f"⚠️ Falha ao enviar áudio complementar")
                else:
                    logger.error(f"❌ Falha ao enviar mensagem")
            else:
                # ✅ Fluxo visual está ativo - welcome_message está bloqueado
                logger.info(f"✅ should_send_welcome=False - welcome_message BLOQUEADO (fluxo visual ativo)")
                logger.info(f"✅ Apenas o fluxo visual será executado, sem welcome_message tradicional")
            
            # ✅ CORREÇÃO: Emitir evento via WebSocket apenas para o dono do bot
            try:
                from app import app, db
                from models import Bot
                with app.app_context():
                    bot = db.session.get(Bot, bot_id)
                    if bot:
                        self.socketio.emit('bot_interaction', {
                            'bot_id': bot_id,
                            'type': 'start',
                            'chat_id': chat_id,
                            'user': message.get('from', {}).get('first_name', 'Usuário')
                        }, room=f'user_{bot.user_id}')
            except Exception as ws_error:
                logger.warning(f"⚠️ Erro ao emitir WebSocket bot_interaction: {ws_error}")
            
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar /start: {e}")
            import traceback
            traceback.print_exc()
```

---

# C) Geração de Pagamento — `_generate_pix_payment` (bot_manager.py)

```python
    def _generate_pix_payment(self, bot_id: int, amount: float, description: str,
                             customer_name: str, customer_username: str, customer_user_id: str,
                             order_bump_shown: bool = False, order_bump_accepted: bool = False, 
                             order_bump_value: float = 0.0, is_downsell: bool = False, 
                             downsell_index: int = None,
                             is_upsell: bool = False,  # ✅ NOVO - UPSELLS
                             upsell_index: int = None,  # ✅ NOVO - UPSELLS
                             is_remarketing: bool = False,  # ✅ NOVO - REMARKETING
                             remarketing_campaign_id: int = None,  # ✅ NOVO - REMARKETING
                             button_index: int = None,  # ✅ NOVO - SISTEMA DE ASSINATURAS
                             button_config: dict = None) -> Optional[Dict[str, Any]]:  # ✅ NOVO - SISTEMA DE ASSINATURAS
        """
        Gera pagamento PIX via gateway configurado
        
        Args:
            bot_id: ID do bot
            amount: Valor do pagamento
            description: Descrição do produto
            customer_name: Nome do cliente
            customer_username: Username do Telegram
            customer_user_id: ID do usuário no Telegram
            
        ✅ VALIDAÇÃO CRÍTICA: customer_user_id não pode ser vazio (destrói tracking Meta Pixel)
        """
        # ✅ VALIDAÇÃO CRÍTICA: customer_user_id obrigatório para tracking
        if not customer_user_id or customer_user_id.strip() == "":
            logger.error(f"❌ ERRO CRÍTICO: customer_user_id vazio ao gerar PIX! Bot: {bot_id}, Valor: R$ {amount:.2f}")
            logger.error(f"   Isso quebra tracking Meta Pixel - Purchase não será atribuído à campanha!")
            logger.error(f"   customer_name: {customer_name}, customer_username: {customer_username}")
            return None
        try:
            # Importar models dentro da função para evitar circular import
            from models import Bot, Gateway, Payment, db
            from app import app
            from sqlalchemy.exc import IntegrityError
            
            with app.app_context():
                # Buscar bot e gateway
                bot = db.session.get(Bot, bot_id)
                if not bot:
                    logger.error(f"Bot {bot_id} não encontrado")
                    return None
                
                # Buscar gateway ativo e verificado do usuário
                # ✅ CORREÇÃO: Filtrar também por gateway_type se necessário, mas permitir qualquer gateway ativo
                gateway = Gateway.query.filter_by(
                    user_id=bot.user_id,
                    is_active=True,
                    is_verified=True
                ).first()
                
                if not gateway:
                    logger.error(f"❌ Nenhum gateway ativo encontrado para usuário {bot.user_id} | Bot: {bot_id}")
                    logger.error(f"   Verifique se há um gateway configurado e ativo em /settings")
                    return None
                
                logger.info(f"💳 Gateway: {gateway.gateway_type.upper()} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")
                
                # ✅ PROTEÇÃO CONTRA MÚLTIPLOS PIX (SOLUÇÃO HÍBRIDA - SENIOR QI 500 + QI 502)
                
                # 1. Verificar se cliente tem PIX pendente para MESMO PRODUTO
                # ✅ CORREÇÃO: Normalizar descrição para comparação precisa
                def normalize_product_name(name):
                    """Remove emojis e normaliza para comparação"""
                    if not name:
                        return ''
                    import re
                    # Remove emojis e caracteres especiais
                    normalized = re.sub(r'[^\w\s]', '', name)
                    return normalized.lower().strip()
                
                normalized_description = normalize_product_name(description)
                
                # Buscar todos os PIX pendentes do cliente
                all_pending = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=customer_user_id,
                    status='pending'
                ).all()
                
                pending_same_product = None
                for p in all_pending:
                    if normalize_product_name(p.product_name) == normalized_description:
                        pending_same_product = p
                        break
                
                # ✅ REGRA DE NEGÓCIO: Reutilizar APENAS se foi gerado há <= 5 minutos E o valor bater exatamente
                if pending_same_product:
                    try:
                        from models import get_brazil_time
                        age_seconds = (get_brazil_time() - pending_same_product.created_at).total_seconds() if pending_same_product.created_at else 999999
                    except Exception:
                        age_seconds = 999999
                    amount_matches = abs(float(pending_same_product.amount) - float(amount)) < 0.01
                    if pending_same_product.status == 'pending' and age_seconds <= 300 and amount_matches:
                        # ✅ CORREÇÃO CRÍTICA: Paradise NÃO REUTILIZA PIX (evita duplicação de IDs)
                        # Paradise gera IDs únicos e não aceita reutilização
                        if gateway.gateway_type == 'paradise':
                            logger.warning(f"⚠️ Paradise não permite reutilizar PIX - gerando NOVO para evitar IDs duplicados.")
                        else:
                            logger.warning(f"⚠️ Já existe PIX pendente (<=5min) e valor igual para {description}. Reutilizando.")
                            pix_result = {
                                'pix_code': pending_same_product.product_description,
                                'pix_code_base64': None,
                                'qr_code_url': None,
                                'transaction_id': pending_same_product.gateway_transaction_id,
                                'transaction_hash': pending_same_product.gateway_transaction_hash,  # ✅ Incluir hash também
                                'payment_id': pending_same_product.payment_id,
                                'expires_at': None
                            }
                            logger.info(f"✅ PIX reutilizado: {pending_same_product.payment_id} | idade={int(age_seconds)}s | valor_ok={amount_matches}")
                            return pix_result
                    else:
                        logger.info(
                            f"♻️ NÃO reutilizar PIX existente: status={pending_same_product.status}, idade={int(age_seconds)}s, valor_ok={amount_matches}. Gerando NOVO PIX."
                        )
                
                # 2. Verificar rate limiting para OUTRO PRODUTO (2 minutos)
                last_pix = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=customer_user_id
                ).order_by(Payment.id.desc()).first()
                
                if last_pix and last_pix.status == 'pending':
                    from models import get_brazil_time
                    time_since = (get_brazil_time() - last_pix.created_at).total_seconds()
                    if time_since < 120:  # 2 minutos
                        wait_time = 120 - int(time_since)
                        wait_minutes = wait_time // 60
                        wait_seconds = wait_time % 60
                        
                        if wait_minutes > 0:
                            time_msg = f"{wait_minutes} minuto{'s' if wait_minutes > 1 else ''} e {wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"
                        else:
                            time_msg = f"{wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"
                        
                        logger.warning(f"⚠️ Rate limit: cliente deve aguardar {time_msg} para gerar novo PIX")
                        return {'rate_limit': True, 'wait_time': time_msg}  # Retorna tempo para frontend
                
                # Gerar ID único do pagamento (só se não houver PIX pendente)
                import uuid
                payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                
                # ✅ PREPARAR CREDENCIAIS ESPECÍFICAS PARA CADA GATEWAY
                # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
                # Isso garante que taxas premium do Top 3 sejam aplicadas em tempo real
                # Prioridade: user.commission_percentage > gateway.split_percentage > 2.0 (padrão)
                user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
                
                # ✅ CRÍTICO: Extrair credenciais e validar ANTES de criar gateway
                # Se descriptografia falhar, properties retornam None
                # IMPORTANTE: Acessar properties explicitamente para forçar descriptografia e capturar exceções
                try:
                    api_key = gateway.api_key
                    # ✅ LOG ESPECÍFICO PARA WIINPAY
                    if gateway.gateway_type == 'wiinpay':
                        if api_key:
                            logger.info(f"✅ [WiinPay] api_key descriptografada com sucesso (len={len(api_key)})")
                        else:
                            logger.warning(f"⚠️ [WiinPay] api_key retornou None (campo interno existe: {bool(gateway._api_key)})")
                except Exception as decrypt_error:
                    logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.api_key (gateway {gateway.id}): {decrypt_error}")
                    logger.error(f"   Tipo do gateway: {gateway.gateway_type}")
                    logger.error(f"   Isso indica que a descriptografia está FALHANDO com exceção")
                    api_key = None
                    # ✅ LOG ESPECÍFICO PARA WIINPAY
                    if gateway.gateway_type == 'wiinpay':
                        logger.error(f"❌ [WiinPay] ERRO CRÍTICO na descriptografia da api_key!")
                        logger.error(f"   Gateway ID: {gateway.id} | User ID: {gateway.user_id}")
                        logger.error(f"   Campo interno existe: {bool(gateway._api_key)}")
                        logger.error(f"   Exceção: {decrypt_error}")
                        logger.error(f"   SOLUÇÃO: Reconfigure o gateway WiinPay com a api_key correta em /settings")
                
                try:
                    client_secret = gateway.client_secret
                except Exception as decrypt_error:
                    logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.client_secret (gateway {gateway.id}): {decrypt_error}")
                    client_secret = None
                
                try:
                    product_hash = gateway.product_hash
                except Exception as decrypt_error:
                    logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.product_hash (gateway {gateway.id}): {decrypt_error}")
                    product_hash = None
                
                try:
                    split_user_id = gateway.split_user_id
                except Exception as decrypt_error:
                    logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.split_user_id (gateway {gateway.id}): {decrypt_error}")
                    split_user_id = None
                
                # ✅ CORREÇÃO CRÍTICA: WiinPay - SEMPRE usar ID da plataforma para split
                # O split_user_id NUNCA deve ser o mesmo user_id da api_key (conta de recebimento)
                # Isso causa erro 422: "A conta de split não pode ser a mesma conta de recebimento"
                if gateway.gateway_type == 'wiinpay':
                    platform_split_id = '68ffcc91e23263e0a01fffa4'  # ID da plataforma
                    old_id = '6877edeba3c39f8451ba5bdd'  # ID antigo (também inválido)
                    
                    # ✅ Extrair user_id da api_key (JWT) para validar
                    try:
                        import jwt
                        import json
                        # Decodificar JWT sem verificar assinatura (apenas para ler payload)
                        decoded = jwt.decode(api_key, options={"verify_signature": False}) if api_key else {}
                        api_key_user_id = decoded.get('userId') or decoded.get('user_id') or ''
                        logger.info(f"🔍 [WiinPay] user_id da api_key (JWT): {api_key_user_id}")
                    except Exception as jwt_error:
                        api_key_user_id = None
                        logger.warning(f"⚠️ [WiinPay] Não foi possível extrair user_id do JWT: {jwt_error}")
                    
                    # ✅ FORÇAR: Sempre usar ID da plataforma, nunca o user_id do usuário
                    if not split_user_id or split_user_id == old_id or split_user_id.strip() == '':
                        logger.info(f"✅ [WiinPay] split_user_id vazio/antigo, usando ID da plataforma: {platform_split_id}")
                        split_user_id = platform_split_id
                    elif split_user_id == api_key_user_id:
                        logger.warning(f"⚠️ [WiinPay] split_user_id é o mesmo da conta de recebimento ({api_key_user_id})!")
                        logger.warning(f"   Isso causará erro 422. Forçando ID da plataforma: {platform_split_id}")
                        split_user_id = platform_split_id
                    elif split_user_id != platform_split_id:
                        logger.warning(f"⚠️ [WiinPay] split_user_id diferente do ID da plataforma: {split_user_id}")
                        logger.warning(f"   Esperado: {platform_split_id} | Usando: {split_user_id}")
                        logger.warning(f"   Forçando ID da plataforma para garantir split correto")
                        split_user_id = platform_split_id
                    else:
                        logger.info(f"✅ [WiinPay] split_user_id correto (ID da plataforma): {split_user_id}")
                
                # ✅ VALIDAÇÃO: Verificar se credenciais foram descriptografadas corretamente
                # Se alguma propriedade retornar None mas o campo interno existir, significa erro de descriptografia
                encryption_error_detected = False
                
                if gateway._api_key and not api_key:
                    logger.error(f"❌ CRÍTICO: Erro ao descriptografar api_key do gateway {gateway.id}")
                    logger.error(f"   Campo interno existe: {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                    logger.error(f"   Property retornou: {api_key}")
                    logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                    logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                    logger.error(f"   Gateway ID: {gateway.id} | Tipo: {gateway.gateway_type} | User: {gateway.user_id}")
                    encryption_error_detected = True
                
                if gateway._client_secret and not client_secret:
                    logger.error(f"❌ CRÍTICO: Erro ao descriptografar client_secret do gateway {gateway.id}")
                    logger.error(f"   Campo interno existe: {gateway._client_secret[:30] if gateway._client_secret else 'None'}...")
                    logger.error(f"   Property retornou: {client_secret}")
                    logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                    logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                    logger.error(f"   Gateway ID: {gateway.id} | Tipo: {gateway.gateway_type} | User: {gateway.user_id}")
                    encryption_error_detected = True
                
                if gateway._product_hash and not product_hash:
                    logger.error(f"❌ CRÍTICO: Erro ao descriptografar product_hash do gateway {gateway.id}")
                    logger.error(f"   Campo interno existe: {gateway._product_hash[:30] if gateway._product_hash else 'None'}...")
                    logger.error(f"   Property retornou: {product_hash}")
                    logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                    logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                    encryption_error_detected = True
                
                if gateway._split_user_id and not split_user_id and gateway.gateway_type == 'wiinpay':
                    logger.warning(f"⚠️ WiinPay: split_user_id não descriptografado (pode ser normal se não configurado)")
                
                # ✅ Se detectou erro de descriptografia, retornar None imediatamente
                if encryption_error_detected:
                    logger.error(f"❌ ERRO DE DESCRIPTOGRAFIA DETECTADO - Payment NÃO será criado")
                    logger.error(f"   ACÃO NECESSÁRIA: Reconfigure o gateway {gateway.gateway_type} (ID: {gateway.id}) em /settings")
                    return None
                
                credentials = {
                    # SyncPay usa client_id/client_secret
                    'client_id': gateway.client_id,
                    'client_secret': client_secret,
                    # Outros gateways usam api_key
                    'api_key': api_key,
                    # ✅ Átomo Pay: api_token é salvo em api_key no banco, mas precisa ser passado como api_token
                    'api_token': api_key if gateway.gateway_type == 'atomopay' else None,
                    # ✅ Babylon: company_id é salvo em client_id no banco
                    'company_id': gateway.client_id if gateway.gateway_type == 'babylon' else None,
                    # Paradise
                    'product_hash': product_hash,
                    'offer_hash': gateway.offer_hash,
                    'store_id': gateway.store_id,
                    # WiinPay
                    'split_user_id': split_user_id,
                    # ✅ RANKING V2.0: Usar taxa do usuário (pode ser premium)
                    'split_percentage': user_commission
                }
                
                # ✅ VALIDAÇÃO ESPECÍFICA POR GATEWAY: Verificar credenciais obrigatórias
                if gateway.gateway_type == 'paradise':
                    if not api_key:
                        logger.error(f"❌ Paradise: api_key ausente ou não descriptografado")
                        return None
                    if not product_hash:
                        logger.error(f"❌ Paradise: product_hash ausente ou não descriptografado")
                        return None
                elif gateway.gateway_type == 'atomopay':
                    if not api_key:
                        logger.error(f"❌ Átomo Pay: api_token (api_key) ausente ou não descriptografado")
                        logger.error(f"   gateway.id: {gateway.id}")
                        return None
                    else:
                        logger.debug(f"🔑 Átomo Pay: api_token presente ({len(api_key)} caracteres)")
                elif gateway.gateway_type == 'syncpay':
                    # ✅ SyncPay usa client_id/client_secret, NÃO api_key
                    if not client_secret:
                        logger.error(f"❌ SyncPay: client_secret ausente ou não descriptografado")
                        logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                        if gateway._client_secret:
                            logger.error(f"   Campo interno existe mas descriptografia falhou!")
                            logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                        return None
                    if not gateway.client_id:
                        logger.error(f"❌ SyncPay: client_id ausente")
                        logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                        return None
                elif gateway.gateway_type in ['pushynpay', 'wiinpay']:
                    if not api_key:
                        logger.error(f"❌ {gateway.gateway_type.upper()}: api_key ausente ou não descriptografado")
                        logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id} | Tipo: {gateway.gateway_type}")
                        if gateway._api_key:
                            logger.error(f"   ❌ Campo interno existe mas descriptografia falhou!")
                            logger.error(f"   Campo interno (primeiros 30 chars): {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                            logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                            logger.error(f"   SOLUÇÃO CRÍTICA: Reconfigure o gateway {gateway.gateway_type.upper()} (ID: {gateway.id}) em /settings")
                            logger.error(f"   Passo a passo:")
                            logger.error(f"   1. Acesse /settings")
                            logger.error(f"   2. Encontre o gateway {gateway.gateway_type.upper()} (ID: {gateway.id})")
                            logger.error(f"   3. Reinsira a api_key do gateway")
                            logger.error(f"   4. Salve as configurações")
                        else:
                            logger.error(f"   Campo interno (_api_key) também está vazio - gateway não foi configurado corretamente")
                            logger.error(f"   SOLUÇÃO: Configure o gateway {gateway.gateway_type.upper()} em /settings")
                        return None
                elif gateway.gateway_type == 'babylon':
                    # ✅ BABYLON requer: api_key (Secret Key) + client_id (Company ID)
                    if not api_key:
                        logger.error(f"❌ BABYLON: api_key (Secret Key) ausente ou não descriptografado")
                        logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                        if gateway._api_key:
                            logger.error(f"   ❌ Campo interno existe mas descriptografia falhou!")
                            logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                            logger.error(f"   SOLUÇÃO: Reconfigure o gateway Babylon (ID: {gateway.id}) em /settings")
                        return None
                    if not gateway.client_id:
                        logger.error(f"❌ BABYLON: client_id (Company ID) ausente")
                        logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                        logger.error(f"   SOLUÇÃO: Configure o Company ID no gateway Babylon em /settings")
                        return None
                
                # Log para auditoria (apenas se for premium)
                if user_commission < 2.0:
                    logger.info(f"🏆 TAXA PREMIUM aplicada: {user_commission}% (User {bot.owner.id})")
                
                # ✅ PATCH 2 QI 200: Garantir que product_hash existe antes de usar
                # Se gateway não tem product_hash, será criado dinamicamente no generate_pix
                # Mas precisamos garantir que será salvo no banco após criação
                original_product_hash = gateway.product_hash
                
                # Gerar PIX via gateway (usando Factory Pattern)
                logger.info(f"🔧 Criando gateway {gateway.gateway_type} com credenciais...")
                
                # ✅ LOG DETALHADO PARA WIINPAY
                if gateway.gateway_type == 'wiinpay':
                    logger.info(f"🔍 [WiinPay Debug] Criando gateway com:")
                    logger.info(f"   - api_key presente: {bool(api_key)}")
                    logger.info(f"   - api_key length: {len(api_key) if api_key else 0}")
                    logger.info(f"   - split_user_id: {split_user_id}")
                    logger.info(f"   - split_percentage: {user_commission}%")
                    logger.info(f"   - credentials keys: {list(credentials.keys())}")
                
                payment_gateway = GatewayFactory.create_gateway(
                    gateway_type=gateway.gateway_type,
                    credentials=credentials
                )
                
                if not payment_gateway:
                    logger.error(f"❌ Erro ao criar gateway {gateway.gateway_type}")
                    if gateway.gateway_type == 'wiinpay':
                        logger.error(f"   WIINPAY: Gateway não foi criado - verifique:")
                        logger.error(f"   1. api_key foi descriptografada corretamente: {bool(api_key)}")
                        logger.error(f"   2. Gateway está ativo e verificado: is_active={gateway.is_active}, is_verified={gateway.is_verified}")
                        logger.error(f"   3. Verifique logs anteriores para erros de descriptografia")
                    return None
                
                logger.info(f"✅ Gateway {gateway.gateway_type} criado com sucesso!")
                
                # ✅ VALIDAÇÃO ESPECÍFICA: WiinPay valor mínimo R$ 3,00
                if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                    logger.error(f"❌ WIINPAY: Valor mínimo R$ 3,00 | Produto: R$ {amount:.2f}")
                    logger.error(f"   SOLUÇÃO: Use Paradise, Pushyn ou SyncPay para valores < R$ 3,00")
                    logger.error(f"   Ou aumente o preço do produto para mínimo R$ 3,00")
                    return None
                
                # Gerar PIX usando gateway isolado com DADOS REAIS DO CLIENTE
                logger.info(f"💰 Gerando PIX: R$ {amount:.2f} | Descrição: {description}")
                # ✅ CRÍTICO: Preparar customer_data ANTES de gerar PIX (para usar depois ao salvar Payment)
                customer_data = {
                    'name': customer_name or 'Cliente',
                    'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
                    'phone': customer_user_id,  # ✅ User ID do Telegram como identificador único
                    'document': customer_user_id  # ✅ User ID do Telegram (gateways aceitam)
                }
                pix_result = payment_gateway.generate_pix(
                    amount=amount,
                    description=description,
                    payment_id=payment_id,
                    customer_data=customer_data
                )
                
                logger.info(f"📊 Resultado do PIX: {pix_result}")
                
                # ✅ CORREÇÃO ROBUSTA: Se Payment foi criado mas gateway retornou None, marcar como 'pending_verification'
                if not pix_result:
                    # ✅ Log detalhado para WiinPay especificamente
                    if gateway.gateway_type == 'wiinpay':
                        logger.error(f"❌ WIINPAY: generate_pix retornou None!")
                        logger.error(f"   Bot ID: {bot_id} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")
                        logger.error(f"   Valor: R$ {amount:.2f} | Descrição: {description}")
                        logger.error(f"   api_key presente: {bool(api_key)}")
                        logger.error(f"   split_user_id: {split_user_id}")
                        logger.error(f"   split_percentage: {user_commission}%")
                        logger.error(f"   Verifique os logs acima para ver se a API da WiinPay retornou algum erro")
                    
                    # ✅ Verificar se Payment foi criado antes de retornar None
                    if 'payment' in locals() and payment:
                        try:
                            logger.warning(f"⚠️ [GATEWAY RETORNOU NONE] Gateway {gateway.gateway_type} retornou None")
                            logger.warning(f"   Bot: {bot_id}, Valor: R$ {amount:.2f}, Payment ID: {payment.payment_id}")
                            logger.warning(f"   Payment será marcado como 'pending_verification' para não perder venda")
                            
                            payment.status = 'pending_verification'
                            payment.gateway_transaction_id = None
                            payment.product_description = None
                            db.session.commit()
                            
                            logger.warning(f"⚠️ Payment {payment.id} marcado como 'pending_verification' (gateway retornou None)")
                            return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway retornou None'}
                        except Exception as commit_error:
                            logger.error(f"❌ Erro ao commitar Payment após gateway retornar None: {commit_error}", exc_info=True)
                            db.session.rollback()
                            return None
                    else:
                        # ✅ Payment não foi criado - retornar None normalmente
                        logger.error(f"❌ Gateway retornou None e Payment não foi criado")
                        return None
                
                if pix_result:
                    # ✅ CRÍTICO: Verificar se transação foi recusada
                    transaction_status = pix_result.get('status')
                    is_refused = transaction_status == 'refused' or pix_result.get('error')
                    
                    if is_refused:
                        logger.warning(f"⚠️ Transação RECUSADA pelo gateway - criando payment com status 'failed' para webhook")
                    else:
                        logger.info(f"✅ PIX gerado com sucesso pelo gateway!")
                    
                    # ✅ BUSCAR BOT_USER PARA COPIAR DADOS DEMOGRÁFICOS
                    from models import BotUser
                    bot_user = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=customer_user_id
                    ).first()
                    
                    # ✅ QI 500: GERAR/REUTILIZAR TRACKING_TOKEN V4 (mantém vínculo PageView → Purchase)
                    from utils.tracking_service import TrackingServiceV4
                    tracking_service = TrackingServiceV4()
                    
                    # Recuperar dados de tracking do bot_user
                    fbclid = getattr(bot_user, 'fbclid', None) if bot_user else None
                    utm_source = getattr(bot_user, 'utm_source', None) if bot_user else None
                    utm_medium = getattr(bot_user, 'utm_medium', None) if bot_user else None
                    utm_campaign = getattr(bot_user, 'utm_campaign', None) if bot_user else None
                    utm_content = getattr(bot_user, 'utm_content', None) if bot_user else None
                    utm_term = getattr(bot_user, 'utm_term', None) if bot_user else None
                    
                    redis_tracking_payload: Dict[str, Any] = {}
                    if not is_remarketing:
                        tracking_token = None

                    # ✅ CORREÇÃO CRÍTICA QI 1000+: PRIORIDADE MÁXIMA para bot_user.tracking_session_id
                    # Isso garante que o token do public_redirect seja SEMPRE usado (tem todos os dados: client_ip, client_user_agent, pageview_event_id)
                    # PROBLEMA IDENTIFICADO: Verificação estava DEPOIS de tracking:last_token e tracking:chat
                    # SOLUÇÃO: Verificar bot_user.tracking_session_id PRIMEIRO (antes de tudo)
                    # ✅ CORREÇÃO CRÍTICA V15: Se token gerado detectado, tentar recuperar token UUID correto via fbclid
                    if is_remarketing:
                        if bot_user and bot_user.tracking_session_id:
                            tracking_token = bot_user.tracking_session_id
                            logger.info(f"✅ [REMARKETING] Forçando tracking_token do BotUser.tracking_session_id: {tracking_token[:20]}...")
                        else:
                            tracking_token = None
                            logger.error(f"❌ [REMARKETING] BotUser sem tracking_session_id - Payment será criado sem tracking_token (atribuição prejudicada)")
                    elif bot_user and bot_user.tracking_session_id and not is_remarketing:
                        tracking_token = bot_user.tracking_session_id
                        logger.info(f"✅ Tracking token recuperado de bot_user.tracking_session_id (PRIORIDADE MÁXIMA): {tracking_token[:20]}...")
                        
                        # ✅ CORREÇÃO CRÍTICA V15: Validar se token é gerado e tentar recuperar token UUID correto
                        is_generated_token = tracking_token.startswith('tracking_')
                        if is_generated_token:
                            logger.error(f"❌ [GENERATE PIX] bot_user.tracking_session_id contém token GERADO: {tracking_token[:30]}...")
                            logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                            logger.error(f"   Tentando recuperar token UUID correto via fbclid...")
                            
                            # ✅ ESTRATÉGIA DE RECUPERAÇÃO: Tentar recuperar token UUID via fbclid
                            if bot_user and getattr(bot_user, 'fbclid', None):
                                try:
                                    fbclid_from_botuser = bot_user.fbclid
                                    tracking_token_key = f"tracking:fbclid:{fbclid_from_botuser}"
                                    recovered_token_from_fbclid = tracking_service.redis.get(tracking_token_key)
                                    if recovered_token_from_fbclid:
                                        # ✅ Validar que token recuperado é UUID (não gerado)
                                        # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                        normalized_recovered = recovered_token_from_fbclid.replace('-', '').lower()
                                        is_recovered_uuid = len(normalized_recovered) == 32 and all(c in '0123456789abcdef' for c in normalized_recovered)
                                        if is_recovered_uuid:
                                            tracking_token = recovered_token_from_fbclid
                                            logger.info(f"✅ [GENERATE PIX] Token UUID correto recuperado via fbclid: {tracking_token[:20]}...")
                                            logger.info(f"   Atualizando bot_user.tracking_session_id com token UUID correto")
                                            bot_user.tracking_session_id = tracking_token
                                        else:
                                            logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via fbclid tem formato inválido: {recovered_token_from_fbclid[:30]}... (len={len(recovered_token_from_fbclid)}) - IGNORANDO")
                                except Exception as e:
                                    logger.warning(f"⚠️ Erro ao recuperar token UUID via fbclid: {e}")
                            else:
                                logger.warning(f"⚠️ [GENERATE PIX] bot_user.fbclid ausente - não é possível recuperar token UUID correto")
                        
                        # ✅ Tentar recuperar payload completo do Redis
                        try:
                            recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                            if recovered_payload:
                                redis_tracking_payload = recovered_payload
                                logger.info(f"✅ Tracking payload recuperado do bot_user.tracking_session_id: fbp={'✅' if recovered_payload.get('fbp') else '❌'}, fbc={'✅' if recovered_payload.get('fbc') else '❌'}, ip={'✅' if recovered_payload.get('client_ip') else '❌'}, ua={'✅' if recovered_payload.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload.get('pageview_event_id') else '❌'}")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao recuperar payload do bot_user.tracking_session_id: {e}")
                    elif bot_user:
                        logger.warning(f"⚠️ BotUser {bot_user.id} encontrado mas tracking_session_id está vazio (telegram_user_id: {customer_user_id})")

                    # ✅ FALLBACK 1: tracking:last_token (se bot_user.tracking_session_id não existir)
                    # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de usar
                    if not is_remarketing and not tracking_token and customer_user_id:
                        try:
                            cached_token = tracking_service.redis.get(f"tracking:last_token:user:{customer_user_id}")
                            if cached_token:
                                # ✅ CORREÇÃO V16: Validar token antes de usar
                                is_generated_token = cached_token.startswith('tracking_')
                                # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                normalized_cached = cached_token.replace('-', '').lower()
                                is_uuid_token = len(normalized_cached) == 32 and all(c in '0123456789abcdef' for c in normalized_cached)
                                
                                if is_generated_token:
                                    logger.error(f"❌ [GENERATE PIX] Token recuperado de tracking:last_token é GERADO: {cached_token[:30]}... - IGNORANDO")
                                    logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                    # ✅ NÃO usar token gerado
                                elif is_uuid_token:
                                    tracking_token = cached_token
                                    logger.info(f"✅ Tracking token recuperado de tracking:last_token:user:{customer_user_id}: {tracking_token[:20]}...")
                                else:
                                    logger.warning(f"⚠️ [GENERATE PIX] Token recuperado de tracking:last_token tem formato inválido: {cached_token[:30]}... (len={len(cached_token)}) - IGNORANDO")
                        except Exception:
                            logger.exception("Falha ao recuperar tracking:last_token do Redis")
                    
                    # ✅ FALLBACK 2: tracking:chat (se bot_user.tracking_session_id não existir)
                    # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de usar
                    # ✅ REGRA: Remarketing NÃO pode gerar/substituir tracking_token aqui
                    if not is_remarketing and not tracking_token and customer_user_id:
                        try:
                            cached_payload = tracking_service.redis.get(f"tracking:chat:{customer_user_id}")
                            if cached_payload:
                                redis_tracking_payload = json.loads(cached_payload)
                                recovered_token_from_chat = redis_tracking_payload.get("tracking_token")
                                if recovered_token_from_chat:
                                    # ✅ CORREÇÃO V16: Validar token antes de usar
                                    is_generated_token = recovered_token_from_chat.startswith('tracking_')
                                    # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                    normalized_chat = recovered_token_from_chat.replace('-', '').lower()
                                    is_uuid_token = len(normalized_chat) == 32 and all(c in '0123456789abcdef' for c in normalized_chat)
                                    
                                    if is_generated_token:
                                        logger.error(f"❌ [GENERATE PIX] Token recuperado de tracking:chat é GERADO: {recovered_token_from_chat[:30]}... - IGNORANDO")
                                        logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                        # ✅ NÃO usar token gerado
                                    elif is_uuid_token:
                                        tracking_token = recovered_token_from_chat
                                        logger.info(f"✅ Tracking token recuperado de tracking:chat:{customer_user_id}: {tracking_token[:20]}...")
                                    else:
                                        logger.warning(f"⚠️ [GENERATE PIX] Token recuperado de tracking:chat tem formato inválido: {recovered_token_from_chat[:30]}... (len={len(recovered_token_from_chat)}) - IGNORANDO")
                        except Exception:
                            logger.exception("Falha ao recuperar tracking:chat do Redis")

                    tracking_data_v4: Dict[str, Any] = redis_tracking_payload if isinstance(redis_tracking_payload, dict) else {}

                    # ✅ CRÍTICO: Recuperar payload completo do Redis ANTES de gerar valores sintéticos
                    if tracking_token:
                        recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                        if recovered_payload:
                            tracking_data_v4 = recovered_payload
                            logger.info(f"✅ Tracking payload recuperado do Redis para token {tracking_token[:20]}... | fbp={'ok' if recovered_payload.get('fbp') else 'missing'} | fbc={'ok' if recovered_payload.get('fbc') else 'missing'} | pageview_event_id={'ok' if recovered_payload.get('pageview_event_id') else 'missing'}")
                        elif not tracking_data_v4:
                            logger.warning("⚠️ Tracking token %s sem payload no Redis - tentando reconstruir via BotUser", tracking_token)
                        # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                        # NUNCA atualizar com token gerado (deve ser UUID de 32 chars do redirect)
                        if bot_user and tracking_token:
                            # ✅ VALIDAÇÃO: tracking_token deve ser UUID (32 ou 36 chars, com ou sem hífens)
                            is_generated_token = tracking_token.startswith('tracking_')
                            # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                            normalized_token_check = tracking_token.replace('-', '').lower()
                            is_uuid_token = len(normalized_token_check) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check)
                            
                            if is_generated_token:
                                logger.error(f"❌ [GENERATE PIX] Tentativa de atualizar bot_user.tracking_session_id com token GERADO: {tracking_token[:30]}...")
                                logger.error(f"   Isso é um BUG - token gerado não deve ser salvo em bot_user.tracking_session_id")
                                # ✅ NÃO atualizar - manter token original do redirect
                            elif is_uuid_token:
                                # ✅ Token é UUID (vem do redirect) - pode atualizar
                                if bot_user.tracking_session_id != tracking_token:
                                    bot_user.tracking_session_id = tracking_token
                                    logger.info(f"✅ bot_user.tracking_session_id atualizado com token do redirect: {tracking_token[:20]}...")
                            else:
                                logger.warning(f"⚠️ [GENERATE PIX] tracking_token com formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})")
                                # ✅ NÃO atualizar - formato inválido

                    # ✅ NOTA: bot_user.tracking_session_id já foi verificado no início (prioridade máxima)
                    # Não precisa verificar novamente aqui
                    
                    if not tracking_token:
                        # ✅ ESTRATÉGIA 1: Tentar recuperar tracking_token do Redis usando fbclid do BotUser
                        # Isso recupera o token original do redirect mesmo se bot_user.tracking_session_id estiver vazio
                        recovered_token_from_fbclid = None
                        if bot_user and getattr(bot_user, 'fbclid', None):
                            try:
                                # ✅ CRÍTICO: Buscar tracking_token no Redis via fbclid (chave: tracking:fbclid:{fbclid})
                                fbclid_from_botuser = bot_user.fbclid
                                tracking_token_key = f"tracking:fbclid:{fbclid_from_botuser}"
                                recovered_token_from_fbclid = tracking_service.redis.get(tracking_token_key)
                                if recovered_token_from_fbclid:
                                    # ✅ Token encontrado via fbclid - recuperar payload completo
                                    tracking_token = recovered_token_from_fbclid
                                    logger.info(f"✅ Tracking token recuperado do Redis via fbclid do BotUser: {tracking_token[:20]}...")
                                    recovered_payload_from_fbclid = tracking_service.recover_tracking_data(tracking_token) or {}
                                    if recovered_payload_from_fbclid:
                                        tracking_data_v4 = recovered_payload_from_fbclid
                                        logger.info(f"✅ Tracking payload recuperado via fbclid: fbp={'✅' if recovered_payload_from_fbclid.get('fbp') else '❌'}, fbc={'✅' if recovered_payload_from_fbclid.get('fbc') else '❌'}, ip={'✅' if recovered_payload_from_fbclid.get('client_ip') else '❌'}, ua={'✅' if recovered_payload_from_fbclid.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload_from_fbclid.get('pageview_event_id') else '❌'}")
                                        # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                                        # Token recuperado via fbclid deve ser UUID (vem do redirect)
                                        if bot_user and tracking_token:
                                            is_generated_token = tracking_token.startswith('tracking_')
                                            # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                            normalized_token_check2 = tracking_token.replace('-', '').lower()
                                            is_uuid_token = len(normalized_token_check2) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check2)
                                            
                                            if is_generated_token:
                                                logger.error(f"❌ [GENERATE PIX] Token recuperado via fbclid é GERADO: {tracking_token[:30]}... - NÃO atualizar bot_user.tracking_session_id")
                                            elif is_uuid_token:
                                                if bot_user.tracking_session_id != tracking_token:
                                                    bot_user.tracking_session_id = tracking_token
                                                    logger.info(f"✅ bot_user.tracking_session_id atualizado com token recuperado via fbclid: {tracking_token[:20]}...")
                                            else:
                                                logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via fbclid tem formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao recuperar tracking_token via fbclid do BotUser: {e}")
                        
                        # ✅ ESTRATÉGIA 2: Tentar recuperar de tracking:chat:{customer_user_id}
                        if not tracking_token and bot_user:
                            try:
                                chat_key = f"tracking:chat:{customer_user_id}"
                                chat_payload_raw = tracking_service.redis.get(chat_key)
                                if chat_payload_raw:
                                    try:
                                        chat_payload = json.loads(chat_payload_raw)
                                        recovered_token_from_chat = chat_payload.get('tracking_token')
                                        if recovered_token_from_chat:
                                            tracking_token = recovered_token_from_chat
                                            logger.info(f"✅ Tracking token recuperado de tracking:chat:{customer_user_id}: {tracking_token[:20]}...")
                                            recovered_payload_from_chat = tracking_service.recover_tracking_data(tracking_token) or {}
                                            if recovered_payload_from_chat:
                                                tracking_data_v4 = recovered_payload_from_chat
                                                logger.info(f"✅ Tracking payload recuperado via chat: fbp={'✅' if recovered_payload_from_chat.get('fbp') else '❌'}, fbc={'✅' if recovered_payload_from_chat.get('fbc') else '❌'}, ip={'✅' if recovered_payload_from_chat.get('client_ip') else '❌'}, ua={'✅' if recovered_payload_from_chat.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload_from_chat.get('pageview_event_id') else '❌'}")
                                                # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                                                # Token recuperado via chat deve ser UUID (vem do redirect)
                                                if bot_user and tracking_token:
                                                    is_generated_token = tracking_token.startswith('tracking_')
                                                    # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                                    normalized_token_check3 = tracking_token.replace('-', '').lower()
                                                    is_uuid_token = len(normalized_token_check3) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check3)
                                                    
                                                    if is_generated_token:
                                                        logger.error(f"❌ [GENERATE PIX] Token recuperado via chat é GERADO: {tracking_token[:30]}... - NÃO atualizar bot_user.tracking_session_id")
                                                    elif is_uuid_token:
                                                        if bot_user.tracking_session_id != tracking_token:
                                                            bot_user.tracking_session_id = tracking_token
                                                            logger.info(f"✅ bot_user.tracking_session_id atualizado com token recuperado via chat: {tracking_token[:20]}...")
                                                    else:
                                                        logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via chat tem formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Erro ao parsear chat_payload: {e}")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao recuperar tracking_token de tracking:chat: {e}")
                        
                        # ✅ CORREÇÃO CRÍTICA V17: Se PIX foi gerado com sucesso, SEMPRE criar Payment
                        # tracking_token ausente não deve bloquear criação de Payment se PIX já foi gerado
                        # Isso evita perder vendas quando gateway gera PIX mas tracking_token não está disponível
                        if not tracking_token:
                            # ✅ Verificar se PIX foi gerado com sucesso (pix_result existe e tem transaction_id)
                            if pix_result and pix_result.get('transaction_id'):
                                gateway_transaction_id_temp = pix_result.get('transaction_id')
                                logger.warning(f"⚠️ [TOKEN AUSENTE] tracking_token AUSENTE - PIX já foi gerado (transaction_id: {gateway_transaction_id_temp})")
                                logger.warning(f"   Isso indica que o usuário NÃO passou pelo redirect ou tracking_session_id não foi salvo")
                                logger.warning(f"   bot_user.tracking_session_id: {getattr(bot_user, 'tracking_session_id', None) if bot_user else 'N/A'}")
                                logger.warning(f"   bot_user.fbclid: {getattr(bot_user, 'fbclid', None) if bot_user else 'N/A'}")
                                logger.warning(f"   Payment será criado mesmo sem tracking_token para evitar perder venda")
                                logger.warning(f"   Meta Pixel Purchase terá atribuição reduzida (sem pageview_event_id)")
                                # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                                # tracking_token será None no Payment
                            else:
                                # ✅ PIX não foi gerado - pode falhar normalmente
                                error_msg = f"❌ [TOKEN AUSENTE] tracking_token AUSENTE e PIX não foi gerado para BotUser {bot_user.id if bot_user else 'N/A'} (customer_user_id: {customer_user_id})"
                                logger.error(error_msg)
                                logger.error(f"   Isso indica que o usuário NÃO passou pelo redirect ou tracking_session_id não foi salvo")
                                logger.error(f"   bot_user.tracking_session_id: {getattr(bot_user, 'tracking_session_id', None) if bot_user else 'N/A'}")
                                logger.error(f"   bot_user.fbclid: {getattr(bot_user, 'fbclid', None) if bot_user else 'N/A'}")
                                logger.error(f"   SOLUÇÃO: Usuário deve acessar link de redirect primeiro: /go/{{slug}}?grim=...&fbclid=...")
                                logger.error(f"   Payment NÃO será criado sem tracking_token válido e sem PIX gerado")
                                
                                # ✅ FALHAR: Não gerar token, não criar Payment sem tracking_token válido E sem PIX
                                raise ValueError(
                                    f"tracking_token ausente e PIX não gerado - usuário deve acessar link de redirect primeiro. "
                                    f"BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id. "
                                    f"SOLUÇÃO: Acessar /go/{{slug}}?grim=...&fbclid=... antes de gerar PIX"
                                )
                    if not tracking_data_v4:
                        tracking_data_v4 = tracking_service.recover_tracking_data(tracking_token) or {}
                    
                    # Enriquecer com dados do BotUser quando faltarem no payload
                    enrichment_source = {
                        "fbclid": fbclid,
                        "utm_source": utm_source,
                        "utm_medium": utm_medium,
                        "utm_campaign": utm_campaign,
                        "utm_content": utm_content,
                        "utm_term": utm_term,
                        "grim": getattr(bot_user, 'campaign_code', None) if bot_user else None,
                    }
                    for key, value in enrichment_source.items():
                        if value and key not in tracking_data_v4:
                            tracking_data_v4[key] = value
                    
                    if tracking_data_v4.get('fbclid'):
                        fbclid = tracking_data_v4['fbclid']
                    if tracking_data_v4.get('utm_source'):
                        utm_source = tracking_data_v4['utm_source']
                    if tracking_data_v4.get('utm_medium'):
                        utm_medium = tracking_data_v4['utm_medium']
                    if tracking_data_v4.get('utm_campaign'):
                        utm_campaign = tracking_data_v4['utm_campaign']
                    if tracking_data_v4.get('utm_content'):
                        utm_content = tracking_data_v4['utm_content']
                    if tracking_data_v4.get('utm_term'):
                        utm_term = tracking_data_v4['utm_term']
                    
                    # ✅ CRÍTICO: Usar valores do Redis se disponíveis, só gerar sintéticos se faltar
                    fbp = tracking_data_v4.get('fbp')
                    fbc = tracking_data_v4.get('fbc')
                    pageview_event_id = tracking_data_v4.get('pageview_event_id')
                    
                    if not fbp:
                        fbp = tracking_service.generate_fbp(str(customer_user_id))
                        logger.warning(f"⚠️ fbp não encontrado no tracking_data_v4 - gerado sintético: {fbp[:30]}...")
                    else:
                        logger.info(f"✅ fbp recuperado do tracking_data_v4: {fbp[:30]}...")
                    
                    # ✅ CRÍTICO: NUNCA gerar fbc sintético em generate_pix_payment
                    # O fbc deve vir EXATAMENTE do redirect (cookie do browser)
                    # Gerar sintético aqui quebra a atribuição porque o timestamp não corresponde ao clique original
                    if fbc:
                        logger.info(f"✅ fbc recuperado do tracking_data_v4: {fbc[:30]}...")
                    else:
                        logger.warning(f"⚠️ fbc não encontrado no tracking_data_v4 - NÃO gerando sintético (preservando atribuição)")
                        # ✅ NÃO gerar fbc sintético - deixar None e confiar no fallback do Purchase
                    
                    if pageview_event_id:
                        logger.info(f"✅ pageview_event_id recuperado do tracking_data_v4: {pageview_event_id}")
                    else:
                        # ✅ FALLBACK: Tentar recuperar do bot_user (se houver tracking_session_id)
                        if bot_user and bot_user.tracking_session_id:
                            try:
                                # ✅ CORREÇÃO: Usar tracking_service (já instanciado acima) ao invés de tracking_service_v4
                                fallback_tracking = tracking_service.recover_tracking_data(bot_user.tracking_session_id)
                                pageview_event_id = fallback_tracking.get('pageview_event_id')
                                if pageview_event_id:
                                    logger.info(f"✅ pageview_event_id recuperado do bot_user.tracking_session_id: {pageview_event_id}")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao recuperar pageview_event_id do bot_user: {e}")
                        
                        if not pageview_event_id:
                            logger.warning(f"⚠️ pageview_event_id não encontrado no tracking_data_v4 nem no bot_user - Purchase pode não fazer dedup perfeito")
                    
                    # Gerar external_ids com dados reais recuperados
                    external_ids = tracking_service.build_external_id_array(
                        fbclid=fbclid,
                        telegram_user_id=str(customer_user_id),
                        email=getattr(bot_user, 'email', None) if bot_user else None,
                        phone=getattr(bot_user, 'phone', None) if bot_user else None
                    )
                    
                    tracking_update_payload = {
                        "tracking_token": tracking_token,
                        "bot_id": bot_id,
                        "customer_user_id": customer_user_id,
                        "fbclid": fbclid,
                        "fbp": fbp,
                        # ✅ CRÍTICO: Só incluir fbc se for válido (não None)
                        # Não sobrescrever fbc válido do Redis com None
                        **({"fbc": fbc} if fbc else {}),
                        "pageview_event_id": pageview_event_id,
                        "pageview_ts": tracking_data_v4.get('pageview_ts'),
                        "grim": tracking_data_v4.get('grim'),
                        "utm_source": utm_source,
                        "utm_medium": utm_medium,
                        "utm_campaign": utm_campaign,
                        "utm_content": utm_content,
                        "utm_term": utm_term,
                        "external_ids": external_ids,
                        "updated_from": "generate_pix_payment",
                    }
                    # ✅ CRÍTICO: Filtrar None/vazios para não sobrescrever dados válidos no Redis
                    tracking_service.save_tracking_token(tracking_token, {k: v for k, v in tracking_update_payload.items() if v})
                    
                    logger.info("Tracking token pronto: %s | fbp=%s | fbc=%s | pageview=%s", tracking_token, 'ok' if fbp else 'missing', 'ok' if fbc else 'missing', 'ok' if pageview_event_id else 'missing')
                    
                    # ✅ CRÍTICO: Determinar status do payment
                    # Se recusado, usar 'failed' para que webhook possa atualizar
                    # Se não recusado, usar 'pending' normalmente
                    payment_status = 'failed' if is_refused else 'pending'
                    
                    # ✅ CRÍTICO: Extrair transaction_id/hash (prioridade: transaction_id > transaction_hash)
                    gateway_transaction_id = (
                        pix_result.get('transaction_id') or 
                        pix_result.get('transaction_hash') or 
                        None
                    )
                    
                    # ✅ CRÍTICO: Extrair gateway_hash (campo 'hash' da resposta) para webhook matching
                    gateway_hash = pix_result.get('gateway_hash') or pix_result.get('transaction_hash')
                    
                    # ✅ CRÍTICO: Extrair reference para matching no webhook
                    reference = pix_result.get('reference')
                    
                    # ✅ PATCH 2 QI 200: Salvar product_hash se foi criado dinamicamente
                    if gateway.gateway_type in ['atomopay', 'umbrellapag'] and payment_gateway:
                        # Verificar se product_hash foi criado dinamicamente
                        current_product_hash = getattr(payment_gateway, 'product_hash', None)
                        if current_product_hash and current_product_hash != original_product_hash:
                            gateway.product_hash = current_product_hash
                            logger.info(f"💾 Product Hash criado dinamicamente e salvo no Gateway: {current_product_hash[:12]}...")
                    
                    # ✅ CRÍTICO: Extrair producer_hash para identificar conta do usuário (multi-tenant)
                    # Salvar no Gateway para que webhook possa identificar qual usuário enviou
                    producer_hash = pix_result.get('producer_hash')
                    if producer_hash and gateway.gateway_type == 'atomopay':
                        # ✅ Salvar producer_hash no Gateway (se ainda não tiver)
                        if not gateway.producer_hash:
                            gateway.producer_hash = producer_hash
                            logger.info(f"💾 Producer Hash salvo no Gateway: {producer_hash[:12]}...")
                    
                    # ✅ PATCH 2 & 3 QI 200: Commit de todas as alterações do Gateway
                    if gateway.gateway_type in ['atomopay', 'umbrellapag']:
                        db.session.commit()
                        if gateway.gateway_type == 'atomopay':
                            logger.info(f"💾 Gateway atualizado (product_hash, producer_hash)")
                        else:
                            logger.info(f"💾 Gateway atualizado (product_hash)")
                    
                    logger.info(f"💾 Salvando Payment com dados do gateway:")
                    logger.info(f"   payment_id: {payment_id}")
                    logger.info(f"   gateway_transaction_id: {gateway_transaction_id}")
                    logger.info(f"   gateway_hash: {gateway_hash}")
                    logger.info(f"   producer_hash: {producer_hash}")  # ✅ Para identificar conta do usuário
                    logger.info(f"   reference: {reference}")
                    
                    # ✅ CORREÇÃO CRÍTICA V17: VALIDAR tracking_token antes de criar Payment
                    # Se PIX foi gerado com sucesso, SEMPRE criar Payment (mesmo sem tracking_token)
                    # Isso evita perder vendas quando gateway gera PIX mas tracking_token não está disponível
                    if not tracking_token:
                        # ✅ Verificar se PIX foi gerado com sucesso (pix_result existe e tem transaction_id)
                        transaction_id_from_result = pix_result.get('transaction_id') if pix_result else None
                        if pix_result and transaction_id_from_result:
                            logger.warning(f"⚠️ [TOKEN AUSENTE] tracking_token AUSENTE - PIX já foi gerado (transaction_id: {transaction_id_from_result})")
                            logger.warning(f"   BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id")
                            logger.warning(f"   Payment será criado mesmo sem tracking_token para evitar perder venda")
                            logger.warning(f"   Meta Pixel Purchase terá atribuição reduzida (sem pageview_event_id)")
                            # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                            # tracking_token será None no Payment
                        else:
                            # ✅ PIX não foi gerado - pode falhar normalmente
                            error_msg = f"❌ [TOKEN AUSENTE] tracking_token AUSENTE e PIX não foi gerado - Payment NÃO será criado"
                            logger.error(error_msg)
                            logger.error(f"   BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id")
                            logger.error(f"   SOLUÇÃO: Usuário deve acessar link de redirect primeiro: /go/{{slug}}?grim=...&fbclid=...")
                            raise ValueError("tracking_token ausente e PIX não gerado - Payment não pode ser criado sem tracking_token válido e sem PIX")
                    
                    # ✅ CORREÇÃO V17: Validar tracking_token apenas se não for None
                    # ✅ CORREÇÃO CRÍTICA: Aceitar UUID com hífens (36 chars) OU sem hífens (32 chars)
                    is_generated_token = False
                    is_uuid_token = False
                    
                    if tracking_token:
                        is_generated_token = tracking_token.startswith('tracking_')
                        
                        # ✅ CORREÇÃO: Normalizar UUID removendo hífens para validação
                        # UUIDs podem vir em dois formatos:
                        # 1. Com hífens: faeac7b2-d4eb-4968-bf3b-87cad1b2bd5a (36 chars)
                        # 2. Sem hífens: faeac7b2d4eb4968bf3b87cad1b2bd5a (32 chars)
                        normalized_token = tracking_token.replace('-', '').lower()
                        is_uuid_token = len(normalized_token) == 32 and all(c in '0123456789abcdef' for c in normalized_token)
                        
                        # ✅ CORREÇÃO V14: Se PIX foi gerado com sucesso, permitir criar Payment mesmo com token gerado
                        # Isso evita perder vendas quando o gateway gera PIX mas o tracking_token não é ideal
                        # O warning será logado mas o Payment será criado para que o webhook possa processar
                        if is_generated_token:
                            logger.warning(f"⚠️ [TOKEN LEGADO] tracking_token LEGADO detectado: {tracking_token[:30]}...")
                            logger.warning(f"   PIX foi gerado com sucesso (transaction_id: {gateway_transaction_id})")
                            logger.warning(f"   Payment será criado mesmo com token legado para evitar perder venda")
                            logger.warning(f"   Meta Pixel Purchase pode ter atribuição reduzida (sem pageview_event_id)")
                            # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                        
                        if not is_uuid_token and not is_generated_token:
                            error_msg = f"❌ [GENERATE PIX] tracking_token com formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})"
                            logger.error(error_msg)
                            logger.error(f"   Payment NÃO será criado com token inválido")
                            logger.error(f"   tracking_token deve ser UUID (32 ou 36 chars, com ou sem hífens) ou gerado (tracking_*)")
                            raise ValueError(f"tracking_token com formato inválido - deve ser UUID (32 ou 36 chars) ou gerado (tracking_*)")
                        
                        # ✅ VALIDAÇÃO PASSOU - criar Payment
                        if is_uuid_token:
                            logger.info(f"✅ [TOKEN UUID] tracking_token validado: {tracking_token[:20]}... (UUID do redirect, len={len(tracking_token)})")
                        else:
                            logger.info(f"⚠️ [TOKEN LEGADO] tracking_token legado: {tracking_token[:20]}... (será usado mesmo assim)")
                    else:
                        # ✅ tracking_token é None - já foi logado como warning acima
                        logger.info(f"⚠️ [TOKEN AUSENTE] Payment será criado sem tracking_token (PIX já foi gerado)")
                    
                    # ✅ SISTEMA DE ASSINATURAS - Preparar dados de subscription
                    button_data_for_subscription = None
                    has_subscription_flag = False
                    
                    if button_config:
                        # Se button_config foi fornecido diretamente, usar
                        button_data_for_subscription = button_config.copy()
                        has_subscription_flag = button_config.get('subscription', {}).get('enabled', False)
                    elif button_index is not None:
                        # Se button_index foi fornecido, buscar do config do bot
                        if bot and bot.config:
                            config_dict = bot.config.to_dict()
                            main_buttons = config_dict.get('main_buttons', [])
                            if button_index < len(main_buttons):
                                button_data_for_subscription = main_buttons[button_index].copy()
                                has_subscription_flag = button_data_for_subscription.get('subscription', {}).get('enabled', False)
                    
                    # ✅ CORREÇÃO: Importar json localmente para evitar UnboundLocalError
                    import json as json_module
                    
                    # Salvar pagamento no banco (incluindo código PIX para reenvio + analytics)
                    # ✅ CRÍTICO: Preparar dados para Payment
                    # Determinar se é downsell, upsell ou normal
                    is_downsell_final = is_downsell or False
                    is_upsell_final = is_upsell or False
                    
                    payment = Payment(
                        bot_id=bot_id,  # ✅ OBRIGATÓRIO: ID do bot
                        payment_id=payment_id,  # ✅ OBRIGATÓRIO: ID único do pagamento
                        gateway_type=gateway.gateway_type if gateway else None,  # ✅ OBRIGATÓRIO: tipo do gateway
                        gateway_transaction_id=gateway_transaction_id,  # ✅ OBRIGATÓRIO: ID da transação
                        gateway_transaction_hash=gateway_hash,  # ✅ CRÍTICO: gateway_hash (campo 'hash' da resposta) para webhook matching
                        payment_method=str(pix_result.get('payment_method') or pix_result.get('paymentMethod') or 'PIX')[:20] if pix_result else 'PIX',
                        amount=amount,
                        customer_name=customer_name,
                        customer_username=customer_username,
                        customer_user_id=customer_user_id,
                        # ✅ CRÍTICO: Salvar email, phone e document do customer_data (para Meta Pixel Purchase)
                        customer_email=customer_data.get('email'),
                        customer_phone=customer_data.get('phone'),
                        customer_document=customer_data.get('document'),
                        product_name=description,
                        product_description=pix_result.get('pix_code'),  # Salvar código PIX para reenvio (None se recusado)
                        status=payment_status,  # ✅ 'failed' se recusado, 'pending' se não
                        # Analytics tracking
                        order_bump_shown=order_bump_shown,
                        order_bump_accepted=order_bump_accepted,
                        order_bump_value=order_bump_value,
                        is_downsell=is_downsell,
                        downsell_index=downsell_index,
                        is_upsell=is_upsell_final,  # ✅ NOVO - UPSELLS
                        upsell_index=upsell_index,  # ✅ NOVO - UPSELLS
                        is_remarketing=is_remarketing,  # ✅ NOVO - REMARKETING
                        remarketing_campaign_id=remarketing_campaign_id,  # ✅ NOVO - REMARKETING
                        # ✅ DEMOGRAPHIC DATA (Copiar de bot_user se disponível, com fallback seguro)
                        customer_age=getattr(bot_user, 'customer_age', None) if bot_user else None,
                        customer_city=getattr(bot_user, 'customer_city', None) if bot_user else None,
                        customer_state=getattr(bot_user, 'customer_state', None) if bot_user else None,
                        customer_country=getattr(bot_user, 'customer_country', 'BR') if bot_user else 'BR',
                        customer_gender=getattr(bot_user, 'customer_gender', None) if bot_user else None,
                        # ✅ DEVICE DATA (Copiar de bot_user se disponível, com fallback seguro)
                        device_type=getattr(bot_user, 'device_type', None) if bot_user else None,
                        os_type=getattr(bot_user, 'os_type', None) if bot_user else None,
                        browser=getattr(bot_user, 'browser', None) if bot_user else None,
                        device_model=getattr(bot_user, 'device_model', None) if bot_user else None,
                        # ✅ CRÍTICO: UTM TRACKING E CAMPAIGN CODE (grim) - PRIORIDADE: tracking_data_v4 > bot_user
                        # ✅ CORREÇÃO CRÍTICA: Usar UTMs do tracking_data_v4 (mais atualizados do redirect) ao invés de bot_user
                        utm_source=utm_source if utm_source else (getattr(bot_user, 'utm_source', None) if bot_user else None),
                        utm_campaign=utm_campaign if utm_campaign else (getattr(bot_user, 'utm_campaign', None) if bot_user else None),
                        utm_content=utm_content if utm_content else (getattr(bot_user, 'utm_content', None) if bot_user else None),
                        utm_medium=utm_medium if utm_medium else (getattr(bot_user, 'utm_medium', None) if bot_user else None),
                        utm_term=utm_term if utm_term else (getattr(bot_user, 'utm_term', None) if bot_user else None),
                        # ✅ CRÍTICO QI 600+: campaign_code (grim) para atribuição de campanha
                        # PRIORIDADE: tracking_data_v4.grim > bot_user.campaign_code
                        campaign_code=tracking_data_v4.get('grim') if tracking_data_v4.get('grim') else (getattr(bot_user, 'campaign_code', None) if bot_user else None),
                        # ✅ CRÍTICO: TRACKING_TOKEN V4 (pode ser None se PIX gerado sem tracking)
                        tracking_token=tracking_token,  # ✅ Token válido (UUID do redirect) ou None se ausente
                        # ✅ CRÍTICO: pageview_event_id para deduplicação Meta Pixel (fallback se Redis expirar)
                        # PRIORIDADE: tracking_data_v4.pageview_event_id > bot_user.pageview_event_id
                        pageview_event_id=pageview_event_id if pageview_event_id else (getattr(bot_user, 'pageview_event_id', None) if bot_user else None),
                        # ✅ CRÍTICO: fbclid para matching perfeito (persistente no banco)
                        # PRIORIDADE: tracking_data_v4.fbclid > bot_user.fbclid
                        fbclid=fbclid if fbclid else (getattr(bot_user, 'fbclid', None) if bot_user else None),
                        # ✅ CRÍTICO: fbp e fbc para fallback no Purchase (se Redis expirar)
                        # PRIORIDADE: tracking_data_v4 > bot_user
                        fbp=fbp if fbp else (getattr(bot_user, 'fbp', None) if bot_user else None),
                        fbc=fbc if fbc else (getattr(bot_user, 'fbc', None) if bot_user else None),
                        # ✅ CONTEXTO ORIGINAL DO CLIQUE (persistente para remarketing)
                        click_context_url=(
                            tracking_data_v4.get('event_source_url')
                            or getattr(bot_user, 'last_click_context_url', None)
                            or None
                        ),
                        # ✅ SISTEMA DE ASSINATURAS - Campos de subscription
                        button_index=button_index,
                        button_config=json_module.dumps(button_data_for_subscription, ensure_ascii=False) if button_data_for_subscription else None,
                        has_subscription=has_subscription_flag
                    )
                    db.session.add(payment)
                    db.session.flush()  # ✅ Flush para obter payment.id antes do commit
                    
                    # ✅ QI 500: Salvar tracking data no Redis (após criar payment para ter payment.id)
                    # ✅ CORREÇÃO V17: Só salvar se tracking_token não for None
                    # ✅ CORREÇÃO ROBUSTA: Não bloquear se Redis falhar
                    if tracking_token:
                        try:
                            tracking_service.save_tracking_data(
                                tracking_token=tracking_token,
                                bot_id=bot_id,
                                customer_user_id=customer_user_id,
                                payment_id=payment.id,
                                fbclid=fbclid,
                                fbp=fbp,
                                fbc=fbc,
                                utm_source=utm_source,
                                utm_medium=utm_medium,
                                utm_campaign=utm_campaign,
                                external_ids=external_ids
                            )
                            logger.info(f"✅ Tracking data salvo no Redis para payment {payment.id}")
                        except Exception as redis_error:
                            logger.warning(f"⚠️ [REDIS INDISPONÍVEL] Erro ao salvar tracking data no Redis: {redis_error}")
                            logger.warning(f"   Payment {payment.id} foi criado mesmo assim (tracking data é opcional)")
                            # ✅ NÃO bloquear - continuar mesmo se Redis falhar
                    else:
                        logger.warning(f"⚠️ [TOKEN AUSENTE] Não salvando tracking data no Redis (tracking_token é None)")
                    
                    # ✅ ATUALIZAR CONTADOR DE TRANSAÇÕES DO GATEWAY
                    gateway.total_transactions += 1
                    
                    # ✅ CORREÇÃO ROBUSTA: Validação de integridade antes de commit
                    try:
                        db.session.commit()
                        logger.info(f"✅ Payment {payment.id} commitado com sucesso")
                    except IntegrityError as integrity_error:
                        db.session.rollback()
                        logger.error(f"❌ [ERRO DE INTEGRIDADE] Erro ao commitar Payment: {integrity_error}", exc_info=True)
                        logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                        logger.error(f"   Gateway Transaction ID: {gateway_transaction_id}")
                        return None
                    except Exception as commit_error:
                        db.session.rollback()
                        logger.error(f"❌ [ERRO AO COMMITAR] Erro ao commitar Payment: {commit_error}", exc_info=True)
                        logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                        return None

                    # ✅ QI 500: PAGEVIEW ENRICHMENT NO MOMENTO DO PIX (FONTE DE VERDADE = PAYMENT)
                    # Re-enviar o MESMO PageView (mesmo event_id) com em/ph quando houver alta confiança.
                    # Meta fará merge por event_id (não duplica PageView).
                    try:
                        resolved_pageview_event_id = (
                            pageview_event_id
                            or getattr(payment, 'pageview_event_id', None)
                            or getattr(bot_user, 'pageview_event_id', None)
                        )
                        logger.info(
                            "🔎 ENRICHMENT CHECK | PIX",
                            extra={
                                "payment_db_id": getattr(payment, 'id', None),
                                "payment_id": getattr(payment, 'payment_id', None),
                                "pageview_event_id": pageview_event_id,
                                "resolved_pageview_event_id": resolved_pageview_event_id,
                                "tracking_token": tracking_token,
                                "has_customer_email": bool(getattr(payment, 'customer_email', None)),
                                "has_customer_phone": bool(getattr(payment, 'customer_phone', None)),
                                "pool_bot": bool(pool_bot),
                                "meta_enabled": bool(pool_bot and pool_bot.pool and pool_bot.pool.meta_tracking_enabled),
                                "meta_pageview_enabled": bool(pool_bot and pool_bot.pool and pool_bot.pool.meta_events_pageview)
                            }
                        )
                        if resolved_pageview_event_id and pool_bot and pool_bot.pool and pool_bot.pool.meta_tracking_enabled and pool_bot.pool.meta_events_pageview:
                            pool_for_meta = pool_bot.pool

                            customer_email = getattr(payment, 'customer_email', None)
                            customer_phone = getattr(payment, 'customer_phone', None)

                            def _is_high_confidence_email(email_value: str) -> bool:
                                if not email_value or not isinstance(email_value, str):
                                    return False
                                email_clean = email_value.strip().lower()
                                if '@' not in email_clean:
                                    return False
                                if email_clean.endswith('@telegram.local'):
                                    return False
                                if email_clean.startswith('user_') and email_clean.endswith('@telegram.local'):
                                    return False
                                return len(email_clean) >= 6

                            def _is_high_confidence_phone(phone_value: str) -> bool:
                                if not phone_value or not isinstance(phone_value, str):
                                    return False
                                digits = ''.join(filter(str.isdigit, phone_value))
                                if len(digits) < 10:
                                    return False
                                if digits in ('11999999999', '00000000000'):
                                    return False
                                return True

                            should_enrich = _is_high_confidence_email(customer_email) or _is_high_confidence_phone(customer_phone)
                            if should_enrich:
                                if not resolved_pageview_event_id:
                                    logger.warning(
                                        "🚨 PAGEVIEW_EVENT_ID AUSENTE | Enrichment impossível",
                                        extra={
                                            "payment_db_id": getattr(payment, 'id', None),
                                            "payment_id": getattr(payment, 'payment_id', None),
                                            "tracking_token": tracking_token,
                                            "bot_user_id": getattr(bot_user, 'id', None),
                                            "is_remarketing": bool(is_remarketing)
                                        }
                                    )
                                    return

                                enrichment_lock_key = f"meta:pageview_enriched:{resolved_pageview_event_id}"
                                lock_ttl_seconds = 60 * 60 * 24 * 30  # 30 dias

                                lock_acquired = False
                                try:
                                    lock_acquired = bool(tracking_service.redis.set(enrichment_lock_key, '1', nx=True, ex=lock_ttl_seconds))
                                except Exception as lock_error:
                                    logger.warning(f"⚠️ [META PAGEVIEW ENRICH] Falha ao criar lock Redis: {lock_error}")

                                logger.info(
                                    "🔎 ENRICHMENT LOCK RESULT",
                                    extra={
                                        "enrichment_lock_key": enrichment_lock_key,
                                        "lock_ttl_seconds": lock_ttl_seconds,
                                        "lock_acquired": bool(lock_acquired)
                                    }
                                )

                                if lock_acquired:
                                    from celery_app import send_meta_event
                                    from utils.encryption import decrypt
                                    from utils.meta_pixel import MetaPixelAPI

                                    try:
                                        access_token = decrypt(pool_for_meta.meta_access_token)
                                    except Exception as decrypt_error:
                                        logger.error(f"❌ [META PAGEVIEW ENRICH] Erro ao descriptografar access_token do pool {pool_for_meta.id}: {decrypt_error}")
                                        access_token = None

                                    if access_token:
                                        # IP/UA/FBP/FBC: pegar do tracking_data_v4, com fallback em Payment
                                        ip_value_for_enrich = tracking_data_v4.get('client_ip') or tracking_data_v4.get('ip') or tracking_data_v4.get('client_ip_address')
                                        if ip_value_for_enrich and isinstance(ip_value_for_enrich, str) and '.AQYBAQIA' in ip_value_for_enrich:
                                            ip_value_for_enrich = ip_value_for_enrich.split('.AQYBAQIA')[0]

                                        ua_value_for_enrich = tracking_data_v4.get('client_user_agent') or tracking_data_v4.get('ua') or tracking_data_v4.get('client_ua')
                                        fbp_value_for_enrich = tracking_data_v4.get('fbp') or getattr(payment, 'fbp', None)
                                        fbc_value_for_enrich = tracking_data_v4.get('fbc') or getattr(payment, 'fbc', None)

                                        fbclid_for_enrich = tracking_data_v4.get('fbclid') or getattr(payment, 'fbclid', None)

                                        telegram_user_id_for_enrich = None
                                        if bot_user and getattr(bot_user, 'telegram_user_id', None):
                                            telegram_user_id_for_enrich = str(bot_user.telegram_user_id)
                                        elif customer_user_id:
                                            telegram_user_id_for_enrich = str(customer_user_id).replace('user_', '')

                                        external_id_list = []
                                        if fbclid_for_enrich and isinstance(fbclid_for_enrich, str) and fbclid_for_enrich.strip():
                                            external_id_list.append(fbclid_for_enrich.strip())
                                        if telegram_user_id_for_enrich and telegram_user_id_for_enrich.strip():
                                            external_id_list.append(telegram_user_id_for_enrich.strip())

                                        user_data_enriched = MetaPixelAPI._build_user_data(
                                            customer_user_id=telegram_user_id_for_enrich,
                                            external_id=external_id_list,
                                            email=customer_email if _is_high_confidence_email(customer_email) else None,
                                            phone=customer_phone if _is_high_confidence_phone(customer_phone) else None,
                                            client_ip=ip_value_for_enrich,
                                            client_user_agent=ua_value_for_enrich,
                                            fbp=fbp_value_for_enrich,
                                            fbc=fbc_value_for_enrich
                                        )

                                        event_source_url_enrich = tracking_data_v4.get('event_source_url') or tracking_data_v4.get('first_page')

                                        pageview_enriched_event = {
                                            'event_name': 'PageView',
                                            'event_time': int(time.time()),
                                            'event_id': resolved_pageview_event_id,
                                            'action_source': 'website',
                                            'event_source_url': event_source_url_enrich,
                                            'user_data': user_data_enriched,
                                            'custom_data': {
                                                'source': 'pageview_enrichment',
                                                'payment_id': getattr(payment, 'payment_id', None),
                                                'payment_db_id': getattr(payment, 'id', None),
                                                'gateway_type': getattr(payment, 'gateway_type', None)
                                            }
                                        }

                                        send_meta_event.delay(
                                            pixel_id=pool_for_meta.meta_pixel_id,
                                            access_token=access_token,
                                            event_data=pageview_enriched_event,
                                            test_code=pool_for_meta.meta_test_event_code
                                        )

                                        logger.info(
                                            f"✅ [META PAGEVIEW ENRICH] Enfileirado após PIX | event_id={resolved_pageview_event_id} | "
                                            f"em={'✅' if user_data_enriched.get('em') else '❌'} | ph={'✅' if user_data_enriched.get('ph') else '❌'}"
                                        )
                                else:
                                    logger.info(f"ℹ️ [META PAGEVIEW ENRICH] Lock já existe (não reenviar) | key={enrichment_lock_key} | ttl={lock_ttl_seconds}s | event_id={resolved_pageview_event_id}")
                    except Exception as enrich_error:
                        logger.warning(f"⚠️ [META PAGEVIEW ENRICH] Falha ao enriquecer PageView após PIX (não bloqueia PIX): {enrich_error}")
                    
                    logger.info(f"✅ Pagamento registrado | Nosso ID: {payment_id} | SyncPay ID: {pix_result.get('transaction_id')}")
                    
                    # NOTIFICAR VIA WEBSOCKET (tempo real - BROADCAST para todos do usuário)
                    try:
                        from app import socketio, app, send_sale_notification
                        from models import Bot
                        
                        with app.app_context():
                            bot = db.session.get(Bot, bot_id)
                            if bot:
                                # ✅ CORREÇÃO CRÍTICA: Emitir evento 'new_sale' APENAS para o usuário dono do bot
                                socketio.emit('new_sale', {
                                    'id': payment.id,
                                    'customer_name': customer_name,
                                    'product_name': description,
                                    'amount': float(amount),
                                    'status': 'pending',
                                    'created_at': payment.created_at.isoformat(),
                                    'bot_id': bot_id
                                }, room=f'user_{bot.user_id}')
                                logger.info(f"📡 Evento 'new_sale' emitido para user_{bot.user_id} - R$ {amount}")
                                
                                # ✅ NOTIFICAR VENDA PENDENTE (Push Notification - respeita configurações)
                                send_sale_notification(
                                    user_id=bot.user_id,
                                    payment=payment,
                                    status='pending'
                                )
                    except Exception as ws_error:
                        logger.warning(f"⚠️ Erro ao emitir WebSocket: {ws_error}")
                    
                    return {
                        'payment_id': payment_id,
                        'pix_code': pix_result.get('pix_code'),
                        'qr_code_url': pix_result.get('qr_code_url'),
                        'qr_code_base64': pix_result.get('qr_code_base64')
                    }
                else:
                    logger.error(f"❌ FALHA AO GERAR PIX NO GATEWAY {gateway.gateway_type.upper()}")
                    logger.error(f"   Gateway Type: {gateway.gateway_type}")
                    logger.error(f"   Valor: R$ {amount:.2f}")
                    logger.error(f"   Descrição: {description}")
                    logger.error(f"   API Key presente: {bool(gateway.api_key)}")
                    
                    # ✅ VALIDAÇÃO ESPECÍFICA WIINPAY
                    if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                        logger.error(f"⚠️ WIINPAY: Valor mínimo é R$ 3,00! Valor enviado: R$ {amount:.2f}")
                        logger.error(f"   SOLUÇÃO: Use outro gateway (Paradise, Pushyn ou SyncPay) para valores < R$ 3,00")
                    
                    return None
                    
        except requests.exceptions.Timeout as timeout_error:
            # ✅ CORREÇÃO ROBUSTA: Gateway timeout - verificar se PIX foi gerado
            logger.warning(f"⚠️ [GATEWAY TIMEOUT] Gateway timeout ao gerar PIX")
            logger.warning(f"   Bot: {bot_id}, Valor: R$ {amount:.2f}")
            
            # ✅ Tentar encontrar Payment criado antes do timeout
            try:
                from models import db, Payment
                from app import app
                with app.app_context():
                    # Tentar encontrar Payment criado antes do timeout
                    payment = Payment.query.filter_by(
                        bot_id=bot_id,
                        customer_user_id=customer_user_id,
                        amount=amount,
                        status='pending'
                    ).order_by(Payment.id.desc()).first()
                    
                    if payment:
                        payment.status = 'pending_verification'
                        payment.gateway_transaction_id = None
                        db.session.commit()
                        logger.warning(f"⚠️ Payment {payment.id} marcado como 'pending_verification' (timeout)")
                        return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway timeout'}
            except Exception as commit_error:
                logger.error(f"❌ Erro ao processar timeout: {commit_error}", exc_info=True)
            
            logger.error(f"❌ Payment não foi criado antes do timeout - venda não iniciada")
            return None
                
        except Exception as e:
            # ✅ CORREÇÃO ROBUSTA: Verificar se gateway gerou PIX antes de fazer rollback
            logger.error(f"❌ [ERRO GATEWAY] Erro ao gerar PIX: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            
            # ✅ Verificar se gateway gerou PIX (pode estar em exception ou response)
            gateway_may_have_generated_pix = False
            transaction_id_from_error = None
            
            # ✅ ESTRATÉGIA 1: Verificar se exception tem transaction_id
            if hasattr(e, 'transaction_id') and e.transaction_id:
                gateway_may_have_generated_pix = True
                transaction_id_from_error = e.transaction_id
                logger.warning(f"⚠️ Exception contém transaction_id: {transaction_id_from_error}")
            
            # ✅ ESTRATÉGIA 2: Verificar se mensagem de erro contém transaction_id
            error_message = str(e).lower()
            if 'transaction_id' in error_message or 'transaction' in error_message:
                # Tentar extrair transaction_id da mensagem
                import re
                tx_match = re.search(r'transaction[_\s]?id[:\s]+([a-z0-9\-]+)', error_message, re.IGNORECASE)
                if tx_match:
                    gateway_may_have_generated_pix = True
                    transaction_id_from_error = tx_match.group(1)
                    logger.warning(f"⚠️ transaction_id extraído da mensagem de erro: {transaction_id_from_error}")
            
            # ✅ Se gateway pode ter gerado PIX, tentar encontrar Payment e marcar como 'pending_verification'
            if gateway_may_have_generated_pix:
                try:
                    from models import db, Payment
                    from app import app
                    with app.app_context():
                        # Tentar encontrar Payment criado antes do erro
                        payment = Payment.query.filter_by(
                            bot_id=bot_id,
                            customer_user_id=customer_user_id,
                            amount=amount
                        ).order_by(Payment.id.desc()).first()
                        
                        if payment:
                            payment.status = 'pending_verification'
                            if transaction_id_from_error:
                                payment.gateway_transaction_id = transaction_id_from_error
                            db.session.commit()
                            logger.warning(f"⚠️ Payment {payment.id} marcado como 'pending_verification' (gateway pode ter gerado PIX)")
                            return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': str(e)}
                except Exception as commit_error:
                    logger.error(f"❌ Erro ao processar erro do gateway: {commit_error}", exc_info=True)
            
            return None
```

---

# D) Modelo `Payment` (models.py)

```python
class Payment(db.Model):
    """Pagamento"""
    __tablename__ = 'payments'
    __table_args__ = (
        db.UniqueConstraint('gateway_type', 'gateway_transaction_hash', name='uq_payment_gateway_hash'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bots.id'), nullable=False, index=True)
    
    # Dados do pagamento
    payment_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    gateway_type = db.Column(db.String(30))
    gateway_transaction_id = db.Column(db.String(100))
    gateway_transaction_hash = db.Column(db.String(100))  # ✅ Hash para consulta de status (Paradise)

    payment_method = db.Column(db.String(20), nullable=True, index=True)
    
    # Valores
    amount = db.Column(db.Float, nullable=False)
    net_amount = db.Column(db.Float)
    
    # Dados do cliente
    customer_user_id = db.Column(db.String(255))
    customer_name = db.Column(db.String(255))
    customer_username = db.Column(db.String(255))
    # ✅ CRÍTICO: Email, phone e document do cliente (para Meta Pixel Purchase)
    customer_email = db.Column(db.String(255), nullable=True, index=True)
    customer_phone = db.Column(db.String(50), nullable=True, index=True)
    customer_document = db.Column(db.String(50), nullable=True)  # CPF/CNPJ
    
    # Produto
    product_name = db.Column(db.String(100))
    product_description = db.Column(db.Text)
    
    # Analytics - Tracking de conversão
    order_bump_shown = db.Column(db.Boolean, default=False)
    order_bump_accepted = db.Column(db.Boolean, default=False)
    order_bump_value = db.Column(db.Float, default=0.0)
    is_downsell = db.Column(db.Boolean, default=False)
    downsell_index = db.Column(db.Integer)
    is_upsell = db.Column(db.Boolean, default=False)
    upsell_index = db.Column(db.Integer)
    is_remarketing = db.Column(db.Boolean, default=False)
    remarketing_campaign_id = db.Column(db.Integer)
    
    # ✅ SISTEMA DE ASSINATURAS - Campos adicionais
    button_index = db.Column(db.Integer, nullable=True, index=True)  # Índice do botão clicado
    button_config = db.Column(db.Text, nullable=True)  # JSON completo do botão no momento da compra
    has_subscription = db.Column(db.Boolean, default=False, index=True)  # Flag rápida para filtrar
    
    # Status
    status = db.Column(db.String(20), default='pending', index=True)  # pending, paid, failed, cancelled (indexado para queries frequentes)
    
    # ✅ META PIXEL INTEGRATION
    meta_purchase_sent = db.Column(db.Boolean, default=False)
    meta_purchase_sent_at = db.Column(db.DateTime, nullable=True)
    meta_event_id = db.Column(db.String(100), nullable=True)
    meta_viewcontent_sent = db.Column(db.Boolean, default=False)
    meta_viewcontent_sent_at = db.Column(db.DateTime, nullable=True)
    
    # ✅ DELIVERY TRACKING - Purchase disparado na página de entrega
    delivery_token = db.Column(db.String(64), unique=True, nullable=True, index=True)  # Token único para acesso à página de entrega
    purchase_sent_from_delivery = db.Column(db.Boolean, default=False)  # Flag se Purchase foi disparado da página de entrega
    
    # ✅ FLUXO VISUAL - Rastreamento de step atual
    flow_step_id = db.Column(db.String(50), nullable=True, index=True)  # ID do step do fluxo que gerou este payment
    # ✅ UTM TRACKING
    utm_source = db.Column(db.String(255), nullable=True)
    utm_campaign = db.Column(db.String(255), nullable=True)
    utm_content = db.Column(db.String(255), nullable=True)
    utm_medium = db.Column(db.String(255), nullable=True)
    utm_term = db.Column(db.String(255), nullable=True)
    fbclid = db.Column(db.String(255), nullable=True)
    campaign_code = db.Column(db.String(255), nullable=True)
    # ✅ CONTEXTO ORIGINAL DO CLIQUE (persistente para remarketing / expiração do Redis)
    click_context_url = db.Column(db.Text, nullable=True)
    
    # ✅ TRACKING V4 - Tracking Token Universal
    tracking_token = db.Column(db.String(200), nullable=True, index=True)  # Tracking V4 - QI 500 (aumentado para 200 para garantir compatibilidade)
    # ✅ CRÍTICO: pageview_event_id para deduplicação Meta Pixel (fallback se Redis expirar)
    pageview_event_id = db.Column(db.String(256), nullable=True, index=True)  # Event ID do PageView para reutilizar no Purchase
    # ✅ META PIXEL COOKIES (para fallback no Purchase se Redis expirar)
    fbp = db.Column(db.String(255), nullable=True)  # Facebook Browser ID (_fbp cookie)
    fbc = db.Column(db.String(255), nullable=True)  # Facebook Click ID (_fbc cookie)
    
    # ✅ DEMOGRAPHIC DATA (Para Analytics Avançado)
    customer_age = db.Column(db.Integer, nullable=True)
    customer_city = db.Column(db.String(100), nullable=True)
    customer_state = db.Column(db.String(255), nullable=True)
    customer_country = db.Column(db.String(255), nullable=True, default='BR')
    customer_gender = db.Column(db.String(50), nullable=True)
    
    # ✅ DEVICE DATA
    device_type = db.Column(db.String(50), nullable=True)  # mobile/desktop
    os_type = db.Column(db.String(255), nullable=True)  # iOS/Android/Windows/Linux/macOS
    browser = db.Column(db.String(255), nullable=True)  # Chrome/Safari/Firefox
    device_model = db.Column(db.String(255), nullable=True)  # iPhone 14 Pro, Galaxy S23, etc.
    
    # Datas
    created_at = db.Column(db.DateTime, default=get_brazil_time, index=True)
    updated_at = db.Column(db.DateTime, default=get_brazil_time, onupdate=get_brazil_time)  # ✅ Campo para debounce no sync
    paid_at = db.Column(db.DateTime)
    
    def to_dict(self):
        """Retorna dados do pagamento em formato dict"""
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'amount': self.amount,
            'net_amount': self.net_amount,
            'customer_name': self.customer_name,
            'customer_username': self.customer_username,
            'product_name': self.product_name,
            'status': self.status,
            'gateway_type': self.gateway_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None
        }
```

---

# E) Template `delivery.html`

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Entrega - Acesso Liberado</title>
    
    {% if pixel_id %}
    <script>
        !function(f,b,e,v,n,t,s)
        {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)};
        if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
        n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];
        s.parentNode.insertBefore(t,s)}(window, document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');
        
        // Inicializa o Pixel
        fbq('init', '{{ pixel_id }}');
        
        // Dispara PageView (Padrão para manter a saúde do pixel)
        fbq('track', 'PageView');
    </script>
    <noscript><img height="1" width="1" style="display:none"
        src="https://www.facebook.com/tr?id={{ pixel_id }}&ev=PageView&noscript=1"
    /></noscript>
    {% endif %}
    <style>
        /* MANTIVE SEU CSS ORIGINAL INTACTO */
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; margin: 0; padding: 20px; text-align: center; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .container { max-width: 500px; width: 100%; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 40px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); }
        .success-icon { font-size: 80px; margin-bottom: 20px; }
        h1 { font-size: 28px; font-weight: 700; margin-bottom: 10px; }
        .product-name { font-size: 20px; font-weight: 600; margin-bottom: 10px; opacity: 0.9; }
        .amount { font-size: 24px; font-weight: 700; margin-bottom: 30px; color: #4ade80; }
        .redirect-button { background: white; color: #667eea; border: none; padding: 16px 32px; border-radius: 12px; font-size: 18px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-block; transition: transform 0.2s, box-shadow 0.2s; margin-top: 20px; }
        .redirect-button:hover { transform: scale(1.05); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2); }
        .loading { display: none; margin-top: 20px; font-size: 14px; opacity: 0.8; }
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✅</div>
        <h1>Acesso Liberado!</h1>
        <div class="product-name">Seu Acesso Imediato</div>
        
        <div class="amount">R$ {{ payment.amount }}</div>
        
        <a href="{{ redirect_url }}" id="redirect-link" class="redirect-button">
            Acessar Agora
        </a>
        <div class="loading" id="loading">Redirecionando...</div>
    </div>
    
    <script>
        // --- CONFIGURAÇÃO DE REDIRECIONAMENTO ---
        const REDIRECT_DELAY_MS = 4000; // 4 segundos é suficiente e melhor UX
        const redirectAllowedAt = Date.now() + REDIRECT_DELAY_MS;
        const redirectUrl = '{{ redirect_url }}'; // Vem do Flask
        const loadingEl = document.getElementById('loading');
        const linkEl = document.getElementById('redirect-link');

        function safeRedirect() {
            const now = Date.now();
            if (now < redirectAllowedAt) {
                return setTimeout(safeRedirect, redirectAllowedAt - now);
            }
            if (loadingEl) loadingEl.style.display = 'block';
            window.location.href = redirectUrl;
        }

        setTimeout(safeRedirect, REDIRECT_DELAY_MS);

        if (linkEl) {
            linkEl.addEventListener('click', function (e) {
                e.preventDefault();
                safeRedirect();
            });
        }
        
        // --- SISTEMA DE ATRIBUIÇÃO CERTEIRA (MATCHING) ---
        (function firePurchaseSafe() {
            {% if pixel_id %}
                if (typeof fbq === 'function') {
                    
                    // 1. Prepara os dados base do evento
                    var purchaseData = {
                        value: {{ payment.amount }},
                        currency: 'BRL',
                        content_name: 'Delivery',
                        eventID: '{{ payment.id }}' // Deduplicação Server-Side obrigatória
                    };

                    // 2. A MÁGICA: Recuperação do FBCLID do Banco
                    // O Jinja injeta o valor salvo no payment.fbclid
                    var savedFbclid = '{{ payment.fbclid if payment.fbclid else "None" }}';
                    
                    if (savedFbclid && savedFbclid !== 'None' && savedFbclid !== '') {
                        // Se temos o fbclid, montamos o parâmetro 'fbc' manualmente
                        // Formato oficial Meta: fb.1.TIMESTAMP_MS.FBCLID
                        // Como não temos o timestamp do clique exato, usamos o atual (aceitável para recovery)
                        var currentTs = Date.now();
                        purchaseData.fbc = 'fb.1.' + currentTs + '.' + savedFbclid;
                        
                        console.log("✅ Pixel: Modo Forced Matching Ativado com FBC:", purchaseData.fbc);
                    } else {
                        console.log("⚠️ Pixel: Modo Cookie Padrão (Sem fbclid no banco)");
                    }

                    // 3. Dispara o evento
                    fbq('track', 'Purchase', purchaseData);
                }
            {% endif %}
        })();
    </script>
    
    <script defer src="https://static.cloudflareinsights.com/beacon.min.js/vcd15cbe7772f49c399c6a5babf22c1241717689176015" integrity="sha512-ZpsOmlRQV6y907TI0dKBHq9Md29nnaEIPlkf84rnaERnq6zvWvPUqr2ft8M1aS28oN72PdrCzSjY4U6VaAw1EQ==" data-cf-beacon='{"version":"2024.11.0","token":"cd8c351eac4d4775b8b97afeae6b047a","r":1,"server_timing":{"name":{"cfCacheStatus":true,"cfEdge":true,"cfExtPri":true,"cfL4":true,"cfOrigin":true,"cfSpeedBrain":true},"location_startswith":null}}' crossorigin="anonymous"></script>
</body>
</html>
```

---

# F) Confirmação Final

Confirmo que todo o código acima foi copiado literalmente do repositório, sem qualquer modificação, omissão ou resumo.
