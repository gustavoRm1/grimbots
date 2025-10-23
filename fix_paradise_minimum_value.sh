#!/bin/bash

echo "🚨 CORREÇÃO - VALOR MÍNIMO PARADISE PARA DOWNSELLS"
echo "================================================"

# Commit da correção
git add gateway_paradise.py
git commit -m "🚨 FIX: Ajusta valor mínimo Paradise para R$ 0,01

- Permite downsells de R$ 0,01
- Corrige erro 'Valor mínimo é R$ 0,50'
- Mantém validação de segurança
- Suporte completo a downsells"

# Push para produção
git push origin main

echo "✅ Correção aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: clique em downsell de R$ 0,01"
echo "4. Deve gerar PIX normalmente"
