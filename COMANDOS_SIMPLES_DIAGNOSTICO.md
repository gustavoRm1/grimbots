# 🔍 COMANDOS SIMPLES - Verificar o que está nos logs

## ⚠️ EXECUTAR NO SERVIDOR LINUX

### **1. Ver últimas 50 linhas do log (qualquer coisa)**

```bash
tail -50 logs/gunicorn.log
```

### **2. Ver se há alguma linha com "Purchase" (últimas 500 linhas)**

```bash
tail -500 logs/gunicorn.log | grep -i purchase
```

### **3. Ver se há alguma linha com "Redirect" (últimas 500 linhas)**

```bash
tail -500 logs/gunicorn.log | grep -i redirect
```

### **4. Ver se há alguma linha com "9363" (Payment ID do erro)**

```bash
tail -1000 logs/gunicorn.log | grep 9363
```

### **5. Ver se há alguma linha com "utm" (qualquer coisa relacionada a UTMs)**

```bash
tail -500 logs/gunicorn.log | grep -i utm
```

### **6. Ver se há alguma linha com "event" (qualquer coisa relacionada a eventos)**

```bash
tail -500 logs/gunicorn.log | grep -i event
```

### **7. Ver se há alguma linha com "tracking" (qualquer coisa relacionada a tracking)**

```bash
tail -500 logs/gunicorn.log | grep -i tracking
```

### **8. Ver se há alguma linha com "campaign" (qualquer coisa relacionada a campanhas)**

```bash
tail -500 logs/gunicorn.log | grep -i campaign
```

---

## 🎯 COMANDO ÚNICO (copiar e colar tudo)

```bash
echo "========================"
echo "ÚLTIMAS 50 LINHAS:"
echo "========================"
tail -50 logs/gunicorn.log
echo ""
echo "========================"
echo "BUSCANDO 'purchase' (últimas 500 linhas):"
echo "========================"
tail -500 logs/gunicorn.log | grep -i purchase
echo ""
echo "========================"
echo "BUSCANDO '9363' (últimas 1000 linhas):"
echo "========================"
tail -1000 logs/gunicorn.log | grep 9363
echo ""
echo "========================"
echo "BUSCANDO 'utm' (últimas 500 linhas):"
echo "========================"
tail -500 logs/gunicorn.log | grep -i utm
echo ""
echo "✅ Concluído!"
```

---

## 📋 PRÓXIMOS PASSOS

1. **Execute o comando único acima** no servidor Linux
2. **Copie TODA a saída** (mesmo que seja vazia) e envie para mim
3. **Se não houver saída**, execute apenas `tail -100 logs/gunicorn.log` e envie o resultado

---

## ⚠️ IMPORTANTE

**Se os comandos não retornarem nada, pode significar:**
- ❌ Não há Purchase events recentes nos logs
- ❌ Os logs estão em outro arquivo/local
- ❌ Os logs não estão sendo gerados

**Solução:**
- Execute `tail -100 logs/gunicorn.log` para ver o que há nos logs recentes
- Verifique se o arquivo `logs/gunicorn.log` existe: `ls -la logs/gunicorn.log`
- Verifique se há outros arquivos de log: `ls -la logs/`

