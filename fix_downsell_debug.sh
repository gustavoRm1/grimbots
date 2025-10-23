#!/bin/bash

echo "🚨 CORREÇÃO COM DEBUG - INVESTIGAR CALLBACK DATA"
echo "==============================================="

# Commit da correção com debug
git add bot_manager.py
git commit -m "🚨 DEBUG FIX: Adiciona logs para investigar callback_data do downsell

- Logs detalhados do callback_data recebido
- Logs das partes parseadas
- Validação de preço > 0
- Debug completo para encontrar problema"

# Push para produção
git push origin main

echo "✅ Correção com DEBUG aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: clique em downsell"
echo "4. Ver logs: sudo journalctl -u grimbots -f | grep DEBUG"
echo "5. Encontre o problema no callback_data"
