#!/bin/bash

# Script para restaurar bot_config.html do backup do Git
# Execute no servidor: bash restore_bot_config_from_backup.sh

set -e

echo "🔄 Restaurando bot_config.html do backup"
echo "========================================="
echo ""

cd /root/grimbots 2>/dev/null || pwd

if [ ! -d .git ]; then
    echo "❌ Não é um repositório Git"
    exit 1
fi

# Listar backups disponíveis
echo "📋 Backups disponíveis:"
git branch | grep "backup" | head -5
echo ""

# Encontrar o backup mais recente
LATEST_BACKUP=$(git branch | grep "backup-before-reset" | sort -r | head -1 | sed 's/^[* ] //')

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ Nenhum backup encontrado"
    exit 1
fi

echo "📍 Backup encontrado: $LATEST_BACKUP"
echo ""

# Verificar o arquivo no backup
if git show "$LATEST_BACKUP:templates/bot_config.html" > /dev/null 2>&1; then
    LINES=$(git show "$LATEST_BACKUP:templates/bot_config.html" | wc -l)
    echo "✅ Arquivo encontrado no backup: $LINES linhas"
    echo ""
    
    # Fazer backup do arquivo atual
    if [ -f "templates/bot_config.html" ]; then
        BACKUP_FILE="templates/bot_config.html.backup.$(date +%Y%m%d_%H%M%S)"
        cp "templates/bot_config.html" "$BACKUP_FILE"
        echo "💾 Backup do arquivo atual: $BACKUP_FILE"
    fi
    
    # Restaurar do backup
    echo "🔄 Restaurando arquivo..."
    git show "$LATEST_BACKUP:templates/bot_config.html" > "templates/bot_config.html"
    
    echo ""
    echo "✅ Arquivo restaurado!"
    echo "📊 Linhas: $(wc -l < templates/bot_config.html)"
    echo ""
    echo "📝 Próximos passos:"
    echo "   1. Verificar o arquivo: cat templates/bot_config.html | head -50"
    echo "   2. Testar no navegador: https://app.grimbots.online/bots/48/config"
    echo "   3. Se estiver OK, fazer commit:"
    echo "      git add templates/bot_config.html"
    echo "      git commit -m 'fix(bot_config): restore complete bot_config.html from backup'"
    echo "      git push origin main"
    echo ""
else
    echo "❌ Arquivo não encontrado no backup"
    exit 1
fi

