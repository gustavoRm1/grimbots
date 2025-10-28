#!/bin/bash
# Instalar Celery como serviço systemd

echo "🚀 Instalando Celery como serviço systemd..."

# Criar arquivo de serviço
cat > /etc/systemd/system/celery.service << 'EOF'
[Unit]
Description=Celery Worker for Grimbots
After=network.target redis.service

[Service]
Type=forking
User=root
Group=root
WorkingDirectory=/root/grimbots
Environment="PATH=/root/grimbots/venv/bin"
ExecStart=/root/grimbots/venv/bin/celery multi start worker1 \
    --pidfile=/var/run/celery/%n.pid \
    --logfile=/var/log/celery/%n%I.log \
    --loglevel=INFO \
    -A celery_app
ExecStop=/root/grimbots/venv/bin/celery multi stop worker1 \
    --pidfile=/var/run/celery/%n.pid
ExecReload=/root/grimbots/venv/bin/celery multi restart worker1 \
    --pidfile=/var/run/celery/%n.pid \
    --logfile=/var/log/celery/%n%I.log \
    --loglevel=INFO \
    -A celery_app
Restart=always
KillMode=mixed
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

# Criar diretórios necessários
mkdir -p /var/run/celery
mkdir -p /var/log/celery
chmod 755 /var/run/celery
chmod 755 /var/log/celery

# Recarregar systemd
systemctl daemon-reload

# Habilitar serviço
systemctl enable celery

# Iniciar serviço
systemctl start celery

# Verificar status
systemctl status celery

echo "✅ Celery instalado e iniciado!"
echo ""
echo "📋 COMANDOS ÚTEIS:"
echo "  systemctl status celery    - Ver status"
echo "  systemctl restart celery   - Reiniciar"
echo "  systemctl stop celery      - Parar"
echo "  journalctl -u celery -f    - Ver logs em tempo real"

