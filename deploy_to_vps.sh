#!/bin/bash
# Script de Deploy Automatizado para VPS
# Uso: ./deploy_to_vps.sh usuario@ip_vps

set -e

VPS_USER=$1
PROJECT_DIR="grimbots-app"

if [ -z "$VPS_USER" ]; then
    echo "❌ Erro: Informe o usuário e IP da VPS"
    echo "Uso: ./deploy_to_vps.sh usuario@ip_vps"
    echo "Exemplo: ./deploy_to_vps.sh grimbots@123.45.67.89"
    exit 1
fi

echo "🚀 Iniciando deploy para $VPS_USER..."

# Criar arquivo tar excluindo arquivos desnecessários
echo "📦 Empacotando projeto..."
tar -czf grimbots-deploy.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='instance/*.db' \
    --exclude='.env' \
    --exclude='*.log' \
    --exclude='node_modules' \
    .

# Upload para VPS
echo "📤 Enviando para VPS..."
scp grimbots-deploy.tar.gz $VPS_USER:/tmp/

# Executar comandos remotos
echo "🔧 Configurando na VPS..."
ssh $VPS_USER << 'ENDSSH'
    set -e
    
    # Criar diretório se não existir
    mkdir -p ~/grimbots-app
    
    # Extrair arquivos
    cd ~/grimbots-app
    tar -xzf /tmp/grimbots-deploy.tar.gz
    rm /tmp/grimbots-deploy.tar.gz
    
    # Criar/ativar venv
    if [ ! -d "venv" ]; then
        echo "📦 Criando ambiente virtual..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # Instalar dependências
    echo "📦 Instalando dependências..."
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install gunicorn
    
    # Criar .env se não existir
    if [ ! -f ".env" ]; then
        echo "⚙️ Criando arquivo .env..."
        cp env.example .env
        echo "⚠️  ATENÇÃO: Configure o .env com suas credenciais!"
    fi
    
    # Criar diretório instance se não existir
    mkdir -p instance
    
    # Inicializar banco se não existir
    if [ ! -f "instance/saas_bot_manager.db" ]; then
        echo "🗄️ Inicializando banco de dados..."
        python3 init_db.py
    fi
    
    # Reiniciar serviço (se existir)
    if sudo systemctl is-active --quiet grimbots; then
        echo "🔄 Reiniciando aplicação..."
        sudo systemctl restart grimbots
        echo "✅ Deploy concluído! Aplicação reiniciada."
    else
        echo "⚠️  Serviço systemd não configurado ainda."
        echo "📋 Configure seguindo o guia DEPLOY_VPS.md"
    fi
ENDSSH

# Limpar arquivo local
rm grimbots-deploy.tar.gz

echo "✨ Deploy finalizado com sucesso!"
echo "📝 Próximos passos:"
echo "   1. SSH na VPS: ssh $VPS_USER"
echo "   2. Configurar .env: nano ~/grimbots-app/.env"
echo "   3. Seguir guia completo: cat ~/grimbots-app/DEPLOY_VPS.md"

