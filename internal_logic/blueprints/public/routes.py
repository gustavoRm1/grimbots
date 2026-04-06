"""
Public Blueprint - GrimBots
Rotas públicas para redirecionamento de tráfego (/go/<slug>) com Cloaker e Load Balancing
"""
import logging
import json
import random
import time
from datetime import datetime
from flask import Blueprint, request, redirect, jsonify, current_app
from internal_logic.core.models import RedirectPool, PoolBot, Bot, db
from internal_logic.core.extensions import limiter

logger = logging.getLogger(__name__)

public_bp = Blueprint('public', __name__, url_prefix='')


def log_cloaker_event_json(event_type, details):
    """Log estruturado para eventos do cloaker (auditoria e compliance)"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        **details
    }
    logger.info(f"CLOAKER_EVENT: {json.dumps(log_entry, ensure_ascii=False)}")


def validate_cloaker_access(request, pool, slug):
    """
    🔐 CLOAKER V2.0 - Validação de acesso ao redirecionamento
    
    Lógica de proteção:
    1. Se cloaker desativado → sempre permitir
    2. Se cloaker ativo → verificar parâmetro 'grim' contra valor configurado
    3. Se UTMs do Facebook presentes (fbclid) → aplicar regras adicionais
    
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
    
    # Se não houver valor configurado para grim, permitir (configuração incompleta)
    if not expected_grim:
        return True, 'grim_not_configured', {
            'check': 'configured',
            'grim_received': grim_param,
            'fbclid_present': bool(fbclid)
        }
    
    # Validar grim
    if grim_param != expected_grim:
        log_cloaker_event_json('access_denied', {
            'slug': slug,
            'pool_id': pool.id,
            'reason': 'invalid_grim',
            'grim_received': grim_param,
            'grim_expected_prefix': expected_grim[:10] if expected_grim else None,
            'fbclid_present': bool(fbclid),
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')[:100]
        })
        return False, 'invalid_grim', {
            'check': 'grim_mismatch',
            'grim_received': grim_param,
            'fbclid_present': bool(fbclid)
        }
    
    # Grim válido → permitir acesso
    log_cloaker_event_json('access_granted', {
        'slug': slug,
        'pool_id': pool.id,
        'reason': 'valid_grim',
        'fbclid_present': bool(fbclid),
        'utm_source': utm_source,
        'ip': request.remote_addr
    })
    
    return True, 'valid_grim', {
        'check': 'passed',
        'grim_matched': True,
        'fbclid_present': bool(fbclid),
        'utm_source': utm_source
    }


@public_bp.route('/go/<slug>')
@limiter.limit("10000 per hour")  # Endpoint público precisa de limite alto
def public_redirect(slug):
    """
    Endpoint PÚBLICO de redirecionamento com Load Balancing + Meta Pixel Tracking + Cloaker
    
    Fluxo:
    1. Busca pool pelo slug
    2. Valida cloaker (se ativo)
    3. Seleciona bot baseado na estratégia do pool
    4. Redireciona para o link do bot
    """
    from internal_logic.core.models import get_brazil_time
    
    # Buscar pool pelo slug
    pool = RedirectPool.query.filter_by(slug=slug, is_active=True).first()
    
    if not pool:
        logger.warning(f"🚫 Pool não encontrado ou inativo: slug={slug}")
        return jsonify({'error': 'Pool not found'}), 404
    
    # 🔐 CLOAKER CHECK
    allowed, reason, log_data = validate_cloaker_access(request, pool, slug)
    
    if not allowed:
        # Retornar 404 disfarçado (não revelar que é proteção)
        return jsonify({'error': 'Not found'}), 404
    
    # Selecionar bot do pool
    selected_bot = pool.select_bot()
    
    if not selected_bot:
        logger.error(f"❌ Nenhum bot disponível no pool {pool.id} ({pool.name})")
        return jsonify({'error': 'No bots available'}), 503
    
    # Obter URL do bot (deep link para Telegram)
    bot_url = f"https://t.me/{selected_bot.bot.username}" if selected_bot.bot and selected_bot.bot.username else None
    
    if not bot_url:
        # Fallback: tentar obter do token
        if selected_bot.bot and selected_bot.bot.token:
            # Extrair username do token (formato: numbers:username-hash)
            token_parts = selected_bot.bot.token.split(':')
            if len(token_parts) > 1:
                username = token_parts[1].split('-')[0]
                bot_url = f"https://t.me/{username}"
        
        if not bot_url:
            logger.error(f"❌ Bot {selected_bot.bot_id} sem username configurado")
            return jsonify({'error': 'Bot not configured'}), 503
    
    # Incrementar contadores
    pool.total_redirects += 1
    selected_bot.total_redirects += 1
    
    try:
        db.session.commit()
    except Exception as e:
        logger.warning(f"⚠️ Erro ao atualizar contadores: {e}")
        db.session.rollback()
    
    # Log de redirecionamento
    logger.info(f"🔄 Redirect: pool={pool.slug} → bot={selected_bot.bot_id} (strategy={pool.distribution_strategy})")
    
    # Redirecionar
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
