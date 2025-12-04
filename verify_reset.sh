#!/bin/bash

# Script para VERIFICAR o que vai acontecer ANTES de resetar
# Execute este primeiro para ver o que será removido

TARGET_COMMIT="ec378a6f8c9a43ffb45f7e4f9ef4f5dc82f62da7"

echo "🔍 VERIFICAÇÃO: O que vai acontecer?"
echo "===================================="
echo ""

cd /root/grimbots 2>/dev/null || pwd

if [ ! -d .git ]; then
    echo "❌ Não é um repositório Git"
    exit 1
fi

# Verificar commit alvo
if ! git cat-file -e "$TARGET_COMMIT^{commit}" 2>/dev/null; then
    echo "❌ Commit alvo NÃO encontrado: $TARGET_COMMIT"
    echo ""
    echo "Buscando commits similares..."
    git log --oneline --all | grep "ec378a6" | head -5
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
CURRENT_COMMIT=$(git rev-parse HEAD)
TARGET_SHORT=$(git rev-parse --short "$TARGET_COMMIT")

echo "📍 Branch atual: $CURRENT_BRANCH"
echo "📍 Commit atual: $(git rev-parse --short HEAD)"
echo "📍 Commit alvo:  $TARGET_SHORT"
echo ""

# Verificar se o alvo está antes do atual
if ! git merge-base --is-ancestor "$TARGET_COMMIT" "$CURRENT_COMMIT" 2>/dev/null; then
    echo "⚠️  ATENÇÃO: O commit alvo NÃO está no histórico antes do commit atual!"
    echo "   Isso significa que você está tentando voltar para um commit que não existe neste branch"
    echo "   ou que está mais à frente no histórico."
    exit 1
fi

# Contar commits que serão removidos
COMMITS_TO_REMOVE=$(git rev-list --count "$TARGET_COMMIT..HEAD" 2>/dev/null || echo "0")

echo "📊 RESUMO:"
echo "=========="
echo "✅ Commit alvo existe: $TARGET_SHORT"
echo "📉 Commits que serão REMOVIDOS: $COMMITS_TO_REMOVE"
echo ""

if [ "$COMMITS_TO_REMOVE" -eq 0 ]; then
    echo "✅ Você já está no commit alvo! Nada a fazer."
    exit 0
fi

# Listar commits que serão removidos
echo "📋 Commits que serão REMOVIDOS (últimos 30):"
echo "--------------------------------------------"
git log --oneline "$TARGET_COMMIT..HEAD" | head -30
if [ "$COMMITS_TO_REMOVE" -gt 30 ]; then
    echo "   ... e mais $((COMMITS_TO_REMOVE - 30)) commits"
fi
echo ""

# Verificar os 7 commits específicos
echo "🔍 Verificando os 7 commits específicos:"
echo "----------------------------------------"
SPECIFIC_COMMITS=(
    "b61ca1861a4963b1db33dc989b381667e7c7c059"
    "2f0130c7c4209d993934bf65f40a1c7a67a11543"
    "395c98a8670e97605c48bb51cd4c405ecf718874"
    "16e89642d726f9feb766114f85c10bf7439fd088"
    "6114b7f8275da4b68334c10145e64794ca7f5b81"
    "95ef66edfbe391ac078775c65bb9e076306276a5"
    "87b4c375203fb32c2ef493ab3143ede8a59d4278"
)

FOUND=0
NOT_FOUND=0
for commit in "${SPECIFIC_COMMITS[@]}"; do
    if git cat-file -e "$commit^{commit}" 2>/dev/null; then
        # Verificar se está na faixa a ser removida
        if git merge-base --is-ancestor "$TARGET_COMMIT" "$commit" 2>/dev/null && \
           git merge-base --is-ancestor "$commit" "$CURRENT_COMMIT" 2>/dev/null; then
            FOUND=$((FOUND + 1))
            SHORT=$(git rev-parse --short "$commit")
            MSG=$(git log --format=%s -1 "$commit" 2>/dev/null || echo "N/A")
            echo "  ✅ $SHORT - $MSG (SERÁ REMOVIDO)"
        else
            NOT_FOUND=$((NOT_FOUND + 1))
            SHORT=$(git rev-parse --short "$commit")
            echo "  ⚠️  $SHORT (não está na faixa a ser removida)"
        fi
    else
        NOT_FOUND=$((NOT_FOUND + 1))
        echo "  ❌ $commit (não encontrado no histórico)"
    fi
done
echo ""

echo "📊 ESTATÍSTICAS:"
echo "================"
echo "✅ Commits específicos que SERÃO removidos: $FOUND"
echo "⚠️  Commits específicos que NÃO serão removidos: $NOT_FOUND"
echo "📉 Total de commits a remover: $COMMITS_TO_REMOVE"
echo ""

# Mostrar o commit alvo
echo "🎯 COMMIT ALVO (onde você vai ficar):"
echo "====================================="
git log --oneline -1 "$TARGET_COMMIT"
echo ""

# Mostrar o que vem depois do alvo (será removido)
echo "🗑️  PRIMEIRO COMMIT QUE SERÁ REMOVIDO:"
echo "======================================"
NEXT_AFTER_TARGET=$(git rev-parse "$TARGET_COMMIT^0" 2>/dev/null || echo "")
if [ -n "$NEXT_AFTER_TARGET" ]; then
    git log --oneline -1 "$(git rev-list -1 "$TARGET_COMMIT..HEAD" 2>/dev/null | head -1)" 2>/dev/null || echo "N/A"
else
    echo "N/A"
fi
echo ""

echo "✅ VERIFICAÇÃO CONCLUÍDA"
echo ""
echo "📝 O QUE VAI ACONTECER:"
echo "======================="
echo "1. ✅ Backup será criado automaticamente"
echo "2. ✅ Reset para: $TARGET_SHORT"
echo "3. ✅ $COMMITS_TO_REMOVE commits serão REMOVIDOS do histórico local"
echo "4. ⚠️  Você precisará fazer FORCE PUSH para atualizar o GitHub"
echo ""
echo "🚀 Para executar o reset:"
echo "   bash reset_to_commit.sh"
echo ""

