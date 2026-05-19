#!/bin/bash

# Script para restaurar bot_config.html COMPLETO e funcional
# Execute no servidor: bash restore_bot_config_full.sh

set -e

cd /root/grimbots 2>/dev/null || pwd

echo "🔄 Restaurando bot_config.html COMPLETO"
echo "======================================="
echo ""

# Método 1: Tentar restaurar do backup
BACKUP=$(git branch | grep "backup-before-reset" | sort -r | head -1 | sed 's/^[* ] //')

if [ -n "$BACKUP" ]; then
    echo "📍 Tentando restaurar do backup: $BACKUP"
    
    if git show "$BACKUP:templates/bot_config.html" > /dev/null 2>&1; then
        LINES=$(git show "$BACKUP:templates/bot_config.html" | wc -l)
        echo "✅ Arquivo encontrado: $LINES linhas"
        
        if [ "$LINES" -gt 4000 ]; then
            echo "✅ Arquivo parece completo (>4000 linhas)"
            git show "$BACKUP:templates/bot_config.html" > templates/bot_config.html
            echo "✅ Restaurado do backup!"
            exit 0
        else
            echo "⚠️  Arquivo parece incompleto ($LINES linhas)"
        fi
    fi
fi

# Método 2: Tentar do reflog
echo ""
echo "📍 Tentando do reflog..."
REFLOG_COMMIT=$(git reflog | grep "HEAD@{1}" | awk '{print $1}' 2>/dev/null || echo "")

if [ -n "$REFLOG_COMMIT" ]; then
    if git show "$REFLOG_COMMIT:templates/bot_config.html" > /dev/null 2>&1; then
        LINES=$(git show "$REFLOG_COMMIT:templates/bot_config.html" | wc -l)
        if [ "$LINES" -gt 4000 ]; then
            echo "✅ Restaurando do reflog: $LINES linhas"
            git show "$REFLOG_COMMIT:templates/bot_config.html" > templates/bot_config.html
            echo "✅ Restaurado!"
            exit 0
        fi
    fi
fi

# Método 3: Tentar do commit 9b48179 (antes do reset)
echo ""
echo "📍 Tentando do commit anterior (9b48179)..."
if git cat-file -e "9b48179:templates/bot_config.html" 2>/dev/null; then
    LINES=$(git show "9b48179:templates/bot_config.html" | wc -l)
    if [ "$LINES" -gt 4000 ]; then
        echo "✅ Restaurando do commit 9b48179: $LINES linhas"
        git show "9b48179:templates/bot_config.html" > templates/bot_config.html
        echo "✅ Restaurado!"
        exit 0
    fi
fi

echo ""
echo "❌ Não foi possível restaurar do Git"
echo "   O arquivo será recriado baseado no template completo"
echo ""

