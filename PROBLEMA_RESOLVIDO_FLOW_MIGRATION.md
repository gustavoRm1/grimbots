# ✅ Problema Resolvido: Migration Flow

## 🔍 Raiz do Problema Identificada

A migration estava executando no **SQLite** (`instance/saas_bot_manager.db`) enquanto o aplicativo em produção está usando **PostgreSQL** (via `DATABASE_URL` no `.env` ou variáveis de ambiente do systemd).

**Causa:** A migration criava um app Flask próprio sem carregar o `.env`, então não detectava a `DATABASE_URL` e usava o fallback SQLite.

## ✅ Solução Aplicada

A migration agora importa diretamente do `app.py`, que:
1. Carrega o `.env` via `load_dotenv()`
2. Usa a mesma `DATABASE_URL` do aplicativo
3. Conecta ao banco correto (PostgreSQL em produção)

## 🚀 Como Executar Agora

### No servidor:
```bash
cd /root/grimbots
source venv/bin/activate
python3 migrations/add_flow_fields.py
```

A migration agora vai:
1. **Detectar automaticamente PostgreSQL** (via `DATABASE_URL` do `.env`)
2. Mostrar qual banco está usando: `🔄 Database detectado: postgresql`
3. Executar no banco correto

## 📋 Verificação

Após executar, você deve ver:
```
🔄 Database detectado: postgresql
🔄 URI: localhost:5432/grimbots  # ou seu banco
🔄 Verificando campos em bot_configs...
✅ Campo flow_enabled já existe... ou será criado
✅ Campo flow_steps já existe... ou será criado
🔄 Verificando campos em payments...
✅ Campo flow_step_id já existe... ou será criado
✅ Migration concluída com sucesso!
```

## ⚠️ IMPORTANTE

Se você já executou a migration no SQLite (como mostrado nos logs), os campos foram criados lá mas **não** no PostgreSQL. Execute novamente agora que a migration foi corrigida.

## 🔄 Depois da Migration

Reinicie o aplicativo:
```bash
sudo systemctl restart grimbots
# ou se estiver rodando manualmente:
./restart-app.sh
```

## ✅ Verificação Final

O erro `column payments.flow_step_id does not exist` deve desaparecer após:
1. Executar a migration corrigida (que vai no PostgreSQL)
2. Reiniciar o aplicativo

