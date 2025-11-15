# 🚨 COMANDOS: EXECUTAR MIGRATION `updated_at`

## ⚠️ URGENTE

**Problema:** Sistema não consegue gerar PIX porque coluna `updated_at` não existe no banco.

**Solução:** Executar migration para adicionar a coluna.

---

## 📋 COMANDOS

### **1. Conectar ao VPS**

```bash
ssh root@seu_vps
```

### **2. Acessar diretório do projeto**

```bash
cd /root/grimbots
```

### **3. Ativar ambiente virtual**

```bash
source venv/bin/activate
```

### **4. Executar Migration**

```bash
python migrations/add_updated_at_to_payment.py
```

### **5. Verificar Resultado**

**Resultado esperado:**
```
================================================================================
🔄 MIGRATION: Adicionar updated_at ao Payment
================================================================================
🔍 Colunas existentes na tabela payments: XX
🔍 Dialeto do banco: postgresql
🔄 Adicionando coluna updated_at...
✅ Coluna updated_at adicionada
✅ Função update_updated_at_column criada/atualizada
✅ Trigger update_payments_updated_at criado
✅ Campo updated_at adicionado com sucesso
✅ Validação: Campo updated_at está presente
================================================================================
✅ MIGRATION CONCLUÍDA COM SUCESSO!
================================================================================
```

### **6. Validar no Banco de Dados (Opcional)**

```bash
# No PostgreSQL:
psql -U seu_usuario -d seu_banco -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'payments' AND column_name = 'updated_at';"
```

**Resultado esperado:**
```
 column_name | data_type
-------------+-----------
 updated_at  | timestamp without time zone
```

### **7. Testar Sistema**

```bash
# Tentar gerar PIX novamente
# Monitorar logs:
tail -f logs/gunicorn.log | grep -iE "Erro ao gerar PIX|updated_at|PIX ENVIADO"
```

**Resultado esperado:**
- ✅ NÃO deve aparecer: `column payments.updated_at does not exist`
- ✅ Deve aparecer: `✅ PIX ENVIADO`

---

## 🔥 COMANDO ÚNICO (RÁPIDO)

```bash
cd /root/grimbots && source venv/bin/activate && python migrations/add_updated_at_to_payment.py
```

---

## ⚠️ NOTAS IMPORTANTES

1. **Migration é idempotente:** Pode executar várias vezes sem problemas
2. **Pode demorar:** Se tabela `payments` for muito grande, pode demorar alguns segundos
3. **Não precisa reiniciar:** Aplicação não precisa ser reiniciada após migration
4. **Backup recomendado:** Se possível, fazer backup antes (mas migration é segura)

---

## ❓ PROBLEMAS COMUNS

### **Problema 1: Permission denied**

**Erro:**
```
PermissionError: [Errno 13] Permission denied
```

**Solução:**
```bash
# Verificar permissões
ls -la migrations/add_updated_at_to_payment.py

# Dar permissão de execução
chmod +x migrations/add_updated_at_to_payment.py
```

### **Problema 2: Module not found**

**Erro:**
```
ModuleNotFoundError: No module named 'app'
```

**Solução:**
```bash
# Garantir que está no diretório correto
cd /root/grimbots

# Verificar que ambiente virtual está ativado
which python
# Deve mostrar: /root/grimbots/venv/bin/python
```

### **Problema 3: Database connection error**

**Erro:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solução:**
```bash
# Verificar se PostgreSQL está rodando
sudo systemctl status postgresql

# Verificar variáveis de ambiente
cat .env | grep -i database
```

---

## ✅ VALIDAÇÃO FINAL

Após executar a migration, validar:

1. **Coluna existe:**
   ```sql
   SELECT column_name FROM information_schema.columns 
   WHERE table_name = 'payments' AND column_name = 'updated_at';
   ```

2. **Trigger existe:**
   ```sql
   SELECT trigger_name FROM information_schema.triggers 
   WHERE event_object_table = 'payments' AND trigger_name = 'update_payments_updated_at';
   ```

3. **Sistema funciona:**
   - Tentar gerar PIX
   - Verificar logs (não deve ter erros)
   - Confirmar que PIX foi gerado com sucesso

---

## 🎯 CONCLUSÃO

**Problema:** Coluna `updated_at` não existe no banco.

**Solução:** Executar migration.

**Comando:**
```bash
cd /root/grimbots && source venv/bin/activate && python migrations/add_updated_at_to_payment.py
```

**Próximo passo:** Testar gerar PIX novamente.

