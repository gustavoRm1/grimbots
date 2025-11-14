# ✅ COMANDOS PARA EXECUTAR MIGRATION

**Data:** 2025-11-14  
**Problema:** `column payments.customer_email does not exist`

---

## 🚀 SOLUÇÃO RÁPIDA

### **OPÇÃO 1: Migration Python (RECOMENDADO)**

```bash
cd /root/grimbots
source venv/bin/activate
python migrations/add_customer_email_phone_document.py
```

**Saída esperada:**
```
================================================================================
🔄 MIGRATION: Adicionar customer_email, customer_phone, customer_document
================================================================================
🔍 Colunas existentes na tabela payments: XX
🔄 Adicionando coluna customer_email...
✅ Campo customer_email adicionado com sucesso
🔄 Adicionando coluna customer_phone...
✅ Campo customer_phone adicionado com sucesso
🔄 Adicionando coluna customer_document...
✅ Campo customer_document adicionado com sucesso
✅ Migration concluída: 3 campo(s) adicionado(s)
================================================================================
✅ MIGRATION CONCLUÍDA COM SUCESSO!
================================================================================
```

---

### **OPÇÃO 2: SQL Direto (SE PYTHON FALHAR)**

```bash
# Conectar ao PostgreSQL
psql -U seu_usuario -d seu_banco

# Executar SQL
ALTER TABLE payments ADD COLUMN IF NOT EXISTS customer_email VARCHAR(255);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(50);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS customer_document VARCHAR(50);

# Verificar
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'payments' 
AND column_name IN ('customer_email', 'customer_phone', 'customer_document');
```

---

### **OPÇÃO 3: Via Python Interativo**

```bash
cd /root/grimbots
source venv/bin/activate
python

# No Python:
from migrations.add_customer_email_phone_document import add_customer_fields
add_customer_fields()
```

---

## ✅ VALIDAÇÃO PÓS-MIGRATION

```bash
# Verificar se colunas foram adicionadas
psql -U seu_usuario -d seu_banco -c "\d payments" | grep customer
```

**Deve mostrar:**
```
customer_email    | character varying(255)
customer_phone    | character varying(50)
customer_document | character varying(50)
```

---

## 🔥 APÓS MIGRATION

**Reiniciar serviços:**
```bash
# Reiniciar Gunicorn
sudo systemctl restart grimbots

# Reiniciar Celery (se necessário)
sudo systemctl restart celery
```

**Verificar logs:**
```bash
tail -f logs/gunicorn.log | grep -i "sync umbrellapay"
```

---

**MIGRATION PRONTA PARA EXECUTAR! ✅**

