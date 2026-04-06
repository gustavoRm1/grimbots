"""
Extensions - Instâncias Flask sem aplicação vinculada (Application Factory Pattern)
Todas as extensões são inicializadas aqui sem o app, depois vinculadas via init_app()
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Instâncias vazias — serão inicializadas via init_app() dentro de create_app()
db = SQLAlchemy()
socketio = SocketIO()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


def create_app():
    """
    Application Factory Pattern — Cria e configura a aplicação Flask
    
    Retorna:
        app: Instância Flask configurada com todas as extensões e blueprints
    """
    # Criar app Flask
    app = Flask(__name__)
    
    # ============================================================================
    # APLICAR CONFIGURAÇÕES CENTRALIZADAS
    # ============================================================================
    from internal_logic.core.config import Config
    Config.init_app(app)
    
    # ============================================================================
    # INICIALIZAR EXTENSÕES FLASK
    # ============================================================================
    db.init_app(app)
    socketio.init_app(app, message_queue=app.config.get('SOCKETIO_MESSAGE_QUEUE'))
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Configurar login_manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'info'
    
    # ============================================================================
    # INICIALIZAR BOT MANAGER
    # ============================================================================
    from bot_manager import BotManager
    bot_manager = BotManager()
    app.config['BOT_MANAGER'] = bot_manager
    
    # ============================================================================
    # REGISTRAR BLUEPRINTS
    # ============================================================================
    from internal_logic.blueprints.auth.routes import auth_bp
    from internal_logic.blueprints.dashboard.routes import dashboard_bp
    from internal_logic.blueprints.webhooks.payments import webhooks_bp
    from internal_logic.blueprints.webhooks.telegram import telegram_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(telegram_bp)
    
    # ============================================================================
    # REGISTRAR BLUEPRINT DE GAMIFICAÇÃO (se disponível)
    # ============================================================================
    try:
        from gamification_api import gamification_bp
        app.register_blueprint(gamification_bp)
    except ImportError:
        pass  # Gamificação é opcional
    
    # ============================================================================
    # REGISTRAR USER LOADER DO FLASK-LOGIN
    # ============================================================================
    from internal_logic.core.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app
