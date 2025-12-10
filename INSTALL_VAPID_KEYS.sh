#!/bin/bash
# Script para instalar chaves VAPID no .env
# Execute: bash INSTALL_VAPID_KEYS.sh

set -e

echo "=========================================="
echo "  INSTALAÇÃO DE CHAVES VAPID"
echo "=========================================="
echo ""

# Verificar se os arquivos existem
if [ ! -f "private_key.pem" ]; then
    echo "❌ Arquivo private_key.pem não encontrado!"
    echo "   Execute primeiro: python3 -m py_vapid --applicationServerKey"
    exit 1
fi

# Ler chave privada (remover quebras de linha para .env)
PRIVATE_KEY=$(cat private_key.pem | tr '\n' '|' | sed 's/|/\\n/g')

# Solicitar Application Server Key
echo "📋 Cole a Application Server Key gerada:"
echo "   (Exemplo: BEhpqgA91-F3kv9KGia9L8NS_NI35AdV6veN81fSiK3FBgf2uLlxrw2XP826dyRxiJtr_mRvytQuZ2ve3pJzO8w)"
read -p "   Application Server Key: " PUBLIC_KEY

if [ -z "$PUBLIC_KEY" ]; then
    echo "❌ Application Server Key é obrigatória!"
    exit 1
fi

# Backup do .env
if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup do .env criado"
fi

# Remover linhas antigas de VAPID
if [ -f ".env" ]; then
    sed -i '/^VAPID_/d' .env
    # Remover linha vazia após remoção (se houver)
    sed -i '/^$/N;/^\n$/d' .env
fi

# Adicionar novas chaves
echo "" >> .env
echo "# VAPID Keys para Push Notifications" >> .env
echo "VAPID_PUBLIC_KEY=${PUBLIC_KEY}" >> .env
echo "VAPID_PRIVATE_KEY=${PRIVATE_KEY}" >> .env
echo "VAPID_EMAIL=admin@grimbots.com" >> .env

echo ""
echo "=========================================="
echo "✅ CHAVES VAPID INSTALADAS COM SUCESSO!"
echo "=========================================="
echo ""
echo "📝 Verificação:"
echo "   cat .env | grep VAPID"
echo ""
echo "🔄 Próximos passos:"
echo "   1. Reiniciar o servidor:"
echo "      systemctl restart grimbots"
echo "      # OU Ctrl+C se rodando manualmente e reiniciar"
echo ""
echo "   2. Verificar logs:"
echo "      tail -f logs/app.log | grep -i push"
echo ""
echo "=========================================="
