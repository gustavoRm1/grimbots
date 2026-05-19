#!/bin/bash

# Script SEGURO para resetar para commit específico
# Cria backup, verifica tudo, e só então faz o reset

set -e

TARGET_COMMIT="ec378a6f8c9a43ffb45f7e4f9ef4f5dc82f62da7"

echo "🎯 Resetar para Commit: $TARGET_COMMIT"
echo "======================================"
echo ""

cd /root/grimbots 2>/dev/null || {
    echo "⚠️  Diretório /root/grimbots não encontrado"
    echo "   Executando no diretório atual: $(pwd)"
}

# Verificar Git
if [ ! -d .git ]; then
    echo "❌ Erro: Não é um repositório Git"
    exit 1
fi

# Verificar commit alvo
if ! git cat-file -e "$TARGET_COMMIT^{commit}" 2>/dev/null; then
    echo "❌ Commit alvo não encontrado: $TARGET_COMMIT"
    echo ""
    echo "Buscando commits similares..."
    git log --oneline --all | grep "ec378a6" | head -5
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Branch: $CURRENT_BRANCH"
echo "📍 Alvo:   $(git rev-parse --short $TARGET_COMMIT)"
echo ""

# Backup
BACKUP="backup-$(date +%Y%m%d_%H%M%S)"
git branch "$BACKUP"
echo "💾 Backup: $BACKUP"
echo ""

# Reset
echo "🔄 Resetando para commit alvo..."
git reset --hard "$TARGET_COMMIT"

echo ""
echo "✅ Concluído!"
echo ""
echo "📤 Para enviar ao GitHub:"
echo "   git push origin $CURRENT_BRANCH --force"
echo ""

