#!/bin/bash
# Script de diagnóstico dos workers RQ

echo "=========================================="
echo " Diagnóstico Workers RQ"
echo "=========================================="

echo ""
echo "1. Verificando Redis:"
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis está rodando"
    redis-cli ping
else
    echo "❌ Redis NÃO está rodando"
    echo "   Inicie com: sudo systemctl start redis"
fi

echo ""
echo "2. Verificando RQ instalado:"
if /root/grimbots/venv/bin/python -c "import rq" 2>/dev/null; then
    echo "✅ RQ está instalado"
else
    echo "❌ RQ NÃO está instalado"
    echo "   Instale com: pip install rq"
fi

echo ""
echo "3. Verificando arquivo start_rq_worker.py:"
if [ -f "/root/grimbots/start_rq_worker.py" ]; then
    echo "✅ Arquivo existe"
    ls -lh /root/grimbots/start_rq_worker.py
else
    echo "❌ Arquivo NÃO existe"
fi

echo ""
echo "4. Testando importação:"
/root/grimbots/venv/bin/python -c "
import sys
sys.path.insert(0, '/root/grimbots')
try:
    from rq import Worker, Queue, Connection
    from redis import Redis
    print('✅ Imports OK')
    
    # Testar conexão Redis
    redis_conn = Redis.from_url('redis://localhost:6379/0', decode_responses=True)
    redis_conn.ping()
    print('✅ Conexão Redis OK')
except Exception as e:
    print(f'❌ Erro: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "5. Testando execução manual:"
echo "Execute: /root/grimbots/venv/bin/python /root/grimbots/start_rq_worker.py tasks"
echo ""

echo "6. Logs do systemd:"
echo "--- rq-worker-tasks (últimas 30 linhas) ---"
sudo journalctl -u rq-worker-tasks -n 30 --no-pager

