#!/bin/bash
# Script de instalação dos workers RQ - QI 200
# Execute: bash install_rq_workers.sh

echo "=========================================="
echo " Instalação Workers RQ - QI 200"
echo "=========================================="

# Verificar se supervisor está instalado
if command -v supervisorctl &> /dev/null; then
    echo "✅ Supervisor encontrado"
    
    # Criar diretório se não existir
    if [ ! -d "/etc/supervisor/conf.d" ]; then
        echo "📁 Criando diretório /etc/supervisor/conf.d..."
        sudo mkdir -p /etc/supervisor/conf.d
    fi
    
    # Copiar configuração
    echo "📋 Copiando configuração do supervisor..."
    sudo cp deploy/supervisor/rq-worker.conf /etc/supervisor/conf.d/rq-worker.conf
    
    # Recarregar supervisor
    echo "🔄 Recarregando supervisor..."
    sudo supervisorctl reread
    sudo supervisorctl update
    
    echo "✅ Workers configurados no supervisor!"
    echo ""
    echo "Para iniciar os workers:"
    echo "  sudo supervisorctl start rq-worker"
    echo "  sudo supervisorctl start rq-worker-gateway"
    echo "  sudo supervisorctl start rq-worker-webhook"
    echo ""
    echo "Para verificar status:"
    echo "  sudo supervisorctl status"
    
else
    echo "⚠️ Supervisor não encontrado"
    echo ""
    echo "Opção 1: Instalar supervisor"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y supervisor"
    echo "  sudo mkdir -p /etc/supervisor/conf.d"
    echo "  sudo cp deploy/supervisor/rq-worker.conf /etc/supervisor/conf.d/"
    echo "  sudo supervisorctl reread"
    echo "  sudo supervisorctl update"
    echo ""
    echo "Opção 2: Usar systemd (criar serviços)"
    echo "  Veja: deploy/systemd/ para arquivos .service"
    echo ""
    echo "Opção 3: Rodar manualmente (desenvolvimento)"
    echo "  Terminal 1: python start_rq_worker.py tasks"
    echo "  Terminal 2: python start_rq_worker.py gateway"
    echo "  Terminal 3: python start_rq_worker.py webhook"
    echo ""
    echo "Opção 4: Usar nohup (produção simples)"
    echo "  nohup python start_rq_worker.py tasks > logs/rq-tasks.log 2>&1 &"
    echo "  nohup python start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &"
    echo "  nohup python start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &"
fi

