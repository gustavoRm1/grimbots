# Executar Migration Flow no Servidor

## ⚠️ ERRO ATUAL
O código está tentando usar os campos `flow_enabled`, `flow_steps` (bot_configs) e `flow_step_id` (payments), mas esses campos ainda não existem no banco de dados PostgreSQL.

## ✅ SOLUÇÃO
Execute a migration no servidor onde o aplicativo está rodando.

### Passo 1: Conectar ao Servidor
```bash
ssh user@seu-servidor.com
cd /root/grimbots  # ou o caminho correto do projeto
```

### Passo 2: Ativar Virtual Environment
```bash
source venv/bin/activate
```

### Passo 3: Executar Migration
```bash
python migrations/add_flow_fields.py
```

**OU usar o script:**
```bash
chmod +x EXECUTAR_MIGRATION_FLOW.sh
./EXECUTAR_MIGRATION_FLOW.sh
```

### Passo 4: Verificar Resultado
A migration deve mostrar:
```
🔄 Database detectado: postgresql
🔄 Verificando campos em bot_configs...
🔄 Adicionando campo flow_enabled na tabela bot_configs...
✅ Campo flow_enabled adicionado com sucesso!
✅ Índice flow_enabled criado com sucesso!
🔄 Adicionando campo flow_steps na tabela bot_configs...
✅ Campo flow_steps adicionado com sucesso!

🔄 Verificando campos em payments...
🔄 Adicionando campo flow_step_id na tabela payments...
✅ Campo flow_step_id adicionado com sucesso!
✅ Índice flow_step_id criado com sucesso!

✅ Migration concluída com sucesso!
```

### Passo 5: Reiniciar Aplicação
```bash
# Se estiver usando systemd:
sudo systemctl restart grimbots

# Ou se estiver rodando manualmente:
# Parar o processo atual (Ctrl+C) e reiniciar
```

## 🔍 VERIFICAÇÃO MANUAL (Opcional)
Para verificar se as colunas foram criadas:

```bash
# Conectar ao PostgreSQL
psql -U seu_usuario -d seu_database

# Verificar colunas de bot_configs
\d bot_configs

# Verificar colunas de payments
\d payments

# Ou via SQL:
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'bot_configs' 
AND column_name IN ('flow_enabled', 'flow_steps');

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'payments' 
AND column_name = 'flow_step_id';
```

## 📝 CAMPOS ADICIONADOS

### bot_configs
- `flow_enabled` (BOOLEAN, DEFAULT FALSE) - Ativar/desativar fluxo visual
- `flow_steps` (TEXT) - JSON array com steps do fluxo

### payments
- `flow_step_id` (VARCHAR(50)) - ID do step do fluxo que gerou este payment

## ❌ SE AINDA DER ERRO
Se a migration falhar, verifique:
1. Permissões do usuário do banco (precisa ALTER TABLE)
2. Se o DATABASE_URL está configurado corretamente
3. Se o virtual environment tem todas as dependências instaladas

