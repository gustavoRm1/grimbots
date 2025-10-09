#!/bin/bash

##############################################################################
# SCRIPT PARA INICIAR BOT MANAGER COM PM2
# Execute após configurar .env e inicializar banco
##############################################################################

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "============================================================"
echo " INICIANDO BOT MANAGER COM PM2"
echo "============================================================"
echo ""

# Ir para diretório do projeto
cd /var/www/bot-manager

# Verificar se .env existe
if [ ! -f .env ]; then
    echo -e "${YELLOW}[AVISO]${NC} Arquivo .env não encontrado!"
    echo "Copie env.example para .env e configure as variáveis:"
    echo "  cp env.example .env"
    echo "  nano .env"
    exit 1
fi

# Verificar se venv existe
if [ ! -d venv ]; then
    echo -e "${YELLOW}[AVISO]${NC} Ambiente virtual não encontrado!"
    echo "Crie o venv:"
    echo "  python3.11 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Ajustar ecosystem.config.js para usar o venv
VENV_PYTHON=$(pwd)/venv/bin/python

echo -e "${CYAN}[INFO]${NC} Ajustando ecosystem.config.js..."

# Criar versão atualizada do ecosystem.config.js
cat > ecosystem.config.js <<EOF
module.exports = {
  apps: [{
    name: 'bot-manager',
    script: '$(pwd)/venv/bin/gunicorn',
    args: [
      '--worker-class', 'eventlet',
      '--workers', '1',
      '--bind', '127.0.0.1:5000',
      '--timeout', '120',
      '--keep-alive', '5',
      '--log-level', 'info',
      '--access-logfile', 'logs/access.log',
      '--error-logfile', 'logs/error.log',
      'wsgi:app'
    ],
    interpreter: '$VENV_PYTHON',
    cwd: '$(pwd)',
    env: {
      FLASK_ENV: 'production',
      PYTHONUNBUFFERED: '1',
      LANG: 'C.UTF-8',
      LC_ALL: 'C.UTF-8'
    },
    max_memory_restart: '500M',
    max_restarts: 10,
    min_uptime: '5s',
    restart_delay: 4000,
    autorestart: true,
    watch: false,
    output: 'logs/pm2-out.log',
    error: 'logs/pm2-error.log',
    log: 'logs/pm2-combined.log',
    time: true,
    merge_logs: true,
    instances: 1,
    exec_mode: 'fork',
    kill_timeout: 5000,
    listen_timeout: 10000
  }]
};
EOF

echo -e "${GREEN}[OK]${NC} ecosystem.config.js atualizado"
echo ""

# Criar diretório de logs
echo -e "${CYAN}[INFO]${NC} Criando diretório de logs..."
mkdir -p logs
touch logs/access.log logs/error.log logs/pm2-out.log logs/pm2-error.log logs/pm2-combined.log
echo -e "${GREEN}[OK]${NC} Logs criados"
echo ""

# Parar PM2 se já estiver rodando
echo -e "${CYAN}[INFO]${NC} Verificando processos PM2..."
if pm2 list | grep -q "bot-manager"; then
    echo -e "${YELLOW}[INFO]${NC} Bot Manager já está rodando, parando..."
    pm2 delete bot-manager
fi

# Iniciar com PM2
echo -e "${CYAN}[INFO]${NC} Iniciando com PM2..."
pm2 start ecosystem.config.js

# Salvar configuração
pm2 save

# Configurar startup (se ainda não foi)
if ! systemctl status pm2-root > /dev/null 2>&1; then
    echo -e "${CYAN}[INFO]${NC} Configurando PM2 para iniciar com o sistema..."
    pm2 startup systemd -u root --hp /root
    pm2 save
fi

echo ""
echo "============================================================"
echo " BOT MANAGER INICIADO COM SUCESSO!"
echo "============================================================"
echo ""
echo -e "${GREEN}STATUS:${NC}"
pm2 list
echo ""
echo -e "${YELLOW}PRÓXIMOS PASSOS:${NC}"
echo ""
echo "1. VERIFICAR LOGS:"
echo "   pm2 logs bot-manager"
echo ""
echo "2. MONITORAR:"
echo "   pm2 monit"
echo ""
echo "3. CONFIGURAR NGINX PROXY MANAGER:"
echo "   - Acesse: http://$(hostname -I | awk '{print $1}'):81"
echo "   - Crie Proxy Host para seu domínio"
echo "   - Aponte para: 127.0.0.1:5000"
echo "   - Habilite SSL e WebSockets"
echo ""
echo "4. TESTAR:"
echo "   curl http://127.0.0.1:5000"
echo ""
echo "============================================================"
echo ""

