#!/bin/bash

echo "🚨 CORREÇÃO COM DEBUG - INVESTIGAR CÁLCULO DO DESCONTO"
echo "===================================================="

# Commit da correção com debug
git add bot_manager.py
git commit -m "🚨 DEBUG FIX: Adiciona logs para investigar cálculo do desconto

- Log do btn_index, btn e original_btn_price
- Log do cálculo: preço * (1 - desconto/100)
- Debug completo para encontrar problema do preço 0
- Sistema volta a funcionar corretamente"

# Push para produção
git push origin main

echo "✅ Correção com DEBUG aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: clique em downsell"
echo "4. Ver logs: sudo journalctl -u grimbots -f | grep DEBUG"
echo "5. Encontre o problema no cálculo do desconto"
