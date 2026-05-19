#!/bin/bash

# 🔥 DIAGNÓSTICO ESPECÍFICO - POOL "red1"
# Execute: ./diagnostico_pool_red1.sh

echo "=========================================="
echo "🔍 DIAGNÓSTICO POOL 'red1' - VENDAS NÃO MARCADAS"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuração
DB_NAME="${DB_NAME:-grimbots}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PASSWORD="${DB_PASSWORD:-123sefudeu}"
export PGPASSWORD="$DB_PASSWORD"

print_section() {
    echo ""
    echo -e "${BLUE}=========================================="
    echo -e "📊 $1"
    echo -e "==========================================${NC}"
    echo ""
}

# 1. INFORMAÇÕES DO POOL "red1"
print_section "1. CONFIGURAÇÃO DO POOL 'red1'"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    id,
    user_id,
    name,
    slug,
    meta_tracking_enabled,
    meta_pixel_id,
    CASE WHEN meta_access_token IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as has_access_token,
    meta_events_purchase,
    CASE 
        WHEN meta_tracking_enabled = true AND meta_pixel_id IS NOT NULL AND meta_access_token IS NOT NULL AND meta_events_purchase = true THEN '✅ CONFIGURADO CORRETAMENTE'
        WHEN meta_tracking_enabled = false THEN '❌ Tracking DESABILITADO'
        WHEN meta_pixel_id IS NULL THEN '❌ Falta Pixel ID'
        WHEN meta_access_token IS NULL THEN '❌ Falta Access Token'
        WHEN meta_events_purchase = false THEN '❌ Purchase Event DESABILITADO'
        ELSE '⚠️ Configuração incompleta'
    END as status_configuracao
FROM redirect_pools
WHERE slug = 'red1' OR name ILIKE '%red1%'
ORDER BY id;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 2. BOTS ASSOCIADOS AO POOL "red1"
print_section "2. BOTS ASSOCIADOS AO POOL 'red1'"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    pb.id as pool_bot_id,
    pb.bot_id,
    b.name as bot_name,
    b.username as bot_username,
    b.user_id as bot_user_id,
    pb.pool_id,
    rp.name as pool_name,
    rp.user_id as pool_user_id,
    CASE WHEN b.user_id = rp.user_id THEN '✅ OK' ELSE '❌ CONFLITO: Bot e Pool de usuários diferentes!' END as user_match
FROM pool_bots pb
JOIN bots b ON b.id = pb.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE rp.slug = 'red1' OR rp.name ILIKE '%red1%'
ORDER BY pb.bot_id;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 3. PAYMENTS DO POOL "red1" (HOJE)
print_section "3. PAYMENTS DO POOL 'red1' - HOJE"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    COUNT(*) as total_payments,
    COUNT(CASE WHEN delivery_token IS NOT NULL THEN 1 END) as with_delivery_token,
    COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as meta_purchase_sent,
    COUNT(CASE WHEN delivery_token IS NOT NULL AND (meta_purchase_sent = false OR meta_purchase_sent IS NULL) THEN 1 END) as problema_count
FROM payments p
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE rp.slug = 'red1' OR rp.name ILIKE '%red1%'
AND p.status = 'paid'
AND DATE(p.created_at) = CURRENT_DATE;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 4. PAYMENTS PROBLEMÁTICOS (TOP 50)
print_section "4. PAYMENTS PROBLEMÁTICOS - POOL 'red1' (TOP 50)"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    p.id,
    p.payment_id,
    p.amount,
    p.created_at,
    p.bot_id,
    b.user_id as bot_user_id,
    pb.pool_id,
    rp.name as pool_name,
    rp.user_id as pool_user_id,
    rp.meta_tracking_enabled,
    rp.meta_events_purchase,
    CASE WHEN rp.meta_pixel_id IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as pool_has_pixel_id,
    CASE WHEN rp.meta_access_token IS NOT NULL THEN 'SIM' ELSE 'NÃO' END as pool_has_access_token,
    p.delivery_token IS NOT NULL as has_delivery_token,
    p.meta_purchase_sent,
    CASE 
        WHEN b.user_id != rp.user_id THEN '❌ Bot e Pool de usuários diferentes!'
        WHEN rp.meta_tracking_enabled = false THEN '❌ Tracking desabilitado'
        WHEN rp.meta_pixel_id IS NULL THEN '❌ Falta pixel_id'
        WHEN rp.meta_access_token IS NULL THEN '❌ Falta access_token'
        WHEN rp.meta_events_purchase = false THEN '❌ Purchase event desabilitado'
        ELSE '⚠️ Outro problema'
    END as possivel_causa
FROM payments p
JOIN bots b ON b.id = p.bot_id
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE (rp.slug = 'red1' OR rp.name ILIKE '%red1%')
AND p.status = 'paid'
AND DATE(p.created_at) = CURRENT_DATE
AND p.delivery_token IS NOT NULL
AND (p.meta_purchase_sent = false OR p.meta_purchase_sent IS NULL)
ORDER BY p.created_at DESC
LIMIT 50;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 5. VERIFICAR SE BOTS ESTÃO EM MÚLTIPLOS POOLS
print_section "5. BOTS EM MÚLTIPLOS POOLS (RISCO DE CONFLITO)"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    pb.bot_id,
    b.name as bot_name,
    b.user_id as bot_user_id,
    COUNT(DISTINCT pb.pool_id) as pools_count,
    STRING_AGG(DISTINCT rp.name || ' (id:' || rp.id || ', user:' || rp.user_id || ')', ', ') as pools_list
FROM pool_bots pb
JOIN bots b ON b.id = pb.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE pb.bot_id IN (
    SELECT DISTINCT bot_id 
    FROM pool_bots pb2
    JOIN redirect_pools rp2 ON rp2.id = pb2.pool_id
    WHERE rp2.slug = 'red1' OR rp2.name ILIKE '%red1%'
)
GROUP BY pb.bot_id, b.name, b.user_id
HAVING COUNT(DISTINCT pb.pool_id) > 1
ORDER BY pools_count DESC;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 6. VERIFICAR TRACKING_DATA DO REDIS (para payments problemáticos)
print_section "6. PAYMENTS COM TRACKING_TOKEN MAS SEM META_PURCHASE_SENT"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
SELECT 
    p.id,
    p.payment_id,
    p.tracking_token IS NOT NULL as has_tracking_token,
    p.tracking_token,
    LENGTH(COALESCE(p.tracking_token, '')) as tracking_token_length,
    CASE 
        WHEN p.tracking_token LIKE 'tracking_%' THEN '❌ Token GERADO (não do redirect)'
        WHEN LENGTH(COALESCE(p.tracking_token, '')) = 32 THEN '✅ Token UUID (do redirect)'
        ELSE '⚠️ Formato desconhecido'
    END as token_type
FROM payments p
JOIN pool_bots pb ON pb.bot_id = p.bot_id
JOIN redirect_pools rp ON rp.id = pb.pool_id
WHERE (rp.slug = 'red1' OR rp.name ILIKE '%red1%')
AND p.status = 'paid'
AND DATE(p.created_at) = CURRENT_DATE
AND p.delivery_token IS NOT NULL
AND (p.meta_purchase_sent = false OR p.meta_purchase_sent IS NULL)
ORDER BY p.created_at DESC
LIMIT 20;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 7. RESUMO EXECUTIVO
print_section "7. RESUMO EXECUTIVO - POOL 'red1'"

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -w -c "
WITH pool_info AS (
    SELECT id, name, slug, user_id, meta_tracking_enabled, meta_pixel_id, meta_access_token, meta_events_purchase
    FROM redirect_pools
    WHERE slug = 'red1' OR name ILIKE '%red1%'
    LIMIT 1
),
payments_stats AS (
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN p.delivery_token IS NOT NULL THEN 1 END) as with_delivery_token,
        COUNT(CASE WHEN p.meta_purchase_sent = true THEN 1 END) as purchase_sent,
        COUNT(CASE WHEN p.delivery_token IS NOT NULL AND (p.meta_purchase_sent = false OR p.meta_purchase_sent IS NULL) THEN 1 END) as problem_count
    FROM payments p
    JOIN pool_bots pb ON pb.bot_id = p.bot_id
    JOIN redirect_pools rp ON rp.id = pb.pool_id
    WHERE (rp.slug = 'red1' OR rp.name ILIKE '%red1%')
    AND p.status = 'paid'
    AND DATE(p.created_at) = CURRENT_DATE
),
bots_in_pool AS (
    SELECT COUNT(DISTINCT pb.bot_id) as bots_count
    FROM pool_bots pb
    JOIN redirect_pools rp ON rp.id = pb.pool_id
    WHERE (rp.slug = 'red1' OR rp.name ILIKE '%red1%')
),
bots_in_multiple_pools AS (
    SELECT COUNT(DISTINCT pb.bot_id) as bots_in_multiple
    FROM pool_bots pb
    WHERE pb.bot_id IN (
        SELECT bot_id 
        FROM pool_bots
        GROUP BY bot_id
        HAVING COUNT(DISTINCT pool_id) > 1
    )
    AND pb.pool_id IN (SELECT id FROM redirect_pools WHERE slug = 'red1' OR name ILIKE '%red1%')
)
SELECT 
    pi.id as \"Pool ID\",
    pi.name as \"Pool Name\",
    pi.slug as \"Pool Slug\",
    pi.user_id as \"Pool User ID\",
    CASE 
        WHEN pi.meta_tracking_enabled = true AND pi.meta_pixel_id IS NOT NULL AND pi.meta_access_token IS NOT NULL AND pi.meta_events_purchase = true THEN '✅ OK'
        ELSE '❌ PROBLEMA'
    END as \"Status Config\",
    ps.total as \"Total Payments (hoje)\",
    ps.with_delivery_token as \"Com delivery_token\",
    ps.purchase_sent as \"Purchase enviado\",
    ps.problem_count as \"❌ PROBLEMA: não enviado\",
    ROUND((ps.purchase_sent::numeric / NULLIF(ps.total, 0) * 100), 2) as \"Taxa envio (%)\",
    bip.bots_count as \"Bots no pool\",
    bimp.bots_in_multiple as \"Bots em múltiplos pools (RISCO)\"
FROM pool_info pi
CROSS JOIN payments_stats ps
CROSS JOIN bots_in_pool bip
CROSS JOIN bots_in_multiple_pools bimp;
" 2>/dev/null || echo "❌ Erro ao conectar ao banco"

# 8. VERIFICAR LOGS (se disponível)
print_section "8. VERIFICAR LOGS RECENTES"

LOG_FILE="${LOG_FILE:-/var/log/grimbots/app.log}"

if [ -f "$LOG_FILE" ]; then
    echo "📄 Buscando logs relacionados ao pool 'red1' e payments problemáticos..."
    echo ""
    
    echo "❌ Erros relacionados a Purchase não enviado (últimas 20):"
    grep -i "purchase.*não.*enviado\|purchase.*não foi\|meta.*purchase.*não\|PROBLEMA RAIZ.*Purchase\|red1" "$LOG_FILE" | tail -20 || echo "  Nenhum erro encontrado"
    
    echo ""
    echo "⚠️ Warnings relacionados a pool 'red1':"
    grep -i "red1\|pool.*id.*1" "$LOG_FILE" | tail -20 || echo "  Nenhum warning encontrado"
    
    echo ""
    echo "✅ Purchase enviados com sucesso para pool 'red1':"
    grep -i "purchase.*enfileirado\|purchase.*enviado.*red1\|meta.*purchase.*sucesso" "$LOG_FILE" | tail -20 || echo "  Nenhum log de sucesso encontrado"
else
    echo "⚠️ Arquivo de log não encontrado em $LOG_FILE"
    echo "📋 Tentando encontrar arquivo de log..."
    find /var/log -name "*grimbots*" -o -name "*app.log*" 2>/dev/null | head -5
fi

echo ""
echo -e "${GREEN}=========================================="
echo -e "✅ DIAGNÓSTICO COMPLETO"
echo -e "==========================================${NC}"
echo ""
echo "📋 Próximos passos:"
echo "1. Analise os dados acima"
echo "2. Verifique se o pool 'red1' está configurado corretamente"
echo "3. Verifique se bots estão em múltiplos pools (risco de conflito)"
echo "4. Verifique se tracking_token está correto (deve ser UUID, não 'tracking_xxx')"
echo ""

