#!/bin/bash
# Script para configurar Systemd automaticamente
# Detecta usuário, grupo e diretório atual

set -e

echo "=========================================="
echo "  SETUP SYSTEMD AUTOMÁTICO"
echo "=========================================="
echo ""

# Detectar configurações
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)
CURRENT_DIR=$(pwd)
VENV_PATH="$CURRENT_DIR/venv"

echo "Configurações detectadas:"
echo "  Usuário: $CURRENT_USER"
echo "  Grupo: $CURRENT_GROUP"
echo "  Diretório: $CURRENT_DIR"
echo "  Venv: $VENV_PATH"
echo ""

# Verificar .env para DATABASE_URL e SECRET_KEY
if [ -f ".env" ]; then
    echo "✅ Arquivo .env encontrado"
    DATABASE_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2- || echo "")
    SECRET_KEY=$(grep "^SECRET_KEY=" .env | cut -d'=' -f2- || echo "")
    REDIS_URL=$(grep "^REDIS_URL=" .env | cut -d'=' -f2- || echo "redis://localhost:6379/0")
else
    echo "⚠️ Arquivo .env não encontrado, usando valores padrão"
    DATABASE_URL="sqlite:///$CURRENT_DIR/instance/saas_bot_manager.db"
    SECRET_KEY="CHANGE_THIS_SECRET_KEY"
    REDIS_URL="redis://localhost:6379/0"
fi

echo "  Database: $DATABASE_URL"
echo "  Redis: $REDIS_URL"
echo ""

# Criar grimbots.service
echo "Criando grimbots.service..."
cat > /tmp/grimbots.service << EOF
[Unit]
Description=Grimbots Gunicorn Application Server
After=network.target redis.service
Wants=redis.service
Documentation=https://github.com/your-repo/grimbots

[Service]
Type=notify
User=$CURRENT_USER
Group=$CURRENT_GROUP
WorkingDirectory=$CURRENT_DIR

# Environment
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$CURRENT_DIR"
Environment="DATABASE_URL=$DATABASE_URL"
Environment="REDIS_URL=$REDIS_URL"
Environment="SECRET_KEY=$SECRET_KEY"
Environment="FLASK_ENV=production"

# Gunicorn command
ExecStart=$VENV_PATH/bin/gunicorn -c $CURRENT_DIR/gunicorn_config.py wsgi:app

# Reload (graceful restart)
ExecReload=/bin/kill -s HUP \$MAINPID

# Kill mode
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=0

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=grimbots

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Criar rq-worker@.service
echo "Criando rq-worker@.service..."
cat > /tmp/rq-worker@.service << EOF
[Unit]
Description=RQ Worker %I
After=network.target redis.service grimbots.service
Wants=redis.service
PartOf=grimbots.service
Documentation=https://python-rq.org/

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_GROUP
WorkingDirectory=$CURRENT_DIR

# Environment
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$CURRENT_DIR"
Environment="REDIS_URL=$REDIS_URL"
Environment="DATABASE_URL=$DATABASE_URL"

# RQ Worker command
# %i será substituído pelo nome após @ (ex: tasks-1, gateway-1)
ExecStart=$VENV_PATH/bin/python $CURRENT_DIR/start_rq_worker.py %i

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=0

# Resource limits
LimitNOFILE=4096

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rq-worker-%i

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Copiar para /etc/systemd/system/
echo ""
echo "Copiando para /etc/systemd/system/..."
sudo cp /tmp/grimbots.service /etc/systemd/system/
sudo cp /tmp/rq-worker@.service /etc/systemd/system/

# Recarregar systemd
echo "Recarregando systemd..."
sudo systemctl daemon-reload

echo ""
echo "✅ Services configurados!"
echo ""
echo "Para verificar:"
echo "  cat /etc/systemd/system/grimbots.service"
echo "  cat /etc/systemd/system/rq-worker@.service"
echo ""

