#!/bin/bash
# Script para recuperar sistema quando trava na inicialização

echo "======================================================================"
echo "🔧 RECUPERAÇÃO DE SISTEMA TRAVADO"
echo "======================================================================"
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# 1. Matar processos Python/Gunicorn travados
echo "💀 PASSO 1: Matando processos travados..."
pkill -9 python 2>/dev/null || true
pkill -9 python3 2>/dev/null || true
pkill -9 gunicorn 2>/dev/null || true
sleep 2
success "Processos mortos"

# 2. Liberar porta 5000
echo ""
echo "🔓 PASSO 2: Liberando porta 5000..."
fuser -k 5000/tcp 2>/dev/null || true
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
sleep 1
success "Porta 5000 liberada"

# 3. Remover locks stale
echo ""
echo "🔓 PASSO 3: Removendo locks stale..."

LOCK_FILES=(
    "/tmp/grimbots_scheduler.lock"
    "/tmp/scheduler.lock"
    "$(pwd)/grimbots_scheduler.lock"
)

for lock_file in "${LOCK_FILES[@]}"; do
    if [ -f "$lock_file" ]; then
        echo "   Removendo: $lock_file"
        rm -f "$lock_file" 2>/dev/null || true
    fi
done

success "Locks removidos"

# 4. Verificar processos Python/Gunicorn ainda rodando
echo ""
echo "🔍 PASSO 4: Verificando processos restantes..."
PYTHON_PROCS=$(ps aux | grep -E '[p]ython|[g]unicorn' | wc -l)
if [ "$PYTHON_PROCS" -gt 0 ]; then
    warning "Ainda há $PYTHON_PROCS processo(s) Python/Gunicorn rodando"
    echo "   Listando processos:"
    ps aux | grep -E '[p]ython|[g]unicorn' | head -5
    echo ""
    read -p "   Deseja matar TODOS os processos Python? (s/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        pkill -9 -f python
        pkill -9 -f gunicorn
        sleep 2
        success "Todos os processos Python foram mortos"
    fi
else
    success "Nenhum processo Python/Gunicorn encontrado"
fi

# 5. Verificar se porta está livre
echo ""
echo "🔍 PASSO 5: Verificando se porta 5000 está livre..."
if lsof -i:5000 > /dev/null 2>&1; then
    error "Porta 5000 ainda está em uso!"
    echo "   Tentando forçar liberação..."
    fuser -k 5000/tcp 2>/dev/null || true
    sleep 2
    if lsof -i:5000 > /dev/null 2>&1; then
        error "Porta 5000 ainda em uso após tentativas - verificar manualmente"
    else
        success "Porta 5000 liberada com sucesso"
    fi
else
    success "Porta 5000 está livre"
fi

# 6. Limpar arquivos temporários
echo ""
echo "🧹 PASSO 6: Limpando arquivos temporários..."
rm -f /tmp/grimbots*.lock 2>/dev/null || true
rm -f /tmp/scheduler*.lock 2>/dev/null || true
rm -f grimbots.pid 2>/dev/null || true
success "Arquivos temporários limpos"

# 7. Verificar Redis
echo ""
echo "🔍 PASSO 7: Verificando Redis..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        success "Redis está rodando"
    else
        warning "Redis não está respondendo"
        echo "   Tentando iniciar Redis..."
        sudo systemctl start redis 2>/dev/null || true
        sleep 2
        if redis-cli ping &> /dev/null; then
            success "Redis iniciado com sucesso"
        else
            error "Redis não conseguiu iniciar - verificar manualmente"
        fi
    fi
else
    warning "redis-cli não encontrado - pulando verificação"
fi

# 8. Resumo final
echo ""
echo "======================================================================"
echo "✅ RECUPERAÇÃO CONCLUÍDA"
echo "======================================================================"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo ""
echo "1. Verificar logs para entender o que causou o travamento:"
echo "   tail -50 logs/gunicorn.log"
echo "   tail -50 logs/error.log"
echo ""
echo "2. Reiniciar a aplicação:"
echo "   ./restart-app.sh"
echo ""
echo "3. Verificar se está funcionando:"
echo "   curl http://localhost:5000/health"
echo ""
echo "4. Se continuar travando, verificar:"
echo "   - Espaço em disco: df -h"
echo "   - Memória: free -h"
echo "   - Logs do sistema: journalctl -xe"
echo ""

