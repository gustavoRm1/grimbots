# 🔍 COMANDOS DE DIAGNÓSTICO - Purchase SEM UTMs e Cobertura 0%

## ⚠️ EXECUTAR NO SERVIDOR LINUX (não no Windows)

### **1. Verificar se há Purchase events recentes**

```bash
tail -500 logs/gunicorn.log | grep -i "purchase" | tail -30
```

### **2. Verificar se há Redirect events recentes**

```bash
tail -500 logs/gunicorn.log | grep -i "redirect" | tail -30
```

### **3. Verificar UTMs em qualquer contexto**

```bash
tail -500 logs/gunicorn.log | grep -i "utm" | tail -30
```

### **4. Verificar event_id em qualquer contexto**

```bash
tail -500 logs/gunicorn.log | grep -iE "event_id|pageview_event_id" | tail -30
```

### **5. Verificar tracking_token em qualquer contexto**

```bash
tail -500 logs/gunicorn.log | grep -i "tracking_token\|tracking:token" | tail -30
```

### **6. Verificar campaign_code em qualquer contexto**

```bash
tail -500 logs/gunicorn.log | grep -iE "campaign_code|grim" | tail -30
```

### **7. Verificar erros críticos recentes**

```bash
tail -500 logs/gunicorn.log | grep -iE "crítico|erro.*purchase|error.*purchase|purchase sem utm" | tail -30
```

### **8. Ver últimas 100 linhas do log (contexto geral)**

```bash
tail -100 logs/gunicorn.log
```

### **9. Verificar especificamente Payment ID 9363 (do erro que você mostrou)**

```bash
tail -1000 logs/gunicorn.log | grep -i "9363\|payment.*9363" | tail -30
```

### **10. Verificar todos os logs de Meta/Purchase/Redirect (últimas 500 linhas)**

```bash
tail -500 logs/gunicorn.log | grep -iE "meta|purchase|redirect|tracking" | tail -50
```

---

## 🎯 COMANDO COMPLETO (copiar e colar tudo de uma vez)

```bash
echo "🔍 DIAGNÓSTICO COMPLETO"
echo "========================"
echo ""
echo "1️⃣ Purchase events recentes:"
tail -500 logs/gunicorn.log | grep -i "purchase" | tail -10
echo ""
echo "2️⃣ Redirect events recentes:"
tail -500 logs/gunicorn.log | grep -i "redirect" | tail -10
echo ""
echo "3️⃣ UTMs recentes:"
tail -500 logs/gunicorn.log | grep -i "utm" | tail -10
echo ""
echo "4️⃣ event_id recentes:"
tail -500 logs/gunicorn.log | grep -iE "event_id|pageview_event_id" | tail -10
echo ""
echo "5️⃣ Erros críticos recentes:"
tail -500 logs/gunicorn.log | grep -iE "crítico|erro.*purchase|purchase sem utm" | tail -10
echo ""
echo "6️⃣ Payment 9363 (do erro):"
tail -1000 logs/gunicorn.log | grep -i "9363" | tail -10
echo ""
echo "✅ Diagnóstico concluído!"
```

---

## 📋 PRÓXIMOS PASSOS

1. **Executar os comandos acima no servidor Linux**
2. **Copiar a saída completa** e enviar para mim
3. **Analisar padrões** para identificar causa raiz

---

## 🔍 O QUE PROCURAR

### **Se NÃO houver Purchase events recentes:**
- ❌ Problema: Não há vendas sendo processadas
- ✅ Solução: Gerar uma venda de teste

### **Se houver Purchase events MAS sem UTMs:**
- ❌ Problema: UTMs não estão sendo salvos no redirect OU não estão sendo recuperados no Purchase
- ✅ Solução: Verificar se Redirect está salvando UTMs e se Purchase está recuperando corretamente

### **Se houver Purchase events MAS sem event_id:**
- ❌ Problema: `pageview_event_id` não está sendo salvo no redirect OU não está sendo recuperado no Purchase
- ✅ Solução: Verificar se Redirect está salvando `pageview_event_id` e se Purchase está recuperando corretamente

---

## ⚠️ IMPORTANTE

**Execute os comandos no servidor Linux, não no Windows!**

Se você está acessando o servidor via SSH:
```bash
ssh root@grimbots.online
cd ~/grimbots
# Depois executar os comandos acima
```

