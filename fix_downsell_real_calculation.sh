#!/bin/bash

echo "🚨 CORREÇÃO CRÍTICA - VALOR REAL DO DOWNSELL"
echo "==========================================="

# Commit da correção crítica
git add bot_manager.py
git commit -m "🚨 CRITICAL FIX: Calcula valor real do downsell

- Se preço < R$ 1,00, busca configuração do downsell
- Calcula valor real: preço_original * (1 - desconto/100)
- R$ 14,97 com 50% OFF = R$ 7,49 (não R$ 9,97)
- Sistema volta a gerar vendas reais"

# Push para produção
git push origin main

echo "✅ Correção CRÍTICA aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: downsell de 50% OFF deve gerar R$ 7,49"
echo "4. Sistema volta a ser profissional!"
