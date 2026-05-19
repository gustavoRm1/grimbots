# 📋 INSTRUÇÕES - DIAGNÓSTICO PURCHASE

## 🔍 EXECUTAR NA VPS

```bash
cd /root/grimbots
chmod +x encontrar_logs_purchase.sh
./encontrar_logs_purchase.sh
```

---

## 📊 O QUE VERIFICAR

### **1. Purchase está sendo enfileirado?**
- Procurar por: `"📤 Purchase enfileirado"` ou `"Purchase enfileirado"`
- Se aparecer: ✅ Purchase está sendo enfileirado
- Se não aparecer: ❌ Purchase não está sendo enfileirado (problema no código)

### **2. Meta está recebendo Purchase?**
- Procurar por: `"SUCCESS.*Purchase"` ou `"events_received.*Purchase"`
- Se aparecer: ✅ Meta recebeu com sucesso
- Se não aparecer: ❌ Meta não recebeu ou rejeitou

### **3. Há erros?**
- Procurar por: `"FAILED.*Purchase"` ou `"ERROR.*Purchase"`
- Se aparecer: ❌ Meta rejeitou ou erro ao processar
- Verificar mensagem de erro

---

## 🎯 PRÓXIMOS PASSOS BASEADOS NO RESULTADO

### **Se Purchase NÃO está sendo enfileirado:**
- Verificar se `has_meta_pixel = True` quando renderiza template
- Verificar se `meta_events_purchase = True` no pool
- Verificar logs: `"[META DELIVERY] Delivery - Purchase via Server enfileirado"`

### **Se Purchase está sendo enfileirado mas Meta não recebe:**
- Verificar logs do Celery para erros
- Verificar se token está válido
- Verificar payload sendo enviado

### **Se Purchase está sendo enviado com sucesso:**
- Verificar se client-side também dispara
- Verificar deduplicação (eventID igual no browser e server)

---

**Execute o script e compartilhe os resultados!**

