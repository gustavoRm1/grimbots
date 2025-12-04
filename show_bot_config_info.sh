#!/bin/bash

# Script para mostrar informações do bot_config.html no servidor
# Execute no servidor: bash show_bot_config_info.sh

cd /root/grimbots

echo "📊 Informações do bot_config.html"
echo "=================================="
echo ""

if [ ! -f "templates/bot_config.html" ]; then
    echo "❌ Arquivo não existe!"
    exit 1
fi

LINES=$(wc -l < templates/bot_config.html)
SIZE=$(du -h templates/bot_config.html | awk '{print $1}')

echo "📏 Tamanho: $LINES linhas ($SIZE)"
echo ""

# Verificar componentes principais
echo "🔍 Componentes encontrados:"
echo ""

COMPONENTS=(
    "botConfigApp:Alpine.js principal"
    "flow_editor.js:Flow Editor JS"
    "order_bump:Order Bumps"
    "subscription:Subscriptions"
    "downsell:Downsells"
    "upsell:Upsells"
    "flow_steps:Flow Steps"
    "welcome_message:Welcome Message"
    "main_buttons:Main Buttons"
    "saveConfig:Função saveConfig"
    "loadConfig:Função loadConfig"
    "addFlowStep:Função addFlowStep"
)

for COMP in "${COMPONENTS[@]}"; do
    KEY=$(echo "$COMP" | cut -d: -f1)
    DESC=$(echo "$COMP" | cut -d: -f2)
    if grep -q "$KEY" templates/bot_config.html; then
        echo "   ✅ $DESC"
    else
        echo "   ❌ $DESC (NÃO encontrado)"
    fi
done

echo ""
echo "📋 Primeiras 10 linhas:"
echo "---"
head -10 templates/bot_config.html
echo "---"
echo ""
echo "📋 Últimas 10 linhas:"
echo "---"
tail -10 templates/bot_config.html
echo "---"
echo ""

# Verificar se está completo
if [ "$LINES" -lt 1000 ]; then
    echo "⚠️  ATENÇÃO: Arquivo parece INCOMPLETO"
    echo "   Arquivo completo deve ter ~5000+ linhas"
    echo ""
    echo "💡 Execute: bash restore_bot_config_server.sh"
elif [ "$LINES" -lt 4000 ]; then
    echo "⚠️  Arquivo pode estar incompleto"
    echo "   Esperado: ~5000+ linhas"
else
    echo "✅ Arquivo parece completo"
fi

echo ""

