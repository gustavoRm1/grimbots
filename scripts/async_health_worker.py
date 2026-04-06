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
from datetime import datetime
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
# SETUP DO CONTEXTO FLASK (EXECUTADO UMA ÚNICA VEZ)
# =============================================================================
logger.info("🚀 Inicializando Async Health Worker...")
logger.info("   Carregando contexto Flask (setup único)...")

from internal_logic.core.extensions import create_app, db
from internal_logic.core.models import RedirectPool, PoolBot, get_brazil_time
from sqlalchemy.orm import joinedload

# Criar aplicação Flask UMA VEZ
app = create_app()

logger.info("✅ Contexto Flask inicializado com sucesso")


# =============================================================================
# FUNÇÕES ASSÍNCRONAS DE VERIFICAÇÃO
# =============================================================================

async def check_bot_status(client: httpx.AsyncClient, pool_bot: PoolBot) -> Tuple[PoolBot, str]:
    """
    Verifica o status de um bot via API do Telegram (assíncrono).
    
    Args:
        client: Cliente HTTPX assíncrono (compartilhado)
        pool_bot: Instância de PoolBot para verificar
        
    Returns:
        Tuple[PoolBot, str]: (pool_bot, status) onde status é 'online' ou 'offline'
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
        
        # Se 200 e ok=True, bot está online
        if response.status_code == 200:
            data = response.json()
            if data.get('ok') is True:
                return (pool_bot, 'online')
        
        # Qualquer outro caso é offline
        return (pool_bot, 'offline')
        
    except httpx.TimeoutException:
        # Timeout é considerado offline
        return (pool_bot, 'offline')
    except httpx.ConnectError:
        # Erro de conexão é considerado offline
        return (pool_bot, 'offline')
    except Exception:
        # Qualquer outra exceção é offline
        return (pool_bot, 'offline')


async def run_health_cycle(client: httpx.AsyncClient) -> Tuple[int, float]:
    """
    Executa um ciclo completo de health check (assíncrono).
    
    Args:
        client: Cliente HTTPX assíncrono
        
    Returns:
        Tuple[int, float]: (pools_atualizados, tempo_execucao)
    """
    start_time = datetime.now()
    
    # ==========================================================================
    # 1. EAGER LOAD - Busca tudo em UMA query (elimina N+1)
    # ==========================================================================
    pools = RedirectPool.query.options(
        joinedload(RedirectPool.pool_bots).joinedload(PoolBot.bot)
    ).filter_by(is_active=True).all()
    
    if not pools:
        return (0, 0.0)
    
    # ==========================================================================
    # 2. COLETAR TODOS OS POOL_BOTS PARA VERIFICAÇÃO MASSIVA
    # ==========================================================================
    all_pool_bots: List[PoolBot] = []
    for pool in pools:
        # Converter lazy load para lista (já está eager loaded)
        pool_bots = list(pool.pool_bots) if hasattr(pool.pool_bots, '__iter__') else []
        all_pool_bots.extend(pool_bots)
    
    # ==========================================================================
    # 3. VERIFICAÇÃO MASSIVA PARALELA COM asyncio.gather()
    # ==========================================================================
    if all_pool_bots:
        # Criar tasks para verificação paralela de TODOS os bots
        tasks = [
            check_bot_status(client, pool_bot)
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
            if status == 'online':
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
                    db.session.rollback()
                    logger.info("   Rollback executado com sucesso")
                except Exception as rollback_error:
                    logger.error(f"   Falha no rollback: {rollback_error}")
                
                # Log da exceção completa para debugging
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
            
            finally:
                # 🔥 CRÍTICO: Limpar sessão do SQLAlchemy para evitar memory leak (Identity Map)
                # Remove todos os objetos da sessão, permitindo Garbage Collector limpar a RAM
                try:
                    db.session.remove()
                    logger.debug("   Sessão do SQLAlchemy limpa (db.session.remove())")
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
