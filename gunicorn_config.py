"""
Configuração Gunicorn para Produção
GRIMBOTS v2.1.0
"""
import multiprocessing
import os

# ✅ Evita que o eventlet use greendns (stub 127.0.0.53 causava timeouts no Telegram)
os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")

# ========================================
# SERVER SOCKET
# ========================================
bind = "127.0.0.1:5000"
backlog = 2048

# ========================================
# WORKER PROCESSES - QI 200 OTIMIZADO
# ========================================
# ✅ QI 200: Múltiplos workers para alta concorrência
# Mínimo 3 workers, máximo baseado em CPU
cpu_count = multiprocessing.cpu_count()
workers = max(3, min(cpu_count * 2 + 1, 8))  # Entre 3 e 8 workers

# ✅ IMPORTANTE: eventlet para Socket.IO
worker_class = "eventlet"

worker_connections = 1000
max_requests = 1000  # Restart worker após N requests (previne memory leak)
max_requests_jitter = 50
timeout = 120
keepalive = 5

# ========================================
# LOGGING
# ========================================
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# ========================================
# PROCESS NAMING
# ========================================
proc_name = "grimbots_v2.1"

# ========================================
# SERVER MECHANICS
# ========================================
daemon = False
pidfile = "grimbots.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# ========================================
# SSL (se não usar Nginx)
# ========================================
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# ========================================
# WORKER BEHAVIOR
# ========================================
preload_app = False  # Não preload com eventlet
reload = os.environ.get('FLASK_ENV') == 'development'

# ========================================
# SECURITY
# ========================================
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# ========================================
# CALLBACKS (opcional)
# ========================================
def on_starting(server):
    """Callback quando servidor inicia"""
    print("="*70)
    print(" GRIMBOTS v2.1.0 - INICIANDO")
    print("="*70)
    print(f" Workers: {workers}")
    print(f" Bind: {bind}")
    print(f" Worker Class: {worker_class}")
    print("="*70)

def on_reload(server):
    """Callback quando servidor recarrega"""
    print("[INFO] Servidor recarregado")

def worker_int(worker):
    """Callback quando worker recebe SIGINT"""
    print(f"[INFO] Worker {worker.pid} recebeu SIGINT")

def worker_abort(worker):
    """Callback quando worker aborta"""
    print(f"[WARN] Worker {worker.pid} abortou")

