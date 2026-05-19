#!/bin/bash
set -e
echo "=========================================="
echo "  MIGRATION: flow_enabled, flow_steps, flow_step_id"
echo "=========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

if [ ! -f "app.py" ]; then
    error "Execute do diretório do projeto (~/grimbots ou c:\\Users\\grcon\\Downloads\\grpay)"
fi

if [ ! -d "venv" ]; then
    warning "Virtual environment não encontrado. Tentando ativar venv padrão..."
fi

# Tentar ativar venv se existir
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null || true
    success "Virtual environment ativado"
fi

echo ""
echo "🔄 Executando migration..."
if python migrations/add_flow_fields.py; then
    success "Migration executada com sucesso!"
else
    error "Migration falhou! Verifique os logs acima."
fi

echo ""
echo "🔄 Reiniciando serviço grimbots (se estiver rodando)..."
if command -v systemctl &> /dev/null && systemctl is-active --quiet grimbots 2>/dev/null; then
    sudo systemctl restart grimbots 2>/dev/null && success "Serviço reiniciado!" || warning "Não foi possível reiniciar serviço (pode estar rodando manualmente)"
else
    warning "Serviço não está rodando via systemctl (pode estar rodando manualmente)"
fi

echo ""
success "CONCLUÍDO! Migration aplicada."
echo ""

