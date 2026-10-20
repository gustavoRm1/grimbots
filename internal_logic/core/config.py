"""
Configuração Centralizada - Application Factory Pattern
Todas as configurações do Flask centralizadas aqui
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente com caminho absoluto
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)


class Config:
    """Configuração base"""
    
    # Diretório base do projeto
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    
    # Caminho absoluto para o banco de dados
    DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
    
    # Criar pasta instance se não existir
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Configurações Flask
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f'sqlite:///{DB_PATH}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Ajuste para suportar PostgreSQL (sem check_same_thread)
    @staticmethod
    def get_connect_args():
        if Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
            return {'check_same_thread': False, 'timeout': 30}
        return {}
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_size': 25,
        'max_overflow': 15,
        'pool_timeout': 30,
    }
    
    # Configurações de Cookies/Sessão
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() in {'1', 'true', 'yes'}
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'None')
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
    REMEMBER_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    
    # CORS
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',')
        if origin.strip()
    ]
    
    # SocketIO
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE') or os.environ.get('REDIS_URL')

    # ✅ Grimbots AI Gateway (bloco 'ai' do Flow Editor) — camada ADITIVA/opt-in.
    # Não afeta o motor tradicional: só é usado quando um step tipo 'ai' roda.
    GRIMBOTS_AI_API_URL = os.environ.get('GRIMBOTS_AI_API_URL', '').rstrip('/')
    GRIMBOTS_AI_API_KEY = os.environ.get('GRIMBOTS_AI_API_KEY', '')
    GRIMBOTS_AI_TIMEOUT = float(os.environ.get('GRIMBOTS_AI_TIMEOUT', '90') or '90')
    GRIMBOTS_AI_MOCK = os.environ.get('GRIMBOTS_AI_MOCK', 'false').lower() in {'1', 'true', 'yes'}
    # Fase 6A — feature flag de contrato. 'v1.0' (default) = comportamento atual byte-a-byte.
    # 'v1.1' apenas HABILITA o suporte técnico; o envio real ainda exige o flag por bloco
    # (step_config['contract_v11']). NAO ativar antes do AI Gateway aceitar os campos novos.
    GRIMBOTS_AI_CONTRACT = (os.environ.get('GRIMBOTS_AI_CONTRACT', 'v1.0') or 'v1.0').strip().lower()
    # E5 — execução shadow (NÃO ATIVAR em produção). Desligado por padrão; ainda
    # exige o flag `shadow` por bloco. Só registra decisão v1.1 x ação real, sem
    # efeito. ASYNC=false roda inline (apenas p/ testes locais).
    GRIMBOTS_AI_SHADOW = (os.environ.get('GRIMBOTS_AI_SHADOW', 'off') or 'off').strip().lower()
    GRIMBOTS_AI_SHADOW_SAMPLE = float(os.environ.get('GRIMBOTS_AI_SHADOW_SAMPLE', '1.0') or '1.0')
    GRIMBOTS_AI_SHADOW_INCLUDE_TEXT = os.environ.get(
        'GRIMBOTS_AI_SHADOW_INCLUDE_TEXT', 'false').lower() in {'1', 'true', 'yes'}
    GRIMBOTS_AI_SHADOW_MAX_TEXT_CHARS = int(
        os.environ.get('GRIMBOTS_AI_SHADOW_MAX_TEXT_CHARS', '0') or '0')
    GRIMBOTS_AI_SHADOW_ASYNC = os.environ.get(
        'GRIMBOTS_AI_SHADOW_ASYNC', 'true').lower() in {'1', 'true', 'yes'}
    GRIMBOTS_AI_SHADOW_WORKERS = int(os.environ.get('GRIMBOTS_AI_SHADOW_WORKERS', '2') or '2')
    # Segredo do HMAC do lead (fallback: SECRET_KEY). Nunca logar.
    GRIMBOTS_AI_SHADOW_SECRET = os.environ.get('GRIMBOTS_AI_SHADOW_SECRET', '')
    # Metadados opcionais do motor (complementam o /health no relatório E5).
    GRIMBOTS_AI_MOTOR_VERSION = os.environ.get('GRIMBOTS_AI_MOTOR_VERSION', '')
    GRIMBOTS_AI_MOTOR_COMMIT = os.environ.get('GRIMBOTS_AI_MOTOR_COMMIT', '')
    # Rollout controlado (piloto com leads reais). Kill-switch global: quando ligado,
    # TODO bloco 'ai' é desviado para HUMANO (mesmo caminho de 'enabled=False'),
    # sem responder, sem coletar decisão e sem efeito. Ausente/inválido => desligado.
    GRIMBOTS_AI_KILL_SWITCH = os.environ.get(
        'GRIMBOTS_AI_KILL_SWITCH', 'false').lower() in {'1', 'true', 'yes'}
    # Percentual de leads elegíveis à IA (0-100). Default 100 = sem restrição (o
    # gate por bloco e demais proteções continuam valendo). Fora da faixa/inválido
    # => 100 (fail-safe: NÃO reduz exposição silenciosamente por config ruim).
    # NUNCA amplia: só REMOVE leads da IA (os não elegíveis vão para HUMANO).
    try:
        _ai_rollout_raw = float(os.environ.get('GRIMBOTS_AI_ROLLOUT_PERCENT', '100') or '100')
        if _ai_rollout_raw != _ai_rollout_raw:  # NaN
            _ai_rollout_raw = 100.0
    except (TypeError, ValueError):
        _ai_rollout_raw = 100.0
    GRIMBOTS_AI_ROLLOUT_PERCENT = max(0.0, min(100.0, _ai_rollout_raw))
    # Allowlist EXPLÍCITA de bots autorizados a usar a IA (piloto isolado).
    # Lista de IDs separados por vírgula (ex.: "140" ou "140,141"). Quando NÃO
    # vazia, SOMENTE esses bots podem acionar a IA; qualquer outro bot com bloco
    # 'ai' é desviado para HUMANO (mesmo caminho de 'enabled=False'). Vazia/ausente
    # => sem restrição por allowlist (os demais gates continuam valendo).
    # NUNCA amplia exposição por si só; é uma trava ADICIONAL.
    _ai_allowlist_raw = os.environ.get('GRIMBOTS_AI_BOT_ALLOWLIST', '') or ''
    _ai_allowlist = set()
    for _tok in _ai_allowlist_raw.split(','):
        _tok = _tok.strip()
        if _tok:
            try:
                _ai_allowlist.add(int(_tok))
            except (TypeError, ValueError):
                continue
    GRIMBOTS_AI_BOT_ALLOWLIST = frozenset(_ai_allowlist)

    @classmethod
    def init_app(cls, app, rq_pool=False):
        """Aplica todas as configurações ao app Flask"""
        
        # SECRET_KEY
        if not cls.SECRET_KEY:
            raise RuntimeError(
                "\n❌ ERRO CRÍTICO: SECRET_KEY não configurada!\n\n"
                "Execute:\n"
                "  python -c \"import secrets; print('SECRET_KEY=' + secrets.token_hex(32))\" >> .env\n"
            )
        
        if cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise RuntimeError(
                "\n❌ ERRO CRÍTICO: SECRET_KEY padrão detectada!\n"
                "Gere uma nova: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            )
        
        if len(cls.SECRET_KEY) < 32:
            raise RuntimeError(
                f"\n❌ ERRO CRÍTICO: SECRET_KEY muito curta ({len(cls.SECRET_KEY)} caracteres)!\n"
                "Mínimo: 32 caracteres. Gere uma nova: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            )
        
        app.config['SECRET_KEY'] = cls.SECRET_KEY
        app.config['SQLALCHEMY_DATABASE_URI'] = cls.SQLALCHEMY_DATABASE_URI
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = cls.SQLALCHEMY_TRACK_MODIFICATIONS
        
        # Adicionar connect_args dinamicamente
        engine_options = cls.SQLALCHEMY_ENGINE_OPTIONS.copy()
        engine_options['connect_args'] = cls.get_connect_args()
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
        
        # Workers RQ usam pool reduzido para não estourar max_connections do PostgreSQL
        if rq_pool:
            rq_options = engine_options.copy()
            rq_options['pool_size'] = 5
            rq_options['max_overflow'] = 3
            rq_options['pool_recycle'] = 300
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = rq_options
        
        # Cookies/Sessão
        if cls.SESSION_COOKIE_DOMAIN:
            app.config['SESSION_COOKIE_DOMAIN'] = cls.SESSION_COOKIE_DOMAIN
            app.config['REMEMBER_COOKIE_DOMAIN'] = cls.REMEMBER_COOKIE_DOMAIN
        
        app.config['SESSION_COOKIE_SECURE'] = cls.SESSION_COOKIE_SECURE
        app.config['REMEMBER_COOKIE_SECURE'] = cls.REMEMBER_COOKIE_SECURE
        app.config['SESSION_COOKIE_SAMESITE'] = cls.SESSION_COOKIE_SAMESITE
        app.config['REMEMBER_COOKIE_SAMESITE'] = cls.REMEMBER_COOKIE_SAMESITE
        app.config['PREFERRED_URL_SCHEME'] = cls.PREFERRED_URL_SCHEME

        # Grimbots AI Gateway (bloco 'ai') — aditivo/opt-in
        app.config['GRIMBOTS_AI_API_URL'] = cls.GRIMBOTS_AI_API_URL
        app.config['GRIMBOTS_AI_API_KEY'] = cls.GRIMBOTS_AI_API_KEY
        app.config['GRIMBOTS_AI_TIMEOUT'] = cls.GRIMBOTS_AI_TIMEOUT
        app.config['GRIMBOTS_AI_MOCK'] = cls.GRIMBOTS_AI_MOCK
        app.config['GRIMBOTS_AI_CONTRACT'] = cls.GRIMBOTS_AI_CONTRACT
        # E5 — shadow (opt-in, desligado por padrão)
        app.config['GRIMBOTS_AI_SHADOW'] = cls.GRIMBOTS_AI_SHADOW
        app.config['GRIMBOTS_AI_SHADOW_SAMPLE'] = cls.GRIMBOTS_AI_SHADOW_SAMPLE
        app.config['GRIMBOTS_AI_SHADOW_INCLUDE_TEXT'] = cls.GRIMBOTS_AI_SHADOW_INCLUDE_TEXT
        app.config['GRIMBOTS_AI_SHADOW_MAX_TEXT_CHARS'] = cls.GRIMBOTS_AI_SHADOW_MAX_TEXT_CHARS
        app.config['GRIMBOTS_AI_SHADOW_WORKERS'] = cls.GRIMBOTS_AI_SHADOW_WORKERS
        app.config['GRIMBOTS_AI_SHADOW_SECRET'] = cls.GRIMBOTS_AI_SHADOW_SECRET
        app.config['GRIMBOTS_AI_MOTOR_VERSION'] = cls.GRIMBOTS_AI_MOTOR_VERSION
        app.config['GRIMBOTS_AI_MOTOR_COMMIT'] = cls.GRIMBOTS_AI_MOTOR_COMMIT
        app.config['GRIMBOTS_AI_KILL_SWITCH'] = cls.GRIMBOTS_AI_KILL_SWITCH
        app.config['GRIMBOTS_AI_ROLLOUT_PERCENT'] = cls.GRIMBOTS_AI_ROLLOUT_PERCENT
        app.config['GRIMBOTS_AI_BOT_ALLOWLIST'] = cls.GRIMBOTS_AI_BOT_ALLOWLIST
