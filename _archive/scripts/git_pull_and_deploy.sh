#!/bin/bash
# Script para fazer pull mesmo com mudanças locais e executar deploy

set -e

echo "=========================================="
echo "  GIT PULL + DEPLOY AUTOMÁTICO"
echo "=========================================="
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# 1. Salvar mudanças locais
echo "💾 Salvando mudanças locais..."
if ! git diff --quiet || ! git diff --cached --quiet; then
    git stash save "Auto-stash antes do pull QI 500 - $(date +%Y%m%d_%H%M%S)"
    success "Mudanças salvas em stash"
    HAD_STASH=true
else
    success "Nenhuma mudança local para salvar"
    HAD_STASH=false
fi

# 2. Fazer pull
echo ""
echo "⬇️  Fazendo pull do repositório..."
git pull origin main
success "Pull concluído"

# 3. Aplicar mudanças locais de volta (se houver)
if [ "$HAD_STASH" = true ]; then
    echo ""
    echo "📦 Aplicando mudanças locais de volta..."
    if git stash pop; then
        success "Mudanças locais aplicadas"
    else
        warning "Conflitos detectados - resolva manualmente"
        echo "Execute: git stash list"
        echo "Execute: git stash show"
        exit 1
    fi
fi

# 4. Dar permissão aos scripts
echo ""
echo "🔧 Preparando scripts..."
chmod +x DEPLOY_COMPLETO.sh setup_systemd.sh start_system.sh verificar_sistema.sh 2>/dev/null || true
success "Scripts prontos"

# 5. Executar deploy
echo ""
echo "🚀 Executando deploy completo..."
echo ""

if [ -f "DEPLOY_COMPLETO.sh" ]; then
    ./DEPLOY_COMPLETO.sh
else
    warning "DEPLOY_COMPLETO.sh não encontrado"
    echo "Execute manualmente os passos:"
    echo "  1. ./setup_systemd.sh"
    echo "  2. ./start_system.sh"
    echo "  3. ./verificar_sistema.sh"
fi

