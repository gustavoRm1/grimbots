#!/bin/bash

# Script para resetar para commit específico e remover commits posteriores
# Objetivo: Voltar para ec378a6f8c9a43ffb45f7e4f9ef4f5dc82f62da7 e remover tudo depois

set -e

TARGET_COMMIT="ec378a6f8c9a43ffb45f7e4f9ef4f5dc82f62da7"

echo "🎯 Resetar para Commit Específico"
echo "=================================="
echo ""
echo "📍 Commit alvo: $TARGET_COMMIT"
echo ""

# Verificar se estamos em um repositório Git
if [ ! -d .git ]; then
    echo "❌ Erro: Não é um repositório Git"
    exit 1
fi

# Verificar se o commit alvo existe
if ! git cat-file -e "$TARGET_COMMIT^{commit}" 2>/dev/null; then
    echo "❌ Erro: Commit alvo não encontrado: $TARGET_COMMIT"
    echo ""
    echo "Verificando commits similares..."
    git log --oneline --all | grep -i "ec378a6" | head -5
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
CURRENT_COMMIT=$(git rev-parse HEAD)

echo "📍 Branch atual: $CURRENT_BRANCH"
echo "📍 Commit atual: $(git rev-parse --short HEAD)"
echo "📍 Commit alvo:  $(git rev-parse --short $TARGET_COMMIT)"
echo ""

# Verificar se já estamos no commit alvo
if [ "$CURRENT_COMMIT" = "$TARGET_COMMIT" ]; then
    echo "✅ Já estamos no commit alvo!"
    exit 0
fi

# Verificar quantos commits serão removidos
COMMITS_TO_REMOVE=$(git rev-list --count "$TARGET_COMMIT..HEAD" 2>/dev/null || echo "0")
echo "📊 Commits que serão removidos: $COMMITS_TO_REMOVE"
echo ""

# Listar commits que serão removidos
echo "📋 Commits que serão removidos:"
git log --oneline "$TARGET_COMMIT..HEAD" | head -20
if [ "$COMMITS_TO_REMOVE" -gt 20 ]; then
    echo "   ... e mais $((COMMITS_TO_REMOVE - 20)) commits"
fi
echo ""

# Verificar se os commits específicos estão na lista
echo "🔍 Verificando commits específicos na lista:"
SPECIFIC_COMMITS=(
    "b61ca1861a4963b1db33dc989b381667e7c7c059"
    "2f0130c7c4209d993934bf65f40a1c7a67a11543"
    "395c98a8670e97605c48bb51cd4c405ecf718874"
    "16e89642d726f9feb766114f85c10bf7439fd088"
    "6114b7f8275da4b68334c10145e64794ca7f5b81"
    "95ef66edfbe391ac078775c65bb9e076306276a5"
    "87b4c375203fb32c2ef493ab3143ede8a59d4278"
)

FOUND_COUNT=0
for commit in "${SPECIFIC_COMMITS[@]}"; do
    if git merge-base --is-ancestor "$TARGET_COMMIT" "$commit" 2>/dev/null && \
       git merge-base --is-ancestor "$commit" "$CURRENT_COMMIT" 2>/dev/null; then
        FOUND_COUNT=$((FOUND_COUNT + 1))
        SHORT=$(git rev-parse --short "$commit")
        MSG=$(git log --format=%s -1 "$commit" 2>/dev/null || echo "N/A")
        echo "  ✅ $SHORT - $MSG (será removido)"
    fi
done

if [ $FOUND_COUNT -eq 0 ]; then
    echo "  ⚠️  Nenhum dos commits específicos encontrado na faixa a ser removida"
    echo "     Eles podem já ter sido removidos ou não estarem neste branch"
fi
echo ""

# Criar backup
BACKUP_BRANCH="backup-before-reset-$(date +%Y%m%d_%H%M%S)"
echo "💾 Criando backup: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH"
echo "✅ Backup criado: $BACKUP_BRANCH"
echo ""

# Verificar se há mudanças não commitadas
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  ATENÇÃO: Há mudanças não commitadas!"
    echo ""
    git status --short
    echo ""
    echo "Opções:"
    echo "  1. Fazer stash (salvar mudanças)"
    echo "  2. Descartar mudanças (perder alterações)"
    echo "  3. Cancelar"
    echo ""
    read -p "Escolha (1/2/3): " OPTION
    
    case "$OPTION" in
        1)
            git stash push -m "Stash antes de reset para $TARGET_COMMIT"
            echo "✅ Mudanças salvas em stash"
            ;;
        2)
            git reset --hard HEAD
            echo "✅ Mudanças descartadas"
            ;;
        3)
            echo "❌ Operação cancelada"
            exit 1
            ;;
        *)
            # Aceitar "sim", "SIM", "s", "S" como stash
            STASH_IT_LOWER=$(echo "$OPTION" | tr '[:upper:]' '[:lower:]')
            if [ "$STASH_IT_LOWER" = "sim" ] || [ "$STASH_IT_LOWER" = "s" ] || [ "$STASH_IT_LOWER" = "1" ]; then
                git stash push -m "Stash antes de reset para $TARGET_COMMIT"
                echo "✅ Mudanças salvas em stash"
            elif [ "$STASH_IT_LOWER" = "não" ] || [ "$STASH_IT_LOWER" = "nao" ] || [ "$STASH_IT_LOWER" = "n" ] || [ "$STASH_IT_LOWER" = "2" ]; then
                git reset --hard HEAD
                echo "✅ Mudanças descartadas"
            else
                echo "❌ Opção inválida. Operação cancelada."
                exit 1
            fi
            ;;
    esac
    echo ""
fi

# Confirmação final
echo "⚠️  ATENÇÃO: Esta operação irá:"
echo "   1. Remover $COMMITS_TO_REMOVE commits do histórico local"
echo "   2. Resetar para o commit: $(git rev-parse --short $TARGET_COMMIT)"
echo "   3. Você precisará fazer FORCE PUSH para atualizar o GitHub"
echo ""
echo "📝 Commit alvo:"
git log --oneline -1 "$TARGET_COMMIT"
echo ""
read -p "⚠️  Continuar? Digite 'SIM' em maiúsculas para confirmar: " CONFIRM

if [ "$CONFIRM" != "SIM" ]; then
    echo "❌ Operação cancelada"
    exit 0
fi

echo ""
echo "🔄 Executando reset..."

# Resetar para o commit alvo (hard reset - remove tudo depois)
git reset --hard "$TARGET_COMMIT"

echo ""
echo "✅ Reset concluído!"
echo ""
echo "📍 Commit atual: $(git rev-parse --short HEAD)"
echo "📍 Branch: $CURRENT_BRANCH"
echo ""

# Verificar status
echo "📊 Status atual:"
git log --oneline -5
echo ""

# Instruções para push
echo "📤 PRÓXIMOS PASSOS:"
echo "==================="
echo ""
echo "1. Verificar que está tudo correto:"
echo "   git log --oneline -10"
echo ""
echo "2. Enviar para GitHub (FORCE PUSH - CUIDADO!):"
echo "   git push origin $CURRENT_BRANCH --force"
echo ""
echo "⚠️  ATENÇÃO: Force push reescreve o histórico no GitHub!"
echo "   Certifique-se de que:"
echo "   - Ninguém mais está trabalhando neste branch"
echo "   - Você tem backup (criado: $BACKUP_BRANCH)"
echo "   - Você tem certeza do que está fazendo"
echo ""
echo "3. Se precisar voltar atrás:"
echo "   git checkout $BACKUP_BRANCH"
echo "   git branch -D $CURRENT_BRANCH"
echo "   git checkout -b $CURRENT_BRANCH"
echo ""

