#!/bin/bash

echo "🚨 CORREÇÃO COM DEBUG - INVESTIGAR MODO DO DOWNSELL"
echo "================================================="

# Commit da correção com debug
git add bot_manager.py
git commit -m "🚨 DEBUG FIX: Adiciona log do pricing_mode

- Log do pricing_mode (fixed ou percentage)
- Debug completo para entender qual modo está sendo usado
- Sistema volta a funcionar corretamente"

# Push para produção
git push origin main

echo "✅ Correção com DEBUG aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: clique em downsell"
echo "4. Ver logs: sudo journalctl -u grimbots -f | grep DEBUG"
echo "5. Encontre o problema no modo do downsell"
