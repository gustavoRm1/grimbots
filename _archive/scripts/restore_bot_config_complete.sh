#!/bin/bash

# Script para restaurar bot_config.html completo do commit antes do reset
# Execute no servidor

set -e

cd /root/grimbots 2>/dev/null || pwd

echo "🔄 Restaurando bot_config.html completo"
echo "======================================="
echo ""

# Encontrar backup
BACKUP=$(git branch | grep "backup-before-reset" | sort -r | head -1 | sed 's/^[* ] //')

if [ -z "$BACKUP" ]; then
    echo "❌ Backup não encontrado"
    echo ""
    echo "Buscando no reflog..."
    BACKUP_COMMIT=$(git reflog | grep "reset" | head -1 | awk '{print $1}')
    if [ -z "$BACKUP_COMMIT" ]; then
        echo "❌ Não foi possível encontrar backup"
        exit 1
    fi
    echo "📍 Usando commit do reflog: $BACKUP_COMMIT"
    BACKUP="$BACKUP_COMMIT"
else
    echo "📍 Backup: $BACKUP"
fi

# Restaurar arquivo
echo "🔄 Restaurando..."
git show "$BACKUP:templates/bot_config.html" > templates/bot_config.html

LINES=$(wc -l < templates/bot_config.html)
echo "✅ Restaurado: $LINES linhas"
echo ""

