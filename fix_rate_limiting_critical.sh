#!/bin/bash

echo "🚨 CORREÇÃO CRÍTICA - RATE LIMITING"
echo "=================================="

# Commit da correção
git add bot_manager.py
git commit -m "🚨 CRITICAL FIX: Rate limiting usando total_seconds() em vez de seconds

- Corrige bug que permitia spam infinito
- Rate limiting agora funciona corretamente (60s)
- Adiciona log detalhado do tempo restante
- Protege sistema contra sobrecarga"

# Push para produção
git push origin main

echo "✅ Correção aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. tail -f logs/app.log | grep 'Rate limiting'"
