#!/bin/bash
# Script para restaurar bot_config.html do commit específico

cd /root/grimbots

# Encontrar o commit com a mensagem específica
COMMIT_HASH=$(git log --all --oneline --grep="add safe strip utility" | head -1 | awk '{print $1}')

if [ -z "$COMMIT_HASH" ]; then
    echo "❌ Commit não encontrado. Tentando busca alternativa..."
    # Tentar busca mais ampla
    COMMIT_HASH=$(git log --all --oneline --grep="safe strip" | head -1 | awk '{print $1}')
fi

if [ -z "$COMMIT_HASH" ]; then
    echo "❌ Commit ainda não encontrado. Listando últimos commits relacionados a bot_config.html:"
    git log --all --oneline -- templates/bot_config.html | head -10
    echo ""
    echo "Por favor, copie o hash do commit desejado e execute:"
    echo "git checkout <HASH> -- templates/bot_config.html"
    exit 1
fi

echo "✅ Commit encontrado: $COMMIT_HASH"
echo "📋 Mensagem do commit:"
git log --format="%B" -n 1 $COMMIT_HASH
echo ""
echo "🔄 Restaurando templates/bot_config.html..."
git checkout $COMMIT_HASH -- templates/bot_config.html

if [ $? -eq 0 ]; then
    echo "✅ Arquivo restaurado com sucesso!"
    echo "📊 Verificando arquivo:"
    ls -lh templates/bot_config.html
    echo ""
    echo "⚠️  IMPORTANTE: Faça commit das mudanças se necessário:"
    echo "   git add templates/bot_config.html"
    echo "   git commit -m 'Restore bot_config.html from commit $COMMIT_HASH'"
else
    echo "❌ Erro ao restaurar arquivo"
    exit 1
fi

