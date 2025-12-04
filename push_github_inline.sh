#!/bin/bash
# Script para copiar e executar no servidor
# Cole este conteúdo no servidor e execute

set -e

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Token não fornecido"
    echo ""
    echo "Uso: GITHUB_TOKEN=seu_token bash push_github_inline.sh"
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
REMOTE_URL=$(git remote get-url origin)

if [[ "$REMOTE_URL" =~ https://github.com/([^/]+)/([^/]+)\.git ]]; then
    USER="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
    
    echo "📤 Fazendo force push para GitHub..."
    echo "📍 Branch: $CURRENT_BRANCH"
    echo "📍 Commit: $(git rev-parse --short HEAD)"
    echo ""
    
    git push "https://${GITHUB_TOKEN}@github.com/${USER}/${REPO}.git" "$CURRENT_BRANCH" --force
    
    echo ""
    echo "✅ Push concluído!"
    echo ""
    echo "🌐 Verifique: https://github.com/${USER}/${REPO}"
else
    echo "❌ URL do remote não reconhecida: $REMOTE_URL"
    exit 1
fi

