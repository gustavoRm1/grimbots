#!/bin/bash

# Script simples para push com token
# Uso: GITHUB_TOKEN=seu_token bash push_with_token.sh

set -e

CURRENT_BRANCH=$(git branch --show-current)

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Token não fornecido"
    echo ""
    echo "Uso: GITHUB_TOKEN=seu_token bash push_with_token.sh"
    echo ""
    echo "Para criar token: https://github.com/settings/tokens"
    echo "Permissões: repo"
    exit 1
fi

REMOTE_URL=$(git remote get-url origin)

if [[ "$REMOTE_URL" =~ https://github.com/([^/]+)/([^/]+)\.git ]]; then
    USER="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
    
    echo "📤 Fazendo force push para GitHub..."
    echo "📍 Branch: $CURRENT_BRANCH"
    echo ""
    
    git push "https://${GITHUB_TOKEN}@github.com/${USER}/${REPO}.git" "$CURRENT_BRANCH" --force
    
    echo ""
    echo "✅ Push concluído!"
else
    echo "❌ URL do remote não reconhecida"
    exit 1
fi

