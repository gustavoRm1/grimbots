# 🚨 CORREÇÕES URGENTES PARA VPS

**Data:** 2025-01-27  
**Status:** ⚠️ ERROS CRÍTICOS IDENTIFICADOS

---

## ❌ PROBLEMAS IDENTIFICADOS

1. **Funções não definidas ao registrar jobs**
   - `check_expired_subscriptions` is not defined
   - `check_pending_subscriptions_in_groups` is not defined
   - `retry_failed_subscription_removals` is not defined
   - **Causa:** Jobs sendo registrados ANTES das funções serem definidas (linhas 893-905, 907-919, 1007-1019)

2. **Colunas faltando no banco de dados**
   - `column payments.button_index does not exist`
   - `column payments.button_config does not exist`
   - `column payments.has_subscription does not exist`

---

## ✅ CORREÇÕES APLICADAS NO CÓDIGO

### 1. Ordem de Registro de Jobs

**Problema:** 3 jobs registrados antes das funções serem definidas:
- `check_expired_subscriptions` (linha 893-905, função na linha 11527)
- `check_pending_subscriptions_in_groups` (linha 907-919, função na linha 11658)
- `retry_failed_subscription_removals` (linha 1007-1019, função na linha 11767)

**Solução:** Todos os 3 registros movidos para DEPOIS das definições das funções (após linha 11820)

**Arquivo:** `app.py`

---

## 🔧 O QUE FAZER NA VPS

### **PASSO 1: Atualizar Código**

```bash
cd ~/grimbots
git pull
```

### **PASSO 2: Adicionar Colunas no Banco de Dados**

**Opção A: Script Python (Recomendado)**

```bash
python scripts/add_payment_subscription_columns.py
```

**Opção B: SQL Direto (PostgreSQL)**

```bash
psql -U seu_usuario -d nome_banco -f scripts/add_payment_subscription_columns.sql
```

**Ou execute manualmente:**

```sql
-- Conectar ao banco
\c nome_do_banco

-- Adicionar colunas
ALTER TABLE payments ADD COLUMN IF NOT EXISTS button_index INTEGER;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS button_config TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS has_subscription BOOLEAN DEFAULT FALSE;

-- Criar índice
CREATE INDEX IF NOT EXISTS idx_payment_has_subscription 
ON payments(has_subscription) 
WHERE has_subscription = TRUE;

-- Verificar
SELECT column_name, data_type 
FROM information_schema.columns
WHERE table_name = 'payments' 
AND column_name IN ('button_index', 'button_config', 'has_subscription');
```

### **PASSO 3: Reiniciar Aplicação**

```bash
./restart-app.sh
```

### **PASSO 4: Verificar Logs**

```bash
# Verificar se jobs foram registrados corretamente
grep "Job.*registrado" logs/app.log | tail -5

# Verificar se não há mais erros de colunas
tail -f logs/gunicorn.log | grep -i "column.*does not exist"
```

---

## ✅ VERIFICAÇÃO FINAL

Após aplicar as correções, verifique:

1. **Jobs registrados:**
```bash
python scripts/verificar_jobs_assinaturas.py
```

**Deve mostrar:**
```
✅ check_expired_subscriptions
✅ check_pending_subscriptions_in_groups
✅ retry_failed_subscription_removals
```

2. **Colunas existem:**
```bash
python scripts/add_payment_subscription_columns.py
```

**Deve mostrar:**
```
⚠️ Coluna button_index já existe
⚠️ Coluna button_config já existe
⚠️ Coluna has_subscription já existe
```

3. **Logs sem erros:**
```bash
tail -50 logs/app.log | grep -i "erro\|error" | grep -i "subscription\|column"
```

**Não deve mostrar erros relacionados a:**
- `is not defined`
- `column.*does not exist`

---

## 📋 CHECKLIST RÁPIDO

- [ ] `git pull` executado
- [ ] Colunas adicionadas ao banco (`button_index`, `button_config`, `has_subscription`)
- [ ] Aplicação reiniciada
- [ ] Jobs de assinaturas registrados (3 jobs)
- [ ] Logs sem erros de "column does not exist"
- [ ] Logs sem erros de "is not defined"

---

## 🐛 TROUBLESHOOTING

### **Erro: "column already exists"**
✅ **OK** - Significa que a coluna já existe, pode ignorar

### **Erro: "permission denied"**
```bash
# Verificar permissões do usuário do banco
# Se necessário, executar como superuser
sudo -u postgres psql -d nome_banco -f scripts/add_payment_subscription_columns.sql
```

### **Jobs ainda não registrando**
```bash
# Verificar se funções estão definidas
grep -n "def check_pending_subscriptions_in_groups" app.py
grep -n "def retry_failed_subscription_removals" app.py

# Verificar ordem de registro
grep -n "scheduler.add_job.*check_pending" app.py
grep -n "scheduler.add_job.*retry_failed" app.py
```

Os registros devem estar DEPOIS das definições das funções.

---

**✅ APÓS APLICAR TODAS AS CORREÇÕES, O SISTEMA DEVE FUNCIONAR CORRETAMENTE!**

