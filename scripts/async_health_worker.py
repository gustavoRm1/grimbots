#!/usr/bin/env python3
"""
Async Health Worker - GrimBots
==============================
Worker assíncrono dedicado ao health check de pools de redirecionamento.

Características:
- Setup de contexto Flask único (zero overhead de boot)
- I/O não-bloqueante com asyncio + httpx
- Eager Load para eliminar N+1 queries
- Verificação massiva paralela com asyncio.gather()
- Recuperação automática de falhas (nunca morre)

Uso:
    python scripts/async_health_worker.py

Arquitetura:
    ┌─────────────────────────────────────────┐
    │  Async Health Worker (Processo Único)  │
    │                                         │
    │  ┌──────────────┐    ┌──────────────┐  │
    │  │ Flask App    │────│ SQLAlchemy   │  │
    │  │ (1x setup)   │    │ Session      │  │
    │  └──────────────┘    └──────────────┘  │
    │         │                               │
    │  ┌──────▼──────┐    ┌──────────────┐  │
    │  │ Asyncio     │────│ HTTPX Client │  │
    │  │ Event Loop  │    │ (Pool 50)    │  │
    │  └─────────────┘    └──────────────┘  │
    │         │                               │
    │  ┌──────▼────────┐                      │
    │  │ Telegram API  │                      │
    │  │ (Paralelo)    │                      │
    │  └───────────────┘                      │
    └─────────────────────────────────────────┘
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Tuple

# Setup logging antes de qualquer import
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Adicionar raiz do projeto ao path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# =============================================================================
# DEPENDÊNCIAS ASSÍNCRONAS
# =============================================================================
try:
    import httpx
except ImportError:
    logger.error("❌ httpx não instalado. Execute: pip install httpx")
    sys.exit(1)

# =============================================================================
# CONSTANTES DE SAÚDE (Fix E + Fix G)
# =============================================================================
# Quantidade de ciclos (≈15s cada) consecutivos de falha de getMe necessária
# para um bot AVULSO (sem PoolBot) ser considerado offline de verdade.
# Exige consistência — evita derrubar bot por um único 502/429/rate-limit
# transitório da API do Telegram, que era a causa do falso-offline em massa.
LOOSE_OFFLINE_THRESHOLD = 3

# Máximo de chamadas HTTP concorrentes à API do Telegram por ciclo.
# Antes o worker disparava ~70 bots × 2 chamadas no mesmo instante,
# saturando a API e causando 502/429 (falso-offline). Fix G limita isso.
MAX_CONCURRENT = 15

# =============================================================================
# SETUP DO CONTEXTO FLASK (EXECUTADO UMA ÚNICA VEZ)
# =============================================================================
logger.info("🚀 Inicializando Async Health Worker...")
logger.info("   Carregando contexto Flask (setup único)...")

from internal_logic.core.extensions import create_app, db, socketio
from internal_logic.core.models import RedirectPool, PoolBot, Bot, get_brazil_time

# Criar aplicação Flask UMA VEZ
app = create_app()

logger.info("✅ Contexto Flask inicializado com sucesso")


# =============================================================================
# FUNÇÕES ASSÍNCRONAS DE VERIFICAÇÃO
# =============================================================================

def _expected_webhook_url(bot_id: int) -> str:
    """
    Retorna a URL de webhook esperada para um bot.

    Args:
        bot_id: ID do bot

    Returns:
        str: URL de webhook esperada, ou '' se WEBHOOK_URL não configurado.
    """
    base = os.environ.get('WEBHOOK_URL', '')
    if not base:
        return ''
    return f"{base}/webhook/telegram/{bot_id}"


async def check_webhook_status(client: httpx.AsyncClient, bot: 'Bot') -> Tuple[str, str]:
    """
    Verifica se o webhook do Telegram aponta corretamente para a plataforma.

    Args:
        client: Cliente HTTPX assíncrono (compartilhado)
        bot: Instância de Bot

    Returns:
        Tuple[str, str]: (config_url, 'ok'|'missing'|'mismatch'|'error')
    """
    expected = _expected_webhook_url(bot.id)
    if not expected:
        return ('', 'error')

    url = f"https://api.telegram.org/bot{bot.token}/getWebhookInfo"
    try:
        response = await client.get(url, timeout=5.0)
        if response.status_code == 200:
            data = response.json().get('result') or {}
            configured = data.get('url', '')
            if configured == expected:
                return (configured, 'ok')
            if not configured:
                return (configured, 'missing')
            return (configured, 'mismatch')
        return ('', 'error')
    except (httpx.TimeoutException, httpx.ConnectError, Exception):
        # Inconclusivo — tratado como erro para não dar falso-positivo de online
        return ('', 'error')


async def check_bot_status(client: httpx.AsyncClient, pool_bot: PoolBot) -> Tuple[PoolBot, str]:
    """
    Verifica o status de um bot via API do Telegram (assíncrono).
    
    Retorna 'online', 'degraded' (getMe ok, webhook fora do ar) ou 'offline'.
    
    Args:
        client: Cliente HTTPX assíncrono (compartilhado)
        pool_bot: Instância de PoolBot para verificar
        
    Returns:
        Tuple[PoolBot, str]: (pool_bot, status) onde status é 'online', 'degraded' ou 'offline'
    """
    # Extrair token do bot
    bot = pool_bot.bot
    if not bot or not bot.token:
        return (pool_bot, 'offline')
    
    token = bot.token
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    try:
        # Timeout de 5 segundos para evitar bloqueios
        response = await client.get(url, timeout=5.0)
        
        # Se 200 e ok=True, bot existe e responde (vivo)
        me_ok = False
        if response.status_code == 200:
            data = response.json()
            if data.get('ok') is True:
                me_ok = True

        if not me_ok:
            return (pool_bot, 'offline')

        # Bot vivo — verificar se o webhook está configurado corretamente
        _, webhook_state = await check_webhook_status(client, bot)
        if webhook_state == 'ok':
            return (pool_bot, 'online')
        if webhook_state in ('missing', 'mismatch'):
            return (pool_bot, 'degraded')
        # getWebhookInfo inconclusivo → considera online (getMe respondeu)
        return (pool_bot, 'online')
        
    except httpx.TimeoutException:
        # Timeout é considerado offline
        return (pool_bot, 'offline')
    except httpx.ConnectError:
        # Erro de conexão é considerado offline
        return (pool_bot, 'offline')
    except Exception:
        # Qualquer outra exceção é offline
        return (pool_bot, 'offline')


async def _limited_check_bot_status(sem: asyncio.Semaphore,
                                    client: httpx.AsyncClient,
                                    pool_bot: PoolBot) -> Tuple[PoolBot, str]:
    """Envolve check_bot_status com o semáforo Fix G (limite de concorrência)."""
    async with sem:
        return await check_bot_status(client, pool_bot)


async def run_health_cycle(client: httpx.AsyncClient) -> Tuple[int, float]:
    """
    Executa um ciclo completo de health check (assíncrono).
    
    Args:
        client: Cliente HTTPX assíncrono
        
    Returns:
        Tuple[int, float]: (pools_atualizados, tempo_execucao)
    """
    start_time = datetime.now()

    # Fix G: Semáforo para limitar chamadas HTTP concorrentes à API do Telegram.
    # Previne 502/429/rate-limit do falso-offline em massa.
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    # ==========================================================================
    # 1. EAGER LOAD - Busca pools ativos (pool_bots é lazy='dynamic', não joinedload)
    # ==========================================================================
    pools = RedirectPool.query.filter_by(is_active=True).all()

    # ==========================================================================
    # 1.5 BOTS AVULSOS - Bots (não manually_disabled) que NÃO estão em pool ativo.
    #     Fix D: antes esses bots eram 100% invisíveis ao health worker, então o
    #     dashboard os mostrava online mesmo quando o bot morria.
    #     Fix E (ref): verifica TODOS os bots não-manually_disabled e sem pool,
    #     independente de is_running, pois o health worker é quem recalcula o
    #     estado de saúde. Assim recupera automaticamente bots derrubados por
    #     falso-negativo (getMe ok → online) e derruba os realmente mortos.
    # ==========================================================================
    # Mapear bot_ids presentes nos pools
    pooled_bot_ids = set()
    for pool in pools:
        for pb in list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []:
            pooled_bot_ids.add(pb.bot_id)

    # Buscar bots sem pool e NÃO desligados manualmente pelo usuário.
    # != True cobre NULL (bots antigos sem o flag definido).
    loose_bots = Bot.query.filter(
        Bot.manually_disabled != True,  # noqa: E712
        ~Bot.id.in_(pooled_bot_ids) if pooled_bot_ids else True
    ).all()

    # ==========================================================================
    # 2. COLETAR TODOS OS POOL_BOTS PARA VERIFICAÇÃO MASSIVA
    # ==========================================================================
    all_pool_bots: List[PoolBot] = []
    for pool in pools:
        # Converter lazy load para lista (já está eager loaded)
        pool_bots = list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []
        all_pool_bots.extend(pool_bots)

    # Se não há pools nem bots avulsos, nada a fazer
    if not pools and not loose_bots:
        return (0, 0.0)
    
    # ==========================================================================
    # 3. VERIFICAÇÃO MASSIVA PARALELA COM asyncio.gather()
    # ==========================================================================
    # Mapa de resultados de bots avulsos: bot_id -> status
    loose_bot_statuses = {}

    if all_pool_bots:
        # Criar tasks para verificação paralela de TODOS os bots (limitado pelo semáforo Fix G)
        tasks = [
            _limited_check_bot_status(sem, client, pool_bot)
            for pool_bot in all_pool_bots
        ]
        
        # Executar TODAS as verificações simultaneamente
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processar resultados
        for result in results:
            if isinstance(result, Exception):
                # Ignorar exceções individuais (já tratadas em check_bot_status)
                continue
            
            pool_bot, status = result
            
            # Atualizar status do pool_bot
            if status in ('online', 'degraded'):
                if pool_bot.status != 'online':
                    pool_bot.status = 'online'
                    pool_bot.consecutive_failures = 0
                pool_bot.last_health_check = get_brazil_time()
            else:
                if pool_bot.status != 'offline':
                    pool_bot.status = 'offline'
                    pool_bot.consecutive_failures += 1
                pool_bot.last_health_check = get_brazil_time()

    # ==========================================================================
    # 3.5 VERIFICAÇÃO DOS BOTS AVULSOS (sem PoolBot)
    # ==========================================================================
    if loose_bots:
        async def _check_loose(bot):
            # getMe — bot responde? (Fix G: limitado pelo semáforo)
            me_ok = False
            async with sem:
                try:
                    resp = await client.get(
                        f"https://api.telegram.org/bot{bot.token}/getMe", timeout=5.0
                    )
                    if resp.status_code == 200 and resp.json().get('ok') is True:
                        me_ok = True
                except Exception:
                    me_ok = False

            if not me_ok:
                return (bot.id, 'offline')

            # Webhook aponta para a plataforma? (semáforo para getWebhookInfo)
            async with sem:
                _, webhook_state = await check_webhook_status(client, bot)
            if webhook_state in ('missing', 'mismatch'):
                return (bot.id, 'degraded')
            return (bot.id, 'online')

        loose_results = await asyncio.gather(
            *[_check_loose(b) for b in loose_bots],
            return_exceptions=True
        )
        for r in loose_results:
            if isinstance(r, Exception):
                continue
            bot_id, st = r
            loose_bot_statuses[bot_id] = st
    
    # ==========================================================================
    # 4. RECALCULAR MÉTRICAS DOS POOLS
    # ==========================================================================
    for pool in pools:
        pool_bots = list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []
        
        total = len(pool_bots)
        online = sum(1 for pb in pool_bots if pb.status == 'online' and pb.is_enabled)
        
        pool.total_bots_count = total
        pool.healthy_bots_count = online
        pool.health_percentage = int((online / total * 100)) if total > 0 else 0
        pool.last_health_check = get_brazil_time()
    
    # ==========================================================================
    # 5. COMMIT ÚNICO
    # ==========================================================================
    db.session.commit()

    # ==========================================================================
    # 6. SINCRONIZAR Bot.is_running COM PoolBot.status (Fix 1 + Fix 4)
    # ==========================================================================
    # Agrupa bots por bot_id e conta online/offline
    bot_ids_status = {}
    for pool_bot in all_pool_bots:
        bot_id = pool_bot.bot_id
        if bot_id not in bot_ids_status:
            bot_ids_status[bot_id] = {'online': 0, 'offline': 0, 'pool_bots': []}
        if pool_bot.status == 'online':
            bot_ids_status[bot_id]['online'] += 1
        else:
            bot_ids_status[bot_id]['offline'] += 1
        bot_ids_status[bot_id]['pool_bots'].append(pool_bot)

    bots_changed = 0
    for bot_id, counts in bot_ids_status.items():
        bot = Bot.query.get(bot_id)
        if not bot:
            continue

        # FIX CRÍTICO: Health worker NUNCA mexe em bot desligado pelo usuário
        if getattr(bot, 'manually_disabled', False):
            continue

        old_is_running = bot.is_running

        if counts['online'] == 0 and counts['offline'] > 0:
            # Todos os PoolBots offline → bot está morto
            if bot.is_running:
                bot.is_running = False
                bot.health_status = 'offline'
                bots_changed += 1
                logger.warning(
                    f"🔴 Bot {bot_id} ({getattr(bot, 'name', '?')}) "
                    f"marcado como OFFLINE — todos os pools mortos"
                )
        else:
            # Pelo menos 1 online → bot está vivo
            if not bot.is_running:
                bot.is_running = True
                bot.health_status = 'online'
                bots_changed += 1
                logger.info(
                    f"🟢 Bot {bot_id} ({getattr(bot, 'name', '?')}) "
                    f"marcado como ONLINE — pools恢复"
                )

        # FIX 4: Aplicar circuit breaker automático se muitas falhas
        for pool_bot in counts['pool_bots']:
            if (pool_bot.status == 'offline'
                    and getattr(pool_bot, 'consecutive_failures', 0) >= 5
                    and not pool_bot.circuit_breaker_until):
                pool_bot.circuit_breaker_until = get_brazil_time() + timedelta(minutes=30)
                logger.warning(
                    f"⚡ Circuit breaker ativado para PoolBot {pool_bot.id} "
                    f"(bot {bot_id}) — {pool_bot.consecutive_failures} falhas, "
                    f"bloqueado por 30min"
                )

        # FIX 3: Notificar usuário via WebSocket se bot caiu
        if old_is_running and not bot.is_running:
            try:
                socketio.emit('bot_status_update', {
                    'bot_id': bot.id,
                    'bot_name': getattr(bot, 'name', 'Bot'),
                    'is_running': False,
                    'message': f'Bot {getattr(bot, "name", "Bot")} ficou offline!'
                }, room=f'user_{bot.user_id}')
                logger.info(
                    f"🔔 WebSocket emitido: bot {bot.id} offline "
                    f"(user {bot.user_id})"
                )
            except Exception as e:
                logger.debug(f"Erro ao emitir WebSocket: {e}")

    # ==========================================================================
    # 6.5 SINC BOTS AVULSOS (sem PoolBot) - Fix D
    #     Dashboard reflete is_running real para bots que não estão em pools,
    #     incluindo detecção de webhook degradado.
    # ==========================================================================
    loose_changed = False
    for bot_id, st in loose_bot_statuses.items():
        bot = Bot.query.get(bot_id)
        if not bot:
            continue

        # FIX CRÍTICO: NUNCA mexe em bot desligado pelo usuário
        if getattr(bot, 'manually_disabled', False):
            continue

        old_is_running = bot.is_running

        # Fix E: gestão de falhas consecutivas nos bots avulsos.
        # Resetar contador quando o bot responde; só marcar offline quando
        # falhar >= LOOSE_OFFLINE_THRESHOLD ciclos consecutivos. Evita derrubar
        # bot por uma única falha transitória (502/429/rate-limit).
        if st == 'online':
            if bot.consecutive_failures != 0:
                bot.consecutive_failures = 0
            if not bot.is_running:
                bot.is_running = True
                bot.health_status = 'online'
                bots_changed += 1
                loose_changed = True
                logger.info(
                    f"🟢 Bot {bot_id} ({getattr(bot, 'name', '?')}) "
                    f"marcado como ONLINE — getMe ok"
                )
        elif st == 'degraded':
            # Bot responde mas webhook está fora/aponta errado → parcial
            bot.consecutive_failures = 0
            bot.health_status = 'degraded'
            bot.last_health_check = get_brazil_time()
            loose_changed = True
            logger.warning(
                f"🟡 Bot {bot_id} ({getattr(bot, 'name', '?')}) "
                f"DEGRADED — webhook do Telegram não aponta para a plataforma"
            )
        else:  # offline (getMe falhou neste ciclo)
            bot.consecutive_failures = getattr(bot, 'consecutive_failures', 0) + 1
            bot.last_health_check = get_brazil_time()
            if bot.consecutive_failures >= LOOSE_OFFLINE_THRESHOLD and bot.is_running:
                bot.is_running = False
                bot.health_status = 'offline'
                bots_changed += 1
                loose_changed = True
                logger.warning(
                    f"🔴 Bot {bot_id} ({getattr(bot, 'name', '?')}) "
                    f"marcado como OFFLINE — {bot.consecutive_failures} "
                    f"falhas consecutivas de getMe"
                )
                # Notificar usuário via WebSocket
                try:
                    socketio.emit('bot_status_update', {
                        'bot_id': bot.id,
                        'bot_name': getattr(bot, 'name', 'Bot'),
                        'is_running': False,
                        'message': f'Bot {getattr(bot, "name", "Bot")} ficou offline!'
                    }, room=f'user_{bot.user_id}')
                except Exception as e:
                    logger.debug(f"Erro ao emitir WebSocket: {e}")
            elif bot.consecutive_failures < LOOSE_OFFLINE_THRESHOLD:
                logger.debug(
                    f"⚠️ Bot {bot_id} ({getattr(bot, 'name', '?')}) "
                    f"falha {bot.consecutive_failures}/{LOOSE_OFFLINE_THRESHOLD} "
                    f"— aguardando consistência antes de marcar offline"
                )

    if bots_changed or loose_changed:
        db.session.commit()
        logger.info(
            f"🔄 Sync Bot.is_running: {bots_changed} bots atualizados"
        )

    elapsed = (datetime.now() - start_time).total_seconds()
    return (len(pools), elapsed)


# =============================================================================
# LOOP PRINCIPAL (while True)
# =============================================================================

async def main_loop():
    """
    Loop principal do worker assíncrono.
    Executa eternamente com recuperação automática de falhas.
    """
    logger.info("🔄 Iniciando loop principal do Async Health Worker")
    
    # Criar cliente HTTPX com pool de conexões (compartilhado entre ciclos)
    # Limitar conexões para não sobrecarregar a API do Telegram
    limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        cycle_count = 0
        
        while True:
            cycle_count += 1
            
            try:
                # Rodar dentro do contexto Flask para acesso ao banco
                with app.app_context():
                    pools_updated, elapsed = await run_health_cycle(client)
                    
                    logger.info(
                        f"✅ Ciclo #{cycle_count} concluído. "
                        f"{pools_updated} pools atualizados em {elapsed:.2f}s"
                    )
                    
            except Exception as e:
                # Worker NUNCA pode morrer - rollback e continua
                logger.error(f"❌ Erro no ciclo #{cycle_count}: {e}")
                
                try:
                    with app.app_context():
                        db.session.rollback()
                        logger.info("   Rollback executado com sucesso")
                except Exception as rollback_error:
                    logger.error(f"   Falha no rollback: {rollback_error}")
                
                # Log da exceção completa para debugging
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
            
            finally:
                # Limpar sessão do SQLAlchemy
                try:
                    with app.app_context():
                        db.session.remove()
                        logger.debug("   Sessão do SQLAlchemy limpa")
                except Exception as cleanup_error:
                    logger.warning(f"   Erro ao limpar sessão: {cleanup_error}")
                
                # Sempre aguardar 15 segundos antes do próximo ciclo
                await asyncio.sleep(15)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("⚠️ Worker interrompido pelo usuário (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"💥 Erro fatal no worker: {e}")
        sys.exit(1)
