-- ============================================================================
-- MIGRAÇÃO: Expandir tracking_token de String(100) para String(200)
-- ============================================================================
-- Data: 2025-11-12
-- Motivo: Tracking tokens podem exceder 100 caracteres em casos especiais
--         e o sistema estava caindo em fallback, quebrando o vínculo PageView → Purchase
-- ============================================================================

-- PostgreSQL
ALTER TABLE payments ALTER COLUMN tracking_token TYPE VARCHAR(200);

-- Verificar se a alteração foi aplicada
SELECT 
    column_name, 
    data_type, 
    character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'payments' 
  AND column_name = 'tracking_token';

-- ============================================================================
-- FIM DA MIGRAÇÃO
-- ============================================================================

