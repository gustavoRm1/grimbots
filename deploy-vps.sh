#!/usr/bin/env bash
set -euo pipefail

# Script completo de deploy na VPS
# Faz pull, reinicia aplicação e verifica status

cd "$(dirname "$0")"

echo "🚀 Iniciando deploy na VPS..."
echo ""

# 1. Descartar mudanças locais
echo "📥 Passo 1/5: Atualizando repositório..."
git reset --hard HEAD
git clean -fd -e logs/ -e .env -e venv/ -e *.pid -e nohup.out
git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ Erro ao fazer pull. Abortando."
    exit 1
fi

echo "✅ Repositório atualizado!"
echo ""

# 2. Verificar se .env existe
echo "📋 Passo 2/5: Verificando configurações..."
if [[ ! -f ".env" ]]; then
    echo "⚠️  Arquivo .env não encontrado!"
    echo "   Crie o arquivo .env com as configurações necessárias."
    exit 1
fi

# 3. Parar aplicação
echo "🛑 Passo 3/5: Parando aplicação..."
if pgrep -f "gunicorn.*wsgi:app" >/dev/null; then
    pgrep -f "gunicorn.*wsgi:app" | xargs -r kill -9
    echo "   Gunicorn parado."
else
    echo "   Gunicorn não estava rodando."
fi

if pgrep -f start_rq_worker.py >/dev/null; then
    pgrep -f start_rq_worker.py | xargs -r kill -9
    echo "   Workers RQ parados."
else
    echo "   Workers RQ não estavam rodando."
fi

sleep 2

# 4. Limpar arquivos PID antigos
echo "🧹 Passo 4/5: Limpando arquivos temporários..."
rm -f grimbots.pid
rm -f nohup.out

# 5. Reiniciar aplicação
echo "🚀 Passo 5/5: Reiniciando aplicação..."

if [[ ! -d "venv" ]]; then
    echo "⚠️  Virtualenv 'venv' não encontrado. Abortando."
    exit 1
fi

# Exportar variáveis do .env
if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
fi

source venv/bin/activate

echo "   Iniciando Gunicorn..."
EVENTLET_NO_GREENDNS=yes nohup gunicorn -w 1 -k eventlet -c gunicorn_config.py wsgi:app > logs/gunicorn.log 2>&1 &

echo "   Iniciando workers RQ..."
nohup python3 start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
nohup python3 start_rq_worker.py tasks   > logs/rq-tasks.log   2>&1 &
nohup python3 start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &

deactivate

sleep 3

# 6. Verificar status
echo ""
echo "📊 Verificando status da aplicação..."
if pgrep -f "gunicorn.*wsgi:app" >/dev/null; then
    echo "✅ Gunicorn está rodando (PID: $(pgrep -f 'gunicorn.*wsgi:app'))"
else
    echo "❌ Gunicorn NÃO está rodando!"
fi

if pgrep -f start_rq_worker.py >/dev/null; then
    echo "✅ Workers RQ estão rodando (PIDs: $(pgrep -f start_rq_worker.py | tr '\n' ' '))"
else
    echo "❌ Workers RQ NÃO estão rodando!"
fi

echo ""
echo "✅ Deploy concluído com sucesso!"
echo ""
echo "📋 Para ver os logs:"
echo "   tail -f logs/error.log"
echo "   tail -f logs/gunicorn.log"

