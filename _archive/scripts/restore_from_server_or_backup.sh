#!/bin/bash

# Script para restaurar bot_config.html do servidor OU do backup
# Execute no servidor: bash restore_from_server_or_backup.sh

set -e

cd /root/grimbots 2>/dev/null || pwd

echo "🔄 Restaurando bot_config.html"
echo "=============================="
echo ""

# Verificar arquivo atual
if [ -f "templates/bot_config.html" ]; then
    CURRENT_LINES=$(wc -l < templates/bot_config.html)
    echo "📍 Arquivo atual: $CURRENT_LINES linhas"
    
    if [ "$CURRENT_LINES" -gt 4000 ]; then
        echo "✅ Arquivo atual parece completo!"
        echo "   Nenhuma ação necessária"
        exit 0
    fi
    echo ""
fi

# Método 1: Tentar do backup do Git
echo "🔍 Buscando no backup do Git..."
BACKUP=$(git branch | grep "backup-before-reset" | sort -r | head -1 | sed 's/^[* ] //')

if [ -n "$BACKUP" ]; then
    if git show "$BACKUP:templates/bot_config.html" > /dev/null 2>&1; then
        LINES=$(git show "$BACKUP:templates/bot_config.html" | wc -l)
        if [ "$LINES" -gt 4000 ]; then
            echo "✅ Restaurando do backup: $BACKUP ($LINES linhas)"
            git show "$BACKUP:templates/bot_config.html" > templates/bot_config.html
            echo "✅ Restaurado!"
            exit 0
        fi
    fi
fi

# Método 2: Tentar do commit 9b48179
echo ""
echo "🔍 Buscando no commit 9b48179..."
if git cat-file -e "9b48179:templates/bot_config.html" 2>/dev/null; then
    LINES=$(git show "9b48179:templates/bot_config.html" | wc -l)
    if [ "$LINES" -gt 4000 ]; then
        echo "✅ Restaurando do commit 9b48179 ($LINES linhas)"
        git show "9b48179:templates/bot_config.html" > templates/bot_config.html
        echo "✅ Restaurado!"
        exit 0
    fi
fi

# Método 3: Tentar do reflog
echo ""
echo "🔍 Buscando no reflog..."
for i in {1..10}; do
    REFLOG_COMMIT=$(git reflog | sed -n "${i}p" | awk '{print $1}' 2>/dev/null || echo "")
    if [ -n "$REFLOG_COMMIT" ] && [ "$REFLOG_COMMIT" != "ec378a6" ]; then
        if git show "$REFLOG_COMMIT:templates/bot_config.html" > /dev/null 2>&1; then
            LINES=$(git show "$REFLOG_COMMIT:templates/bot_config.html" | wc -l)
            if [ "$LINES" -gt 4000 ]; then
                echo "✅ Restaurando do reflog HEAD@{$i} ($LINES linhas)"
                git show "$REFLOG_COMMIT:templates/bot_config.html" > templates/bot_config.html
                echo "✅ Restaurado!"
                exit 0
            fi
        fi
    fi
done

echo ""
echo "❌ Não foi possível restaurar do Git"
echo ""
echo "📥 Opção: Baixar do servidor atual (se estiver funcionando)"
echo "   Execute localmente: bash download_bot_config_from_server.sh"
echo ""
echo "🔧 Ou recriar o arquivo completo manualmente"
echo ""

