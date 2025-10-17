#!/bin/bash

# ============================================================================
# DEPLOY COM REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS
# ============================================================================

echo "🚀 INICIANDO DEPLOY COM REINICIALIZAÇÃO AUTOMÁTICA..."

# 1. Backup do banco (opcional)
echo "📦 Fazendo backup do banco..."
cp instance/saas_bot_manager.db instance/saas_bot_manager.db.backup.$(date +%Y%m%d_%H%M%S)

# 2. Pull das atualizações
echo "⬇️ Baixando atualizações..."
git pull origin main

# 3. Instalar dependências (se necessário)
echo "📦 Verificando dependências..."
pip install -r requirements.txt

# 4. Reiniciar serviço (isso vai executar restart_all_active_bots() automaticamente)
echo "🔄 Reiniciando serviço (bots serão reiniciados automaticamente)..."
sudo systemctl restart grimbots

# 5. Aguardar inicialização
echo "⏳ Aguardando inicialização do serviço..."
sleep 5

# 6. Verificar status
echo "📊 Verificando status do serviço..."
sudo systemctl status grimbots --no-pager -l

# 7. Verificar logs de reinicialização
echo "📋 Verificando logs de reinicialização dos bots..."
sudo journalctl -u grimbots -n 50 --no-pager | grep -E "(REINICIALIZAÇÃO|Bot.*reiniciado|Sucessos|Falhas)"

echo "✅ DEPLOY CONCLUÍDO!"
echo "🎯 Todos os bots ativos foram reiniciados automaticamente!"
echo "📊 Verifique os logs acima para confirmar o sucesso."
