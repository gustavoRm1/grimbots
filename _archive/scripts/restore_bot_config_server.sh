#!/bin/bash

# Script para restaurar bot_config.html COMPLETO no servidor
# Execute no servidor: bash restore_bot_config_server.sh

set -e

cd /root/grimbots

echo "🔧 Restaurando bot_config.html COMPLETO"
echo "======================================"
echo ""

# Verificar arquivo atual
if [ -f "templates/bot_config.html" ]; then
    CURRENT_LINES=$(wc -l < templates/bot_config.html)
    echo "📍 Arquivo atual: $CURRENT_LINES linhas"
    
    if [ "$CURRENT_LINES" -gt 4000 ]; then
        echo "✅ Arquivo já está completo!"
        echo "   Nenhuma ação necessária"
        exit 0
    fi
    echo ""
fi

# Backup do arquivo atual
if [ -f "templates/bot_config.html" ]; then
    BACKUP_CURRENT="templates/bot_config.html.backup.$(date +%Y%m%d_%H%M%S)"
    cp "templates/bot_config.html" "$BACKUP_CURRENT"
    echo "💾 Backup do atual: $BACKUP_CURRENT"
    echo ""
fi

# Tentar restaurar do backup do Git
RESTORED=false

echo "🔍 Buscando backups..."
echo ""

# Listar todos os backups possíveis
POSSIBLE_SOURCES=(
    "$(git branch | grep 'backup-before-reset' | sort -r | head -1 | sed 's/^[* ] //')"
    "9b48179"
    "$(git reflog | grep 'reset' | head -1 | awk '{print $1}')"
    "$(git reflog | sed -n '2p' | awk '{print $1}')"
    "$(git reflog | sed -n '3p' | awk '{print $1}')"
)

for SOURCE in "${POSSIBLE_SOURCES[@]}"; do
    if [ -n "$SOURCE" ] && [ "$SOURCE" != "ec378a6" ] && [ "$SOURCE" != "HEAD" ]; then
        echo "   Tentando: $SOURCE"
        if git cat-file -e "$SOURCE:templates/bot_config.html" 2>/dev/null; then
            LINES=$(git show "$SOURCE:templates/bot_config.html" | wc -l)
            echo "      ✅ Encontrado: $LINES linhas"
            if [ "$LINES" -gt 4000 ]; then
                echo ""
                echo "✅ Restaurando de: $SOURCE"
                git show "$SOURCE:templates/bot_config.html" > templates/bot_config.html
                RESTORED=true
                break
            else
                echo "      ⚠️  Arquivo muito pequeno ($LINES linhas)"
            fi
        else
            echo "      ❌ Não encontrado"
        fi
    fi
done

if [ "$RESTORED" = true ]; then
    echo ""
    echo "✅ Arquivo restaurado!"
    LINES=$(wc -l < templates/bot_config.html)
    echo "📊 Linhas: $LINES"
    echo ""
    
    # Verificar estrutura básica
    echo "🔍 Verificando estrutura..."
    if grep -q "botConfigApp" templates/bot_config.html; then
        echo "   ✅ botConfigApp encontrado"
    else
        echo "   ⚠️  botConfigApp NÃO encontrado"
    fi
    
    if grep -q "flow_editor.js" templates/bot_config.html; then
        echo "   ✅ flow_editor.js encontrado"
    else
        echo "   ⚠️  flow_editor.js NÃO encontrado"
    fi
    
    if grep -q "order_bump" templates/bot_config.html; then
        echo "   ✅ order_bump encontrado"
    else
        echo "   ⚠️  order_bump NÃO encontrado"
    fi
    
    if grep -q "subscription" templates/bot_config.html; then
        echo "   ✅ subscription encontrado"
    else
        echo "   ⚠️  subscription NÃO encontrado"
    fi
    
    echo ""
    echo "📝 Próximos passos:"
    echo "   1. Testar: https://app.grimbots.online/bots/48/config"
    echo "   2. Se estiver OK, fazer commit:"
    echo "      git add templates/bot_config.html"
    echo "      git commit -m 'fix(bot_config): restore complete functional bot_config.html'"
    echo "      git push origin main"
    echo ""
    exit 0
fi

echo ""
echo "❌ Não foi possível restaurar do Git"
echo ""
echo "📋 Opções:"
echo "   1. O arquivo no servidor pode estar funcionando mesmo com poucas linhas"
echo "   2. Teste primeiro: https://app.grimbots.online/bots/48/config"
echo "   3. Se não funcionar, será necessário recriar manualmente"
echo ""
echo "📊 Status atual:"
echo "   Linhas: $(wc -l < templates/bot_config.html 2>/dev/null || echo '0')"
echo ""

