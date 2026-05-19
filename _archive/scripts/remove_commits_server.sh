#!/bin/bash

# Script para executar no servidor via SSH
# Execute: ssh root@app.grimbots.online 'bash -s' < remove_commits_server.sh
# OU copie para o servidor e execute lá

set -e

cd /root/grimbots || { echo "❌ Erro: Diretório /root/grimbots não encontrado"; exit 1; }

echo "🗑️  Removendo Commits Específicos"
echo "=================================="
echo ""

# IDs dos commits
COMMITS=(
    "b61ca1861a4963b1db33dc989b381667e7c7c059"
    "2f0130c7c4209d993934bf65f40a1c7a67a11543"
    "395c98a8670e97605c48bb51cd4c405ecf718874"
    "16e89642d726f9feb766114f85c10bf7439fd088"
    "6114b7f8275da4b68334c10145e64794ca7f5b81"
    "95ef66edfbe391ac078775c65bb9e076306276a5"
    "87b4c375203fb32c2ef493ab3143ede8a59d4278"
)

CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Branch: $CURRENT_BRANCH"
echo ""

# Backup
BACKUP_BRANCH="backup-$(date +%Y%m%d_%H%M%S)"
git branch "$BACKUP_BRANCH"
echo "💾 Backup: $BACKUP_BRANCH"
echo ""

# Verificar commits
FOUND=0
OLDEST_COMMIT=""
for commit in "${COMMITS[@]}"; do
    if git cat-file -e "$commit^{commit}" 2>/dev/null; then
        FOUND=$((FOUND + 1))
        SHORT=$(git rev-parse --short "$commit")
        MSG=$(git log --format=%s -1 "$commit" 2>/dev/null || echo "N/A")
        echo "✅ $SHORT - $MSG"
        
        # Encontrar o mais antigo
        if [ -z "$OLDEST_COMMIT" ]; then
            OLDEST_COMMIT="$commit"
        elif git merge-base --is-ancestor "$commit" "$OLDEST_COMMIT" 2>/dev/null; then
            OLDEST_COMMIT="$commit"
        fi
    fi
done

if [ $FOUND -eq 0 ]; then
    echo "⚠️  Nenhum commit encontrado"
    exit 0
fi

BASE_COMMIT=$(git rev-parse "$OLDEST_COMMIT^" 2>/dev/null || echo "")
if [ -z "$BASE_COMMIT" ]; then
    echo "❌ Erro: Não foi possível encontrar o commit base"
    exit 1
fi

BASE_SHORT=$(git rev-parse --short "$BASE_COMMIT")
echo ""
echo "📌 Base para rebase: $BASE_SHORT"
echo ""

# Iniciar rebase
echo "🔄 Iniciando rebase interativo..."
echo "   No editor, altere 'pick' para 'drop' nos commits listados acima"
echo ""
git rebase -i "$BASE_COMMIT"

echo ""
echo "✅ Rebase concluído!"
echo ""
echo "📤 Para enviar: git push origin $CURRENT_BRANCH --force"
echo ""

