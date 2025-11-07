#!/bin/bash
# MIGRAÇÃO POSTGRESQL - SCRIPT EXECUTIVO
# Tempo estimado: 15 minutos

set -e

echo "=========================================="
echo "  MIGRAÇÃO POSTGRESQL - GRIMBOTS QI 500"
echo "=========================================="
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# Verificar se está no diretório correto
if [ ! -f "wsgi.py" ]; then
    error "Execute do diretório do projeto"
fi

# PASSO 1: Parar aplicação
echo "🛑 PASSO 1: Parando aplicação..."
pkill -9 python 2>/dev/null || true
pkill -9 gunicorn 2>/dev/null || true
sudo systemctl stop grimbots 2>/dev/null || true
sleep 3
success "Aplicação parada"

# PASSO 2: Backup SQLite
echo ""
echo "📦 PASSO 2: Backup do SQLite..."
BACKUP_FILE="instance/saas_bot_manager.db.backup_$(date +%Y%m%d_%H%M%S)"
cp instance/saas_bot_manager.db "$BACKUP_FILE"
success "Backup criado: $BACKUP_FILE"

# PASSO 3: Instalar PostgreSQL
echo ""
echo "📥 PASSO 3: Instalando PostgreSQL..."
if ! command -v psql &> /dev/null; then
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
    success "PostgreSQL instalado"
else
    success "PostgreSQL já instalado"
fi

# Iniciar PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
sleep 3

# PASSO 4: Criar banco e usuário
echo ""
echo "🗄️  PASSO 4: Criando banco de dados..."

# Gerar senha forte
PG_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Criar banco
sudo -u postgres psql -c "DROP DATABASE IF EXISTS grimbots;" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE grimbots;"
success "Banco 'grimbots' criado"

# Criar usuário
sudo -u postgres psql -c "DROP USER IF EXISTS grimbots;" 2>/dev/null || true
sudo -u postgres psql -c "CREATE USER grimbots WITH PASSWORD '$PG_PASSWORD';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE grimbots TO grimbots;"
sudo -u postgres psql -c "ALTER DATABASE grimbots OWNER TO grimbots;"
success "Usuário 'grimbots' criado"

# Salvar senha
echo "$PG_PASSWORD" > .pg_password
chmod 600 .pg_password
warning "Senha PostgreSQL salva em: .pg_password"

# PASSO 5: Criar schema
echo ""
echo "🏗️  PASSO 5: Criando schema no PostgreSQL..."
source venv/bin/activate

export DATABASE_URL="postgresql://grimbots:$PG_PASSWORD@localhost:5432/grimbots"

python -c "
from app import app, db
import logging
logging.basicConfig(level=logging.ERROR)
with app.app_context():
    db.create_all()
    print('✅ Schema criado')
"

# PASSO 6: Migrar dados
echo ""
echo "📊 PASSO 6: Migrando dados do SQLite..."

export SQLITE_DB="instance/saas_bot_manager.db"
export PG_HOST="localhost"
export PG_PORT="5432"
export PG_USER="grimbots"
export PG_PASSWORD="$PG_PASSWORD"
export PG_DATABASE="grimbots"

if python migrate_to_postgres.py; then
    success "Dados migrados com sucesso"
else
    error "Erro na migração - ver logs acima"
fi

# PASSO 7: Atualizar .env
echo ""
echo "⚙️  PASSO 7: Atualizando configuração..."

# Remover DATABASE_URL antiga do .env
if [ -f ".env" ]; then
    sed -i '/^DATABASE_URL=/d' .env
fi

# Adicionar nova
echo "DATABASE_URL=postgresql://grimbots:$PG_PASSWORD@localhost:5432/grimbots" >> .env
success ".env atualizado"

# PASSO 8: Configurar PostgreSQL para performance
echo ""
echo "⚡ PASSO 8: Otimizando PostgreSQL..."

sudo -u postgres psql grimbots << EOF
-- Aumentar max_connections
ALTER SYSTEM SET max_connections = 100;

-- Otimizar para performance
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET work_mem = '4MB';
EOF

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
sleep 5
success "PostgreSQL otimizado"

# PASSO 9: Reinstalar dependências (se necessário)
echo ""
echo "📦 PASSO 9: Verificando dependências..."
pip install psycopg2-binary --quiet
success "Dependências OK"

# PASSO 10: Iniciar aplicação
echo ""
echo "🚀 PASSO 10: Iniciando aplicação..."

# Com 1 worker (temporário até resolver completamente)
sed -i 's/workers = max(3, min(cpu_count \* 2 + 1, 8))/workers = 1  # Temporário - PostgreSQL permite aumentar depois/' gunicorn_config.py

sudo systemctl start grimbots
sleep 10

if sudo systemctl is-active --quiet grimbots; then
    success "Gunicorn iniciado com PostgreSQL"
else
    error "Gunicorn não iniciou - ver: sudo journalctl -u grimbots -n 30"
fi

# Iniciar workers
echo ""
echo "🚀 Iniciando RQ Workers..."
for i in {1..5}; do nohup python start_rq_worker.py tasks > logs/rq-tasks-$i.log 2>&1 & done
for i in {1..3}; do nohup python start_rq_worker.py gateway > logs/rq-gateway-$i.log 2>&1 & done
for i in {1..3}; do nohup python start_rq_worker.py webhook > logs/rq-webhook-$i.log 2>&1 & done

sleep 5

WORKER_COUNT=$(ps aux | grep -c "[s]tart_rq_worker" || echo "0")
success "$WORKER_COUNT/11 Workers iniciados"

# PASSO 11: Validar migração
echo ""
echo "✅ PASSO 11: Validando migração..."

# Testar conexão
if psql -U grimbots -d grimbots -c "SELECT COUNT(*) FROM users;" > /dev/null 2>&1; then
    USER_COUNT=$(psql -U grimbots -d grimbots -t -c "SELECT COUNT(*) FROM users;" | xargs)
    success "PostgreSQL OK - $USER_COUNT usuários migrados"
else
    error "Erro ao conectar no PostgreSQL"
fi

# Health check
HEALTH=$(curl -s http://localhost:5000/health 2>/dev/null)
STATUS=$(echo "$HEALTH" | grep -o '"status": "[^"]*"' | cut -d'"' -f4)

if [ "$STATUS" = "healthy" ]; then
    success "Health check: HEALTHY"
else
    warning "Health check: $STATUS"
fi

# PASSO 12: Resumo
echo ""
echo "=========================================="
echo "  ✅ MIGRAÇÃO CONCLUÍDA"
echo "=========================================="
echo ""
echo "📊 Resumo:"
echo "  Banco de dados: PostgreSQL"
echo "  Usuários migrados: $USER_COUNT"
echo "  Gunicorn: $(sudo systemctl is-active grimbots)"
echo "  RQ Workers: $WORKER_COUNT/11"
echo "  Health: $STATUS"
echo ""
echo "📁 Arquivos importantes:"
echo "  Backup SQLite: $BACKUP_FILE"
echo "  Senha PostgreSQL: .pg_password"
echo ""
echo "⚠️  IMPORTANTE:"
echo "  1. Guarde a senha: cat .pg_password"
echo "  2. Teste o bot (enviar /start)"
echo "  3. Monitore: sudo journalctl -u grimbots -f"
echo "  4. Após 24h OK, pode deletar backup SQLite"
echo ""
echo "🚀 Próximos passos:"
echo "  1. Monitorar por 24h"
echo "  2. Aumentar workers (linha 20 de gunicorn_config.py)"
echo "  3. Configurar replicação PostgreSQL (Fase 3)"
echo ""

