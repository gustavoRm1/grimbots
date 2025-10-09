#!/bin/bash

##############################################################################
# SCRIPT DE SETUP AUTOMATIZADO - BOT MANAGER SAAS
# Deploy com PM2 + Nginx Proxy Manager + PostgreSQL
##############################################################################

set -e  # Sair se houver erro

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo "============================================================"
echo " BOT MANAGER SAAS - SETUP AUTOMÁTICO"
echo "============================================================"
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
   echo -e "${RED}[ERRO]${NC} Este script precisa ser executado como root"
   echo "Execute: sudo bash setup-production.sh"
   exit 1
fi

echo -e "${GREEN}[OK]${NC} Executando como root"
echo ""

##############################################################################
# PASSO 1: ATUALIZAR SISTEMA
##############################################################################

echo -e "${CYAN}[1/10]${NC} Atualizando sistema..."
apt update && apt upgrade -y
echo -e "${GREEN}[OK]${NC} Sistema atualizado"
echo ""

##############################################################################
# PASSO 2: INSTALAR DEPENDÊNCIAS BÁSICAS
##############################################################################

echo -e "${CYAN}[2/10]${NC} Instalando dependências básicas..."
apt install -y \
  curl \
  wget \
  git \
  nano \
  htop \
  build-essential \
  software-properties-common \
  ca-certificates \
  gnupg \
  lsb-release \
  ufw

echo -e "${GREEN}[OK]${NC} Dependências instaladas"
echo ""

##############################################################################
# PASSO 3: INSTALAR PYTHON 3.11
##############################################################################

echo -e "${CYAN}[3/10]${NC} Instalando Python 3.11..."

# Adicionar repositório deadsnakes
add-apt-repository ppa:deadsnakes/ppa -y
apt update

# Instalar Python 3.11
apt install -y \
  python3.11 \
  python3.11-venv \
  python3.11-dev \
  python3-pip

# Verificar
PYTHON_VERSION=$(python3.11 --version)
echo -e "${GREEN}[OK]${NC} Python instalado: $PYTHON_VERSION"
echo ""

##############################################################################
# PASSO 4: INSTALAR NODE.JS E NPM
##############################################################################

echo -e "${CYAN}[4/10]${NC} Instalando Node.js 20 LTS..."

# Adicionar repositório NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -

# Instalar Node.js
apt install -y nodejs

# Verificar
NODE_VERSION=$(node --version)
NPM_VERSION=$(npm --version)
echo -e "${GREEN}[OK]${NC} Node.js: $NODE_VERSION | NPM: $NPM_VERSION"
echo ""

##############################################################################
# PASSO 5: INSTALAR DOCKER
##############################################################################

echo -e "${CYAN}[5/10]${NC} Instalando Docker..."

# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Instalar Docker Compose
apt install -y docker-compose

# Verificar
DOCKER_VERSION=$(docker --version)
COMPOSE_VERSION=$(docker-compose --version)
echo -e "${GREEN}[OK]${NC} Docker: $DOCKER_VERSION"
echo -e "${GREEN}[OK]${NC} Compose: $COMPOSE_VERSION"
echo ""

##############################################################################
# PASSO 6: INSTALAR PM2
##############################################################################

echo -e "${CYAN}[6/10]${NC} Instalando PM2..."

# Instalar PM2 globalmente
npm install -g pm2

# Verificar
PM2_VERSION=$(pm2 --version)
echo -e "${GREEN}[OK]${NC} PM2 instalado: v$PM2_VERSION"
echo ""

##############################################################################
# PASSO 7: CONFIGURAR POSTGRESQL (DOCKER)
##############################################################################

echo -e "${CYAN}[7/10]${NC} Configurando PostgreSQL..."

# Solicitar senha do banco
echo -e "${YELLOW}Digite a senha do PostgreSQL (mínimo 16 caracteres):${NC}"
read -s DB_PASSWORD
echo ""

if [ ${#DB_PASSWORD} -lt 16 ]; then
    echo -e "${RED}[ERRO]${NC} Senha muito curta! Mínimo 16 caracteres."
    exit 1
fi

# Criar diretório
mkdir -p /opt/postgresql

# Criar docker-compose.yml
cat > /opt/postgresql/docker-compose.yml <<EOF
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: postgres-botmanager
    restart: always
    environment:
      POSTGRES_DB: botmanager_db
      POSTGRES_USER: botmanager
      POSTGRES_PASSWORD: $DB_PASSWORD
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge

volumes:
  postgres_data:
EOF

# Iniciar PostgreSQL
cd /opt/postgresql
docker-compose up -d

# Aguardar inicialização
sleep 5

# Testar
docker exec postgres-botmanager psql -U botmanager -d botmanager_db -c "SELECT version();" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}[OK]${NC} PostgreSQL rodando"
else
    echo -e "${RED}[ERRO]${NC} PostgreSQL falhou ao iniciar"
    exit 1
fi
echo ""

##############################################################################
# PASSO 8: INSTALAR NGINX PROXY MANAGER
##############################################################################

echo -e "${CYAN}[8/10]${NC} Instalando Nginx Proxy Manager..."

# Criar diretório
mkdir -p /opt/nginx-proxy-manager
cd /opt/nginx-proxy-manager

# Criar docker-compose.yml
cat > docker-compose.yml <<'EOF'
version: '3.8'

services:
  app:
    image: 'jc21/nginx-proxy-manager:latest'
    container_name: nginx-proxy-manager
    restart: unless-stopped
    ports:
      - '80:80'
      - '443:443'
      - '81:81'
    environment:
      DB_SQLITE_FILE: "/data/database.sqlite"
      DISABLE_IPV6: 'true'
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
    networks:
      - npm-network

networks:
  npm-network:
    driver: bridge
EOF

# Iniciar NPM
docker-compose up -d

# Aguardar inicialização
sleep 10

echo -e "${GREEN}[OK]${NC} Nginx Proxy Manager rodando"
echo -e "${YELLOW}[INFO]${NC} Acesse: http://$(hostname -I | awk '{print $1}'):81"
echo -e "${YELLOW}[INFO]${NC} Login padrão: admin@example.com / changeme"
echo ""

##############################################################################
# PASSO 9: CONFIGURAR FIREWALL
##############################################################################

echo -e "${CYAN}[9/10]${NC} Configurando firewall..."

# Configurar UFW
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 81/tcp    # NPM Admin (TEMPORÁRIO)
ufw --force enable

echo -e "${GREEN}[OK]${NC} Firewall configurado"
echo -e "${YELLOW}[AVISO]${NC} Lembre-se de bloquear porta 81 após configurar NPM:"
echo "  ufw delete allow 81/tcp && ufw reload"
echo ""

##############################################################################
# PASSO 10: RESUMO E PRÓXIMOS PASSOS
##############################################################################

echo -e "${CYAN}[10/10]${NC} Setup básico concluído!"
echo ""
echo "============================================================"
echo " SETUP AUTOMÁTICO CONCLUÍDO!"
echo "============================================================"
echo ""
echo -e "${GREEN}INSTALADO:${NC}"
echo "  ✅ Python 3.11"
echo "  ✅ Node.js 20 + NPM"
echo "  ✅ Docker + Docker Compose"
echo "  ✅ PM2"
echo "  ✅ PostgreSQL (Docker)"
echo "  ✅ Nginx Proxy Manager (Docker)"
echo "  ✅ Firewall (UFW)"
echo ""
echo -e "${YELLOW}PRÓXIMOS PASSOS:${NC}"
echo ""
echo "1. CLONAR PROJETO:"
echo "   cd /var/www"
echo "   git clone https://github.com/gustavoRm1/grimbots.git bot-manager"
echo "   cd bot-manager"
echo ""
echo "2. CONFIGURAR AMBIENTE:"
echo "   python3.11 -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "3. CONFIGURAR .env:"
echo "   cp env.example .env"
echo "   nano .env"
echo "   (Preencher todas as variáveis)"
echo ""
echo "   DATABASE_URL=postgresql://botmanager:$DB_PASSWORD@127.0.0.1:5432/botmanager_db"
echo ""
echo "4. INICIALIZAR BANCO:"
echo "   python init_db.py"
echo ""
echo "5. AJUSTAR ecosystem.config.js:"
echo "   nano ecosystem.config.js"
echo "   (Verificar caminho do interpreter)"
echo ""
echo "6. INICIAR COM PM2:"
echo "   pm2 start ecosystem.config.js"
echo "   pm2 save"
echo ""
echo "7. CONFIGURAR NGINX PROXY MANAGER:"
echo "   - Acesse: http://$(hostname -I | awk '{print $1}'):81"
echo "   - Login: admin@example.com / changeme"
echo "   - TROQUE A SENHA!"
echo "   - Crie Proxy Host com SSL"
echo ""
echo "8. CONFIGURAR WEBHOOK SYNCPAY:"
echo "   - URL: https://seu-dominio.com.br/webhook/payment/syncpay"
echo ""
echo "============================================================"
echo -e "${GREEN}SERVIDOR PRONTO PARA RECEBER O PROJETO!${NC}"
echo "============================================================"
echo ""
echo "Documentação completa: docs/DEPLOY_PM2_NPM.md"
echo ""

