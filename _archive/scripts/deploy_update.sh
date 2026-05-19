#!/bin/bash
# Script para fazer deploy das mudanças (pull, restart)
# Descartar mudanças locais e fazer pull do repositório remoto

set -e  # Parar em caso de erro

echo "=========================================="
echo "  DEPLOY UPDATE - GRIMBOTS"
echo "=========================================="

# 1. Verificar status do git
echo ""
echo "📋 Verificando status do Git..."
git status --short

# 2. Descartar mudanças locais não commitadas
echo ""
echo "🗑️  Descartando mudanças locais não commitadas..."
git reset --hard HEAD

# 3. Limpar arquivos não rastreados (exceto logs e arquivos importantes)
echo "🧹 Limpando arquivos não rastreados..."
git clean -fd -e logs/ -e .env -e venv/ -e "*.pid" -e nohup.out -e "*.log" -e "*.pyc" -e "__pycache__" 2>/dev/null || true

# 4. Fazer pull do repositório remoto
echo ""
echo "⬇️ Fazendo pull do repositório remoto..."
git pull origin main || {
    echo "❌ Erro ao fazer pull. Verifique conflitos."
    exit 1
}

# 4. Verificar processos gunicorn rodando
echo ""
echo "🔍 Verificando processos Gunicorn..."
GUNICORN_PIDS=$(ps aux | grep "[g]unicorn" | awk '{print $2}')
if [ -z "$GUNICORN_PIDS" ]; then
    echo "⚠️ Nenhum processo Gunicorn encontrado rodando"
else
    echo "📌 Processos Gunicorn encontrados: $GUNICORN_PIDS"
fi

# 5. Parar processos Gunicorn existentes
echo ""
echo "🛑 Parando processos Gunicorn..."
pkill -f gunicorn || {
    echo "⚠️ Nenhum processo Gunicorn para parar"
}
sleep 2

# 6. Verificar se ainda há processos
REMAINING=$(ps aux | grep "[g]unicorn" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️ Ainda há processos Gunicorn rodando. Forçando parada..."
    pkill -9 -f gunicorn
    sleep 1
fi

# 7. Verificar se há arquivo PID
if [ -f "grimbots.pid" ]; then
    echo "🗑️ Removendo arquivo PID antigo..."
    rm -f grimbots.pid
fi

# 8. Ativar ambiente virtual (se existir)
if [ -d "venv" ]; then
    echo ""
    echo "🐍 Ativando ambiente virtual..."
    source venv/bin/activate
fi

# 9. Iniciar Gunicorn em background
echo ""
echo "🚀 Iniciando Gunicorn..."
cd ~/grimbots || cd /root/grimbots || pwd

# Usar gunicorn_config.py se existir
if [ -f "gunicorn_config.py" ]; then
    nohup gunicorn -c gunicorn_config.py wsgi:application > logs/gunicorn.log 2>&1 &
else
    nohup gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 --timeout 120 --access-logfile logs/access.log --error-logfile logs/error.log wsgi:application > logs/gunicorn.log 2>&1 &
fi

GUNICORN_PID=$!
echo "✅ Gunicorn iniciado com PID: $GUNICORN_PID"

# 10. Aguardar alguns segundos e verificar se está rodando
sleep 3
if ps -p $GUNICORN_PID > /dev/null 2>&1; then
    echo "✅ Gunicorn está rodando corretamente (PID: $GUNICORN_PID)"
else
    echo "❌ Gunicorn não está rodando. Verifique os logs:"
    echo "   tail -f logs/gunicorn.log"
    echo "   tail -f logs/error.log"
    exit 1
fi

# 11. Mostrar logs recentes
echo ""
echo "📋 Últimas linhas do log de erro:"
tail -n 5 logs/error.log 2>/dev/null || echo "   (log ainda não criado)"

echo ""
echo "=========================================="
echo "  ✅ DEPLOY CONCLUÍDO"
echo "=========================================="
echo ""
echo "Para monitorar os logs:"
echo "  tail -f logs/error.log"
echo "  tail -f logs/gunicorn.log"
echo ""
echo "Para verificar processos:"
echo "  ps aux | grep gunicorn"
echo ""

