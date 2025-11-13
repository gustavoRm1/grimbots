# 🚨 AÇÃO NECESSÁRIA: Aplicar Migração do Banco

## ⚠️ Status Atual

A validação mostrou que as colunas `fbp` e `fbc` **ainda não existem** no banco de dados.

**Erro encontrado:**
```
ERROR:  column "fbc" does not exist
```

---

## ✅ SOLUÇÃO: Aplicar Migração

Execute o comando abaixo na VPS:

```bash
cd /root/grimbots
psql -U grimbots -d grimbots -f scripts/migration_add_fbp_fbc_bot_users.sql
```

---

## 📋 Validação Após Migração

Após executar a migração, valide:

```bash
# 1. Verificar se as colunas foram criadas
psql -U grimbots -d grimbots -c "\d+ bot_users" | grep -E 'fbc|fbp'

# 2. Executar validação completa novamente
./scripts/validar_deploy_fbc_fix.sh
```

**Esperado:**
- ✅ Ver colunas `fbp` e `fbc` listadas
- ✅ Validação completa deve passar (7/7 sucessos)

---

## 🔄 Sequência Completa de Deploy

```bash
cd /root/grimbots

# 1. Aplicar migração (CRÍTICO - fazer primeiro!)
psql -U grimbots -d grimbots -f scripts/migration_add_fbp_fbc_bot_users.sql

# 2. Commit e push (se ainda não fez)
git add models.py tasks_async.py app.py scripts/migration_add_fbp_fbc_bot_users.sql
git commit -m "fix: adicionar campos fbp/fbc ao BotUser e garantir fbc no Purchase"
git push

# 3. Reiniciar serviços
./restart-app.sh

# 4. Validar
./scripts/validar_deploy_fbc_fix.sh
```

---

## ✅ Após Aplicar Migração

1. **Fazer uma nova venda de teste**
2. **Verificar se `fbc` aparece no payload:**
   ```bash
   tail -n 500 logs/celery.log | grep -A 30 "META PAYLOAD COMPLETO (Purchase)" | tail -35
   ```
3. **Validar no Meta Events Manager**

---

**Execute a migração agora para completar o deploy!**

