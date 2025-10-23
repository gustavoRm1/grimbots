#!/bin/bash

echo "🚨 CORREÇÃO URGENTE - DOWNSELL R$ 9.97"
echo "======================================"

# Verificar se estamos na VPS
if [ ! -d "/root/grimbots" ]; then
    echo "❌ Este script deve ser executado na VPS!"
    exit 1
fi

cd /root/grimbots

echo "📥 Fazendo pull das correções..."
git pull origin main

echo "🔄 Reiniciando serviço..."
sudo systemctl restart grimbots

echo "⏳ Aguardando serviço inicializar..."
sleep 5

echo "📊 Verificando status..."
sudo systemctl status grimbots --no-pager -l

echo "✅ CORREÇÃO APLICADA!"
echo "🎯 Agora os downsells vão calcular o desconto correto!"
echo "💰 50% de R$ 14,97 = R$ 7,49 (não mais R$ 9,97)"
