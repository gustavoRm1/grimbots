# ✅ COMO VERIFICAR SE PARAMETER BUILDER FUNCIONOU

## 🎯 **VERIFICAÇÃO RÁPIDA (5 MINUTOS)**

### **1. VERIFICAR LOGS EM TEMPO REAL**

```bash
# No VPS, executar:
tail -f logs/gunicorn.log | grep -E "PARAM BUILDER|PARAMETER BUILDER|fbc processado|fbp processado|client_ip processado"
```

**O que procurar:**
- ✅ `[PARAM BUILDER] fbc capturado do cookie`
- ✅ `[PARAM BUILDER] fbc gerado baseado em fbclid`
- ✅ `[PARAM BUILDER] fbp capturado do cookie`
- ✅ `[PARAM BUILDER] client_ip capturado do Parameter Builder (_fbi)`
- ✅ `[META PAGEVIEW] PageView - fbc processado pelo Parameter Builder`
- ✅ `[META PURCHASE] Purchase - fbc processado pelo Parameter Builder`

---

### **2. VERIFICAR META EVENTS MANAGER**

1. Acesse: **Meta Events Manager** → **Eventos** → **Comprar (Purchase)**
2. Verifique a seção **"Parâmetros compartilhados"**
3. Procure por **"ID do clique (fbc)"**

**Antes da implementação:**
- ❌ **"Seu servidor não está enviando o ID de clique (fbc) pela API de Conversões"**

**Depois da implementação:**
- ✅ **"ID do clique (fbc) - Sem hash - nenhum hash necessário"**
- ✅ **Percentual de eventos que enviam: X% do total de eventos**
- ✅ **Medidor de cobertura: X de 100**

**Meta recomenda:**
- ✅ **Cobertura de `fbc` > 50%** (ideal: > 80%)
- ✅ **"Pelo menos um aumento mediano de 100% em conversões adicionais já relatadas"**

---

## 🔍 **VERIFICAÇÃO DETALHADA**

### **3. TESTAR REDIRECT COM FBclid**

**Passo 1**: Criar URL de teste com `fbclid`:
```
https://app.grimbots.online/go/SEU_SLUG?grim=SEU_GRIM&fbclid=IwAR1234567890...
```

**Passo 2**: Acessar URL e verificar logs:
```bash
tail -f logs/gunicorn.log | grep -E "PARAM BUILDER|PageView.*fbc|PageView.*fbp"
```

**O que deve aparecer:**
- ✅ `[PARAM BUILDER] fbc gerado baseado em fbclid (conforme doc Meta): fb.1.1234567890.IwAR1234567890...`
- ✅ `[META PAGEVIEW] PageView - fbc processado pelo Parameter Builder (origem: generated_from_fbclid)`
- ✅ `[META PAGEVIEW] PageView - fbp processado pelo Parameter Builder (origem: cookie)`
- ✅ `[META PAGEVIEW] PageView - client_ip processado pelo Parameter Builder (origem: parameter_builder)`

---

### **4. TESTAR PURCHASE EVENT**

**Passo 1**: Gerar um pagamento via bot
**Passo 2**: Verificar logs do Purchase:
```bash
tail -f logs/gunicorn.log | grep -E "META PURCHASE.*fbc|META PURCHASE.*Parameter Builder"
```

**O que deve aparecer:**
- ✅ `[META PURCHASE] Purchase - fbc processado pelo Parameter Builder (origem: cookie/generated_from_fbclid)`
- ✅ `[META PURCHASE] Purchase - fbp processado pelo Parameter Builder (origem: cookie)`
- ✅ `[META PURCHASE] Purchase - client_ip processado pelo Parameter Builder (origem: parameter_builder)`
- ✅ `[META PURCHASE] Purchase - fbc REAL aplicado: fb.1.1234567890...`

---

### **5. VERIFICAR REDIS (DADOS SALVOS)**

```bash
# No VPS, executar:
cd ~/grimbots
source venv/bin/activate
python3 << 'EOF'
import redis
import json

r = redis.from_url('redis://localhost:6379/0', decode_responses=True)

# Buscar último tracking_token (exemplo)
keys = r.keys('tracking:*')
if keys:
    latest_key = keys[-1]
    data = r.get(latest_key)
    if data:
        tracking_data = json.loads(data)
        print(f"✅ Tracking Token: {latest_key}")
        print(f"   fbc: {tracking_data.get('fbc', '❌ NONE')[:50] if tracking_data.get('fbc') else '❌ NONE'}")
        print(f"   fbc_origin: {tracking_data.get('fbc_origin', '❌ NONE')}")
        print(f"   fbp: {tracking_data.get('fbp', '❌ NONE')[:30] if tracking_data.get('fbp') else '❌ NONE'}")
        print(f"   client_ip: {tracking_data.get('client_ip', '❌ NONE')}")
        print(f"   client_ip_origin: {tracking_data.get('client_ip_origin', '❌ NONE')}")
        print(f"   fbclid: {tracking_data.get('fbclid', '❌ NONE')[:50] if tracking_data.get('fbclid') else '❌ NONE'}")
    else:
        print("❌ Dados não encontrados")
else:
    print("❌ Nenhum tracking_token encontrado")
EOF
```

---

## 📊 **MÉTRICAS PARA MONITORAR**

### **1. COBERTURA DE `fbc`**

**Comando para verificar cobertura:**
```bash
# Contar eventos com fbc nos últimos logs
grep -c "fbc processado pelo Parameter Builder" logs/gunicorn.log
grep -c "Purchase - fbc REAL aplicado" logs/gunicorn.log
grep -c "Purchase - fbc ausente ou ignorado" logs/gunicorn.log
```

**Cálculo:**
- **Total de Purchase events**: `grep -c "META PURCHASE.*Purchase -" logs/gunicorn.log`
- **Purchase com fbc**: `grep -c "Purchase - fbc REAL aplicado" logs/gunicorn.log`
- **Cobertura**: `(Purchase com fbc / Total de Purchase events) * 100`

**Expectativa**: **> 50%** (ideal: **> 80%**)

---

### **2. ORIGEM DO `fbc`**

**Comandos:**
```bash
# FBC do cookie (MAIS CONFIÁVEL)
grep -c "fbc processado pelo Parameter Builder (origem: cookie)" logs/gunicorn.log

# FBC gerado baseado em fbclid (CONFORME META BEST PRACTICES)
grep -c "fbc processado pelo Parameter Builder (origem: generated_from_fbclid)" logs/gunicorn.log

# FBC ausente
grep -c "fbc ausente ou ignorado" logs/gunicorn.log
```

**Expectativa**:
- ✅ **FBC do cookie**: > 30% (ideal: > 50%)
- ✅ **FBC gerado**: > 20% (ideal: > 40%)
- ⚠️ **FBC ausente**: < 50% (ideal: < 20%)

---

### **3. CLIENT_IP DO PARAMETER BUILDER**

**Comandos:**
```bash
# Client IP do Parameter Builder (_fbi)
grep -c "client_ip processado pelo Parameter Builder (origem: parameter_builder)" logs/gunicorn.log

# Client IP do X-Forwarded-For
grep -c "client_ip processado pelo Parameter Builder (origem: x_forwarded_for)" logs/gunicorn.log

# Client IP ausente
grep -c "client_ip NÃO encontrado" logs/gunicorn.log
```

**Expectativa**:
- ✅ **Client IP do Parameter Builder**: > 50% (ideal: > 70%)
- ✅ **Client IP do X-Forwarded-For**: > 30% (ideal: > 20%)
- ⚠️ **Client IP ausente**: < 20% (ideal: < 10%)

---

## 🔬 **VALIDAÇÃO VIA META EVENTS MANAGER**

### **1. ACESSAR META EVENTS MANAGER**

1. Acesse: **Meta Business Suite** → **Events Manager**
2. Selecione seu **Pixel ID**
3. Vá em **Eventos** → **Comprar (Purchase)**

---

### **2. VERIFICAR SEÇÃO "Parâmetros compartilhados"**

**Procurar por:**
- ✅ **"ID do clique (fbc)"** → Deve aparecer com **"Sem hash - nenhum hash necessário"**
- ✅ **"Percentual de eventos que enviam"** → Deve ser **> 50%** (ideal: **> 80%**)
- ✅ **"Medidor de cobertura"** → Deve ser **> 50 de 100** (ideal: **> 80 de 100**)

**Se ainda aparecer:**
- ❌ **"Seu servidor não está enviando o ID de clique (fbc) pela API de Conversões"**
- ⚠️ **Aguarde 24-48 horas** para Meta processar os dados

---

### **3. VERIFICAR SEÇÃO "Desempenho atual dos parâmetros"**

**Procurar por:**
- ✅ **"Melhore a desduplicação para este evento"** → Deve **NÃO aparecer mais** se `event_id` estiver correto
- ✅ **"Melhore a qualidade de combinação"** → Deve melhorar com `fbc` sendo enviado

---

## 🧪 **TESTE MANUAL COMPLETO**

### **Script de Teste Completo**

```bash
#!/bin/bash
# Salvar como: testar_parameter_builder.sh

echo "🧪 TESTANDO PARAMETER BUILDER"
echo "================================"
echo ""

# 1. Verificar se função existe
echo "1️⃣ Verificando se função process_meta_parameters existe..."
python3 << 'EOF'
try:
    from utils.meta_pixel import process_meta_parameters
    print("✅ Função process_meta_parameters encontrada!")
    
    # Testar função
    result = process_meta_parameters(
        request_cookies={'_fbc': 'fb.1.1234567890.IwAR1234567890', '_fbp': 'fb.1.1234567890.1234567890', '_fbi': '192.168.1.1'},
        request_args={'fbclid': 'IwAR1234567890'},
        request_headers={'X-Forwarded-For': '192.168.1.1'},
        request_remote_addr='192.168.1.2'
    )
    
    print(f"✅ Teste da função OK!")
    print(f"   fbc: {result.get('fbc', 'None')[:50] if result.get('fbc') else 'None'}")
    print(f"   fbc_origin: {result.get('fbc_origin', 'None')}")
    print(f"   fbp: {result.get('fbp', 'None')[:30] if result.get('fbp') else 'None'}")
    print(f"   client_ip_address: {result.get('client_ip_address', 'None')}")
    print(f"   ip_origin: {result.get('ip_origin', 'None')}")
except Exception as e:
    print(f"❌ ERRO: {e}")
EOF

echo ""
echo "2️⃣ Verificando logs recentes (últimos 100 linhas)..."
echo ""

# 2. Verificar logs recentes
tail -100 logs/gunicorn.log | grep -E "PARAM BUILDER|Parameter Builder|fbc processado|fbp processado" | tail -10

echo ""
echo "3️⃣ Estatísticas dos últimos eventos..."
echo ""

# 3. Estatísticas
TOTAL_PAGEVIEW=$(tail -1000 logs/gunicorn.log | grep -c "META PAGEVIEW.*PageView -" || echo "0")
PAGEVIEW_FBC=$(tail -1000 logs/gunicorn.log | grep -c "PageView - fbc processado pelo Parameter Builder" || echo "0")
TOTAL_PURCHASE=$(tail -1000 logs/gunicorn.log | grep -c "META PURCHASE.*Purchase -" || echo "0")
PURCHASE_FBC=$(tail -1000 logs/gunicorn.log | grep -c "Purchase - fbc REAL aplicado" || echo "0")

echo "   PageView: ${PAGEVIEW_FBC}/${TOTAL_PAGEVIEW} com fbc ($(echo "scale=1; ${PAGEVIEW_FBC}*100/${TOTAL_PAGEVIEW}" | bc)%)"
echo "   Purchase: ${PURCHASE_FBC}/${TOTAL_PURCHASE} com fbc ($(echo "scale=1; ${PURCHASE_FBC}*100/${TOTAL_PURCHASE}" | bc)%)"

echo ""
echo "✅ Teste concluído!"
```

**Executar:**
```bash
chmod +x testar_parameter_builder.sh
./testar_parameter_builder.sh
```

---

## ⚡ **VERIFICAÇÃO RÁPIDA (1 MINUTO)**

### **Comando Único**

```bash
tail -500 logs/gunicorn.log | grep -E "fbc processado pelo Parameter Builder|fbc REAL aplicado|fbc ausente" | tail -20
```

**O que procurar:**
- ✅ Múltiplas linhas com `fbc processado pelo Parameter Builder`
- ✅ Múltiplas linhas com `fbc REAL aplicado`
- ⚠️ **NÃO** ver muitas linhas com `fbc ausente ou ignorado`

---

## 📈 **RESULTADO ESPERADO**

### **ANTES DA IMPLEMENTAÇÃO:**
```
[META PURCHASE] Purchase - fbc ausente ou ignorado. Match Quality será prejudicada.
[META PURCHASE] Purchase - fbc NÃO encontrado em nenhuma fonte!
```

### **DEPOIS DA IMPLEMENTAÇÃO:**
```
[PARAM BUILDER] fbc gerado baseado em fbclid (conforme doc Meta): fb.1.1234567890...
[META PAGEVIEW] PageView - fbc processado pelo Parameter Builder (origem: generated_from_fbclid): fb.1.1234567890...
[META PURCHASE] Purchase - fbc processado pelo Parameter Builder (origem: generated_from_fbclid): fb.1.1234567890...
[META PURCHASE] Purchase - fbc REAL aplicado: fb.1.1234567890...
```

---

## 🎯 **CHECKLIST DE VALIDAÇÃO**

- [ ] Função `process_meta_parameters` existe e funciona
- [ ] Logs mostram `fbc processado pelo Parameter Builder`
- [ ] Logs mostram `fbc REAL aplicado` (Purchase)
- [ ] Logs mostram `client_ip processado pelo Parameter Builder`
- [ ] Meta Events Manager mostra cobertura de `fbc` > 50%
- [ ] Meta Events Manager **NÃO** mostra mais: "Seu servidor não está enviando o ID de clique (fbc)"
- [ ] Estatísticas mostram cobertura de `fbc` > 50% nos eventos

---

## ⚠️ **SE NÃO FUNCIONAR**

### **Verificar:**
1. ✅ Aplicação foi reiniciada após implementação?
2. ✅ Logs estão sendo gerados?
3. ✅ Redis está funcionando?
4. ✅ Client-side Parameter Builder está capturando `_fbc`, `_fbp`, `_fbi`?

### **Comandos de Debug:**
```bash
# Verificar se função foi importada corretamente
python3 -c "from utils.meta_pixel import process_meta_parameters; print('✅ OK')"

# Verificar erros nos logs
tail -100 logs/gunicorn.log | grep -i error

# Verificar se Parameter Builder está sendo chamado
tail -500 logs/gunicorn.log | grep -c "process_meta_parameters"
```

---

## ✅ **CONCLUSÃO**

**Se todos os itens do checklist estiverem OK**, a implementação está funcionando corretamente!

**Tempo de propagação no Meta Events Manager**: 24-48 horas para dados aparecerem.

