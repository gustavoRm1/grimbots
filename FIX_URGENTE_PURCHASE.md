# 🚨 FIX URGENTE: META PURCHASE NÃO ENVIA

## **🔴 PROBLEMAS IDENTIFICADOS:**

### **1. NENHUM external_id/fbclid CAPTURADO** ❌
```
Com external_id: 0 (0.0%)
Com fbclid: 0 (0.0%)
```

**CAUSA:** Sistema não está capturando fbclid corretamente no redirect

### **2. NENHUM Purchase ENVIADO** ❌
```
Enviados ao Meta: 0
NÃO enviados: 65
```

**CAUSA:** Eventos não estão sendo disparados

### **3. TRACKING ELITE NÃO ATIVO** ❌
```
Com IP: 0 (0.0%)
Com UA: 0 (0.0%)
```

**CAUSA:** Migration não foi rodada

---

## **🔧 CORREÇÃO IMEDIATA:**

### **PASSO 1: RODAR MIGRATION**
```bash
cd ~/grimbots
python migrate_add_tracking_fields.py
```

### **PASSO 2: VERIFICAR CAPTURA DE FBCLID**

O problema é que o código está esperando fbclid dentro do `start_param` decodificado, mas o Facebook pode estar enviando de forma diferente.

Vou verificar os logs:
```bash
sudo journalctl -u grimbots | grep "fbclid" | tail -20
```

Se não aparecer fbclid NOS LOGS, o problema é na captura.

### **PASSO 3: FIX CRÍTICO - CAPTURAR FBCLID NO REDIRECT**

O código atual em `app.py` (linha ~2750) **JÁ CAPTURA fbclid**, mas pode não estar associando corretamente ao BotUser.

**Verificar se está salvando no Redis:**
```bash
redis-cli KEYS "tracking:*"
redis-cli GET "tracking:FBCLID_AQUI"
```

Se estiver vazio, o problema é que fbclid não está vindo na URL.

### **PASSO 4: TESTAR URL COMPLETA**

```bash
# Fazer request COM fbclid
curl -v "https://app.grimbots.online/go/red1?testecamu01&fbclid=TESTE_MANUAL_123&utm_source=facebook"

# Verificar Redis
redis-cli GET "tracking:TESTE_MANUAL_123"
```

---

## **💡 SOLUÇÃO ALTERNATIVA (SE FBCLID NÃO VEM):**

Se o Facebook NÃO está enviando fbclid, podemos:

1. **Gerar external_id sintético:**
```python
# No redirect
import uuid
external_id = str(uuid.uuid4())

# Salvar no Redis
tracking_data['external_id'] = external_id

# Passar no start_param
redirect_url = f"https://t.me/{bot.username}?start=e_{external_id}"
```

2. **Usar Session ID como external_id:**
```python
# No redirect
session_id = str(uuid.uuid4())
# Este session_id vira external_id
```

---

## **🎯 EXECUTE AGORA:**

```bash
# 1. Migration
python migrate_add_tracking_fields.py

# 2. Ver últimos redirects
sudo journalctl -u grimbots -n 100 | grep -E "Redirect:|fbclid|TRACKING ELITE"

# 3. Testar redirect manual
curl -v "https://app.grimbots.online/go/red1?testecamu01&fbclid=TESTE123"

# 4. Ver Redis
redis-cli GET "tracking:TESTE123"
```

**ME MANDE A SAÍDA!** 🎯

