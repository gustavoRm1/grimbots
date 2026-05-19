#!/usr/bin/env bash
set -euo pipefail

# Script para fazer pull do repositório sem conflitos
# Descartar mudanças locais não commitadas e fazer pull

cd "$(dirname "$0")"

echo "📥 Atualizando repositório..."

# 1. Verificar status atual
echo "📊 Status atual do repositório:"
git status --short

# 2. Descartar mudanças locais não commitadas
echo "🗑️  Descartando mudanças locais não commitadas..."
git reset --hard HEAD

# 3. Limpar arquivos não rastreados (exceto logs e arquivos importantes)
echo "🧹 Limpando arquivos não rastreados..."
git clean -fd -e logs/ -e .env -e venv/ -e *.pid

# 4. Fazer pull
echo "⬇️  Fazendo pull do repositório..."
git pull origin main

# 5. Verificar se há conflitos
if [ $? -eq 0 ]; then
    echo "✅ Repositório atualizado com sucesso!"
    echo ""
    echo "📋 Últimos commits:"
    git log --oneline -5
else
    echo "❌ Erro ao fazer pull. Verifique os logs acima."
    exit 1
fi

