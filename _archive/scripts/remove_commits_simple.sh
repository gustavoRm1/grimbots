#!/bin/bash

# Script simples para remover commits específicos
# Execute no servidor: bash remove_commits_simple.sh

set -e

echo "🗑️  Removendo Commits Específicos"
echo "=================================="
echo ""

# IDs dos commits a serem removidos
COMMITS=(
    "b61ca1861a4963b1db33dc989b381667e7c7c059"
    "2f0130c7c4209d993934bf65f40a1c7a67a11543"
    "395c98a8670e97605c48bb51cd4c405ecf718874"
    "16e89642d726f9feb766114f85c10bf7439fd088"
    "6114b7f8275da4b68334c10145e64794ca7f5b81"
    "95ef66edfbe391ac078775c65bb9e076306276a5"
    "87b4c375203fb32c2ef493ab3143ede8a59d4278"
)

# Verificar Git
if [ ! -d .git ]; then
    echo "❌ Erro: Não é um repositório Git"
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Branch atual: $CURRENT_BRANCH"
echo ""

# Backup
BACKUP_BRANCH="backup-$(date +%Y%m%d_%H%M%S)"
echo "💾 Criando backup: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH"
echo "✅ Backup criado"
echo ""

# Verificar commits
echo "🔍 Verificando commits..."
FOUND=0
for commit in "${COMMITS[@]}"; do
    if git cat-file -e "$commit^{commit}" 2>/dev/null; then
        FOUND=$((FOUND + 1))
        SHORT=$(git rev-parse --short "$commit")
        MSG=$(git log --format=%s -1 "$commit" 2>/dev/null || echo "N/A")
        echo "  ✅ $SHORT - $MSG"
    else
        echo "  ⚠️  $commit (não encontrado)"
    fi
done
echo ""

if [ $FOUND -eq 0 ]; then
    echo "⚠️  Nenhum commit encontrado. Eles podem já ter sido removidos."
    exit 0
fi

echo "📋 Encontrados: $FOUND commits"
echo ""

# Encontrar o commit mais antigo para determinar o base do rebase
OLDEST_COMMIT=""
for commit in "${COMMITS[@]}"; do
    if git cat-file -e "$commit^{commit}" 2>/dev/null; then
        if [ -z "$OLDEST_COMMIT" ]; then
            OLDEST_COMMIT="$commit"
        else
            # Verificar qual é mais antigo (mais próximo da raiz)
            if git merge-base --is-ancestor "$commit" "$OLDEST_COMMIT" 2>/dev/null; then
                OLDEST_COMMIT="$commit"
            fi
        fi
    fi
done

if [ -z "$OLDEST_COMMIT" ]; then
    echo "❌ Erro: Não foi possível determinar o commit base"
    exit 1
fi

BASE_COMMIT=$(git rev-parse "$OLDEST_COMMIT^" 2>/dev/null || echo "")
if [ -z "$BASE_COMMIT" ]; then
    echo "❌ Erro: Não foi possível encontrar o commit base"
    exit 1
fi

BASE_SHORT=$(git rev-parse --short "$BASE_COMMIT")
echo "📌 Commit base para rebase: $BASE_SHORT"
echo ""

# Confirmação
read -p "⚠️  ATENÇÃO: Esta operação reescreverá o histórico Git. Continuar? (sim/não): " CONFIRM
if [ "$CONFIRM" != "sim" ]; then
    echo "❌ Cancelado"
    exit 0
fi

echo ""
echo "🔄 Iniciando rebase interativo..."
echo ""
echo "📝 INSTRUÇÕES:"
echo "=============="
echo "1. Um editor será aberto com a lista de commits"
echo "2. Para cada commit abaixo, altere 'pick' para 'drop':"
echo ""

for commit in "${COMMITS[@]}"; do
    if git cat-file -e "$commit^{commit}" 2>/dev/null; then
        SHORT=$(git rev-parse --short "$commit")
        MSG=$(git log --format=%s -1 "$commit" 2>/dev/null || echo "N/A")
        echo "   - $SHORT $MSG"
    fi
done

echo ""
echo "3. Salve e feche o editor"
echo "4. Se houver conflitos, resolva e continue: git rebase --continue"
echo "5. Após concluir: git push origin $CURRENT_BRANCH --force"
echo ""
read -p "Pressione ENTER para iniciar o rebase..."

# Iniciar rebase interativo
git rebase -i "$BASE_COMMIT"

echo ""
echo "✅ Rebase concluído!"
echo ""
echo "📤 Para enviar as alterações ao remoto:"
echo "   git push origin $CURRENT_BRANCH --force"
echo ""
echo "⚠️  CUIDADO: Force push reescreve o histórico no remoto!"
echo "   Certifique-se de que ninguém mais está trabalhando neste branch"
echo ""

