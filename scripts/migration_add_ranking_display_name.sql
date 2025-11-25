-- ✅ Migração: Adicionar campos de nome de exibição no ranking
-- Data: 2025-11-25
-- Descrição: Adiciona campos ranking_display_name e ranking_first_visit_handled na tabela users
-- Execute: psql -U grimbots -d grimbots -f scripts/migration_add_ranking_display_name.sql

-- Verificar se as colunas já existem antes de adicionar (PostgreSQL)
DO $$
BEGIN
    -- Adicionar coluna ranking_display_name se não existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'ranking_display_name'
    ) THEN
        ALTER TABLE users ADD COLUMN ranking_display_name VARCHAR(50) NULL;
        RAISE NOTICE '✅ Coluna ranking_display_name adicionada com sucesso';
    ELSE
        RAISE NOTICE 'ℹ️ Coluna ranking_display_name já existe (pulando)';
    END IF;

    -- Adicionar coluna ranking_first_visit_handled se não existir
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'ranking_first_visit_handled'
    ) THEN
        ALTER TABLE users ADD COLUMN ranking_first_visit_handled BOOLEAN DEFAULT FALSE;
        RAISE NOTICE '✅ Coluna ranking_first_visit_handled adicionada com sucesso';
    ELSE
        RAISE NOTICE 'ℹ️ Coluna ranking_first_visit_handled já existe (pulando)';
    END IF;
END $$;

-- ✅ Comentários nas colunas (PostgreSQL)
COMMENT ON COLUMN users.ranking_display_name IS 'Nome escolhido pelo usuário para aparecer no ranking (LGPD compliant)';
COMMENT ON COLUMN users.ranking_first_visit_handled IS 'Flag indicando se o usuário já escolheu o nome na primeira visita ao ranking';

-- ✅ Verificar se as colunas foram criadas
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable,
    column_default,
    CASE 
        WHEN column_name = 'ranking_display_name' THEN 'Nome escolhido pelo usuário para aparecer no ranking'
        WHEN column_name = 'ranking_first_visit_handled' THEN 'Flag indicando se o usuário já escolheu o nome na primeira visita'
    END as description
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('ranking_display_name', 'ranking_first_visit_handled')
ORDER BY column_name;

