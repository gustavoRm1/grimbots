#!/bin/bash
# Script para fazer PUSH para origin/main
# Garante que o commit vá para o repositório remoto

set -e

echo "=========================================="
echo "  PUSH PARA ORIGIN/MAIN"
echo "=========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    error "Execute do diretório do projeto"
fi

# Verificar se git está disponível
if ! command -v git &> /dev/null; then
    error "Git não está instalado ou não está no PATH"
fi

# Verificar branch atual
current_branch=$(git rev-parse --abbrev-ref HEAD)
echo "📌 Branch atual: $current_branch"

# Verificar se há commits não enviados
commits_ahead=$(git rev-list --count HEAD ^origin/main 2>/dev/null || echo "0")

if [ "$commits_ahead" = "0" ]; then
    warning "Não há commits para enviar. Todos os commits já estão em origin/main."
    echo ""
    echo "Para verificar commits locais:"
    echo "  git log origin/main..HEAD --oneline"
    exit 0
fi

echo ""
echo "📊 Commits a serem enviados: $commits_ahead"
git log origin/main..HEAD --oneline

echo ""
warning "Deseja fazer PUSH para origin/main? (y/n)"
read -r response

if [ "$response" != "y" ]; then
    error "Push cancelado pelo usuário"
fi

# Fazer push para origin/main
echo ""
success "Fazendo push para origin/main..."

if git push origin main; then
    success "✅ Push concluído com sucesso!"
    echo ""
    echo "Commit enviado para: origin/main"
    echo ""
    success "Verificando se foi enviado corretamente..."
    git log origin/main --oneline -1
else
    error "❌ Erro ao fazer push. Verifique as mensagens acima."
fi

echo ""
success "=========================================="
success "  PUSH CONCLUÍDO!"
success "=========================================="

