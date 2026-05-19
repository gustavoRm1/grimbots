#!/bin/bash

# Script para remover commits específicos do histórico Git
# Execute no servidor: bash remove_commits.sh

set -e

echo "🗑️  Script para Remover Commits Específicos"
echo "=============================================="
echo ""

# IDs dos commits a serem removidos
COMMITS_TO_REMOVE=(
    "b61ca1861a4963b1db33dc989b381667e7c7c059"
    "2f0130c7c4209d993934bf65f40a1c7a67a11543"
    "395c98a8670e97605c48bb51cd4c405ecf718874"
    "16e89642d726f9feb766114f85c10bf7439fd088"
    "6114b7f8275da4b68334c10145e64794ca7f5b81"
    "95ef66edfbe391ac078775c65bb9e076306276a5"
    "87b4c375203fb32c2ef493ab3143ede8a59d4278"
)

# Verificar se estamos em um repositório Git
if [ ! -d .git ]; then
    echo "❌ Erro: Não é um repositório Git"
    exit 1
fi

# Fazer backup do branch atual
CURRENT_BRANCH=$(git branch --show-current)
BACKUP_BRANCH="backup-before-remove-commits-$(date +%Y%m%d_%H%M%S)"
echo "💾 Criando backup do branch atual: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH"
echo "✅ Backup criado: $BACKUP_BRANCH"
echo ""

# Verificar quais commits existem
echo "🔍 Verificando commits no histórico..."
EXISTING_COMMITS=()
for commit in "${COMMITS_TO_REMOVE[@]}"; do
    if git cat-file -e "$commit^{commit}" 2>/dev/null; then
        EXISTING_COMMITS+=("$commit")
        echo "  ✅ Encontrado: $commit"
        git log --oneline -1 "$commit"
    else
        echo "  ⚠️  Não encontrado: $commit"
    fi
done
echo ""

if [ ${#EXISTING_COMMITS[@]} -eq 0 ]; then
    echo "⚠️  Nenhum dos commits especificados foi encontrado no histórico"
    echo "   Eles podem já ter sido removidos ou não existirem neste repositório"
    exit 0
fi

echo "📋 Commits que serão removidos: ${#EXISTING_COMMITS[@]}"
echo ""

# Perguntar confirmação
read -p "⚠️  ATENÇÃO: Esta operação irá reescrever o histórico Git. Continuar? (sim/não): " CONFIRM
if [ "$CONFIRM" != "sim" ]; then
    echo "❌ Operação cancelada"
    exit 0
fi

echo ""
echo "🔄 Iniciando remoção dos commits..."

# Método 1: Usar git rebase interativo para remover commits específicos
# Primeiro, precisamos encontrar o commit base (antes do primeiro commit a ser removido)

# Encontrar o commit mais antigo a ser removido
OLDEST_COMMIT=""
for commit in "${EXISTING_COMMITS[@]}"; do
    if [ -z "$OLDEST_COMMIT" ]; then
        OLDEST_COMMIT="$commit"
    else
        # Verificar qual é mais antigo
        if git merge-base --is-ancestor "$commit" "$OLDEST_COMMIT" 2>/dev/null; then
            OLDEST_COMMIT="$commit"
        fi
    fi
done

echo "📌 Commit mais antigo a ser removido: $OLDEST_COMMIT"
BASE_COMMIT=$(git rev-parse "$OLDEST_COMMIT^" 2>/dev/null || echo "")

if [ -z "$BASE_COMMIT" ]; then
    echo "❌ Erro: Não foi possível encontrar o commit base"
    exit 1
fi

echo "📌 Commit base (antes do mais antigo): $BASE_COMMIT"
echo ""

# Método alternativo: Usar git filter-branch ou git rebase
# Vamos usar uma abordagem mais segura: criar um novo branch sem esses commits

echo "🌿 Criando novo branch sem os commits..."
NEW_BRANCH="${CURRENT_BRANCH}-cleaned-$(date +%Y%m%d_%H%M%S)"
git checkout -b "$NEW_BRANCH" "$BASE_COMMIT"

# Aplicar todos os commits após o base, exceto os que queremos remover
echo "🔄 Aplicando commits (exceto os removidos)..."
git cherry-pick "$BASE_COMMIT..$CURRENT_BRANCH" --strategy-option=ours || true

# Método mais direto: usar git rebase interativo
echo ""
echo "📝 Usando git rebase interativo..."
echo "   Você precisará editar o arquivo para remover as linhas dos commits"
echo ""

# Criar script de rebase automático
REBASE_SCRIPT="/tmp/rebase_script_$$.sh"
cat > "$REBASE_SCRIPT" << 'EOF'
#!/bin/bash
# Script gerado automaticamente para remover commits
EOF

# Encontrar o commit base para rebase
REBASE_BASE=$(git merge-base "$BASE_COMMIT" "$CURRENT_BRANCH" 2>/dev/null || echo "$BASE_COMMIT")

echo "🔄 Executando rebase interativo a partir de: $REBASE_BASE"
echo "   No editor que abrir, altere 'pick' para 'drop' nas linhas dos commits:"
for commit in "${EXISTING_COMMITS[@]}"; do
    SHORT_HASH=$(git rev-parse --short "$commit" 2>/dev/null || echo "$commit")
    echo "   - $SHORT_HASH"
done
echo ""

# Método mais automático: usar git filter-branch
echo "🔧 Usando método automático com git filter-branch..."

# Criar script de filtro
FILTER_SCRIPT="/tmp/filter_commits_$$.sh"
cat > "$FILTER_SCRIPT" << 'SCRIPT'
#!/bin/bash
# Script para filtrar commits
for commit_hash in "$@"; do
    if [ "$(git rev-parse HEAD)" = "$commit_hash" ]; then
        # Pular este commit (não fazer nada, apenas avançar)
        git reset --soft HEAD^
        git commit --allow-empty -m "Removed commit $commit_hash"
        exit 0
    fi
done
# Manter commit normal
git commit-tree "$@"
SCRIPT

chmod +x "$FILTER_SCRIPT"

# Método mais simples e direto: git rebase com drop automático
echo ""
echo "🎯 Método Recomendado: Rebase Interativo Manual"
echo "================================================"
echo ""
echo "Execute os seguintes comandos no servidor:"
echo ""
echo "1. Voltar para o branch original:"
echo "   git checkout $CURRENT_BRANCH"
echo ""
echo "2. Iniciar rebase interativo:"
echo "   git rebase -i $REBASE_BASE"
echo ""
echo "3. No editor, altere 'pick' para 'drop' nas linhas dos commits:"
for commit in "${EXISTING_COMMITS[@]}"; do
    SHORT_HASH=$(git rev-parse --short "$commit" 2>/dev/null || echo "$commit")
    MSG=$(git log --format=%s -1 "$commit" 2>/dev/null || echo "commit message")
    echo "   - $SHORT_HASH $MSG"
done
echo ""
echo "4. Salve e feche o editor"
echo ""
echo "5. Se houver conflitos, resolva e continue:"
echo "   git rebase --continue"
echo ""
echo "6. Após concluir, force push (CUIDADO!):"
echo "   git push origin $CURRENT_BRANCH --force"
echo ""

# Alternativa: Script automático usando git rebase com sequencer
echo "🤖 Alternativa: Script Automático"
echo "=================================="
echo ""
echo "Criando script automático..."

AUTO_SCRIPT="remove_commits_auto.sh"
cat > "$AUTO_SCRIPT" << 'AUTO'
#!/bin/bash
# Script automático para remover commits via rebase

CURRENT_BRANCH=$(git branch --show-current)
COMMITS_TO_DROP=(
    "b61ca1861a4963b1db33dc989b381667e7c7c059"
    "2f0130c7c4209d993934bf65f40a1c7a67a11543"
    "395c98a8670e97605c48bb51cd4c405ecf718874"
    "16e89642d726f9feb766114f85c10bf7439fd088"
    "6114b7f8275da4b68334c10145e64794ca7f5b81"
    "95ef66edfbe391ac078775c65bb9e076306276a5"
    "87b4c375203fb32c2ef493ab3143ede8a59d4278"
)

# Encontrar o commit mais antigo
OLDEST=$(git rev-list --max-count=1 --reverse "${COMMITS_TO_DROP[@]}" 2>/dev/null || echo "")
if [ -z "$OLDEST" ]; then
    echo "❌ Não foi possível encontrar os commits"
    exit 1
fi

BASE=$(git rev-parse "$OLDEST^" 2>/dev/null || echo "")
if [ -z "$BASE" ]; then
    echo "❌ Não foi possível encontrar o commit base"
    exit 1
fi

echo "🔄 Iniciando rebase automático..."
echo "   Base: $(git rev-parse --short $BASE)"
echo "   Branch: $CURRENT_BRANCH"
echo ""

# Criar sequência de comandos para o rebase
REBASE_TODO=$(mktemp)
git log --oneline --reverse "$BASE..HEAD" | while read line; do
    HASH=$(echo "$line" | cut -d' ' -f1)
    FULL_HASH=$(git rev-parse "$HASH")
    
    # Verificar se este commit deve ser removido
    SHOULD_DROP=false
    for drop_hash in "${COMMITS_TO_DROP[@]}"; do
        if [ "$FULL_HASH" = "$drop_hash" ]; then
            SHOULD_DROP=true
            break
        fi
    done
    
    if [ "$SHOULD_DROP" = true ]; then
        echo "drop $HASH $(echo "$line" | cut -d' ' -f2-)" >> "$REBASE_TODO"
        echo "  ❌ Removendo: $line"
    else
        echo "pick $HASH $(echo "$line" | cut -d' ' -f2-)" >> "$REBASE_TODO"
        echo "  ✅ Mantendo: $line"
    fi
done

echo ""
echo "📝 Sequência de rebase criada em: $REBASE_TODO"
echo ""
echo "Para executar o rebase:"
echo "   git rebase -i $BASE"
echo "   (Copie o conteúdo de $REBASE_TODO para o editor)"
echo ""

# Método mais direto: usar git rebase com sequencer manual
echo "🎯 MÉTODO RECOMENDADO - Execute no servidor:"
echo "=============================================="
echo ""
echo "git rebase -i $BASE"
echo ""
echo "No editor, para cada commit listado abaixo, altere 'pick' para 'drop':"
echo ""
for commit in "${COMMITS_TO_DROP[@]}"; do
    if git cat-file -e "$commit^{commit}" 2>/dev/null; then
        SHORT=$(git rev-parse --short "$commit")
        MSG=$(git log --format=%s -1 "$commit" 2>/dev/null || echo "N/A")
        echo "   drop $SHORT $MSG"
    fi
done
echo ""
echo "Salve e feche. Se houver conflitos, resolva e continue com:"
echo "   git rebase --continue"
echo ""
echo "Após concluir, force push:"
echo "   git push origin $CURRENT_BRANCH --force"
echo ""

AUTO

chmod +x "$AUTO_SCRIPT"
echo "✅ Script automático criado: $AUTO_SCRIPT"
echo ""

echo "📋 RESUMO:"
echo "=========="
echo "Branch atual: $CURRENT_BRANCH"
echo "Backup criado: $BACKUP_BRANCH"
echo "Commits a remover: ${#EXISTING_COMMITS[@]}"
echo ""
echo "✅ Próximos passos:"
echo "   1. Execute: git rebase -i $REBASE_BASE"
echo "   2. Altere 'pick' para 'drop' nos commits listados acima"
echo "   3. Salve e feche"
echo "   4. Resolva conflitos se houver"
echo "   5. Force push: git push origin $CURRENT_BRANCH --force"
echo ""

