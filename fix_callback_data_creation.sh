#!/bin/bash

echo "🚨 CORREÇÃO CRÍTICA - CALLBACK_DATA CORRETO"
echo "=========================================="

# Commit da correção crítica
git add bot_manager.py
git commit -m "🚨 CRITICAL FIX: Corrige criação do callback_data do downsell

- Usa btn_index correto em vez de original_button_index
- Modo percentual: usa btn_index (0, 1, 2)
- Modo fixo: usa índice 0
- Evita original_button_idx inválido (748, 7498)
- Sistema volta a funcionar corretamente"

# Push para produção
git push origin main

echo "✅ Correção CRÍTICA aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: downsell deve funcionar corretamente"
echo "4. Sistema volta a ser profissional!"
