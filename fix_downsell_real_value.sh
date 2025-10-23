#!/bin/bash

echo "🚨 CORREÇÃO URGENTE - VALOR REAL DO DOWNSELL"
echo "==========================================="

# Commit da correção urgente
git add bot_manager.py
git commit -m "🚨 URGENT FIX: Corrige valor do downsell para valor real

- Se preço < R$ 1,00, usa valor padrão R$ 9,97
- Evita downsells de R$ 0,01 que perdem vendas
- Logs detalhados para debug
- Sistema volta a gerar vendas reais"

# Push para produção
git push origin main

echo "✅ Correção URGENTE aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: downsell deve gerar R$ 9,97"
echo "4. Sistema volta a gerar vendas reais!"
