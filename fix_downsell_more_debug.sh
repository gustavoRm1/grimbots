#!/bin/bash

echo "🚨 CORREÇÃO COM MAIS DEBUG - INVESTIGAR _send_downsell"
echo "===================================================="

# Commit da correção com mais debug
git add bot_manager.py
git commit -m "🚨 MORE DEBUG: Adiciona logs detalhados no _send_downsell

- Log da configuração do downsell recebida
- Log do original_price
- Log do original_button_index
- Debug completo para encontrar problema do preço 0"

# Push para produção
git push origin main

echo "✅ Correção com MAIS DEBUG aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: clique em downsell"
echo "4. Ver logs: sudo journalctl -u grimbots -f | grep DEBUG"
echo "5. Encontre o problema na configuração do downsell"
