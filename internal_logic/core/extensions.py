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
import os
from flask_limiter.util import get_remote_address

# Instâncias vazias — serão inicializadas via init_app() dentro de create_app()
db = SQLAlchemy()
socketio = SocketIO()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
)


def create_app():
    """
    Application Factory Pattern — Cria e configura a aplicação Flask
    """
    # Mapeamento absoluto da raiz do projeto (dois níveis acima de 'core')
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    # Inicializa o Flask apontando explicitamente para as pastas front-end da raiz
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
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
    # REGISTRAR BLUEPRINTS
    # ============================================================================
    from internal_logic.blueprints.auth.routes import auth_bp
    from internal_logic.blueprints.dashboard.routes import dashboard_bp
    from internal_logic.blueprints.webhooks.payments import webhooks_bp
    from internal_logic.blueprints.webhooks.telegram import telegram_bp
    from internal_logic.blueprints.admin.routes import admin_bp
    from internal_logic.blueprints.public.routes import public_bp
    from internal_logic.blueprints.delivery.routes import delivery_bp
    from internal_logic.blueprints.remarketing.routes import remarketing_bp
    from internal_logic.blueprints.bots.routes import bots_bp
    from internal_logic.blueprints.api.routes import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(telegram_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(delivery_bp)
    app.register_blueprint(remarketing_bp, url_prefix='/remarketing')
    app.register_blueprint(bots_bp, url_prefix='/bots')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # ============================================================================
    # REGISTRAR BLUEPRINT DE GAMIFICAÇÃO (se disponível)
    # ============================================================================
    try:
        from gamification_api import gamification_bp
        app.register_blueprint(gamification_bp)
    except ImportError:
        pass  # Gamificação é opcional
    
    # ============================================================================
    # ALIAS DE COMPATIBILIDADE PARA ENDPOINTS LEGADOS (url_for antigo)
    # ============================================================================
    # Adicionar ALIAS para manter compatibilidade com url_for legados nos templates
    # Mapeia requisições do nome antigo (monólito) para o novo nome (blueprint.rota)
    app.add_url_rule('/dashboard', endpoint='dashboard', view_func=app.view_functions.get('dashboard.dashboard'))
    app.add_url_rule('/login', endpoint='login', view_func=app.view_functions.get('auth.login'))
    app.add_url_rule('/logout', endpoint='logout', view_func=app.view_functions.get('auth.logout'))
    app.add_url_rule('/register', endpoint='register', view_func=app.view_functions.get('auth.register'))
    
    # Alias adicionais que podem estar no menu base:
    if app.view_functions.get('dashboard.settings'):
        app.add_url_rule('/settings', endpoint='settings', view_func=app.view_functions.get('dashboard.settings'))
    if app.view_functions.get('dashboard.ranking'):
        app.add_url_rule('/ranking', endpoint='ranking', view_func=app.view_functions.get('dashboard.ranking'))
    if app.view_functions.get('dashboard.chat'):
        app.add_url_rule('/chat', endpoint='chat', view_func=app.view_functions.get('dashboard.chat'))
    if app.view_functions.get('dashboard.redirect_pools_page'):
        app.add_url_rule('/redirect-pools', endpoint='redirect_pools_page', view_func=app.view_functions.get('dashboard.redirect_pools_page'))
    
    # Alias para admin
    if app.view_functions.get('admin.admin_dashboard'):
        app.add_url_rule('/admin', endpoint='admin_dashboard', view_func=app.view_functions.get('admin.admin_dashboard'))
    
    # ============================================================================
    # REGISTRAR USER LOADER DO FLASK-LOGIN
    # ============================================================================
    from internal_logic.core.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # ============================================================================
    # REGISTRAR COMANDOS CLI
    # ============================================================================
    from internal_logic.core.commands import register_commands
    register_commands(app)
    
    # ============================================================================
    # 🔥 CRÍTICO: MOTOR DE AUTO-CURA DE WEBHOOKS (SELF-HEALING ARCHITECTURE)
    # ============================================================================
    # Inicia thread de sincronização de webhooks no boot do servidor.
    # NÃO bloqueia o Gunicorn - roda em background (daemon thread).
    # Garante que todos os bots ativos estejam sempre conectados ao Telegram.
    # ============================================================================
    from internal_logic.services.webhook_syncer import start_webhook_sync_thread
    start_webhook_sync_thread(app)
    
    # ============================================================================
    # 🔥 CRÍTICO: TEARDOWN HANDLER PARA LIMPAR TRANSAÇÕES BLOQUEADAS
    # ============================================================================
    @app.teardown_request
    def teardown_request(exception=None):
        """
        Limpa sessão do SQLAlchemy após cada requisição.
        Previne 'InFailedSqlTransaction' quando uma transação anterior falhou.
        """
        if exception:
            db.session.rollback()
        db.session.remove()
    
    return app
