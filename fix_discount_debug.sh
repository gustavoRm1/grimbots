#!/bin/bash

echo "🚨 CORREÇÃO COM DEBUG - INVESTIGAR original_price"
echo "==============================================="

# Commit da correção com debug
git add bot_manager.py
git commit -m "🚨 DEBUG FIX: Adiciona logs para investigar original_price

- Log do original_price recebido
- Log do discount_percentage
- Se original_price = 0, usa preço padrão R$ 9,97
- Debug completo para encontrar problema do cálculo"

# Push para produção
git push origin main

echo "✅ Correção com DEBUG aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: clique em downsell de 50% OFF"
echo "4. Ver logs: sudo journalctl -u grimbots -f | grep DEBUG"
echo "5. Encontre o problema no original_price"
