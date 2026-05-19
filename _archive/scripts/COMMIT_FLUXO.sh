#!/bin/bash
# Script para fazer commit da implementação do Fluxo Visual
# Commit target: d5f1decb8d5cd7214850ba4ae07fe304070be585 (origin/main)

set -e

echo "=========================================="
echo "  COMMIT: Implementação Fluxo Visual"
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

# Verificar se estamos em main ou master
if [ "$current_branch" != "main" ] && [ "$current_branch" != "master" ]; then
    warning "Você não está na branch main/master. Deseja continuar? (y/n)"
    read -r response
    if [ "$response" != "y" ]; then
        error "Commit cancelado"
    fi
fi

# Verificar status do git
echo ""
echo "📊 Status do repositório:"
git status --short

echo ""
warning "Os seguintes arquivos serão adicionados ao commit:"
echo "  - models.py"
echo "  - bot_manager.py"
echo "  - app.py"
echo "  - templates/bot_config.html"
echo "  - migrations/add_flow_fields.py"
echo "  - EXECUTAR_MIGRATION_FLOW.sh"
echo "  - DEBATE_PROFUNDO_QI500_EDITOR_FLUXO.md"
echo "  - COMMIT_FLUXO_IMPLEMENTACAO.md"
echo ""
warning "Deseja continuar com o commit? (y/n)"
read -r response

if [ "$response" != "y" ]; then
    error "Commit cancelado pelo usuário"
fi

# Adicionar arquivos modificados
success "Adicionando arquivos ao staging..."
git add models.py
git add bot_manager.py
git add app.py
git add templates/bot_config.html

# Adicionar arquivos novos
git add migrations/add_flow_fields.py
git add EXECUTAR_MIGRATION_FLOW.sh
git add DEBATE_PROFUNDO_QI500_EDITOR_FLUXO.md
git add COMMIT_FLUXO_IMPLEMENTACAO.md

success "Arquivos adicionados ao staging"

# Criar commit
echo ""
success "Criando commit..."

git commit -m "feat: Implementação completa do editor de fluxograma visual

- Adicionado campos flow_enabled e flow_steps ao BotConfig
- Adicionado campo flow_step_id ao Payment  
- Implementado executor de fluxo recursivo (síncrono até payment, assíncrono após)
- Implementado lista visual de steps no frontend
- Suporte a condições limitadas (payment: next/pending, message: retry)
- Fallback robusto para welcome_message se fluxo falhar
- Backward compatible - bots antigos continuam funcionando normalmente

Arquitetura: Híbrida (lista visual padrão + executor recursivo stateless)
Performance: Síncrono até payment (rápido), assíncrono após callback (pesado)
Estado: Stateless (apenas payment.flow_step_id para determinar próximo step)"

commit_hash=$(git rev-parse HEAD)
success "Commit criado: $commit_hash"

echo ""
success "=========================================="
success "  COMMIT CONCLUÍDO COM SUCESSO!"
success "=========================================="
echo ""
echo "Commit hash: $commit_hash"
echo ""
warning "Para fazer push para origin/main:"
echo "  git push origin main"
echo ""

