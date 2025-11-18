#!/bin/bash
# Script para executar migration do utmify_pixel_id
# Execute este script no servidor de produção

set -e

echo "=========================================="
echo "  MIGRATION: utmify_pixel_id"
echo "=========================================="
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# Verificar se está no diretório correto
if [ ! -f "app.py" ]; then
    error "Execute do diretório do projeto (~/grimbots)"
fi

# Verificar se venv existe
if [ ! -d "venv" ]; then
    error "Virtual environment não encontrado. Execute: python3 -m venv venv"
fi

# Ativar venv
source venv/bin/activate
success "Virtual environment ativado"

# Executar migration
echo ""
echo "🔄 Executando migration..."
if python migrations/add_utmify_pixel_id.py; then
    success "Migration executada com sucesso!"
else
    error "Migration falhou! Verifique os logs acima."
fi

echo ""
echo "✅ CONCLUÍDO! Reinicie a aplicação:"
echo "   sudo systemctl restart grimbots"
echo ""

