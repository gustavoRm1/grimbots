#!/bin/bash

# Script AUTOMÁTICO para resetar para commit específico
# Descarta mudanças não commitadas automaticamente

set -e

TARGET_COMMIT="ec378a6f8c9a43ffb45f7e4f9ef4f5dc82f62da7"

echo "🎯 Resetar para Commit: $TARGET_COMMIT (AUTOMÁTICO)"
echo "==================================================="
echo ""

cd /root/grimbots 2>/dev/null || pwd

if [ ! -d .git ]; then
    echo "❌ Não é um repositório Git"
    exit 1
fi

# Verificar commit alvo
if ! git cat-file -e "$TARGET_COMMIT^{commit}" 2>/dev/null; then
    echo "❌ Commit alvo não encontrado: $TARGET_COMMIT"
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Branch: $CURRENT_BRANCH"
echo "📍 Alvo:   $(git rev-parse --short $TARGET_COMMIT)"
echo ""

# Backup
BACKUP="backup-auto-$(date +%Y%m%d_%H%M%S)"
git branch "$BACKUP"
echo "💾 Backup: $BACKUP"
echo ""

# Descartar mudanças não commitadas automaticamente
if ! git diff-index --quiet HEAD --; then
    echo "🗑️  Descartando mudanças não commitadas..."
    git reset --hard HEAD
    echo "✅ Mudanças descartadas"
    echo ""
fi

# Reset
echo "🔄 Resetando para commit alvo..."
git reset --hard "$TARGET_COMMIT"

echo ""
echo "✅ Reset concluído!"
echo ""
echo "📍 Commit atual: $(git rev-parse --short HEAD)"
echo ""
echo "📤 Para atualizar o GitHub:"
echo "   git push origin $CURRENT_BRANCH --force"
echo ""

