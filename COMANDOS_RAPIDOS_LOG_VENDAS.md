# ⚡ COMANDOS RÁPIDOS - Ver Logs de Vendas

## 🎯 COMANDOS MAIS USADOS

### **1. Ver Últimas Vendas (rápido)**
```bash
tail -100 logs/gunicorn.log | grep -i "payment"
```

### **2. Ver Vendas em Tempo Real**
```bash
tail -f logs/gunicorn.log | grep -i "payment"
```

### **3. Ver Última Venda Específica**
```bash
# Substituir 9380 pelo ID da venda
tail -500 logs/gunicorn.log | grep "9380"
```

### **4. Ver Todas as Vendas Recentes**
```bash
tail -500 logs/gunicorn.log | grep -iE "payment|pix|purchase"
```

---

## 📊 SCRIPTS PRONTOS

### **1. Executar Script Completo**
```bash
bash ver_logs_vendas.sh
```

### **2. Ver Venda Específica**
```bash
# Exemplo: ver venda 9380
bash ver_venda_especifica.sh 9380
```

### **3. Ver Vendas de Hoje**
```bash
bash ver_vendas_hoje.sh
```

---

## 🔍 FILTROS ÚTEIS

### **Ver apenas Vendas Confirmadas**
```bash
tail -500 logs/gunicorn.log | grep -i "paid\|confirmado"
```

### **Ver apenas Purchase Events**
```bash
tail -500 logs/gunicorn.log | grep -i "purchase"
```

### **Ver apenas Erros**
```bash
tail -500 logs/gunicorn.log | grep -i "erro\|error\|❌"
```

### **Ver apenas PIX Gerados**
```bash
tail -500 logs/gunicorn.log | grep -i "pix.*gerado\|payment.*created"
```

---

## ⚠️ IMPORTANTE

**Execute os comandos no servidor Linux, não no Windows!**

Se você está no Windows, acesse o servidor via SSH:
```bash
ssh root@grimbots.online
cd ~/grimbots
# Depois executar os comandos acima
```

