#!/bin/bash

echo "🔍 Iniciando sincronização com o repositório..."

echo "🗑️ Passo 1: Descartando TODAS as mudanças locais (Hard Reset)..."
git reset --hard HEAD

echo "🧹 Passo 2: Removendo arquivos de cache temporários do Python..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "🧹 Passo 3: Limpando arquivos não rastreados (Protegendo logs, .env e venv)..."
git clean -fd -e logs/ -e .env -e venv/

echo "⬇️ Passo 4: Fazendo pull do repositório principal..."
git pull origin main

echo "✅ PRONTO! Repositório atualizado com sucesso!"
