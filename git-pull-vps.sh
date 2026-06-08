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

echo "📦 Passo 5: Instalando dependências (inclui novas adições ao requirements.txt)..."
/root/grimbots/venv/bin/pip install -r requirements.txt

echo "🗄️ Passo 6: Aplicando migrações de banco de dados (índices de performance)..."
if command -v psql &>/dev/null; then
    /root/grimbots/venv/bin/python -c "
import os, re
url = os.environ.get('DATABASE_URL', '')
m = re.match(r'postgresql://(.+):(.+)@(.+)/(.+)', url)
if m:
    print(f'psql -h {m.group(3)} -U {m.group(1)} -d {m.group(4)} -f /root/grimbots/deploy/sql/create_indexes.sql')
else:
    print('⚠️ DATABASE_URL não reconhecida — execute o SQL manualmente: psql -d <db> -f deploy/sql/create_indexes.sql')
" 2>/dev/null | bash 2>/dev/null || echo "   ⚠️ Migração SQL manual necessária: psql -d <db> -f deploy/sql/create_indexes.sql"
else
    echo "   ⚠️ psql não encontrado — migração manual: psql -d <db> -f deploy/sql/create_indexes.sql"
fi

echo ""
echo "=============================================="
echo "✅ Código atualizado com sucesso!"
echo "📋 Próximo passo: sudo bash restart-system.sh"
echo "=============================================="
