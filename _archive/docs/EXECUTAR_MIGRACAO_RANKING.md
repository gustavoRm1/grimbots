# 🚀 MIGRAÇÃO: Campos de Nome no Ranking

## Problema
As colunas `ranking_display_name` e `ranking_first_visit_handled` foram adicionadas ao modelo Python, mas não existem no banco de dados PostgreSQL.

## Erro
```
psycopg2.errors.UndefinedColumn: column users.ranking_display_name does not exist
```

## Solução

### Opção 1: Executar SQL diretamente (Recomendado)

```bash
# No servidor, execute:
psql -U grimbots -d grimbots -f scripts/migration_add_ranking_display_name.sql
```

### Opção 2: Executar script Python

```bash
# No servidor, execute:
cd ~/grimbots
source venv/bin/activate
python migrations/add_ranking_display_name_fields.py
```

### Opção 3: Executar SQL manualmente

Conecte ao PostgreSQL e execute:

```sql
-- Adicionar coluna ranking_display_name
ALTER TABLE users ADD COLUMN IF NOT EXISTS ranking_display_name VARCHAR(50) NULL;

-- Adicionar coluna ranking_first_visit_handled
ALTER TABLE users ADD COLUMN IF NOT EXISTS ranking_first_visit_handled BOOLEAN DEFAULT FALSE;

-- Verificar se foram criadas
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('ranking_display_name', 'ranking_first_visit_handled');
```

## ✅ Após executar

Reinicie a aplicação:

```bash
sudo systemctl restart grimbots
```

