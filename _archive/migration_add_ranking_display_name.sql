-- ✅ Migração: Adicionar campos de nome de exibição no ranking
-- Data: 2025-11-25
-- Descrição: Adiciona campos ranking_display_name e ranking_first_visit_handled na tabela users

-- Adicionar coluna ranking_display_name (nome escolhido pelo usuário para aparecer no ranking)
ALTER TABLE users ADD COLUMN IF NOT EXISTS ranking_display_name VARCHAR(50) NULL;

-- Adicionar coluna ranking_first_visit_handled (flag para controlar primeira visita ao ranking)
ALTER TABLE users ADD COLUMN IF NOT EXISTS ranking_first_visit_handled BOOLEAN DEFAULT FALSE;

-- ✅ Comentários nas colunas (PostgreSQL)
COMMENT ON COLUMN users.ranking_display_name IS 'Nome escolhido pelo usuário para aparecer no ranking (LGPD compliant)';
COMMENT ON COLUMN users.ranking_first_visit_handled IS 'Flag indicando se o usuário já escolheu o nome na primeira visita ao ranking';

-- ✅ Verificar se as colunas foram criadas
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('ranking_display_name', 'ranking_first_visit_handled');

