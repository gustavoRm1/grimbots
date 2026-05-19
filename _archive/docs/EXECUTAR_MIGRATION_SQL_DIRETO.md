# Executar Migration SQL Direto no PostgreSQL

## ⚠️ URGENTE
O código está tentando usar campos que não existem no banco. Execute esta migration **imediatamente** no servidor.

## ✅ OPÇÃO 1: Via psql (Mais Rápido)

### Conectar ao PostgreSQL:
```bash
psql -U seu_usuario -d seu_database
# ou
psql -h localhost -U postgres -d grimbots
```

### Executar SQL:
```sql
-- Copiar e colar todo o conteúdo de migrations/add_flow_fields.sql
ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS flow_enabled BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_bot_configs_flow_enabled ON bot_configs(flow_enabled);
ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS flow_steps TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS flow_step_id VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_payments_flow_step_id ON payments(flow_step_id);
```

## ✅ OPÇÃO 2: Via arquivo SQL

```bash
# No servidor
cd /root/grimbots
psql -U seu_usuario -d seu_database -f migrations/add_flow_fields.sql
```

## ✅ OPÇÃO 3: Via Python (se psql não estiver disponível)

```bash
cd /root/grimbots
source venv/bin/activate
python migrations/add_flow_fields.py
```

## ✅ OPÇÃO 4: Uma linha via psql

```bash
psql -U seu_usuario -d seu_database -c "ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS flow_enabled BOOLEAN DEFAULT FALSE; CREATE INDEX IF NOT EXISTS idx_bot_configs_flow_enabled ON bot_configs(flow_enabled); ALTER TABLE bot_configs ADD COLUMN IF NOT EXISTS flow_steps TEXT; ALTER TABLE payments ADD COLUMN IF NOT EXISTS flow_step_id VARCHAR(50); CREATE INDEX IF NOT EXISTS idx_payments_flow_step_id ON payments(flow_step_id);"
```

## 🔍 VERIFICAR SE FUNCIONOU

```sql
-- Verificar colunas em bot_configs
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'bot_configs' 
AND column_name IN ('flow_enabled', 'flow_steps');

-- Verificar colunas em payments
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'payments' 
AND column_name = 'flow_step_id';
```

Deve retornar:
```
 column_name  | data_type 
--------------+-----------
 flow_enabled | boolean
 flow_steps   | text
```

E:
```
 column_name  | data_type 
--------------+-----------
 flow_step_id | character varying
```

## ⚠️ DEPOIS DE EXECUTAR

Reinicie o aplicativo:
```bash
sudo systemctl restart grimbots
# ou se estiver rodando manualmente, pare e reinicie
```

## ❌ SE AINDA DER ERRO

Verifique:
1. Permissões do usuário do banco (precisa `ALTER TABLE`)
2. Se o nome da tabela está correto (`bot_configs` e `payments`)
3. Se consegue conectar ao banco via psql

