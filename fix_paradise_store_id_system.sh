#!/bin/bash

# Script para corrigir configuração Paradise - Store ID do sistema
# Execute na VPS

echo "🔧 CORRIGINDO CONFIGURAÇÃO PARADISE - STORE ID DO SISTEMA"
echo "========================================================"

# 1. Backup do .env
echo "📁 Fazendo backup do .env..."
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# 2. Adicionar PARADISE_STORE_ID ao .env
echo "⚙️ Adicionando PARADISE_STORE_ID ao .env..."
if ! grep -q "PARADISE_STORE_ID" .env; then
    echo "" >> .env
    echo "# Paradise API V30 - Store ID do Sistema (Split da Plataforma)" >> .env
    echo "PARADISE_STORE_ID=177" >> .env
    echo "✅ PARADISE_STORE_ID adicionado ao .env"
else
    echo "✅ PARADISE_STORE_ID já existe no .env"
fi

# 3. Commit das correções
echo "💾 Commitando correções..."
git add templates/settings.html gateway_paradise.py
git commit -m "🔧 CORREÇÃO CRÍTICA: Store ID do sistema, não do usuário

- Remove Store ID do frontend (usuários não devem ter acesso)
- Store ID agora vem do .env (PARADISE_STORE_ID)
- Split da plataforma controlado pelo dono do sistema
- Usuários só configuram: API Key, Product Hash, Offer Hash
- Sistema usa Store ID do dono para split automático

Fixes: Segurança - usuários não podem alterar split da plataforma"

# 4. Push
echo "🚀 Enviando para repositório..."
git push origin main

# 5. Reiniciar serviço
echo "🔄 Reiniciando serviço..."
sudo systemctl restart grimbots

echo ""
echo "✅ CONFIGURAÇÃO CORRIGIDA!"
echo "📋 Agora:"
echo "   ✅ Usuários configuram: API Key, Product Hash, Offer Hash"
echo "   ✅ Sistema usa Store ID do dono (PARADISE_STORE_ID=177)"
echo "   ✅ Split da plataforma controlado pelo dono"
echo ""
echo "🎯 Teste: Acesse Settings → Gateways → Paradise"
echo "📊 Monitore: tail -f logs/app.log | grep -i paradise"
