#!/bin/bash

# Script para aplicar correções críticas do Paradise API V30
# Execute na VPS após fazer git pull

echo "🔧 APLICANDO CORREÇÕES CRÍTICAS - PARADISE API V30"
echo "=================================================="

# 1. Fazer backup do arquivo atual
echo "📁 Fazendo backup do gateway_paradise.py..."
cp gateway_paradise.py gateway_paradise.py.backup.$(date +%Y%m%d_%H%M%S)

# 2. Fazer commit das correções
echo "💾 Commitando correções..."
git add gateway_paradise.py
git commit -m "🔧 CORREÇÃO CRÍTICA: Validação de dados do cliente Paradise API V30

- Adiciona validação de telefone brasileiro
- Adiciona validação de CPF/documento
- Corrige split percentage logging
- Resolve erro 400 da API Paradise

Fixes: Status 400 - dados inválidos do cliente"

# 3. Push para repositório
echo "🚀 Enviando para repositório..."
git push origin main

# 4. Reiniciar serviço
echo "🔄 Reiniciando serviço..."
sudo systemctl restart grimbots

# 5. Verificar status
echo "✅ Verificando status do serviço..."
sudo systemctl status grimbots --no-pager -l

echo ""
echo "🎯 CORREÇÕES APLICADAS COM SUCESSO!"
echo "📊 Monitore os logs: tail -f logs/app.log | grep -i paradise"
echo "🧪 Teste uma transação para verificar se o erro foi resolvido"
