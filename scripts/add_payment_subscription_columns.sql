-- Script SQL para adicionar colunas de subscription na tabela payments
-- PostgreSQL

-- Verificar se colunas já existem antes de adicionar (evita erro se já existir)
DO $$
BEGIN
    -- Adicionar button_index se não existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'payments' AND column_name = 'button_index'
    ) THEN
        ALTER TABLE payments ADD COLUMN button_index INTEGER;
        RAISE NOTICE '✅ Coluna button_index adicionada';
    ELSE
        RAISE NOTICE '⚠️ Coluna button_index já existe';
    END IF;

    -- Adicionar button_config se não existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'payments' AND column_name = 'button_config'
    ) THEN
        ALTER TABLE payments ADD COLUMN button_config TEXT;
        RAISE NOTICE '✅ Coluna button_config adicionada';
    ELSE
        RAISE NOTICE '⚠️ Coluna button_config já existe';
    END IF;

    -- Adicionar has_subscription se não existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'payments' AND column_name = 'has_subscription'
    ) THEN
        ALTER TABLE payments ADD COLUMN has_subscription BOOLEAN DEFAULT FALSE;
        RAISE NOTICE '✅ Coluna has_subscription adicionada';
    ELSE
        RAISE NOTICE '⚠️ Coluna has_subscription já existe';
    END IF;
END $$;

-- Criar índice para performance (se não existir)
CREATE INDEX IF NOT EXISTS idx_payment_has_subscription 
ON payments(has_subscription) 
WHERE has_subscription = TRUE;

-- Verificar colunas criadas
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'payments' 
AND column_name IN ('button_index', 'button_config', 'has_subscription')
ORDER BY column_name;

