#!/bin/bash

# Script para corrigir frontend Paradise - Campo Store ID faltando
# Execute na VPS após fazer git pull

echo "🔧 CORRIGINDO FRONTEND PARADISE - CAMPO STORE ID FALTANDO"
echo "========================================================"

# 1. Fazer backup
echo "📁 Fazendo backup do settings.html..."
cp templates/settings.html templates/settings.html.backup.$(date +%Y%m%d_%H%M%S)

# 2. Commit das correções
echo "💾 Commitando correção do frontend..."
git add templates/settings.html
git commit -m "🔧 CORREÇÃO CRÍTICA: Adiciona campo Store ID no frontend Paradise

- Frontend estava incompleto (faltava Store ID)
- Usuários não conseguiam configurar Store ID
- Causava erro 400 na API Paradise
- Agora frontend tem todos os 4 campos necessários:
  * API Key
  * Product Hash  
  * Offer Hash
  * Store ID

Fixes: Frontend incompleto para configuração Paradise"

# 3. Push
echo "🚀 Enviando para repositório..."
git push origin main

# 4. Reiniciar serviço
echo "🔄 Reiniciando serviço..."
sudo systemctl restart grimbots

echo ""
echo "✅ FRONTEND CORRIGIDO!"
echo "📋 Agora o usuário pode configurar:"
echo "   ✅ API Key (sk_...)"
echo "   ✅ Product Hash (prod_...)"
echo "   ✅ Offer Hash (hash-da-oferta)"
echo "   ✅ Store ID (177)"
echo ""
echo "🎯 Teste: Acesse Settings → Gateways → Paradise"
echo "📊 Monitore: tail -f logs/app.log | grep -i paradise"
