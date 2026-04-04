#!/usr/bin/env bash
set -e

echo "🛠️ Criando o serviço Systemd Definitivo para a API (Gunicorn)..."

# Descobre o diretório atual e o usuário
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)
VENV_PATH="$CURRENT_DIR/venv"

cat << EOF > /tmp/grimbots.service
[Unit]
Description=Grimbots Gunicorn API Server
After=network.target redis.service
Wants=redis.service

[Service]
Type=notify
User=$CURRENT_USER
Group=www-data
WorkingDirectory=$CURRENT_DIR
EnvironmentFile=$CURRENT_DIR/.env
ExecStart=$VENV_PATH/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 --timeout 120 --log-level info wsgi:app
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/grimbots.service /etc/systemd/system/grimbots.service
sudo systemctl daemon-reload
sudo systemctl enable grimbots

echo "✅ Serviço Systemd configurado e ativado. A API agora é gerida pelo Linux."
