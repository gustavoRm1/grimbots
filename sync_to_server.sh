#!/bin/bash

# Script para enviar bot_config.html do local para o servidor
# Execute: bash sync_to_server.sh

set -e

echo "📤 Enviando bot_config.html para o servidor..."

# Configurações
SERVER_USER="root"
SERVER_HOST="app.grimbots.online"
LOCAL_PATH="templates/bot_config.html"
SERVER_PATH="/root/grimbots/templates/bot_config.html"

# Verificar se arquivo local existe
if [ ! -f "$LOCAL_PATH" ]; then
    echo "❌ Arquivo local não encontrado: $LOCAL_PATH"
    exit 1
fi

# Fazer backup no servidor antes de enviar
echo "💾 Fazendo backup no servidor..."
ssh "$SERVER_USER@$SERVER_HOST" "cp $SERVER_PATH ${SERVER_PATH}.backup.\$(date +%Y%m%d_%H%M%S) 2>/dev/null || true"

# Enviar para o servidor
echo "⬆️  Enviando para $SERVER_USER@$SERVER_HOST..."
scp "$LOCAL_PATH" "$SERVER_USER@$SERVER_HOST:$SERVER_PATH"

if [ $? -eq 0 ]; then
    echo "✅ Arquivo enviado com sucesso!"
    echo ""
    echo "🔄 Próximo passo: Reiniciar Flask no servidor"
    echo ""
    echo "Execute no servidor:"
    echo "  sudo systemctl restart grimbots"
    echo "  # ou"
    echo "  sudo supervisorctl restart grimbots"
else
    echo "❌ Erro ao enviar"
    exit 1
fi

