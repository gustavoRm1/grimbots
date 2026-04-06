"""
Public Blueprint - GrimBots
Rotas públicas para redirecionamento de tráfego (/go/<slug>) com Cloaker e Load Balancing
"""
import logging
import time
from datetime import datetime
from flask import Blueprint, request, redirect, jsonify, render_template
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
    # 3. RASTREIO (Meta CAPI) - NÃO BLOQUEANTE
    # ═══════════════════════════════════════════════════════════
    try:
        if getattr(pool, 'meta_tracking_enabled', False):
            TrackingService.fire_pageview(pool, request, async_mode=True)
    except Exception as e:
        # Tracking nunca bloqueia o redirect
        logger.debug(f"📊 Tracking não disparado: {e}")
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
    # 6. REDIRECT
    # ═══════════════════════════════════════════════════════════
    pipeline_duration = (time.time() - pipeline_start) * 1000
    logger.info(f"🔄 Redirect: pool={pool.slug} → bot={selected_bot.bot_id} ({pipeline_duration:.1f}ms)")
    
    return redirect(bot_url, code=302)


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
