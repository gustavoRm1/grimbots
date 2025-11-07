#!/bin/bash
# Detectar e iniciar PostgreSQL com nome correto do service

echo "🔍 Detectando serviço PostgreSQL..."

# Tentar diferentes nomes de serviço
if systemctl list-units --type=service | grep -q "postgresql@"; then
    # PostgreSQL com versão específica (ex: postgresql@14-main)
    PG_SERVICE=$(systemctl list-units --type=service | grep "postgresql@" | awk '{print $1}' | head -1)
    echo "✅ Serviço encontrado: $PG_SERVICE"
elif systemctl list-units --type=service | grep -q "postgresql.service"; then
    PG_SERVICE="postgresql.service"
    echo "✅ Serviço encontrado: $PG_SERVICE"
elif systemctl list-unit-files | grep -q "postgresql"; then
    PG_SERVICE=$(systemctl list-unit-files | grep "postgresql" | awk '{print $1}' | head -1)
    echo "✅ Serviço encontrado: $PG_SERVICE"
else
    echo "❌ Nenhum serviço PostgreSQL encontrado"
    echo "Tentando iniciar diretamente..."
    
    # Tentar iniciar cluster manualmente
    PG_VERSION=$(ls /etc/postgresql/ | head -1)
    if [ -n "$PG_VERSION" ]; then
        echo "Versão encontrada: $PG_VERSION"
        sudo pg_ctlcluster $PG_VERSION main start
        echo "✅ PostgreSQL iniciado via pg_ctlcluster"
    else
        echo "❌ PostgreSQL não instalado corretamente"
        exit 1
    fi
    exit 0
fi

# Iniciar serviço
echo "Iniciando $PG_SERVICE..."
sudo systemctl start $PG_SERVICE
sudo systemctl enable $PG_SERVICE

sleep 3

# Verificar
if sudo systemctl is-active --quiet $PG_SERVICE 2>/dev/null; then
    echo "✅ PostgreSQL rodando"
else
    # Tentar método alternativo
    echo "⚠️ Systemctl falhou, tentando pg_ctlcluster..."
    PG_VERSION=$(ls /etc/postgresql/ | head -1)
    if [ -n "$PG_VERSION" ]; then
        sudo pg_ctlcluster $PG_VERSION main start
        echo "✅ PostgreSQL iniciado"
    fi
fi

# Testar conexão
if sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ PostgreSQL acessível"
else
    echo "❌ PostgreSQL não acessível"
    exit 1
fi

