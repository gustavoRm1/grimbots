"""
RQ Job Helpers - Isolamento de User ID em Workers
=================================================

Helpers para garantir que jobs RQ recebam e usem o user_id corretamente,
mantendo o isolamento de namespace no Redis durante processamento em background.

Uso:
    from app.workers.helpers import enqueue_with_user, with_user_context
    
    # Enfileirar job com user_id
    enqueue_with_user(
        user_id=current_user.id,
        func=send_downsell_job,
        payment_id=payment.id
    )
    
    # Decorator para jobs
    @with_user_context
    def send_downsell_job(user_id, payment_id):
        state = NamespacedRedisBotState(user_id=user_id)
        # ... processamento isolado
"""

import logging
import functools
from typing import Callable, Any, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# ENFILEIRAMENTO COM USER ID
# ============================================================================

def enqueue_with_user(queue, user_id: int, func: Callable, *args, **kwargs) -> Any:
    """
    Enfileira job RQ garantindo que user_id esteja no payload.
    
    Esta função WRAPPA o job original para injetar user_id como primeiro argumento,
    garantindo que o worker tenha acesso ao contexto do usuário.
    
    Args:
        queue: Instância da fila RQ (ex: get_queue('high'))
        user_id: ID do usuário (obrigatório para isolamento)
        func: Função a ser executada (deve aceitar user_id como primeiro arg)
        *args: Argumentos adicionais para a função
        **kwargs: Keyword arguments para enqueue (timeout, ttl, retry, etc)
        
    Returns:
        Job RQ enfileirado
        
    Example:
        >>> from rq import Queue
        >>> from redis import Redis
        >>> 
        >>> queue = Queue('high', connection=Redis())
        >>> job = enqueue_with_user(
        ...     queue=queue,
        ...     user_id=current_user.id,
        ...     func=process_payment_job,
        ...     payment_id=123,
        ...     timeout='5m'
        ... )
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"user_id deve ser inteiro positivo, recebido: {user_id}")
    
    # Criar wrapper que injeta user_id
    def _wrapper(user_id_inner: int, *job_args, **job_kwargs):
        # Adicionar user_id aos kwargs para acesso fácil
        job_kwargs['_user_id'] = user_id_inner
        
        # Chamar função original com user_id como primeiro arg
        return func(user_id_inner, *job_args, **job_kwargs)
    
    # Log para auditoria
    logger.info(f"📥 Enfileirando job {func.__name__} para user_id={user_id}")
    
    # Enfileirar o wrapper com user_id como primeiro argumento
    return queue.enqueue(_wrapper, user_id, *args, **kwargs)


def enqueue_with_user_and_bot(queue, user_id: int, bot_id: int, 
                               func: Callable, *args, **kwargs) -> Any:
    """
    Enfileira job RQ com user_id E bot_id no payload.
    
    Útil para operações específicas de um bot (ex: envio de downsell).
    
    Args:
        queue: Instância da fila RQ
        user_id: ID do usuário
        bot_id: ID do bot
        func: Função a ser executada (deve aceitar user_id, bot_id como primeiros args)
        
    Example:
        >>> job = enqueue_with_user_and_bot(
        ...     queue,
        ...     user_id=42,
        ...     bot_id=123,
        ...     func=send_downsell_job,
        ...     payment_id=456
        ... )
    """
    def _wrapper(user_id_inner: int, bot_id_inner: int, *job_args, **job_kwargs):
        job_kwargs['_user_id'] = user_id_inner
        job_kwargs['_bot_id'] = bot_id_inner
        return func(user_id_inner, bot_id_inner, *job_args, **job_kwargs)
    
    logger.info(f"📥 Enfileirando job {func.__name__} para user_id={user_id}, bot_id={bot_id}")
    
    return queue.enqueue(_wrapper, user_id, bot_id, *args, **kwargs)


# ============================================================================
# DECORATORS PARA JOBS
# ============================================================================

def with_user_context(func: Callable) -> Callable:
    """
    Decorator que garante user_id no contexto e inicializa Redis isolado.
    
    Este decorator deve ser usado em funções que serão chamadas como jobs RQ.
    Ele automaticamente:
    1. Extrai user_id dos argumentos
    2. Inicializa NamespacedRedisBotState
    3. Injeta estado isolado no contexto da função
    
    Args:
        func: Função a ser decorada (deve ter user_id como primeiro arg)
        
    Returns:
        Função wrapada
        
    Example:
        >>> @with_user_context
        ... def process_payment(user_id: int, payment_id: int, bot_state=None):
        ...     # bot_state já está inicializado com namespace isolado
        ...     active_bots = bot_state.get_all_active_bots()
        ...     # ...
    """
    @functools.wraps(func)
    def wrapper(user_id: int, *args, **kwargs):
        from app.core.redis_bot_state_v2 import NamespacedRedisBotState
        
        # Criar estado isolado
        bot_state = NamespacedRedisBotState(user_id=user_id)
        
        # Injetar bot_state nos kwargs
        kwargs['bot_state'] = bot_state
        kwargs['_user_id'] = user_id
        
        logger.info(f"🎯 Executando job {func.__name__} no contexto de user_id={user_id}")
        
        try:
            return func(user_id, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Erro no job {func.__name__} para user {user_id}: {e}")
            raise
    
    return wrapper


def with_isolated_redis(func: Callable) -> Callable:
    """
    Decorator que inicializa GrimBotsRedis isolado para a função.
    
    Similar a with_user_context, mas para operações que só precisam do Redis
    (sem precisar do estado completo do bot).
    
    Example:
        >>> @with_isolated_redis
        ... def cache_tracking_data(user_id: int, tracking_token: str, data: dict, redis=None):
        ...     # redis já é instância de GrimBotsRedis(user_id=user_id)
        ...     redis.set(f"tracking:{tracking_token}", json.dumps(data), ex=3600)
    """
    @functools.wraps(func)
    def wrapper(user_id: int, *args, **kwargs):
        from app.core.redis_wrapper import get_namespaced_redis
        
        # Criar cliente Redis isolado
        redis = get_namespaced_redis(user_id)
        
        # Injetar nos kwargs
        kwargs['redis'] = redis
        kwargs['_user_id'] = user_id
        
        return func(user_id, *args, **kwargs)
    
    return wrapper


# ============================================================================
# CONTEXT MANAGERS
# ============================================================================

class UserContext:
    """
    Context manager para operações com namespace isolado.
    
    Example:
        >>> with UserContext(user_id=42) as ctx:
        ...     ctx.redis.set("key", "value")
        ...     ctx.bot_state.register_bot(bot_id=123, ...)
    """
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.redis = None
        self.bot_state = None
    
    def __enter__(self):
        from app.core.redis_wrapper import get_namespaced_redis
        from app.core.redis_bot_state_v2 import NamespacedRedisBotState
        
        self.redis = get_namespaced_redis(self.user_id)
        self.bot_state = NamespacedRedisBotState(self.user_id)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup opcional
        pass


def get_job_context(job) -> Optional[Dict[str, Any]]:
    """
    Extrai contexto (user_id, bot_id) de um job RQ.
    
    Útil para logging e debugging.
    
    Args:
        job: Instância de rq.job.Job
        
    Returns:
        Dict com user_id, bot_id, etc.
    """
    args = job.args if job.args else []
    kwargs = job.kwargs if job.kwargs else {}
    
    context = {
        'job_id': job.id,
        'func_name': job.func_name if hasattr(job, 'func_name') else str(job.func),
    }
    
    # Extrair user_id (geralmente primeiro arg)
    if len(args) >= 1 and isinstance(args[0], int):
        context['user_id'] = args[0]
    elif '_user_id' in kwargs:
        context['user_id'] = kwargs['_user_id']
    
    # Extrair bot_id (geralmente segundo arg)
    if len(args) >= 2 and isinstance(args[1], int):
        context['bot_id'] = args[1]
    elif '_bot_id' in kwargs:
        context['bot_id'] = kwargs['_bot_id']
    
    return context


# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def validate_job_isolation(job) -> bool:
    """
    Valida se um job tem user_id no payload (garantia de isolamento).
    
    Args:
        job: Instância de rq.job.Job
        
    Returns:
        True se tem user_id, False se não
    """
    context = get_job_context(job)
    has_user_id = 'user_id' in context
    
    if not has_user_id:
        logger.warning(f"⚠️ Job {job.id} SEM user_id no payload! Risco de interferência!")
    
    return has_user_id


def log_job_context(job):
    """
    Loga contexto do job para auditoria.
    """
    context = get_job_context(job)
    user_id = context.get('user_id', 'N/A')
    bot_id = context.get('bot_id', 'N/A')
    
    logger.info(f"📋 Job {job.id}: user_id={user_id}, bot_id={bot_id}, func={context['func_name']}")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'enqueue_with_user',
    'enqueue_with_user_and_bot', 
    'with_user_context',
    'with_isolated_redis',
    'UserContext',
    'get_job_context',
    'validate_job_isolation',
    'log_job_context',
]
