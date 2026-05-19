#!/bin/bash
# Script para corrigir problema do Gunicorn

echo "🔧 CORRIGINDO GUNICORN..."
echo ""

# 1. Parar serviço
echo "1️⃣ Parando serviço systemd..."
sudo systemctl stop grimbots

# 2. Parar todos os processos Gunicorn
echo "2️⃣ Parando todos os processos Gunicorn..."
pkill -9 -f gunicorn
sleep 2

# 3. Remover arquivo PID stale
echo "3️⃣ Removendo arquivo PID stale..."
rm -f grimbots.pid
rm -f /root/grimbots/grimbots.pid

# 4. Verificar se porta está em uso
echo "4️⃣ Verificando porta 5000..."
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null ; then
    echo "   ⚠️  Porta 5000 em uso, matando processo..."
    lsof -ti:5000 | xargs kill -9
    sleep 2
fi

# 5. Verificar processos restantes
echo "5️⃣ Verificando processos restantes..."
ps aux | grep gunicorn | grep -v grep
if [ $? -eq 0 ]; then
    echo "   ⚠️  Ainda há processos Gunicorn, forçando kill..."
    pkill -9 -f gunicorn
    sleep 2
fi

# 6. Testar importação do app
echo "6️⃣ Testando importação do app..."
cd /root/grimbots
source venv/bin/activate
python -c "from app import app; print('✅ App importado com sucesso')" 2>&1
if [ $? -ne 0 ]; then
    echo "   ❌ ERRO: App não pode ser importado!"
    echo "   Verifique os logs acima para ver o erro real"
    exit 1
fi

# 7. Tentar iniciar Gunicorn manualmente (para ver erro)
echo ""
echo "7️⃣ Tentando iniciar Gunicorn manualmente (para ver erro real)..."
echo "   (Pressione Ctrl+C após ver o erro ou sucesso)"
echo ""
gunicorn -w 1 -k eventlet -c gunicorn_config.py wsgi:application 2>&1

