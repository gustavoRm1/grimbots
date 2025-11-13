-- Migration: Adicionar colunas fbp e fbc ao bot_users
-- Data: 2025-11-13
-- Descrição: Adiciona campos para armazenar cookies _fbp e _fbc do Meta Pixel para matching Purchase com PageView
-- Status: Idempotente (pode ser executada múltiplas vezes sem erro)

-- Verificar se as colunas já existem antes de adicionar
DO $$
BEGIN
    -- Adicionar coluna fbp se não existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'bot_users' AND column_name = 'fbp'
    ) THEN
        ALTER TABLE bot_users ADD COLUMN fbp VARCHAR(255) NULL;
        RAISE NOTICE '✅ Coluna fbp adicionada com sucesso';
    ELSE
        RAISE NOTICE 'ℹ️ Coluna fbp já existe (pulando)';
    END IF;

    -- Adicionar coluna fbc se não existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'bot_users' AND column_name = 'fbc'
    ) THEN
        ALTER TABLE bot_users ADD COLUMN fbc VARCHAR(255) NULL;
        RAISE NOTICE '✅ Coluna fbc adicionada com sucesso';
    ELSE
        RAISE NOTICE 'ℹ️ Coluna fbc já existe (pulando)';
    END IF;
END $$;

-- Verificar se as colunas foram criadas
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable,
    CASE 
        WHEN column_name = 'fbp' THEN 'Facebook Browser ID (_fbp cookie)'
        WHEN column_name = 'fbc' THEN 'Facebook Click ID (_fbc cookie)'
    END as description
FROM information_schema.columns
WHERE table_name = 'bot_users' 
    AND column_name IN ('fbp', 'fbc')
ORDER BY column_name;

