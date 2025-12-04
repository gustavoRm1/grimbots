#!/bin/bash

# Script para baixar bot_config.html do servidor para local
# Execute: bash sync_from_server.sh

set -e

echo "📥 Baixando bot_config.html do servidor..."

# Configurações
SERVER_USER="root"
SERVER_HOST="app.grimbots.online"
SERVER_PATH="/root/grimbots/templates/bot_config.html"
LOCAL_PATH="templates/bot_config.html"

# Criar diretório se não existir
mkdir -p templates

# Fazer backup do arquivo local se existir
if [ -f "$LOCAL_PATH" ]; then
    BACKUP_FILE="${LOCAL_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "💾 Backup local: $BACKUP_FILE"
    cp "$LOCAL_PATH" "$BACKUP_FILE"
fi

# Baixar do servidor
echo "⬇️  Baixando de $SERVER_USER@$SERVER_HOST..."
scp "$SERVER_USER@$SERVER_HOST:$SERVER_PATH" "$LOCAL_PATH"

if [ $? -eq 0 ]; then
    echo "✅ Arquivo baixado com sucesso!"
    echo ""
    echo "📊 Tamanho: $(wc -l < $LOCAL_PATH) linhas"
    echo ""
    echo "✅ Pronto para editar no Cursor!"
else
    echo "❌ Erro ao baixar"
    exit 1
fi

