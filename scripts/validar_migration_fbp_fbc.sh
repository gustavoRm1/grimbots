#!/bin/bash
# Script para validar migration fbp/fbc na tabela payments

echo "=========================================="
echo "  VALIDAÇÃO - MIGRATION fbp/fbc PAYMENTS"
echo "=========================================="

export PGPASSWORD=123sefudeu

echo ""
echo "1. Verificar se colunas fbp e fbc existem na tabela payments:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'payments' 
AND column_name IN ('fbp', 'fbc')
ORDER BY column_name;
"

echo ""
echo "2. Verificar estrutura completa da tabela payments (colunas relacionadas a tracking):"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT column_name, data_type, character_maximum_length, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'payments' 
AND column_name IN ('tracking_token', 'pageview_event_id', 'fbp', 'fbc', 'fbclid')
ORDER BY column_name;
"

echo ""
echo "3. Verificar se existem payments com fbp/fbc já preenchidos:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT 
    COUNT(*) as total_payments,
    COUNT(fbp) as payments_with_fbp,
    COUNT(fbc) as payments_with_fbc,
    COUNT(tracking_token) as payments_with_tracking_token,
    COUNT(pageview_event_id) as payments_with_pageview_event_id
FROM payments;
"

echo ""
echo "4. Verificar últimos 5 payments criados:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    status,
    tracking_token,
    pageview_event_id,
    fbp IS NOT NULL as has_fbp,
    fbc IS NOT NULL as has_fbc,
    created_at
FROM payments
ORDER BY id DESC
LIMIT 5;
"

echo ""
echo "=========================================="
echo "  VALIDAÇÃO CONCLUÍDA"
echo "=========================================="

