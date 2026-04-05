"""
Configuração Centralizada - Application Factory Pattern
Todas as configurações do Flask centralizadas aqui
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()


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
        'pool_recycle': 300,
        'pool_size': 30,
        'max_overflow': 15,
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
    
    @classmethod
    def init_app(cls, app):
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
        
        # Cookies/Sessão
        if cls.SESSION_COOKIE_DOMAIN:
            app.config['SESSION_COOKIE_DOMAIN'] = cls.SESSION_COOKIE_DOMAIN
            app.config['REMEMBER_COOKIE_DOMAIN'] = cls.REMEMBER_COOKIE_DOMAIN
        
        app.config['SESSION_COOKIE_SECURE'] = cls.SESSION_COOKIE_SECURE
        app.config['REMEMBER_COOKIE_SECURE'] = cls.REMEMBER_COOKIE_SECURE
        app.config['SESSION_COOKIE_SAMESITE'] = cls.SESSION_COOKIE_SAMESITE
        app.config['REMEMBER_COOKIE_SAMESITE'] = cls.REMEMBER_COOKIE_SAMESITE
        app.config['PREFERRED_URL_SCHEME'] = cls.PREFERRED_URL_SCHEME
