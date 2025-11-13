#!/bin/bash
# Script de Verificação Pré-Deploy - Meta Pixel Tracking
# Execute no servidor antes de fazer deploy

set -e

echo "=========================================="
echo "  VERIFICAÇÃO PRÉ-DEPLOY - META PIXEL"
echo "=========================================="
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

# 1. Verificar schema do banco
echo "1. Verificando schema do banco de dados..."
echo "-------------------------------------------"
psql -c "\d+ payments" | grep -E "tracking_token|fbclid|pageview_event_id|meta_event_id" || true
echo ""

# 2. Verificar tamanhos das colunas
echo "2. Verificando tamanhos das colunas..."
echo "-------------------------------------------"
psql -c "SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name='payments' AND column_name IN ('tracking_token','fbclid','pageview_event_id','meta_event_id');"
echo ""

# 3. Verificar truncamento
echo "3. Verificando truncamento de fbclid..."
echo "-------------------------------------------"
psql -c "SELECT payment_id, length(fbclid) AS fbclid_len, length(tracking_token) AS token_len, length(meta_event_id) AS event_id_len FROM payments WHERE fbclid IS NOT NULL ORDER BY created_at DESC LIMIT 20;"
echo ""

# 4. Verificar payments recentes
echo "4. Verificando payments recentes..."
echo "-------------------------------------------"
psql -c "SELECT payment_id, status, length(tracking_token) AS token_len, length(fbclid) AS fbclid_len, meta_purchase_sent, meta_event_id IS NOT NULL AS has_event_id, created_at FROM payments WHERE created_at >= NOW()-INTERVAL '2 days' ORDER BY created_at DESC LIMIT 20;"
echo ""

# 5. Verificar Redis (pegar token recente)
echo "5. Verificando Redis (últimos 10 tokens)..."
echo "-------------------------------------------"
redis-cli KEYS "tracking:*" | grep -E "^tracking:[a-f0-9]{32}$" | tail -n 10 | while read key; do
    echo "Token: $key"
    redis-cli GET "$key" | python3 -m json.tool 2>/dev/null | head -n 20 || echo "  (erro ao parsear JSON)"
    echo ""
done
echo ""

# 6. Verificar ENCRYPTION_KEY nos workers
echo "6. Verificando ENCRYPTION_KEY nos workers..."
echo "-------------------------------------------"
ps auxww | grep -E 'rq|celery' | grep -v grep | while read line; do
    pid=$(echo $line | awk '{print $2}')
    echo "PID: $pid"
    if [ -f "/proc/$pid/environ" ]; then
        cat /proc/$pid/environ 2>/dev/null | tr '\0' '\n' | grep ENCRYPTION_KEY || warning "ENCRYPTION_KEY não encontrado no processo $pid"
    else
        warning "Não foi possível verificar processo $pid"
    fi
    echo ""
done
echo ""

# 7. Verificar systemd services
echo "7. Verificando systemd services..."
echo "-------------------------------------------"
if systemctl list-units | grep -q start_rq_worker; then
    systemctl show start_rq_worker.service | grep -E "Environment|EnvironmentFile" || warning "ENCRYPTION_KEY não configurado no systemd"
fi
if systemctl list-units | grep -q celery; then
    systemctl show celery.service | grep -E "Environment|EnvironmentFile" || warning "ENCRYPTION_KEY não configurado no systemd"
fi
echo ""

# 8. Verificar código (creation_time)
echo "8. Verificando código (creation_time)..."
echo "-------------------------------------------"
if grep -r "creation_time" app.py utils/meta_pixel.py 2>/dev/null; then
    error "creation_time ainda presente no código!"
else
    success "creation_time não encontrado no código"
fi
echo ""

# 9. Verificar idempotência
echo "9. Verificando idempotência (meta_purchase_sent check)..."
echo "-------------------------------------------"
if grep -A 5 "def send_meta_pixel_purchase_event" app.py | grep -q "meta_purchase_sent"; then
    success "Verificação de meta_purchase_sent encontrada"
else
    error "Verificação de meta_purchase_sent NÃO encontrada!"
fi
echo ""

echo "=========================================="
echo "  VERIFICAÇÃO CONCLUÍDA"
echo "=========================================="

