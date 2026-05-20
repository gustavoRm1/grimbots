#!/bin/bash

echo "🔄 Iniciando o RESTART COMPLETO do sistema Grimbots..."

echo "🌐 Passo 1: Reiniciando o Servidor Web (Painel e API)..."
sudo systemctl restart grimbots
if [ $? -eq 0 ]; then
    echo "   ✅ Web Server reiniciado."
else
    echo "   ❌ Erro ao reiniciar o Web Server!"
fi

echo "💀 Passo 2: Matando os Workers (Robôs) antigos da RAM..."
pkill -f start_rq_worker.py
sleep 2

echo "🤖 Passo 3: Levantando os novos Workers com o código atualizado..."
nohup venv/bin/python start_rq_worker.py marathon > worker_marathon.log 2>&1 &
echo "   ✅ Worker: Marathon online."

nohup venv/bin/python start_rq_worker.py tasks > worker_tasks.log 2>&1 &
echo "   ✅ Worker: Tasks online."

nohup venv/bin/python start_rq_worker.py webhook > worker_webhook.log 2>&1 &
echo "   ✅ Worker: Webhook online."

nohup venv/bin/python start_rq_worker.py gateway > worker_gateway.log 2>&1 &
echo "   ✅ Worker: Gateway online."

echo "🚀 TUDO PRONTO! Sistema 100% atualizado e operando."
