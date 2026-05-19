#!/bin/bash

# 🔥 DIAGNÓSTICO ESPECÍFICO - POOL "red1" (VERSÃO DETALHADA)
# Execute: ./diagnostico_pool_red1_detalhado.sh

echo "=========================================="
echo "🔍 DIAGNÓSTICO POOL 'red1' - ANÁLISE DETALHADA"
echo "=========================================="
echo ""

# Configuração
DB_NAME="${DB_NAME:-grimbots}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PASSWORD="${DB_PASSWORD:-123sefudeu}"
export PGPASSWORD="$DB_PASSWORD"

print_section() {
    echo ""
    echo "=========================================="
    echo "📊 $1"
    echo "=========================================="
    echo ""
}

# 1. PAYMENTS DE HOJE - ANÁLISE DETALHADA
print_section "1. PAYMENTS DE HOJE - ANÁLISE DETALHADA"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    COUNT(*) as total_payments,
    COUNT(CASE WHEN delivery_token IS NOT NULL THEN 1 END) as with_delivery_token,
    COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as meta_purchase_sent_true,
    COUNT(CASE WHEN meta_purchase_sent = false THEN 1 END) as meta_purchase_sent_false,
    COUNT(CASE WHEN meta_purchase_sent IS NULL THEN 1 END) as meta_purchase_sent_null,
    COUNT(CASE WHEN delivery_token IS NOT NULL AND meta_purchase_sent = true THEN 1 END) as delivery_token_and_sent,
    COUNT(CASE WHEN delivery_token IS NOT NULL AND (meta_purchase_sent = false OR meta_purchase_sent IS NULL) THEN 1 END) as delivery_token_but_not_sent,
    COUNT(CASE WHEN delivery_token IS NULL AND meta_purchase_sent = true THEN 1 END) as no_delivery_token_but_sent
FROM payments p
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE rp.slug = 'red1'
AND p.status = 'paid'
AND DATE(p.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') = CURRENT_DATE;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 2. PAYMENTS RECENTES (ÚLTIMAS 24H) - ANÁLISE POR HORA
print_section "2. PAYMENTS ÚLTIMAS 24H - ANÁLISE POR HORA"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    DATE_TRUNC('hour', p.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') as hora,
    COUNT(*) as total,
    COUNT(CASE WHEN delivery_token IS NOT NULL THEN 1 END) as with_delivery_token,
    COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as purchase_sent,
    COUNT(CASE WHEN delivery_token IS NOT NULL AND (meta_purchase_sent = false OR meta_purchase_sent IS NULL) THEN 1 END) as problema
FROM payments p
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE rp.slug = 'red1'
AND p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', p.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')
ORDER BY hora DESC
LIMIT 24;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 3. PAYMENTS COM PROBLEMA (TOP 100) - DETALHADO
print_section "3. PAYMENTS COM PROBLEMA - DETALHADO (TOP 100)"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    p.id,
    p.payment_id,
    p.amount,
    p.created_at,
    p.bot_id,
    b.name as bot_name,
    p.delivery_token IS NOT NULL as has_delivery_token,
    p.meta_purchase_sent,
    p.tracking_token,
    CASE 
        WHEN p.tracking_token IS NULL THEN '❌ Sem tracking_token'
        WHEN p.tracking_token LIKE 'tracking_%' THEN '❌ Token GERADO (não do redirect)'
        WHEN LENGTH(p.tracking_token) = 32 THEN '✅ Token UUID (do redirect)'
        ELSE '⚠️ Formato desconhecido'
    END as token_status,
    bu.tracking_session_id IS NOT NULL as has_bot_user_tracking_session,
    bu.tracking_session_id
FROM payments p
JOIN bots b ON b.id = p.bot_id
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
LEFT JOIN bot_users bu ON bu.bot_id = p.bot_id AND bu.telegram_user_id = REPLACE(p.customer_user_id, 'user_', '')
WHERE rp.slug = 'red1'
AND p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
AND p.delivery_token IS NOT NULL
AND (p.meta_purchase_sent = false OR p.meta_purchase_sent IS NULL)
ORDER BY p.created_at DESC
LIMIT 100;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 4. VERIFICAR SE PAYMENTS FORAM ACESSADOS NO /delivery
print_section "4. VERIFICAR ACESSO AO /delivery"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    COUNT(*) as total_with_delivery_token,
    COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as purchase_sent,
    COUNT(CASE WHEN meta_purchase_sent = false OR meta_purchase_sent IS NULL THEN 1 END) as purchase_not_sent,
    COUNT(CASE WHEN purchase_sent_from_delivery = true THEN 1 END) as accessed_delivery_page,
    COUNT(CASE WHEN purchase_sent_from_delivery = false OR purchase_sent_from_delivery IS NULL THEN 1 END) as not_accessed_delivery_page
FROM payments p
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE rp.slug = 'red1'
AND p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
AND p.delivery_token IS NOT NULL;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 5. ANÁLISE DE BOT_USER.TRACKING_SESSION_ID
print_section "5. ANÁLISE DE BOT_USER.TRACKING_SESSION_ID"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    COUNT(DISTINCT p.id) as payments_count,
    COUNT(CASE WHEN bu.tracking_session_id IS NOT NULL THEN 1 END) as has_tracking_session_id,
    COUNT(CASE WHEN bu.tracking_session_id IS NULL THEN 1 END) as no_tracking_session_id,
    COUNT(CASE WHEN bu.tracking_session_id LIKE 'tracking_%' THEN 1 END) as tracking_session_id_gerado,
    COUNT(CASE WHEN bu.tracking_session_id IS NOT NULL AND LENGTH(bu.tracking_session_id) = 32 THEN 1 END) as tracking_session_id_uuid
FROM payments p
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
LEFT JOIN bot_users bu ON bu.bot_id = p.bot_id AND bu.telegram_user_id = REPLACE(p.customer_user_id, 'user_', '')
WHERE rp.slug = 'red1'
AND p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
AND p.delivery_token IS NOT NULL;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 6. RESUMO EXECUTIVO COMPLETO
print_section "6. RESUMO EXECUTIVO COMPLETO"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
WITH stats AS (
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN p.delivery_token IS NOT NULL THEN 1 END) as with_delivery_token,
        COUNT(CASE WHEN p.meta_purchase_sent = true THEN 1 END) as purchase_sent,
        COUNT(CASE WHEN p.delivery_token IS NOT NULL AND p.meta_purchase_sent = true THEN 1 END) as delivery_token_and_sent,
        COUNT(CASE WHEN p.delivery_token IS NOT NULL AND (p.meta_purchase_sent = false OR p.meta_purchase_sent IS NULL) THEN 1 END) as delivery_token_but_not_sent
    FROM payments p
    JOIN pool_bots pb ON pb.bot_id = p.bot_id
    JOIN redirect_pools rp ON rp.id = pb.pool_id
    WHERE rp.slug = 'red1'
    AND p.status = 'paid'
    AND p.created_at >= NOW() - INTERVAL '24 hours'
)
SELECT 
    total as \"Total Payments (24h)\",
    with_delivery_token as \"Com delivery_token\",
    purchase_sent as \"Purchase enviado (total)\",
    delivery_token_and_sent as \"✅ OK: delivery_token + purchase enviado\",
    delivery_token_but_not_sent as \"❌ PROBLEMA: delivery_token mas SEM purchase\",
    ROUND((delivery_token_and_sent::numeric / NULLIF(with_delivery_token, 0) * 100), 2) as \"Taxa envio (%)\"
FROM stats;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

echo ""
echo "=========================================="
echo "✅ DIAGNÓSTICO COMPLETO"
echo "=========================================="
echo ""

