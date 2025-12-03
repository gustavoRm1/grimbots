#!/bin/bash

# 🔥 DIAGNÓSTICO COMPLETO META PURCHASE - VPS
# Execute este script na VPS para coletar dados REAIS do sistema

echo "=========================================="
echo "🔍 DIAGNÓSTICO META PURCHASE TRACKING"
echo "=========================================="
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para imprimir seção
print_section() {
    echo ""
    echo -e "${BLUE}=========================================="
    echo -e "📊 $1"
    echo -e "==========================================${NC}"
    echo ""
}

# 1. ANÁLISE DO BANCO DE DADOS
print_section "1. ANÁLISE DO BANCO DE DADOS"

# Configurar conexão do banco (ajuste conforme seu ambiente)
DB_NAME="${DB_NAME:-grimbots}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PASSWORD="${DB_PASSWORD:-123sefudeu}"

# Configurar PGPASSWORD para evitar prompts
export PGPASSWORD="$DB_PASSWORD"

# Verificar se psql está disponível
if command -v psql &> /dev/null; then
    echo "✅ PostgreSQL client encontrado"
    echo "📋 Configuração: DB=$DB_NAME USER=$DB_USER HOST=$DB_HOST"
    
    # Query 1: Total de payments 'paid' dos últimos 7 dias
    echo ""
    echo "📊 Payments 'paid' dos últimos 7 dias:"
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
    SELECT 
        COUNT(*) as total_payments,
        COUNT(delivery_token) as with_delivery_token,
        COUNT(CASE WHEN delivery_token IS NOT NULL THEN 1 END) as has_delivery_token,
        COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as meta_purchase_sent_count,
        COUNT(CASE WHEN delivery_token IS NOT NULL AND meta_purchase_sent = false THEN 1 END) as delivery_token_but_no_purchase,
        COUNT(CASE WHEN delivery_token IS NULL THEN 1 END) as missing_delivery_token
    FROM payments
    WHERE status = 'paid'
    AND created_at >= NOW() - INTERVAL '7 days';
    " 2>/dev/null || echo "❌ Erro ao conectar ao banco"
    
    # Query 2: Análise por pool
    echo ""
    echo "📊 Análise por Pool (configuração Meta Pixel):"
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
    SELECT 
        rp.id as pool_id,
        rp.name as pool_name,
        rp.meta_tracking_enabled,
        CASE WHEN rp.meta_pixel_id IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as has_pixel_id,
        CASE WHEN rp.meta_access_token IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as has_access_token,
        rp.meta_events_purchase,
        COUNT(DISTINCT pb.bot_id) as bots_count,
        COUNT(DISTINCT p.id) as payments_count,
        COUNT(DISTINCT CASE WHEN p.meta_purchase_sent = true THEN p.id END) as purchases_sent
    FROM redirect_pools rp
    LEFT JOIN pool_bots pb ON pb.pool_id = rp.id
    LEFT JOIN payments p ON p.bot_id = pb.bot_id AND p.status = 'paid' AND p.created_at >= NOW() - INTERVAL '7 days'
    GROUP BY rp.id, rp.name, rp.meta_tracking_enabled, rp.meta_pixel_id, rp.meta_access_token, rp.meta_events_purchase
    ORDER BY payments_count DESC;
    " 2>/dev/null || echo "❌ Erro ao conectar ao banco"
    
    # Query 3: Payments problemáticos (tem delivery_token mas não tem meta_purchase_sent)
    echo ""
    echo "📊 Payments com delivery_token mas SEM meta_purchase_sent (TOP 20):"
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
    SELECT 
        p.id,
        p.payment_id,
        p.amount,
        p.created_at,
        p.delivery_token IS NOT NULL as has_delivery_token,
        p.meta_purchase_sent,
        b.id as bot_id,
        pb.pool_id,
        rp.name as pool_name,
        rp.meta_tracking_enabled,
        rp.meta_events_purchase,
        CASE WHEN rp.meta_pixel_id IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as pool_has_pixel_id,
        CASE WHEN rp.meta_access_token IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as pool_has_access_token
    FROM payments p
    JOIN bots b ON b.id = p.bot_id
    LEFT JOIN pool_bots pb ON pb.bot_id = b.id
    LEFT JOIN redirect_pools rp ON rp.id = pb.pool_id
    WHERE p.status = 'paid'
    AND p.delivery_token IS NOT NULL
    AND (p.meta_purchase_sent = false OR p.meta_purchase_sent IS NULL)
    AND p.created_at >= NOW() - INTERVAL '7 days'
    ORDER BY p.created_at DESC
    LIMIT 20;
    " 2>/dev/null || echo "❌ Erro ao conectar ao banco"
    
else
    echo "⚠️ PostgreSQL client não encontrado. Pulando análise do banco."
fi

# 2. ANÁLISE DE LOGS
print_section "2. ANÁLISE DE LOGS (ÚLTIMAS 1000 LINHAS)"

LOG_FILE="${LOG_FILE:-/var/log/grimbots/app.log}"

if [ -f "$LOG_FILE" ]; then
    echo "📄 Arquivo de log: $LOG_FILE"
    echo ""
    
    echo "❌ ERROS relacionados a Purchase não enviado:"
    grep -i "purchase.*não.*enviado\|purchase.*não foi\|meta.*purchase.*não\|PROBLEMA RAIZ.*Purchase" "$LOG_FILE" | tail -20 || echo "  Nenhum erro encontrado"
    
    echo ""
    echo "⚠️ WARNINGS relacionados a Purchase:"
    grep -i "warning.*purchase\|purchase.*warning" "$LOG_FILE" | tail -20 || echo "  Nenhum warning encontrado"
    
    echo ""
    echo "✅ Purchase enviados com sucesso:"
    grep -i "purchase.*enfileirado\|purchase.*enviado\|meta.*purchase.*sucesso" "$LOG_FILE" | tail -20 || echo "  Nenhum log de sucesso encontrado"
    
    echo ""
    echo "🔍 Logs de delivery_page (últimos 50):"
    grep -i "delivery.*payment\|delivery_page" "$LOG_FILE" | tail -50 || echo "  Nenhum log encontrado"
    
else
    echo "⚠️ Arquivo de log não encontrado em $LOG_FILE"
    echo "📋 Tentando encontrar arquivo de log..."
    find /var/log -name "*grimbots*" -o -name "*app.log*" 2>/dev/null | head -5
fi

# 3. ANÁLISE DO CELERY
print_section "3. ANÁLISE DO CELERY"

if command -v celery &> /dev/null; then
    echo "✅ Celery encontrado"
    
    # Verificar workers ativos
    echo ""
    echo "👷 Workers ativos:"
    celery -A celery_app inspect active 2>/dev/null || echo "  Não foi possível verificar workers"
    
    # Verificar tasks falhadas
    echo ""
    echo "❌ Tasks falhadas (últimas 10):"
    celery -A celery_app inspect reserved 2>/dev/null | grep -i "send_meta_event\|purchase" || echo "  Nenhuma task relacionada encontrada"
    
else
    echo "⚠️ Celery não encontrado no PATH"
fi

# Verificar se há processos Celery rodando
echo ""
echo "🔍 Processos Celery rodando:"
ps aux | grep -i celery | grep -v grep || echo "  Nenhum processo Celery encontrado"

# 4. ANÁLISE DO REDIS
print_section "4. ANÁLISE DO REDIS"

if command -v redis-cli &> /dev/null; then
    REDIS_HOST="${REDIS_HOST:-localhost}"
    REDIS_PORT="${REDIS_PORT:-6379}"
    
    echo "✅ Redis client encontrado"
    
    # Verificar conexão
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &> /dev/null; then
        echo "✅ Redis está respondendo"
        
        # Contar tracking tokens no Redis
        echo ""
        echo "🔑 Tracking tokens no Redis:"
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --scan --pattern "tracking:*" | wc -l | xargs echo "  Total de keys 'tracking:*':"
        
        # Verificar tamanho do Redis
        echo ""
        echo "💾 Tamanho do Redis:"
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" INFO memory | grep -E "used_memory_human|used_memory_peak_human" || echo "  Não foi possível obter informações"
        
    else
        echo "❌ Redis não está respondendo em $REDIS_HOST:$REDIS_PORT"
    fi
else
    echo "⚠️ Redis client não encontrado"
fi

# 5. ANÁLISE DE CONFIGURAÇÃO DOS POOLS
print_section "5. ANÁLISE DE CONFIGURAÇÃO DOS POOLS"

if command -v psql &> /dev/null; then
    echo "📊 Resumo de configuração dos pools:"
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
    SELECT 
        COUNT(*) as total_pools,
        COUNT(CASE WHEN meta_tracking_enabled = true THEN 1 END) as pools_with_meta_tracking,
        COUNT(CASE WHEN meta_pixel_id IS NOT NULL THEN 1 END) as pools_with_pixel_id,
        COUNT(CASE WHEN meta_access_token IS NOT NULL THEN 1 END) as pools_with_access_token,
        COUNT(CASE WHEN meta_events_purchase = true THEN 1 END) as pools_with_purchase_enabled,
        COUNT(CASE WHEN meta_tracking_enabled = true AND meta_pixel_id IS NOT NULL AND meta_access_token IS NOT NULL AND meta_events_purchase = true THEN 1 END) as pools_fully_configured
    FROM redirect_pools;
    " 2>/dev/null || echo "❌ Erro ao conectar ao banco"
    
    echo ""
    echo "📊 Pools com configuração incompleta:"
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
    SELECT 
        id,
        name,
        meta_tracking_enabled,
        CASE WHEN meta_pixel_id IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as has_pixel_id,
        CASE WHEN meta_access_token IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as has_access_token,
        meta_events_purchase,
        CASE 
            WHEN meta_tracking_enabled = true AND (meta_pixel_id IS NULL OR meta_access_token IS NULL) THEN '❌ Tracking ativo mas falta pixel_id ou access_token'
            WHEN meta_tracking_enabled = true AND meta_pixel_id IS NOT NULL AND meta_access_token IS NOT NULL AND meta_events_purchase = false THEN '❌ Pixel configurado mas Purchase Event desabilitado'
            WHEN meta_tracking_enabled = false THEN '⚠️ Tracking desabilitado'
            ELSE '✅ OK'
        END as status
    FROM redirect_pools
    WHERE meta_tracking_enabled = true
    AND (meta_pixel_id IS NULL OR meta_access_token IS NULL OR meta_events_purchase = false)
    ORDER BY name;
    " 2>/dev/null || echo "❌ Erro ao conectar ao banco"
fi

# 6. ANÁLISE DE BOTS SEM POOL
print_section "6. BOTS SEM POOL ASSOCIADO"

if command -v psql &> /dev/null; then
    echo "📊 Bots que têm payments 'paid' mas não estão associados a nenhum pool:"
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
    SELECT 
        b.id as bot_id,
        b.username as bot_username,
        COUNT(p.id) as payments_count,
        COUNT(CASE WHEN p.delivery_token IS NOT NULL THEN 1 END) as with_delivery_token,
        COUNT(CASE WHEN p.meta_purchase_sent = true THEN 1 END) as purchases_sent
    FROM bots b
    JOIN payments p ON p.bot_id = b.id
    LEFT JOIN pool_bots pb ON pb.bot_id = b.id
    WHERE p.status = 'paid'
    AND p.created_at >= NOW() - INTERVAL '7 days'
    AND pb.id IS NULL
    GROUP BY b.id, b.username
    ORDER BY payments_count DESC
    LIMIT 10;
    " 2>/dev/null || echo "❌ Erro ao conectar ao banco"
fi

# 7. ANÁLISE DE WEBHOOKS
print_section "7. ANÁLISE DE WEBHOOKS (ÚLTIMAS 24H)"

if [ -f "$LOG_FILE" ]; then
    echo "📄 Webhooks recebidos relacionados a payments 'paid':"
    grep -i "webhook.*paid\|status.*paid\|payment.*confirmed" "$LOG_FILE" | grep -v "❌\|ERRO\|ERROR" | tail -30 || echo "  Nenhum webhook encontrado"
    
    echo ""
    echo "📄 Chamadas de send_payment_delivery:"
    grep -i "send_payment_delivery\|send_deliverable" "$LOG_FILE" | tail -20 || echo "  Nenhuma chamada encontrada"
fi

# 8. RESUMO FINAL
print_section "8. RESUMO FINAL"

if command -v psql &> /dev/null; then
    echo "📊 RESUMO EXECUTIVO:"
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
    WITH payment_stats AS (
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN delivery_token IS NOT NULL THEN 1 END) as with_delivery_token,
            COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as purchase_sent,
            COUNT(CASE WHEN delivery_token IS NOT NULL AND (meta_purchase_sent = false OR meta_purchase_sent IS NULL) THEN 1 END) as problem_count
        FROM payments
        WHERE status = 'paid'
        AND created_at >= NOW() - INTERVAL '7 days'
    ),
    pool_stats AS (
        SELECT 
            COUNT(DISTINCT rp.id) as total_pools,
            COUNT(DISTINCT CASE WHEN rp.meta_tracking_enabled = true AND rp.meta_pixel_id IS NOT NULL AND rp.meta_access_token IS NOT NULL AND rp.meta_events_purchase = true THEN rp.id END) as pools_ready
        FROM redirect_pools rp
    )
    SELECT 
        ps.total as \"Total Payments (7 dias)\",
        ps.with_delivery_token as \"Com delivery_token\",
        ps.purchase_sent as \"Purchase enviado\",
        ps.problem_count as \"❌ PROBLEMA: delivery_token mas SEM purchase\",
        ROUND((ps.purchase_sent::numeric / NULLIF(ps.total, 0) * 100), 2) as \"Taxa de envio (%)\",
        pst.total_pools as \"Total Pools\",
        pst.pools_ready as \"Pools configurados corretamente\"
    FROM payment_stats ps
    CROSS JOIN pool_stats pst;
    " 2>/dev/null || echo "❌ Erro ao conectar ao banco"
fi

echo ""
echo -e "${GREEN}=========================================="
echo -e "✅ DIAGNÓSTICO COMPLETO"
echo -e "==========================================${NC}"
echo ""
echo "📋 Próximos passos:"
echo "1. Analise os dados acima"
echo "2. Identifique padrões de falha"
echo "3. Corrija a causa raiz identificada"
echo ""

