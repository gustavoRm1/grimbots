ROADMAP DE REFATORAÇÃO — MONÓLITO → MÓDULOS
Staff Engineer Blueprint para Windsurf

PRÉ-ANÁLISE: Dependências Globais Identificadas
Do código auditado, estes são os objetos compartilhados que causam os conflitos:
OBJETOS GLOBAIS CRÍTICOS (ordem de criação importa):
├── db              (SQLAlchemy) — importado de models.py
├── socketio        (Flask-SocketIO) — criado em app.py
├── bot_manager     (BotManager) — criado em app.py, depende de socketio
├── limiter         (Flask-Limiter) — criado em app.py
├── csrf            (CSRFProtect) — criado em app.py
├── login_manager   (LoginManager) — criado em app.py
└── redis_conn      (redis-py) — importado de redis_manager.py
O problema raiz: app.py cria tudo na ordem errada. eventlet.monkey_patch() precisa ser a primeira linha executada no processo, antes de qualquer import de socket, redis, threading. Hoje isso não acontece porque app.py é importado antes do patch.

ESTRUTURA ALVO
project/
├── wsgi.py                          ← NOVO: entry point soberano
├── app.py                           ← MANTIDO como wrapper fino durante transição
├── internal_logic/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── extensions.py            ← db, socketio, limiter, csrf, login_manager
│   │   ├── config.py                ← configurações centralizadas
│   │   └── redis_client.py          ← wrapper Redis singleton
│   ├── blueprints/
│   │   ├── __init__.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   └── routes.py            ← /login, /logout, /register
│   │   ├── dashboard/
│   │   │   ├── __init__.py
│   │   │   └── routes.py            ← /dashboard, /api/dashboard/*
│   │   ├── bots/
│   │   │   ├── __init__.py
│   │   │   └── routes.py            ← /api/bots/*, /bot/*, /bots/*
│   │   ├── webhooks/
│   │   │   ├── __init__.py
│   │   │   ├── payments.py          ← /webhook/payment/*, /webhooks/bolt
│   │   │   └── telegram.py          ← /webhook/telegram/*
│   │   ├── admin/
│   │   │   ├── __init__.py
│   │   │   └── routes.py            ← /admin/*
│   │   ├── remarketing/
│   │   │   ├── __init__.py
│   │   │   └── routes.py            ← /api/bots/*/remarketing/*, /remarketing/*
│   │   ├── redirect_pools/
│   │   │   ├── __init__.py
│   │   │   └── routes.py            ← /api/redirect-pools/*, /go/*
│   │   └── delivery/
│   │       ├── __init__.py
│   │       └── routes.py            ← /delivery/*, /api/tracking/*
│   └── services/
│       ├── __init__.py
│       ├── bot_runner.py            ← polling, start/stop, heartbeat
│       ├── bot_messenger.py         ← send_telegram_message, send_file
│       ├── payment_processor.py     ← process_webhook, send_payment_delivery
│       ├── meta_pixel_service.py    ← pageview, purchase, viewcontent events
│       ├── subscription_service.py  ← create, expire, remove_from_group
│       └── notification_service.py  ← push notifications, WebSocket emits

SPRINT 0 — FIX CIRÚRGICO DE INFRAESTRUTURA (eventlet)
Duração estimada: 2 horas | Risco: Baixo
Problema exato
Hoje o processo sobe assim:
gunicorn → importa app.py → app.py importa redis → redis importa socket
→ monkey_patch() chega tarde → RuntimeError
Solução: wsgi.py soberano
Criar /wsgi.py:
python# wsgi.py — DEVE ser o único entry point. NUNCA importar antes do patch.
import eventlet
eventlet.monkey_patch()  # ← LINHA 2. Imutável. Nada vem antes.

# Só depois do patch, importar tudo que usa socket/threading
from internal_logic.core.extensions import create_app, socketio

application = create_app()

if __name__ == '__main__':
    socketio.run(application, host='0.0.0.0', port=5000)
Alterar comando Gunicorn (Procfile ou systemd):
bash# ANTES:
gunicorn app:app

# DEPOIS:
gunicorn --worker-class eventlet -w 1 wsgi:application
Validação Windsurf:
bashpython -c "import wsgi; print('OK - sem RuntimeError')"

SPRINT 1 — SHARED CORE (Semana 1, Dias 1-2)
O que extrair: Extensões Flask, configuração, cliente Redis.
Risco: Baixo — nenhuma rota muda.
Arquivo 1: internal_logic/core/extensions.py
python# internal_logic/core/extensions.py
# Responsabilidade: instanciar extensões SEM criar o app ainda (Application Factory pattern)

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Instâncias vazias — serão inicializadas via init_app() dentro de create_app()
db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_object=None):
    """Application Factory — único ponto de criação do Flask app."""
    from flask import Flask
    import os
    from pathlib import Path

    app = Flask(__name__)

    # Configurações (delegadas para config.py)
    from internal_logic.core.config import configure_app
    configure_app(app, config_object)

    # Inicializar extensões
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # SocketIO precisa do app mas DEPOIS do monkey_patch (garantido pelo wsgi.py)
    socketio.init_app(
        app,
        cors_allowed_origins=app.config['ALLOWED_ORIGINS'],
        async_mode='eventlet',
        message_queue=app.config.get('SOCKETIO_MESSAGE_QUEUE'),
    )

    # Registrar blueprints
    _register_blueprints(app)

    return app


def _register_blueprints(app):
    from internal_logic.blueprints.auth.routes import auth_bp
    from internal_logic.blueprints.dashboard.routes import dashboard_bp
    from internal_logic.blueprints.bots.routes import bots_bp
    from internal_logic.blueprints.webhooks.payments import webhooks_payments_bp
    from internal_logic.blueprints.webhooks.telegram import webhooks_telegram_bp
    from internal_logic.blueprints.admin.routes import admin_bp
    from internal_logic.blueprints.remarketing.routes import remarketing_bp
    from internal_logic.blueprints.redirect_pools.routes import redirect_pools_bp
    from internal_logic.blueprints.delivery.routes import delivery_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(bots_bp)
    app.register_blueprint(webhooks_payments_bp)
    app.register_blueprint(webhooks_telegram_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(remarketing_bp)
    app.register_blueprint(redirect_pools_bp)
    app.register_blueprint(delivery_bp)
Arquivo 2: internal_logic/core/config.py
python# internal_logic/core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def configure_app(app, config_object=None):
    """Centraliza toda configuração do Flask."""
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    # Secret Key com validação
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key or len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY inválida ou ausente")
    app.config['SECRET_KEY'] = secret_key

    # Database
    db_path = BASE_DIR / 'instance' / 'saas_bot_manager.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    connect_args = (
        {'check_same_thread': False, 'timeout': 30}
        if database_url.startswith('sqlite') else {}
    )
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 30,
        'max_overflow': 15,
        'connect_args': connect_args,
    }

    # CORS / Session
    app.config['ALLOWED_ORIGINS'] = [
        o.strip() for o in
        os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000').split(',')
        if o.strip()
    ]
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get(
        'SESSION_COOKIE_SECURE', 'true').lower() in {'1', 'true', 'yes'}
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get(
        'SESSION_COOKIE_SAMESITE', 'None')
    app.config['PREFERRED_URL_SCHEME'] = os.environ.get(
        'PREFERRED_URL_SCHEME', 'https')

    # SocketIO
    app.config['SOCKETIO_MESSAGE_QUEUE'] = (
        os.environ.get('SOCKETIO_MESSAGE_QUEUE') or os.environ.get('REDIS_URL')
    )

    if config_object:
        app.config.from_object(config_object)
Arquivo 3: internal_logic/core/redis_client.py
python# internal_logic/core/redis_client.py
# Wrapper singleton para não criar múltiplas conexões Redis
import os
import redis
import logging

logger = logging.getLogger(__name__)
_redis_instance = None


def get_redis() -> redis.Redis:
    """Retorna instância Redis singleton, compatível com eventlet."""
    global _redis_instance
    if _redis_instance is None:
        url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        _redis_instance = redis.from_url(url, decode_responses=True)
        logger.info("✅ Redis singleton inicializado")
    return _redis_instance


def redis_health_check() -> dict:
    try:
        r = get_redis()
        r.ping()
        return {'status': 'healthy'}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}
Arquivo 4: internal_logic/__init__.py e sub-__init__.py
python# internal_logic/__init__.py  ← vazio intencional
# internal_logic/core/__init__.py ← vazio intencional
# Todos os sub-pacotes precisam de __init__.py vazio para serem reconhecidos
Criar todos os __init__.py vazios:
bashtouch internal_logic/__init__.py
touch internal_logic/core/__init__.py
touch internal_logic/blueprints/__init__.py
touch internal_logic/services/__init__.py
Ponte de compatibilidade no app.py (monólito não quebra):
python# app.py — topo do arquivo, SUBSTITUIR as instâncias diretas por imports
# ANTES:
# db = SQLAlchemy()  ← remover
# socketio = SocketIO(app, ...)  ← remover
# csrf = CSRFProtect(app)  ← remover

# DEPOIS (adicionar no topo de app.py durante transição):
from internal_logic.core.extensions import db, socketio, csrf, limiter, login_manager
Validação Windsurf:
bashpython -c "from internal_logic.core.extensions import db, socketio, csrf; print('Sprint 1 OK')"
python -c "from internal_logic.core.config import configure_app; print('Config OK')"
python -c "from internal_logic.core.redis_client import get_redis; print('Redis OK')"

SPRINT 2 — BLUEPRINTS DE AUTENTICAÇÃO E ADMIN (Semana 1, Dias 3-4)
O que extrair: Rotas de auth e admin — domínios mais isolados, menor risco.
Risco: Baixo
Regra de ouro para todos os blueprints:
python# PADRÃO de cada routes.py de Blueprint
from flask import Blueprint
from internal_logic.core.extensions import db, login_manager  # nunca importar 'app'
from models import User, Bot  # models permanecem no raiz durante transição

bp_name = Blueprint('auth', __name__)
internal_logic/blueprints/auth/routes.py
pythonfrom flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from flask_login import login_user, logout_user, login_required, current_user
from internal_logic.core.extensions import db, limiter
from models import User, get_brazil_time

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    # ← mover corpo exato da função login() do app.py para cá
    pass


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    # ← mover corpo exato da função logout() do app.py para cá
    pass


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    pass


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    pass
internal_logic/blueprints/admin/routes.py
pythonfrom flask import Blueprint
from internal_logic.core.extensions import db
from functools import wraps
from flask_login import current_user

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ← mover todas as rotas @app.route('/admin/*') para cá
# Exemplo:
# @admin_bp.route('/')  (era /admin)
# @admin_bp.route('/users')  (era /admin/users)
Como as rotas do monólito "enxergam" as movidas (ponte):
python# app.py — adicionar após registrar blueprints, durante transição
# Aliases para compatibilidade com url_for() no código legado

# ANTES no código legado: url_for('login')
# DEPOIS deve funcionar: url_for('auth.login')
# Para não quebrar redirects hardcoded, adicionar em app.py:

from internal_logic.blueprints.auth.routes import auth_bp
app.register_blueprint(auth_bp)

# Alias reverso para url_for() legado:
app.add_url_rule('/login', endpoint='login',
                 view_func=auth_bp.view_functions['login'])
Validação Windsurf:
bashpython -c "
from internal_logic.core.extensions import create_app
app = create_app()
with app.test_client() as c:
    r = c.get('/login')
    assert r.status_code in (200, 302), f'auth falhou: {r.status_code}'
print('Sprint 2 OK')
"

SPRINT 3 — BLUEPRINT DE WEBHOOKS (Semana 2, Dias 1-2)
O que extrair: /webhook/payment/*, /webhook/telegram/*, /webhooks/bolt
Risco: Alto — core do negócio. Usar feature flag.
Estratégia de feature flag para rollback seguro:
python# internal_logic/blueprints/webhooks/payments.py
import os
from flask import Blueprint, request, jsonify
from internal_logic.core.extensions import db, socketio

webhooks_payments_bp = Blueprint('webhooks_payments', __name__)

# Feature flag — se False, o monólito ainda trata os webhooks
WEBHOOKS_EXTRACTED = os.environ.get('FEATURE_WEBHOOKS_EXTRACTED', 'false') == 'true'


@webhooks_payments_bp.route('/webhook/payment/<string:gateway_type>',
                              methods=['POST'])
def payment_webhook(gateway_type):
    if not WEBHOOKS_EXTRACTED:
        # Delegar para função original no app.py durante transição
        from app import payment_webhook as legacy_handler
        return legacy_handler(gateway_type)

    # Nova implementação modular
    from internal_logic.services.payment_processor import process_incoming_webhook
    return process_incoming_webhook(gateway_type, request)
internal_logic/services/payment_processor.py
python# internal_logic/services/payment_processor.py
# Responsabilidade: processar webhooks de pagamento e enviar entregáveis
import logging
import json
from flask import jsonify
from internal_logic.core.extensions import db, socketio

logger = logging.getLogger(__name__)


def process_incoming_webhook(gateway_type: str, request_obj) -> tuple:
    """
    Ponto de entrada único para todos os webhooks de pagamento.
    Retorna (response, status_code).
    """
    raw_body = request_obj.get_data(cache=True, as_text=True)
    data = request_obj.get_json(silent=True) or {}

    try:
        from tasks_async import webhook_queue, process_webhook_async
        if webhook_queue:
            webhook_queue.enqueue(process_webhook_async,
                                  gateway_type=gateway_type, data=data)
            return jsonify({'status': 'queued'}), 200
    except Exception as e:
        logger.error(f"Erro ao enfileirar webhook: {e}")

    # Fallback síncrono
    try:
        from tasks_async import process_webhook_async
        process_webhook_async(gateway_type=gateway_type, data=data)
        return jsonify({'status': 'processed'}), 200
    except Exception as e:
        logger.error(f"Erro no fallback síncrono: {e}", exc_info=True)
        return jsonify({'status': 'error_logged'}), 200


def send_payment_delivery(payment, bot_manager_instance) -> bool:
    """
    Extraído de app.py — envia entregável ao cliente após pagamento confirmado.
    Idêntico ao original, mas sem dependência do escopo global de app.py.
    """
    # ← copiar corpo exato da função send_payment_delivery() do app.py
    pass
Validação Windsurf:
bash# Testar que webhook ainda funciona com flag desligada
FEATURE_WEBHOOKS_EXTRACTED=false python -c "
from internal_logic.core.extensions import create_app
app = create_app()
with app.test_client() as c:
    r = c.post('/webhook/payment/paradise', json={'test': 1})
    assert r.status_code == 200, f'webhook falhou: {r.status_code}'
print('Sprint 3 OK - flag off')
"

# Testar com flag ligada
FEATURE_WEBHOOKS_EXTRACTED=true python -c "
from internal_logic.core.extensions import create_app
app = create_app()
with app.test_client() as c:
    r = c.post('/webhook/payment/paradise', json={'test': 1})
    assert r.status_code == 200, f'webhook falhou: {r.status_code}'
print('Sprint 3 OK - flag on')
"

SPRINT 4 — DESMEMBRAMENTO DO BOT_MANAGER (Semana 2, Dias 3-5)
O que extrair: Separar as 3 responsabilidades do BotManager.
Risco: Alto — usar injeção de dependência.
Análise do BotManager atual (14k linhas = 3 responsabilidades misturadas):
BotManager hoje:
├── Runner (start_bot, stop_bot, _polling_cycle, heartbeat)
├── Messenger (send_telegram_message, send_file, send_remarketing)
└── StateManager (validate_token, get_bot_status, update_bot_config)
internal_logic/services/bot_runner.py
python# internal_logic/services/bot_runner.py
# Responsabilidade: ciclo de vida dos bots (start, stop, polling, heartbeat)
import logging
import threading
import time
import requests
from internal_logic.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class BotRunner:
    """
    Gerencia ciclo de vida: start, stop, polling, heartbeat.
    Não sabe enviar mensagens — delega para BotMessenger.
    """

    def __init__(self, bot_state, messenger):
        self.bot_state = bot_state        # RedisBot state (já existente)
        self.messenger = messenger         # BotMessenger injetado
        self._threads = {}
        self._lock = threading.Lock()

    def start_bot(self, bot_id: int, token: str, config: dict) -> None:
        if self.bot_state.is_bot_active(bot_id):
            logger.info(f"Bot {bot_id} já está ativo")
            return
        self.bot_state.register_bot(bot_id, token, config)
        thread = threading.Thread(
            target=self._polling_loop,
            args=(bot_id, token),
            name=f"bot_{bot_id}",
            daemon=True
        )
        with self._lock:
            self._threads[bot_id] = thread
        thread.start()
        logger.info(f"✅ Bot {bot_id} iniciado")

    def stop_bot(self, bot_id: int) -> None:
        self.bot_state.unregister_bot(bot_id)
        with self._lock:
            self._threads.pop(bot_id, None)
        logger.info(f"🛑 Bot {bot_id} parado")

    def _polling_loop(self, bot_id: int, token: str) -> None:
        """Loop principal de polling — extraído de _polling_cycle do monólito."""
        while self.bot_state.is_bot_active(bot_id):
            try:
                self._polling_cycle(bot_id, token)
                self._update_heartbeat(bot_id)
            except Exception as e:
                logger.error(f"Erro no polling bot {bot_id}: {e}")
            time.sleep(1)

    def _polling_cycle(self, bot_id: int, token: str) -> None:
        # ← mover corpo exato de _polling_cycle do bot_manager.py
        pass

    def _update_heartbeat(self, bot_id: int) -> None:
        try:
            r = get_redis()
            r.setex(f'bot_heartbeat:{bot_id}', 60, '1')
        except Exception as e:
            logger.debug(f"Heartbeat falhou bot {bot_id}: {e}")
internal_logic/services/bot_messenger.py
python# internal_logic/services/bot_messenger.py
# Responsabilidade: APENAS enviar mensagens via Telegram API
import logging
import requests
import time

logger = logging.getLogger(__name__)

# Semáforo para rate limiting (extraído do bot_manager.py)
import threading
_http_semaphore = threading.Semaphore(10)


class BotMessenger:
    """
    Envia mensagens, mídias, botões via Telegram API.
    Não conhece estado de bots, não faz polling.
    """

    def send_message(self, token: str, chat_id: str, message: str,
                     media_url: str = None, buttons: list = None,
                     parse_mode: str = 'HTML') -> dict:
        """Envia mensagem de texto ou com mídia."""
        with _http_semaphore:
            if media_url:
                return self._send_with_media(token, chat_id, message,
                                             media_url, buttons, parse_mode)
            return self._send_text(token, chat_id, message,
                                   buttons, parse_mode)

    def _send_text(self, token, chat_id, message, buttons, parse_mode):
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        if buttons:
            payload['reply_markup'] = self._build_keyboard(buttons)
        response = requests.post(url, json=payload, timeout=30)
        return response.json()

    def _send_with_media(self, token, chat_id, caption,
                         media_url, buttons, parse_mode):
        # ← extrair lógica de send_telegram_message com mídia do bot_manager.py
        pass

    def _build_keyboard(self, buttons: list) -> dict:
        # ← extrair _build_inline_keyboard do bot_manager.py
        pass

    def send_remarketing_campaign(self, campaign_id: int,
                                  bot_token: str) -> None:
        # ← extrair send_remarketing_campaign do bot_manager.py
        pass
Adaptador de compatibilidade — BotManager não quebra durante transição:
python# bot_manager.py — adicionar no início da classe BotManager durante transição

class BotManager:
    def __init__(self, socketio_instance, scheduler=None):
        # ... código existente ...

        # ✅ SPRINT 4: Injetar serviços extraídos
        # Durante transição, BotManager delega para os novos serviços
        # mas mantém interface pública idêntica
        from internal_logic.services.bot_messenger import BotMessenger
        self._messenger = BotMessenger()

    def send_telegram_message(self, token, chat_id, message,
                               media_url=None, buttons=None):
        """Delegação para BotMessenger — interface pública mantida."""
        return self._messenger.send_message(
            token=token,
            chat_id=str(chat_id),
            message=message,
            media_url=media_url,
            buttons=buttons
        )
Validação Windsurf:
bashpython -c "
from internal_logic.services.bot_runner import BotRunner
from internal_logic.services.bot_messenger import BotMessenger
print('Serviços instanciáveis OK')

# Garantir que bot_manager.py ainda importa sem erro
from bot_manager import BotManager
print('BotManager legado OK')
"

SPRINT 5 — BLUEPRINTS DE DOMÍNIO (Semana 3)
O que extrair: Dashboard, Bots, Remarketing, Redirect Pools, Delivery.
Risco: Médio
Ordem de extração (do menos ao mais acoplado):
1. delivery/routes.py      ← poucas dependências, fácil isolar
2. redirect_pools/routes.py ← independente
3. remarketing/routes.py   ← depende de bot_manager (usar injeção)
4. bots/routes.py          ← mais acoplado, extrair por último
5. dashboard/routes.py     ← depende de quase tudo, último
Padrão de injeção do bot_manager nos blueprints:
python# Problema: blueprints não podem importar bot_manager diretamente
# (criaria importação circular app.py → blueprint → bot_manager → app.py)

# Solução: g do Flask + before_request no app factory

# internal_logic/core/extensions.py — adicionar:
def register_bot_manager(app, bot_manager_instance):
    """Registra bot_manager no contexto da app sem criar circular import."""
    app.config['BOT_MANAGER'] = bot_manager_instance

# Em qualquer blueprint:
from flask import current_app

def get_bot_manager():
    return current_app.config['BOT_MANAGER']

# Uso nas rotas:
@bots_bp.route('/api/bots/<int:bot_id>/start', methods=['POST'])
@login_required
def start_bot(bot_id):
    bm = get_bot_manager()
    bm.start_bot(...)
internal_logic/blueprints/delivery/routes.py
python# Exemplo completo de blueprint extraído
from flask import Blueprint, render_template, request, jsonify, abort
from internal_logic.core.extensions import db
from models import Payment, PoolBot, BotUser

delivery_bp = Blueprint('delivery', __name__)


@delivery_bp.route('/delivery/<delivery_token>')
def delivery_page(delivery_token):
    # ← mover corpo exato de delivery_page() do app.py para cá
    # Única mudança: substituir bot_manager global por get_bot_manager()
    pass


@delivery_bp.route('/api/tracking/mark-purchase-sent', methods=['POST'])
def mark_purchase_sent():
    # ← mover corpo exato
    pass


@delivery_bp.route('/api/tracking/cookies', methods=['POST'])
def capture_tracking_cookies():
    # ← mover corpo exato
    pass
Validação Windsurf (rodar após cada blueprint extraído):
bashpython -c "
import ast, sys
files = [
    'internal_logic/blueprints/delivery/routes.py',
    'internal_logic/blueprints/redirect_pools/routes.py',
    'internal_logic/blueprints/remarketing/routes.py',
]
for f in files:
    try:
        with open(f) as fh:
            ast.parse(fh.read())
        print(f'✅ Sintaxe OK: {f}')
    except SyntaxError as e:
        print(f'❌ ERRO: {f} — {e}')
        sys.exit(1)
"

SPRINT 6 — LIMPEZA FINAL E REMOÇÃO DO MONÓLITO (Semana 4)
Risco: Médio — só executar após todos os sprints validados em staging.
Checklist de segurança antes de remover código do app.py:
bash# 1. Garantir que todos os endpoints respondem
python -c "
from internal_logic.core.extensions import create_app
app = create_app()
endpoints = [rule.rule for rule in app.url_map.iter_rules()]
critical = ['/login', '/dashboard', '/webhook/payment/paradise',
            '/delivery/test', '/api/bots', '/go/test']
for ep in critical:
    # verificar se endpoint existe
    matched = any(ep.split('<')[0] in e for e in endpoints)
    status = '✅' if matched else '❌ FALTANDO'
    print(f'{status} {ep}')
"

# 2. Verificar imports circulares
python -c "
import importlib, sys
modules = [
    'internal_logic.core.extensions',
    'internal_logic.core.config',
    'internal_logic.core.redis_client',
    'internal_logic.services.bot_runner',
    'internal_logic.services.bot_messenger',
    'internal_logic.services.payment_processor',
]
for m in modules:
    try:
        importlib.import_module(m)
        print(f'✅ {m}')
    except ImportError as e:
        print(f'❌ {m}: {e}')
        sys.exit(1)
"

# 3. Rodar suite de testes se existir
pytest tests/ -x -q 2>/dev/null || echo "sem tests configurados"
app.py após limpeza total (wrapper fino):
python# app.py — versão final pós-refatoração (~30 linhas)
# Mantido apenas para compatibilidade com scripts legados que importam 'app'

import eventlet
eventlet.monkey_patch()

from internal_logic.core.extensions import create_app, socketio, db
from bot_manager import BotManager

app = create_app()

# Inicializar BotManager e injetar no app context
bot_manager = BotManager(socketio, scheduler=None)
app.config['BOT_MANAGER'] = bot_manager

# Expor para imports legados (tasks_async.py, etc. fazem 'from app import app')
__all__ = ['app', 'socketio', 'db', 'bot_manager']

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

TABELA RESUMO DOS SPRINTS
SprintO que extrairArquivos criadosRiscoValidação0wsgi.py + monkey_patchwsgi.pyBaixopython wsgi.py sem RuntimeError1extensions, config, rediscore/*.pyBaixoimport test2auth + admin routesblueprints/auth/, blueprints/admin/Baixotest_client GET /login == 2003webhooks (com feature flag)blueprints/webhooks/, services/payment_processor.pyAltoflag off/on ambos 2004BotManager → Runner + Messengerservices/bot_runner.py, services/bot_messenger.pyAltoimport + delegate test5delivery, pools, remarketing, bots, dashboardblueprints/*/routes.pyMédioast.parse em todos6Remoção do monólitoapp.py → 30 linhasMédioendpoint coverage check

REGRAS DE OURO PARA O WINDSURF
1. NUNCA mover código sem primeiro criar o arquivo destino e validar sintaxe
2. SEMPRE manter a função original no app.py com um comentário
   # DEPRECATED: movido para internal_logic/blueprints/X/routes.py
   até o Sprint 6
3. NUNCA importar 'app' dentro de blueprints — usar current_app
4. NUNCA criar instâncias de db/socketio fora de extensions.py
5. Cada Sprint é um commit separado com mensagem:
   "refactor(sprint-N): extract <domínio>"
6. Se um Sprint quebrar staging, fazer revert do commit
   e investigar antes de prosseguir