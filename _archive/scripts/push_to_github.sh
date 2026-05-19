#!/bin/bash

# Script para fazer force push para GitHub usando token
# Execute: bash push_to_github.sh

set -e

echo "📤 Force Push para GitHub"
echo "========================"
echo ""

CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Branch: $CURRENT_BRANCH"
echo "📍 Commit: $(git rev-parse --short HEAD)"
echo ""

# Verificar se há remote configurado
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "❌ Remote 'origin' não configurado"
    exit 1
fi

REMOTE_URL=$(git remote get-url origin)
echo "🔗 Remote: $REMOTE_URL"
echo ""

# Verificar se é HTTPS ou SSH
if echo "$REMOTE_URL" | grep -q "^https://"; then
    echo "📝 Usando HTTPS - Será necessário token"
    echo ""
    echo "⚠️  GitHub não aceita mais senha!"
    echo "   Você precisa usar um Personal Access Token (PAT)"
    echo ""
    echo "📋 Opções:"
    echo "   1. Usar token via URL (temporário)"
    echo "   2. Configurar token no Git Credential Helper"
    echo "   3. Usar SSH (se tiver chave configurada)"
    echo ""
    read -p "Escolha (1/2/3): " OPTION
    
    case "$OPTION" in
        1)
            echo ""
            echo "🔑 Para criar um token:"
            echo "   https://github.com/settings/tokens"
            echo "   Permissões necessárias: repo"
            echo ""
            read -p "Cole o token aqui: " GITHUB_TOKEN
            if [ -z "$GITHUB_TOKEN" ]; then
                echo "❌ Token vazio"
                exit 1
            fi
            
            # Extrair usuário e repo da URL
            if [[ "$REMOTE_URL" =~ https://github.com/([^/]+)/([^/]+)\.git ]]; then
                USER="${BASH_REMATCH[1]}"
                REPO="${BASH_REMATCH[2]}"
                TOKEN_URL="https://${GITHUB_TOKEN}@github.com/${USER}/${REPO}.git"
                
                echo ""
                echo "🔄 Fazendo push..."
                git push "$TOKEN_URL" "$CURRENT_BRANCH" --force
            else
                echo "❌ Não foi possível extrair usuário/repo da URL"
                exit 1
            fi
            ;;
        2)
            echo ""
            echo "🔑 Para criar um token:"
            echo "   https://github.com/settings/tokens"
            echo "   Permissões necessárias: repo"
            echo ""
            read -p "Cole o token aqui: " GITHUB_TOKEN
            if [ -z "$GITHUB_TOKEN" ]; then
                echo "❌ Token vazio"
                exit 1
            fi
            
            # Configurar credential helper
            git config --global credential.helper store
            echo "https://$(git config user.name):${GITHUB_TOKEN}@github.com" > ~/.git-credentials
            chmod 600 ~/.git-credentials
            
            echo ""
            echo "🔄 Fazendo push..."
            git push origin "$CURRENT_BRANCH" --force
            ;;
        3)
            echo ""
            echo "🔄 Convertendo para SSH..."
            if [[ "$REMOTE_URL" =~ https://github.com/([^/]+)/([^/]+)\.git ]]; then
                USER="${BASH_REMATCH[1]}"
                REPO="${BASH_REMATCH[2]}"
                SSH_URL="git@github.com:${USER}/${REPO}.git"
                
                echo "   Nova URL: $SSH_URL"
                read -p "Alterar remote para SSH? (sim/não): " CHANGE_REMOTE
                if [ "$CHANGE_REMOTE" = "sim" ] || [ "$CHANGE_REMOTE" = "SIM" ]; then
                    git remote set-url origin "$SSH_URL"
                    echo "✅ Remote alterado para SSH"
                fi
                
                echo ""
                echo "🔄 Fazendo push via SSH..."
                git push origin "$CURRENT_BRANCH" --force
            else
                echo "❌ Não foi possível converter URL"
                exit 1
            fi
            ;;
        *)
            echo "❌ Opção inválida"
            exit 1
            ;;
    esac
else
    # Já é SSH
    echo "✅ Usando SSH"
    echo ""
    echo "🔄 Fazendo push..."
    git push origin "$CURRENT_BRANCH" --force
fi

echo ""
echo "✅ Push concluído!"
echo ""
echo "🌐 Verifique no GitHub:"
echo "   https://github.com/$(git config user.name)/$(basename -s .git $(git remote get-url origin))"
echo ""

