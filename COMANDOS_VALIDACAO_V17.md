# 🔍 COMANDOS DE VALIDAÇÃO - PATCH V17

## 📋 OBJETIVO

Validar que o PATCH V17 está funcionando corretamente e que Payments estão sendo criados mesmo sem `tracking_token`.

---

## 🔍 COMANDOS DE VALIDAÇÃO

### **1. Verificar se há Payments criados sem tracking_token**

```bash
# No banco de dados
psql -c "SELECT COUNT(*) FROM payments WHERE tracking_token IS NULL AND status = 'pending' AND created_at > NOW() - INTERVAL '24 hours';"
```

### **2. Verificar se há Payments criados com tracking_token legado**

```bash
# No banco de dados
psql -c "SELECT COUNT(*) FROM payments WHERE tracking_token LIKE 'tracking_%' AND status = 'pending' AND created_at > NOW() - INTERVAL '24 hours';"
```

### **3. Verificar logs de Payments criados sem tracking_token**

```bash
# Nos logs
tail -f logs/gunicorn.log | grep -i "\[TOKEN AUSENTE\]"
```

### **4. Verificar se Payments estão sendo criados após PIX gerado**

```bash
# Nos logs
tail -f logs/gunicorn.log | grep -i "PIX gerado com sucesso\|Payment será criado mesmo sem tracking_token"
```

### **5. Comparar número de Payments no sistema vs gateway**

```bash
# Payments pendentes no sistema (últimas 24h)
psql -c "SELECT COUNT(*) FROM payments WHERE status = 'pending' AND created_at > NOW() - INTERVAL '24 hours';"

# Verificar se há discrepância significativa
# Se houver, verificar logs para entender por que Payments não estão sendo criados
```

---

## ✅ RESULTADO ESPERADO

**Antes do PATCH V17:**
- ❌ 167 vendas pendentes no gateway
- ❌ 12 vendas pendentes no sistema
- ❌ Discrepância: 155 pagamentos "órfãos"

**Depois do PATCH V17:**
- ✅ Número de vendas pendentes no sistema deve aumentar
- ✅ Discrepância deve diminuir significativamente
- ✅ Todos os PIX gerados devem ter Payment correspondente

---

**COMANDOS DE VALIDAÇÃO PRONTOS! ✅**

