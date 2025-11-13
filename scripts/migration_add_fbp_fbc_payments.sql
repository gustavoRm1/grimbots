-- Migration: Adicionar colunas fbp e fbc na tabela payments
-- Data: 2025-11-13
-- Objetivo: Permitir fallback de fbp/fbc no Purchase Event se Redis expirar

ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS fbp VARCHAR(255) NULL,
ADD COLUMN IF NOT EXISTS fbc VARCHAR(255) NULL;

-- Criar índices para melhor performance (opcional)
-- CREATE INDEX IF NOT EXISTS idx_payments_fbp ON payments(fbp) WHERE fbp IS NOT NULL;
-- CREATE INDEX IF NOT EXISTS idx_payments_fbc ON payments(fbc) WHERE fbc IS NOT NULL;

COMMENT ON COLUMN payments.fbp IS 'Facebook Browser ID (_fbp cookie) - Fallback para Purchase Event';
COMMENT ON COLUMN payments.fbc IS 'Facebook Click ID (_fbc cookie) - Fallback para Purchase Event';

