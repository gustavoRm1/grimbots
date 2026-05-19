#!/usr/bin/env bash
# Script para fazer git pull na VPS sem erros
# Resolve problema de "unstaged changes" automaticamente

cd ~/grimbots || cd /root/grimbots || exit 1

echo "🔍 Verificando quais arquivos estão causando problema..."
git status --short

echo ""
echo "🗑️  Passo 1: Descartando TODAS as mudanças locais..."
git reset --hard HEAD

echo ""
echo "🧹 Passo 2: Removendo arquivos temporários..."
rm -f gateway_umbrellapag_fixed.py reenqueue_atomopay.py grimbots.pid nohup.out 2>/dev/null || true

echo ""
echo "🧹 Passo 3: Limpando arquivos não rastreados (exceto logs, .env, venv, .git-pull-vps.sh)..."
git clean -fd -e logs/ -e .env -e venv/ -e "*.pid" -e nohup.out -e "*.log" -e "*.pyc" -e "__pycache__" -e ".git-pull-vps.sh" 2>/dev/null || true

echo ""
echo "⬇️  Passo 4: Fazendo pull do repositório..."
if git pull origin main; then
    echo "✅ Pull realizado com sucesso!"
else
    echo "⚠️  Tentando forçar atualização..."
    git fetch origin main
    git reset --hard origin/main
    echo "✅ Repositório atualizado forçadamente!"
fi

echo ""
echo "📋 Status final:"
git status --short

echo ""
echo "✅ PRONTO! Repositório atualizado com sucesso!"
