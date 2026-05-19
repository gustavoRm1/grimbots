#!/bin/bash

# Script para restaurar/recriar bot_config.html COMPLETO
# Execute no servidor: bash fix_bot_config_complete.sh

set -e

cd /root/grimbots 2>/dev/null || pwd

echo "🔧 Restaurando/Recriando bot_config.html COMPLETO"
echo "=================================================="
echo ""

# Backup do arquivo atual
if [ -f "templates/bot_config.html" ]; then
    BACKUP_CURRENT="templates/bot_config.html.backup.$(date +%Y%m%d_%H%M%S)"
    cp "templates/bot_config.html" "$BACKUP_CURRENT"
    echo "💾 Backup do atual: $BACKUP_CURRENT"
fi

# Tentar restaurar do backup do Git
RESTORED=false

# Listar todos os backups possíveis
echo "🔍 Buscando backups..."
POSSIBLE_SOURCES=(
    "$(git branch | grep 'backup-before-reset' | sort -r | head -1 | sed 's/^[* ] //')"
    "9b48179"
    "$(git reflog | grep 'reset' | head -1 | awk '{print $1}')"
)

for SOURCE in "${POSSIBLE_SOURCES[@]}"; do
    if [ -n "$SOURCE" ] && [ "$SOURCE" != "ec378a6" ]; then
        if git cat-file -e "$SOURCE:templates/bot_config.html" 2>/dev/null; then
            LINES=$(git show "$SOURCE:templates/bot_config.html" | wc -l)
            if [ "$LINES" -gt 4000 ]; then
                echo "✅ Encontrado em: $SOURCE ($LINES linhas)"
                git show "$SOURCE:templates/bot_config.html" > templates/bot_config.html
                RESTORED=true
                break
            fi
        fi
    fi
done

if [ "$RESTORED" = true ]; then
    echo ""
    echo "✅ Arquivo restaurado do Git!"
    LINES=$(wc -l < templates/bot_config.html)
    echo "📊 Linhas: $LINES"
    echo ""
    echo "📝 Próximos passos:"
    echo "   1. Testar: https://app.grimbots.online/bots/48/config"
    echo "   2. Se estiver OK, fazer commit:"
    echo "      git add templates/bot_config.html"
    echo "      git commit -m 'fix(bot_config): restore complete functional bot_config.html'"
    echo "      git push origin main"
    exit 0
fi

echo ""
echo "⚠️  Não foi possível restaurar do Git"
echo ""
echo "📥 SOLUÇÃO: Baixar do servidor atual"
echo "===================================="
echo ""
echo "O arquivo no servidor (https://app.grimbots.online) deve estar funcionando."
echo "Execute no seu computador local:"
echo ""
echo "   bash download_bot_config_from_server.sh"
echo ""
echo "Isso vai baixar o arquivo completo do servidor para o local."
echo "Depois você pode fazer commit e push."
echo ""

