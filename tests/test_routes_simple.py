"""
Teste de rotas - Verificar url_map do Flask (sem eventlet)
"""
import os
import sys

# Adicionar raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock eventlet antes de importar
class MockEventlet:
    def monkey_patch(self, *args, **kwargs):
        pass
sys.modules['eventlet'] = MockEventlet()
sys.modules['eventlet.green'] = MockEventlet()

from flask import Flask
from internal_logic.core.config import Config

# Criar app mínimo para testar rotas
app = Flask(__name__, 
           template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
           static_folder=os.path.join(os.path.dirname(__file__), 'static'))
Config.init_app(app)

# Forçar SECRET_KEY para sessões
app.config['SECRET_KEY'] = 'test-secret-key'

# Inicializar apenas db e login (sem socketio/eventlet)
from internal_logic.core.extensions import db, login_manager
db.init_app(app)
login_manager.init_app(app)

# Registrar blueprints
from internal_logic.blueprints.auth.routes import auth_bp
from internal_logic.blueprints.dashboard.routes import dashboard_bp
from internal_logic.blueprints.webhooks.payments import webhooks_bp
from internal_logic.blueprints.webhooks.telegram import telegram_bp
from internal_logic.blueprints.admin.routes import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(webhooks_bp)
app.register_blueprint(telegram_bp)
app.register_blueprint(admin_bp)

# User loader
from internal_logic.core.models import User
@login_manager.user_loader
def load_user(user_id):
    return None  # Simplificado para teste

print("=" * 80)
print("MAPA DE ROTAS DO FLASK (url_map)")
print("=" * 80)
print()

count = 0
for rule in app.url_map.iter_rules():
    methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
    print(f"{rule.endpoint:40s} {methods:20s} {rule.rule}")
    count += 1

print()
print("=" * 80)
print(f"TOTAL DE ROTAS: {count}")
print("=" * 80)

# Verificar rotas críticas
print("\n🔍 ROTAS CRÍTICAS VERIFICADAS:")
critical_routes = ['/', '/login', '/dashboard', '/ranking', '/admin']
for route in critical_routes:
    found = any(rule.rule == route for rule in app.url_map.iter_rules())
    status = "✅" if found else "❌"
    print(f"{status} {route}")
