#!/bin/bash

echo "🚨 CORREÇÃO URGENTE - ERRO DE IMPORT"
echo "===================================="

# Commit da correção urgente
git add bot_manager.py
git commit -m "🚨 URGENT FIX: Remove import duplicado do threading

- Remove import threading dentro da função
- Usa threading já importado no topo
- Corrige UnboundLocalError
- Sistema volta a funcionar"

# Push para produção
git push origin main

echo "✅ Correção URGENTE aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. sudo systemctl status grimbots"
echo "4. Sistema deve funcionar normalmente"
