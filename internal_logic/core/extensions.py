"""
Extensions - Instâncias Flask sem aplicação vinculada (Application Factory Pattern)
Todas as extensões são inicializadas aqui sem o app, depois vinculadas via init_app()
"""

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
