"""
Public Blueprint - GrimBots
Rotas públicas para redirecionamento de tráfego (/go/<slug>) com Cloaker e Load Balancing
"""
import logging
import time
from datetime import datetime
from flask import Blueprint, request, redirect, jsonify, render_template, make_response, current_app
from internal_logic.core.extensions import csrf
from internal_logic.core.models import RedirectPool, PoolBot, db
from internal_logic.core.extensions import limiter
from internal_logic.core.metrics import get_metrics_service
from internal_logic.services.cloaker_service import CloakerService
from internal_logic.services.bot_intelligence import BotIntelligenceService

logger = logging.getLogger(__name__)

public_bp = Blueprint('public', __name__, url_prefix='')


@public_bp.route('/go/<slug>')
@limiter.limit("60 per minute", key_func=lambda: request.remote_addr)
def public_redirect(slug):
    """
    🚀 Endpoint PROFISSIONAL de Redirecionamento
    
    Pipeline de Tráfego:
    1. Busca Simples
    2. Escudo (Cloaker V2.0)
    3. Rastreio (Meta CAPI)
    4. Inteligência (Seleção de Bot)
    5. Métricas Atômicas
    6. Redirect
    
    ⚠️ Serviços secundários NÃO bloqueiam o redirect
    """
    pipeline_start = time.time()
    
    # ═══════════════════════════════════════════════════════════
    # 1. BUSCA SIMPLES (sem joinedload - incompatible com lazy='dynamic')
    # ═══════════════════════════════════════════════════════════
    try:
        pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first()
        
        if not pool:
            logger.warning(f"🚫 Pool não encontrado: slug={slug}")
            return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        logger.error(f"❌ Erro ao buscar pool: {e}")
        return jsonify({'error': 'Service unavailable'}), 503
    
    # ═══════════════════════════════════════════════════════════
    # 2. ESCUDO (Cloaker V2.0) - BLOQUEANTE
    # ═══════════════════════════════════════════════════════════
    try:
        allowed, reason, log_data = CloakerService.validate_access(request, pool)
        if not allowed:
            return render_template('cloaker_block.html', pixel_id=getattr(pool, 'meta_pixel_id', None)), 200
    except Exception as e:
        logger.error(f"❌ Erro no cloaker: {e}")
        # Em caso de falha no cloaker, permitir acesso (fail-open)
        pass
    
    # ═══════════════════════════════════════════════════════════
    # 3. RASTREIO (Meta CAPI) - PREPARAR VARIÁVEIS
    # =================================================================
    tracking_token = None
    pixel_id_to_use = None
    fbclid = request.args.get('fbclid', '')
    
    try:
        if getattr(pool, 'meta_tracking_enabled', False):
            # Gerar tracking token
            import uuid
            tracking_token = uuid.uuid4().hex
            
            # Obter pixel_id do pool
            pixel_id_to_use = getattr(pool, 'meta_pixel_id', None)
            
            # Salvar tracking data no Redis (pool_id, pixel_id para o delivery)
            from utils.tracking_service import TrackingServiceV4
            tracking_service_v4 = TrackingServiceV4()
            tracking_service_v4.save_tracking_token(tracking_token, {
                'pool_id': pool.id,
                'pixel_id': pool.meta_pixel_id,
                'client_ip': request.remote_addr,
                'client_user_agent': request.headers.get('User-Agent', ''),
                'fbclid': request.args.get('fbclid', ''),
                'pageview_event_id': f"pageview_{tracking_token}",
            })

            # Disparar PageView (async) — V4: IP/UA plain text, event_id consistente
            from internal_logic.services.server_tracking import is_server_mode
            if is_server_mode(pool):
                from utils.encryption import decrypt
                access_token = decrypt(pool.meta_access_token) if pool.meta_access_token else None
            else:
                access_token = pool.meta_access_token
            if access_token:
                tracking_service_v4.fire_pageview(
                    pixel_id=pool.meta_pixel_id,
                    access_token=access_token,
                    tracking_token=tracking_token,
                    client_ip=request.remote_addr or '',
                    client_user_agent=request.headers.get('User-Agent', ''),
                    fbclid=request.args.get('fbclid', '') or None,
                    fbp=request.cookies.get('_fbp', '') or None,
                    fbc=request.cookies.get('_fbc', '') or None,
                    pageview_ts=int(time.time() * 1000),
                    event_source_url=request.url,
                    async_mode=True,
                )
            
            logger.info(f"[PIXEL_STICKY] /go/{slug}: pixel_id={pixel_id_to_use}, tracking_token={tracking_token}")
    except Exception as e:
        # Tracking nunca bloqueia o redirect
        logger.debug(f" Tracking não disparado: {e}")
        pass
    
    # ═══════════════════════════════════════════════════════════
    # 4. INTELIGÊNCIA (Seleção de Bot)
    # ═══════════════════════════════════════════════════════════
    try:
        selected_bot = BotIntelligenceService.select_bot(pool)
        
        if not selected_bot:
            # Fallback: tentar URL de fallback ou primeiro bot
            logger.warning(f"⚠️ Nenhum bot online no pool {pool.id}")
            
            # if hasattr(pool, 'fallback_url') and pool.fallback_url:
            #     return redirect(pool.fallback_url, code=302)
            
            all_bots = list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []
            if all_bots:
                selected_bot = all_bots[0]
                logger.info(f"🔄 Fallback para bot offline: {selected_bot.bot_id}")
            else:
                return jsonify({'error': 'No bots configured'}), 503
        
        bot_url = BotIntelligenceService.get_bot_telegram_url(selected_bot)
        if not bot_url:
            return jsonify({'error': 'Bot not configured'}), 503
            
    except Exception as e:
        logger.error(f"❌ Erro na seleção de bot: {e}")
        return jsonify({'error': 'Selection error'}), 503
    
    # ═══════════════════════════════════════════════════════════
    # 5. MÉTRICAS ATÔMICAS - NÃO BLOQUEANTE
    # ═══════════════════════════════════════════════════════════
    try:
        metrics_service = get_metrics_service(db.session)
        metrics_service.increment_redirect_counters(pool.id, selected_bot.id)
    except Exception as e:
        # Métricas nunca bloqueiam o redirect
        logger.debug(f"📊 Métricas não incrementadas: {e}")
        pass
    
    # ═══════════════════════════════════════════════════════════
    # 6. RENDER TEMPLATE (SEM REDIRECT 302)
    # =================================================================
    pipeline_duration = (time.time() - pipeline_start) * 1000
    logger.info(f"[PIXEL_STICKY] Render: pool={pool.slug} -> bot={selected_bot.bot_id} ({pipeline_duration:.1f}ms)")
    
    # Extrair bot_username da URL do Telegram
    bot_username = selected_bot.bot.username if hasattr(selected_bot.bot, 'username') else 'bot'
    bot_username_safe = bot_username.replace('@', '')
    
    # ✅ Pre-hashear fbclid para external_id do browser (match com server-side SHA-256)
    import hashlib as _hashlib
    fbclid_hash = _hashlib.sha256(fbclid.encode()).hexdigest() if fbclid else ''

    response = make_response(render_template('telegram_redirect.html',
        bot_username=bot_username_safe,
        tracking_token=tracking_token,
        pixel_id=pixel_id_to_use,
        fbclid=fbclid if fbclid else '',
        fbclid_hash=fbclid_hash,
        utm_source=request.args.get('utm_source', ''),
        utm_campaign=request.args.get('utm_campaign', ''),
        utm_medium=request.args.get('utm_medium', ''),
        utm_content=request.args.get('utm_content', ''),
        utm_term=request.args.get('utm_term', ''),
        grim=request.args.get('grim', ''),
        redirect_url=bot_url  # URL final para redirecionamento JS
    ))
    
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@public_bp.route('/health')
def public_health_check():
    """Health check público para monitoramento"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0'
    })


@public_bp.route('/termos-de-uso')
def termos_de_uso():
    """Página de Termos de Uso"""
    return render_template('termos_de_uso.html')


@public_bp.route('/politica-privacidade')
def politica_privacidade():
    """Página de Política de Privacidade"""
    return render_template('politica_privacidade.html')


@public_bp.route('/llms.txt')
def llms_txt():
    """llms.txt - AI-friendly guide to Grimbots"""
    resp = make_response("""# Grimbots - LLMs.txt
> Plataforma de automação de vendas no Telegram.

## Docs
- Termos de Uso: https://grimbots.com.br/termos-de-uso
- Política de Privacidade: https://grimbots.com.br/politica-privacidade
- Pricing: https://grimbots.com.br/pricing.md

## Core Features
- Multi-bots ilimitados: crie quantos bots de vendas precisar
- Order Bump: ofertas de pós-venda automáticas
- Downsell: segundas ofertas com desconto automático
- Meta Pixel CAPI: tracking de conversões mesmo com bloqueadores
- 7 gateways de pagamento: SyncPay, PushynPay, WiinPay, UmbrellaPag, BoltPay, BabylonPay, AguiaPags
- Painel visual sem código: arrastar e soltar para criar fluxos
- Suporte 24/7

## Key Differentiators
1. Gratuito para começar (sem cartão de crédito)
2. Bots ilimitados em todos os planos
3. Tracking anti-bloqueador com Meta CAPI
4. Múltiplos gateways sem taxa extra
""")
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@public_bp.route('/pricing.md')
def pricing_md():
    """pricing.md - Human-readable pricing page"""
    resp = make_response("""# Preços Grimbots

## Grátis
**R$ 0/mês**
- 1 fluxo de vendas ativo
- 1 gateway de pagamento
- Order bump básico
- Meta Pixel
- Suporte via Telegram

## Profissional
**R$ 47/mês**
- Fluxos ilimitados
- 3 gateways de pagamento
- Order bump + downsell
- Meta Pixel + CAPI
- Relatórios básicos
- Suporte prioritário

## Enterprise
**R$ 97/mês**
- Fluxos ilimitados
- 7 gateways de pagamento
- Order bump + downsell ilimitados
- Meta Pixel + CAPI avançado
- Relatórios avançados
- API exclusiva
- Gerente de conta

## Comparativo
| Funcionalidade | Grátis | Profissional | Enterprise |
|---|---|---|---|
| Fluxos ativos | 1 | Ilimitados | Ilimitados |
| Gateways | 1 | 3 | 7 |
| Order bump | Básico | Avançado | Ilimitado |
| Downsell | - | ✓ | ✓ |
| Meta Pixel | ✓ | ✓ + CAPI | ✓ + CAPI |
| API | - | - | ✓ |
| Suporte | Telegram | Prioritário | Gerente dedicado |
| Preço | R$ 0 | R$ 47/mês | R$ 97/mês |
""")
    resp.headers['Content-Type'] = 'text/markdown; charset=utf-8'
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@public_bp.route('/robots.txt')
def robots_txt():
    """robots.txt for search engines"""
    resp = make_response("""User-agent: *
Allow: /
Allow: /static/
Disallow: /go/
Disallow: /api/
Disallow: /admin/

Sitemap: https://grimbots.com.br/sitemap.xml
""")
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@public_bp.route('/sitemap.xml')
def sitemap_xml():
    """XML sitemap for search engines"""
    pages = [
        {'loc': 'https://grimbots.com.br/', 'priority': '1.0', 'changefreq': 'weekly'},
        {'loc': 'https://grimbots.com.br/termos-de-uso', 'priority': '0.5', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/politica-privacidade', 'priority': '0.6', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/blog', 'priority': '0.8', 'changefreq': 'weekly'},
        {'loc': 'https://grimbots.com.br/blog/automacao-vendas-telegram', 'priority': '0.7', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/blog/meta-pixel-capi-telegram', 'priority': '0.7', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/blog/order-bump-downsell-telegram', 'priority': '0.7', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/blog/gateways-pagamento-telegram', 'priority': '0.7', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/blog/bot-vendas-sem-codigo', 'priority': '0.7', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/pricing.md', 'priority': '0.5', 'changefreq': 'monthly'},
        {'loc': 'https://grimbots.com.br/llms.txt', 'priority': '0.3', 'changefreq': 'monthly'},
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for p in pages:
        xml += f'  <url>\n    <loc>{p["loc"]}</loc>\n    <priority>{p["priority"]}</priority>\n    <changefreq>{p["changefreq"]}</changefreq>\n  </url>\n'
    xml += '</urlset>'
    resp = make_response(xml)
    resp.headers['Content-Type'] = 'application/xml; charset=utf-8'
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@public_bp.route('/api/tracking/cookies', methods=['POST'])
@csrf.exempt
def capture_tracking_cookies():
    """
    V4.1: ENDPOINT PARA CAPTURAR COOKIES _FBP E _FBC DO BROWSER
    
    Chamado via Beacon API pelo telegram_redirect.html após Meta Pixel carregar.
    Atualiza tracking_data no Redis com cookies gerados pelo Meta Pixel.
    """
    try:
        # V4.1: Parsing robusto da V1 para Beacon API
        import json as json_lib
        
        # 1. Tentar forçar o JSON ignorando o Content-Type
        data = request.get_json(force=True, silent=True)
        
        # 2. Fallback: Parsear manualmente do body
        if not data:
            try:
                raw_data = request.get_data(as_text=True)
                if raw_data:
                    data = json_lib.loads(raw_data)
            except (json_lib.JSONDecodeError, ValueError):
                pass
        
        # 3. Fallback: Form data
        if not data and request.form:
            data = {
                'tracking_token': request.form.get('tracking_token'),
                '_fbp': request.form.get('_fbp'),
                '_fbc': request.form.get('_fbc')
            }
            
        if not data:
            logger.error("[TRACKING API] Nenhum dado recebido do Beacon API.")
            return jsonify({'success': False, 'error': 'No data received'}), 400
            
    except Exception as e:
        logger.error(f"[TRACKING API] Erro critico no parsing: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    
    try:
        # V4.1: Validar dados
        tracking_token = data.get('tracking_token')
        if not tracking_token:
            return jsonify({'success': False, 'error': 'tracking_token required'}), 400
        
        # V4.1: Recuperar tracking_data existente
        from utils.tracking_service import TrackingServiceV4
        tracking_service_v4 = TrackingServiceV4()
        existing_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
        
        # V4.1: Atualizar com cookies do browser
        fbp = data.get('fbp') or data.get('_fbp') or existing_data.get('fbp')
        fbc = data.get('fbc') or data.get('_fbc') or existing_data.get('fbc')
        fbi = data.get('_fbi')  # client-side verified IP
        updated_data = {
            **existing_data,
            'fbp': fbp,
            'fbc': fbc,
            'fbc_origin': 'cookie' if fbc else existing_data.get('fbc_origin'),
            'fbp_origin': 'cookie' if fbp else existing_data.get('fbp_origin'),
            'pageview_sent': True,
        }
        if fbi:
            updated_data['client_ip'] = fbi
        
        # V4.1: Salvar dados atualizados no Redis
        tracking_service_v4.save_tracking_token(tracking_token, updated_data)
        
        logger.info(f"✅ V4.1 - Cookies capturados: {tracking_token[:8]}... | fbp: {'✅' if updated_data.get('fbp') else '❌'} | fbc: {'✅' if updated_data.get('fbc') else '❌'} | client_ip: {'✅' if fbi else '❌'}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"❌ V4.1 - Erro ao capturar cookies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
