#!/bin/bash
# DEPLOY COMPLETO QI 500 - UM ÚNICO COMANDO
# Configura, mata tudo, inicia limpo e valida

set -e
trap 'echo "❌ Erro na linha $LINENO"' ERR

echo "=========================================="
echo "  DEPLOY COMPLETO QI 500 - GRIMBOTS"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Verificar diretório
if [ ! -f "wsgi.py" ]; then
    error "Execute do diretório raiz do projeto (onde está wsgi.py)"
fi

# Detectar configurações
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)
CURRENT_DIR=$(pwd)
VENV_PATH="$CURRENT_DIR/venv"

info "Usuário: $CURRENT_USER"
info "Diretório: $CURRENT_DIR"
echo ""

# ==========================================
# FASE 1: TESTAR REDIS MANAGER
# ==========================================
echo "📋 FASE 1: Testando Redis Manager..."
source venv/bin/activate

if python redis_manager.py > /tmp/redis_test.log 2>&1; then
    success "Redis Manager funcionando"
else
    error "Redis Manager com problemas. Ver: /tmp/redis_test.log"
fi

# ==========================================
# FASE 2: CONFIGURAR SYSTEMD
# ==========================================
echo ""
echo "⚙️  FASE 2: Configurando Systemd..."

# Ler .env
DATABASE_URL=$(grep "^DATABASE_URL=" .env 2>/dev/null | cut -d'=' -f2- || echo "sqlite:///$CURRENT_DIR/instance/saas_bot_manager.db")
SECRET_KEY=$(grep "^SECRET_KEY=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
REDIS_URL=$(grep "^REDIS_URL=" .env 2>/dev/null | cut -d'=' -f2- || echo "redis://localhost:6379/0")

if [ -z "$SECRET_KEY" ]; then
    warning "SECRET_KEY não encontrado em .env, usando padrão (INSEGURO!)"
    SECRET_KEY="dev-secret-key-change-in-production"
fi

# Criar grimbots.service
cat > /tmp/grimbots.service << EOF
[Unit]
Description=Grimbots Gunicorn Application Server
After=network.target redis.service
Wants=redis.service

[Service]
Type=notify
User=$CURRENT_USER
Group=$CURRENT_GROUP
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$CURRENT_DIR"
Environment="DATABASE_URL=$DATABASE_URL"
Environment="REDIS_URL=$REDIS_URL"
Environment="SECRET_KEY=$SECRET_KEY"
Environment="FLASK_ENV=production"
ExecStart=$VENV_PATH/bin/gunicorn -c $CURRENT_DIR/gunicorn_config.py wsgi:app
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30
Restart=always
RestartSec=10
StartLimitInterval=0
LimitNOFILE=65536
StandardOutput=journal
StandardError=journal
SyslogIdentifier=grimbots
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Criar rq-worker@.service
cat > /tmp/rq-worker@.service << EOF
[Unit]
Description=RQ Worker %I
After=network.target redis.service grimbots.service
Wants=redis.service
PartOf=grimbots.service

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_GROUP
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$CURRENT_DIR"
Environment="REDIS_URL=$REDIS_URL"
Environment="DATABASE_URL=$DATABASE_URL"
ExecStart=$VENV_PATH/bin/python $CURRENT_DIR/start_rq_worker.py %i
Restart=always
RestartSec=10
StartLimitInterval=0
LimitNOFILE=4096
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rq-worker-%i
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Copiar
sudo cp /tmp/grimbots.service /etc/systemd/system/
sudo cp /tmp/rq-worker@.service /etc/systemd/system/
sudo systemctl daemon-reload
success "Systemd configurado"

# ==========================================
# FASE 3: MATAR PROCESSOS
# ==========================================
echo ""
echo "💀 FASE 3: Matando processos antigos..."
pkill -9 python 2>/dev/null || true
pkill -9 python3 2>/dev/null || true
pkill -9 gunicorn 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 3
success "Processos mortos"

# Verificar porta
if lsof -i:5000 > /dev/null 2>&1; then
    warning "Porta 5000 ainda em uso, forçando..."
    lsof -ti:5000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

if lsof -i:5000 > /dev/null 2>&1; then
    error "Não foi possível liberar porta 5000!"
fi
success "Porta 5000 livre"

# ==========================================
# FASE 4: INICIAR SERVICES
# ==========================================
echo ""
echo "🚀 FASE 4: Iniciando serviços..."

# Habilitar
sudo systemctl enable grimbots 2>/dev/null || true

# Iniciar Gunicorn
sudo systemctl start grimbots

# Aguardar
sleep 5

# Verificar
if sudo systemctl is-active --quiet grimbots; then
    success "Gunicorn iniciado"
else
    error "Gunicorn NÃO iniciou! Ver: sudo journalctl -u grimbots -n 30"
fi

# Iniciar RQ Workers
info "Iniciando RQ Workers..."
for i in {1..5}; do 
    sudo systemctl enable rq-worker@tasks-$i 2>/dev/null || true
    sudo systemctl start rq-worker@tasks-$i
done

for i in {1..3}; do 
    sudo systemctl enable rq-worker@gateway-$i 2>/dev/null || true
    sudo systemctl start rq-worker@gateway-$i
done

for i in {1..3}; do 
    sudo systemctl enable rq-worker@webhook-$i 2>/dev/null || true
    sudo systemctl start rq-worker@webhook-$i
done

sleep 5

WORKER_COUNT=$(sudo systemctl status 'rq-worker@*' 2>/dev/null | grep -c "active (running)" || echo "0")
success "$WORKER_COUNT/11 RQ Workers iniciados"

# ==========================================
# FASE 5: VALIDAR
# ==========================================
echo ""
echo "🏥 FASE 5: Validando sistema..."

# Health check
sleep 3  # Aguardar app inicializar
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health 2>/dev/null || echo "000")

if [ "$HEALTH" = "200" ]; then
    success "Health check OK"
    curl -s http://localhost:5000/health 2>/dev/null | python3 -m json.tool 2>/dev/null | head -20 || true
elif [ "$HEALTH" = "503" ]; then
    warning "Health check: UNHEALTHY (503)"
else
    warning "Health check: INACESSÍVEL (HTTP $HEALTH)"
fi

# ==========================================
# RESUMO FINAL
# ==========================================
echo ""
echo "=========================================="
echo "  ✅ DEPLOY CONCLUÍDO"
echo "=========================================="
echo ""
echo "📊 Status:"
if sudo systemctl is-active --quiet grimbots; then
    success "Gunicorn: RODANDO"
else
    error "Gunicorn: PARADO"
fi

echo "  RQ Workers: $WORKER_COUNT/11"
echo "  Health Check: HTTP $HEALTH"
echo ""

if lsof -i:5000 > /dev/null 2>&1; then
    PID=$(lsof -ti:5000)
    success "Porta 5000: PID $PID"
else
    error "Porta 5000: LIVRE (problema!)"
fi

echo ""
echo "📋 Próximos passos:"
echo "  1. Testar bot (enviar /start)"
echo "  2. Monitorar: sudo journalctl -u grimbots -f"
echo "  3. Health: curl http://localhost:5000/health"
echo "  4. Validar: ./verificar_sistema.sh"
echo ""
echo "🔧 Comandos úteis:"
echo "  sudo systemctl status grimbots"
echo "  sudo systemctl restart grimbots"
echo "  sudo journalctl -u grimbots -f"
echo ""

# Exit code
if sudo systemctl is-active --quiet grimbots && [ "$WORKER_COUNT" -ge 10 ]; then
    success "SISTEMA OPERACIONAL ✅"
    exit 0
else
    warning "SISTEMA COM PROBLEMAS - Verifique logs"
    exit 1
fi

