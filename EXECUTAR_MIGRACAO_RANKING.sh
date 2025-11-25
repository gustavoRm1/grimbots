#!/bin/bash
# Script para executar migração de campos do ranking
# Adiciona ranking_display_name e ranking_first_visit_handled na tabela users

set -e

echo "=========================================="
echo "  MIGRAÇÃO: Campos de Nome no Ranking"
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

# Detectar tipo de banco
if [ -z "$DATABASE_URL" ]; then
    # Tentar ler do .env
    if [ -f ".env" ]; then
        export DATABASE_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2- | tr -d '"' || echo "")
    fi
fi

if [ -z "$DATABASE_URL" ]; then
    error "DATABASE_URL não configurada. Configure em .env ou variável de ambiente."
fi

echo "📊 DATABASE_URL detectada: ${DATABASE_URL:0:30}..."
echo ""

# Extrair credenciais do PostgreSQL
if [[ "$DATABASE_URL" == postgresql://* ]]; then
    # PostgreSQL
    echo "🗄️  Banco detectado: PostgreSQL"
    
    # Extrair informações da URL
    # Formato: postgresql://user:password@host:port/database
    DB_INFO=$(echo "$DATABASE_URL" | sed 's|postgresql://||' | sed 's|/@|/|')
    DB_USER=$(echo "$DB_INFO" | cut -d':' -f1)
    DB_PASS=$(echo "$DB_INFO" | cut -d':' -f2 | cut -d'@' -f1)
    DB_HOST_PORT=$(echo "$DB_INFO" | cut -d'@' -f2 | cut -d'/' -f1)
    DB_HOST=$(echo "$DB_HOST_PORT" | cut -d':' -f1)
    DB_PORT=$(echo "$DB_HOST_PORT" | cut -d':' -f2)
    DB_NAME=$(echo "$DB_INFO" | cut -d'/' -f2)
    
    # Usar porta padrão se não especificada
    if [ -z "$DB_PORT" ] || [ "$DB_PORT" == "$DB_HOST" ]; then
        DB_PORT="5432"
    fi
    
    echo "   Host: $DB_HOST"
    echo "   Port: $DB_PORT"
    echo "   Database: $DB_NAME"
    echo "   User: $DB_USER"
    echo ""
    
    # Executar migração SQL
    echo "🔄 Executando migração SQL..."
    export PGPASSWORD="$DB_PASS"
    
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f scripts/migration_add_ranking_display_name.sql; then
        success "Migração executada com sucesso!"
    else
        error "Erro ao executar migração SQL"
    fi
    
    # Verificar colunas
    echo ""
    echo "🔍 Verificando colunas criadas..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name IN ('ranking_display_name', 'ranking_first_visit_handled');
    "
    
    success "Migração concluída!"
    
elif [[ "$DATABASE_URL" == sqlite://* ]]; then
    # SQLite
    echo "🗄️  Banco detectado: SQLite"
    warning "SQLite detectado. Executando migração via Python..."
    
    # Executar script Python
    if python migrations/add_ranking_display_name_fields.py; then
        success "Migração executada com sucesso!"
    else
        error "Erro ao executar migração Python"
    fi
    
else
    error "Tipo de banco não suportado ou DATABASE_URL inválida"
fi

echo ""
echo "=========================================="
echo "✅ Migração finalizada!"
echo "=========================================="

