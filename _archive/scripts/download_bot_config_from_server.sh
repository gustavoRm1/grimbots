#!/bin/bash

# Script para baixar bot_config.html do servidor
# Execute localmente: bash download_bot_config_from_server.sh

set -e

echo "📥 Baixando bot_config.html do servidor"
echo "========================================"
echo ""

SERVER_USER="root"
SERVER_HOST="app.grimbots.online"
SERVER_PATH="/root/grimbots/templates/bot_config.html"
LOCAL_PATH="templates/bot_config.html"

# Criar diretório se não existir
mkdir -p templates

# Backup do arquivo local se existir
if [ -f "$LOCAL_PATH" ]; then
    BACKUP_FILE="${LOCAL_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$LOCAL_PATH" "$BACKUP_FILE"
    echo "💾 Backup local: $BACKUP_FILE"
fi

# Baixar do servidor
echo "⬇️  Baixando de $SERVER_USER@$SERVER_HOST..."
scp "$SERVER_USER@$SERVER_HOST:$SERVER_PATH" "$LOCAL_PATH"

if [ $? -eq 0 ]; then
    LINES=$(wc -l < "$LOCAL_PATH" 2>/dev/null || echo "0")
    echo "✅ Arquivo baixado com sucesso!"
    echo "📊 Linhas: $LINES"
    echo ""
    
    if [ "$LINES" -lt 1000 ]; then
        echo "⚠️  ATENÇÃO: Arquivo parece incompleto ($LINES linhas)"
        echo "   O arquivo completo deve ter ~5000+ linhas"
    else
        echo "✅ Arquivo parece completo"
    fi
else
    echo "❌ Erro ao baixar"
    exit 1
fi

