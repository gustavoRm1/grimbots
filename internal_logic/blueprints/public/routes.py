"""
Public Blueprint - GrimBots
Rotas públicas para redirecionamento de tráfego (/go/<slug>) com Cloaker e Load Balancing
"""
import logging
import time
from datetime import datetime
from flask import Blueprint, request, redirect, jsonify, render_template, make_response
from internal_logic.core.models import RedirectPool, PoolBot, db
from internal_logic.core.extensions import limiter
from internal_logic.core.metrics import MetricsService
from internal_logic.services.cloaker_service import CloakerService
from internal_logic.services.tracking_service import TrackingService
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
            return render_template('cloaker_block.html'), 200
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
            
            # Disparar PageView (async)
            TrackingService.fire_pageview(pool, request, async_mode=True)
            
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
            
            if hasattr(pool, 'fallback_url') and pool.fallback_url:
                return redirect(pool.fallback_url, code=302)
            
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
        MetricsService.increment_redirect_counters(pool.id, selected_bot.bot_id)
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
    
    response = make_response(render_template('telegram_redirect.html',
        bot_username=bot_username_safe,
        tracking_token=tracking_token,
        pixel_id=pixel_id_to_use,
        fbclid=fbclid if fbclid else '',
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


def health_check_all_pools():
    """
    Health Check de todos os bots em todos os pools ativos
    
    Esta função é chamada periodicamente (a cada 15 segundos) para:
    1. Verificar a saúde de cada bot nos pools
    2. Atualizar métricas agregadas do pool
    3. Atualizar circuit breakers se necessário
    
    Deve ser executada via APScheduler ou Celery no background.
    """
    from internal_logic.core.models import get_brazil_time
    
    try:
        # Buscar todos os pools ativos
        pools = RedirectPool.query.filter_by(is_active=True).all()
        
        checked_count = 0
        updated_count = 0
        
        for pool in pools:
            try:
                # Verificar cada bot do pool
                pool_bots = pool.pool_bots.all() if hasattr(pool.pool_bots, 'all') else list(pool.pool_bots)
                
                for pool_bot in pool_bots:
                    try:
                        # Verificar se o bot está online (simplificado - em produção verificaria API Telegram)
                        # Aqui usamos a lógica de verificação de saúde básica
                        if pool_bot.bot and pool_bot.bot.token:
                            # Bot tem token = considerado online para este health check básico
                            if pool_bot.status != 'online':
                                pool_bot.status = 'online'
                                pool_bot.last_health_check = get_brazil_time()
                                updated_count += 1
                        else:
                            # Bot sem token = offline
                            if pool_bot.status != 'offline':
                                pool_bot.status = 'offline'
                                pool_bot.consecutive_failures += 1
                                pool_bot.last_health_check = get_brazil_time()
                                updated_count += 1
                        
                        checked_count += 1
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao verificar bot {pool_bot.bot_id}: {e}")
                        continue
                
                # Atualizar métricas do pool
                pool.update_health()
                
            except Exception as e:
                logger.error(f"❌ Erro no health check do pool {pool.id}: {e}")
                continue
        
        # Commit das alterações
        try:
            db.session.commit()
            logger.info(f"✅ Health check concluído: {checked_count} bots verificados, {updated_count} atualizados")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar health check: {e}")
            db.session.rollback()
            
    except Exception as e:
        logger.error(f"❌ Erro crítico no health_check_all_pools: {e}", exc_info=True)


@public_bp.route('/api/tracking/cookies', methods=['POST'])
def capture_tracking_cookies():
    """
    V4.1: ENDPOINT PARA CAPTURAR COOKIES _FBP E _FBC DO BROWSER
    
    Chamado via Beacon API pelo telegram_redirect.html após Meta Pixel carregar.
    Atualiza tracking_data no Redis com cookies gerados pelo Meta Pixel.
    """
    try:
        # V4.1: Parsear JSON (Beacon API não envia Content-Type)
        data = None
        
        try:
            data = request.get_json(force=True, silent=True)
        except Exception:
            pass
        
        if not data:
            try:
                raw_data = request.get_data(as_text=True)
                if raw_data:
                    import json as json_lib
                    data = json_lib.loads(raw_data)
            except (json_lib.JSONDecodeError, ValueError) as e:
                logger.warning(f"❌ Erro ao parsear JSON: {e}")
                return jsonify({'success': False}), 400
        
        # V4.1: Validar dados
        tracking_token = data.get('tracking_token')
        if not tracking_token:
            return jsonify({'success': False, 'error': 'tracking_token required'}), 400
        
        # V4.1: Recuperar tracking_data existente
        from internal_logic.services.tracking_service_v4 import TrackingServiceV4
        tracking_service_v4 = TrackingServiceV4()
        existing_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
        
        # V4.1: Atualizar com cookies do browser
        updated_data = {
            **existing_data,
            'fbp': data.get('fbp') or existing_data.get('fbp'),
            'fbc': data.get('fbc') or existing_data.get('fbc'),
            'fbc_origin': 'cookie' if data.get('fbc') else existing_data.get('fbc_origin'),
            'fbp_origin': 'cookie' if data.get('fbp') else existing_data.get('fbp_origin'),
            'pageview_sent': True,  # Marcar que PageView foi enviado
        }
        
        # V4.1: Salvar dados atualizados no Redis
        tracking_service_v4.save_tracking_token(tracking_token, updated_data, ttl=3600)
        
        logger.info(f"✅ V4.1 - Cookies capturados: {tracking_token[:8]}... | fbp: {'✅' if data.get('fbp') else '❌'} | fbc: {'✅' if data.get('fbc') else '❌'}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"❌ V4.1 - Erro ao capturar cookies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
