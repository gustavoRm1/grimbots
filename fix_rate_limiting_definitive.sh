#!/bin/bash

echo "🚨 CORREÇÃO DEFINITIVA - RATE LIMITING COM CACHE"
echo "================================================"

# Commit da correção definitiva
git add bot_manager.py
git commit -m "🚨 DEFINITIVE FIX: Rate limiting com cache em memória

- Usa cache em memória em vez de banco de dados
- Evita problema do SQLAlchemy onupdate automático
- Rate limiting real e eficiente
- Proteção definitiva contra spam"

# Push para produção
git push origin main

echo "✅ Correção DEFINITIVA aplicada!"
echo "📋 Próximos passos na VPS:"
echo "1. git pull origin main"
echo "2. sudo systemctl restart grimbots"
echo "3. Teste: digite mensagens rapidamente"
echo "4. Deve aparecer: Rate limiting bloqueado"
