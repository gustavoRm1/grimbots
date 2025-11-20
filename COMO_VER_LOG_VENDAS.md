# 📊 COMO VER LOGS DE VENDAS

## 🎯 OBJETIVO

Verificar logs de vendas (payments) no sistema para diagnosticar problemas e confirmar funcionamento.

---

## 📋 COMANDOS BÁSICOS

### **1. Ver Últimas Vendas (últimas 50 linhas)**

```bash
tail -50 logs/gunicorn.log | grep -i "payment\|venda\|purchase"
```

### **2. Ver Todas as Vendas Recentes (últimas 500 linhas)**

```bash
tail -500 logs/gunicorn.log | grep -i "payment\|venda\|purchase"
```

### **3. Ver Vendas em Tempo Real**

```bash
tail -f logs/gunicorn.log | grep -i "payment\|venda\|purchase"
```

### **4. Ver Últimas 100 Linhas do Log (qualquer coisa)**

```bash
tail -100 logs/gunicorn.log
```

---

## 🔍 COMANDOS ESPECÍFICOS

### **1. Ver Pagamentos Gerados (PIX gerados)**

```bash
tail -500 logs/gunicorn.log | grep -i "pix.*gerado\|payment.*created\|payment.*pending"
```

### **2. Ver Pagamentos Confirmados (paid)**

```bash
tail -500 logs/gunicorn.log | grep -i "payment.*paid\|payment.*confirmado\|status.*paid"
```

### **3. Ver Purchase Events Enviados**

```bash
tail -500 logs/gunicorn.log | grep -i "purchase.*enviado\|purchase.*sent\|purchase.*events received"
```

### **4. Ver Erros em Vendas**

```bash
tail -500 logs/gunicorn.log | grep -i "erro.*payment\|error.*payment\|❌.*payment"
```

---

## 📊 VERIFICAR VENDA ESPECÍFICA

### **1. Ver Venda por Payment ID**

```bash
# Substituir 9380 pelo ID da venda
tail -1000 logs/gunicorn.log | grep "9380\|payment.*9380"
```

### **2. Ver Venda por Payment ID Completo**

```bash
# Substituir BOT43_1763607031_eabd7eaf pelo payment_id completo
tail -1000 logs/gunicorn.log | grep "BOT43_1763607031_eabd7eaf"
```

---

## 🎯 COMANDOS AVANÇADOS

### **1. Ver Todas as Vendas do Último Dia**

```bash
tail -5000 logs/gunicorn.log | grep -i "payment.*paid\|payment.*confirmado"
```

### **2. Ver Vendas com Valor**

```bash
tail -500 logs/gunicorn.log | grep -E "R\$ [0-9]+|[0-9]+\.[0-9]+.*payment|payment.*[0-9]+\.[0-9]+"
```

### **3. Ver Vendas com Bot ID**

```bash
# Substituir 43 pelo bot_id
tail -500 logs/gunicorn.log | grep -i "bot.*43.*payment\|payment.*bot.*43"
```

### **4. Ver Vendas com Telegram User ID**

```bash
# Substituir 5662124356 pelo telegram_user_id
tail -500 logs/gunicorn.log | grep "5662124356\|customer_user_id.*5662124356"
```

---

## 🔍 VERIFICAR STATUS DE VENDAS

### **1. Ver Vendas Pendentes**

```bash
tail -500 logs/gunicorn.log | grep -i "payment.*pending\|status.*pending"
```

### **2. Ver Vendas Confirmadas**

```bash
tail -500 logs/gunicorn.log | grep -i "payment.*paid\|status.*paid\|payment.*confirmado"
```

### **3. Ver Vendas Canceladas**

```bash
tail -500 logs/gunicorn.log | grep -i "payment.*cancelled\|status.*cancelled\|payment.*cancelado"
```

---

## 📋 COMANDO COMPLETO (copiar e colar)

```bash
echo "📊 LOGS DE VENDAS"
echo "=================="
echo ""
echo "1️⃣ Últimas vendas (últimas 50 linhas):"
tail -50 logs/gunicorn.log | grep -i "payment\|venda\|purchase"
echo ""
echo "2️⃣ Pagamentos gerados (PIX):"
tail -500 logs/gunicorn.log | grep -i "pix.*gerado\|payment.*created" | tail -5
echo ""
echo "3️⃣ Pagamentos confirmados (paid):"
tail -500 logs/gunicorn.log | grep -i "payment.*paid\|status.*paid" | tail -5
echo ""
echo "4️⃣ Purchase events enviados:"
tail -500 logs/gunicorn.log | grep -i "purchase.*enviado\|purchase.*sent" | tail -5
echo ""
echo "5️⃣ Erros em vendas:"
tail -500 logs/gunicorn.log | grep -i "erro.*payment\|error.*payment" | tail -5
echo ""
echo "✅ Verificação concluída!"
```

---

## 🎯 SCRIPTS CRIADOS

### **Script 1: ver_logs_vendas.sh**

```bash
#!/bin/bash
echo "📊 LOGS DE VENDAS"
echo "=================="
echo ""
echo "1️⃣ Últimas vendas (últimas 100 linhas):"
tail -100 logs/gunicorn.log | grep -i "payment\|venda\|purchase"
echo ""
echo "2️⃣ Pagamentos gerados (últimos 10):"
tail -1000 logs/gunicorn.log | grep -i "pix.*gerado\|payment.*created" | tail -10
echo ""
echo "3️⃣ Pagamentos confirmados (últimos 10):"
tail -1000 logs/gunicorn.log | grep -i "payment.*paid\|status.*paid" | tail -10
echo ""
echo "4️⃣ Purchase events enviados (últimos 10):"
tail -1000 logs/gunicorn.log | grep -i "purchase.*enviado\|purchase.*sent\|purchase.*events received" | tail -10
echo ""
echo "✅ Verificação concluída!"
```

### **Script 2: ver_venda_especifica.sh**

```bash
#!/bin/bash
# Uso: bash ver_venda_especifica.sh <payment_id>
# Exemplo: bash ver_venda_especifica.sh 9380

if [ -z "$1" ]; then
    echo "❌ Uso: bash ver_venda_especifica.sh <payment_id>"
    echo "   Exemplo: bash ver_venda_especifica.sh 9380"
    exit 1
fi

PAYMENT_ID=$1

echo "🔍 VERIFICANDO VENDA: $PAYMENT_ID"
echo "=================================="
echo ""
echo "1️⃣ Logs relacionados a payment $PAYMENT_ID:"
tail -1000 logs/gunicorn.log | grep -i "$PAYMENT_ID" | tail -20
echo ""
echo "2️⃣ Payment gerado:"
tail -1000 logs/gunicorn.log | grep -i "payment.*$PAYMENT_ID.*created\|pix.*gerado.*$PAYMENT_ID" | tail -3
echo ""
echo "3️⃣ Payment confirmado:"
tail -1000 logs/gunicorn.log | grep -i "payment.*$PAYMENT_ID.*paid\|status.*paid.*$PAYMENT_ID" | tail -3
echo ""
echo "4️⃣ Purchase event:"
tail -1000 logs/gunicorn.log | grep -i "purchase.*$PAYMENT_ID\|payment.*$PAYMENT_ID.*purchase" | tail -5
echo ""
echo "✅ Verificação concluída!"
```

---

## 📊 O QUE PROCURAR NOS LOGS

### **✅ Venda Gerada com Sucesso:**
```
✅ PIX ENVIADO! ID: BOT43_1763607031_eabd7eaf
Payment criado: 9380
```

### **✅ Venda Confirmada:**
```
✅ Payment confirmado: 9380
Status atualizado: paid
Payment paid: 9380
```

### **✅ Purchase Event Enviado:**
```
✅ Purchase ENVIADO: BOT43_1763607031_eabd7eaf | Events Received: 1
Purchase via Server enfileirado com sucesso
```

### **❌ Erro em Venda:**
```
❌ Erro ao gerar PIX
❌ Erro ao confirmar payment
❌ Payment não encontrado
```

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ Executar comandos acima no servidor Linux
2. ✅ Verificar logs de vendas específicas
3. ✅ Verificar se Purchase events estão sendo enviados
4. ✅ Verificar se há erros em vendas

---

## ⚠️ IMPORTANTE

**Execute os comandos no servidor Linux, não no Windows!**

Se você está acessando o servidor via SSH:
```bash
ssh root@grimbots.online
cd ~/grimbots
# Depois executar os comandos acima
```

