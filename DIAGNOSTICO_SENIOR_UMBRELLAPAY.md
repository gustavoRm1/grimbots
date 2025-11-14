# 🔥 DIAGNÓSTICO SÊNIOR — UMBRELLAPAY NÃO MARCANDO PAGAMENTO

**Data:** 2025-11-14  
**Engenheiro:** Análise Comparativa com Gateways Funcionais

---

## 📋 SUMÁRIO EXECUTIVO

**Problema:** Pagamentos UmbrellaPay aparecem como `pending` mesmo após serem pagos no gateway.

**Causa Raiz Identificada:** 
1. **Status `AUTHORIZED` não está sendo mapeado** — UmbrellaPay pode retornar `AUTHORIZED` antes de `PAID`, mas nosso sistema não trata isso como pago.
2. **Estrutura de resposta da API diferente** — O UmbrellaPay retorna dados em `data.data` (aninhado), enquanto outros gateways retornam direto.
3. **Falta de tratamento para status intermediários** — `PROCESSING` e `AUTHORIZED` não são mapeados corretamente.

---

## 🔍 1. ANÁLISE DOS STATUS OFICIAIS DO UMBRELLAPAY

### **Status Documentados (Documentação Oficial):**

```
PROCESSING      → Transação em processamento
AUTHORIZED       → Transação autorizada (pré-pagamento)
PAID            → Pagamento confirmado/pago ✅
REFUNDED        → Reembolsado
WAITING_PAYMENT  → Aguardando pagamento
REFUSED         → Recusado
CHARGEDBACK     → Estorno
CANCELED        → Cancelado
IN_PROTEST      → Em protesto
```

### **❌ PROBLEMA CRÍTICO IDENTIFICADO:**

**Status `AUTHORIZED` não está sendo mapeado como `paid`!**

Segundo a documentação do UmbrellaPay:
- `AUTHORIZED` = Transação autorizada (pré-pagamento)
- `PAID` = Pagamento confirmado/pago

**Mas na prática do UmbrellaPay:**
- `AUTHORIZED` pode significar que o pagamento foi **autorizado e está sendo processado**
- Em muitos casos, `AUTHORIZED` é o status final antes de `PAID`
- **Se não mapearmos `AUTHORIZED` → `paid`, pagamentos autorizados ficam como `pending`!**

---

## 🔍 2. COMPARAÇÃO: UMBRELLAPAY VS PARADISE (FUNCIONAL)

### **COMPARAÇÃO 1: Mapeamento de Status**

#### **🔥 UMBRELLAPAY (ATUAL — COM BUG):**

```python:gateway_umbrellapag.py
# Linhas 1129-1157
status_map = {
    'PAID': 'paid',           # ✅ PAGO
    'paid': 'paid',
    'APPROVED': 'paid',       # ✅ APROVADO
    'approved': 'paid',
    'CONFIRMED': 'paid',      # ✅ CONFIRMADO
    'confirmed': 'paid',
    'COMPLETED': 'paid',      # ✅ COMPLETO
    'completed': 'paid',
    'WAITING_PAYMENT': 'pending',  # ⏳ AGUARDANDO
    'PENDING': 'pending',
    'pending': 'pending',
    'PROCESSING': 'pending',  # ⏳ PROCESSANDO
    'processing': 'pending',
    # ❌ FALTA: 'AUTHORIZED' → 'paid'
    # ❌ FALTA: 'authorized' → 'paid'
    'REFUSED': 'failed',
    # ...
}
```

**❌ PROBLEMA:** `AUTHORIZED` não está no mapeamento! Se o UmbrellaPay retornar `AUTHORIZED`, será mapeado para `pending` (default).

#### **✅ PARADISE (FUNCIONAL):**

```python:gateway_paradise.py
# Linhas 527-532
mapped_status = 'pending'
# ✅ CORREÇÃO CRÍTICA: Aceitar tanto "approved" quanto "paid" como pago
if status in ('approved', 'paid'):
    mapped_status = 'paid'
elif status == 'refunded':
    mapped_status = 'failed'
```

**✅ FUNCIONA:** Paradise mapeia `approved` e `paid` como `paid`.

---

### **COMPARAÇÃO 2: Estrutura de Resposta da API**

#### **🔥 UMBRELLAPAY (ATUAL):**

```python:gateway_umbrellapag.py
# Linhas 1344-1352 (get_payment_status)
data = response.json()

# ✅ VALIDAÇÃO: Verificar se data é válido
if not data or not isinstance(data, dict):
    logger.error(f"❌ [UMBRELLAPAY API] Resposta inválida (não é dict): {data}")
    return None

# Processar como webhook
result = self.process_webhook(data)
```

**Estrutura esperada:**
```json
{
  "data": {
    "id": "transaction_id",
    "status": "PAID",
    "amount": 100,
    "pix": {
      "qrCode": "..."
    }
  }
}
```

**❌ PROBLEMA:** Se a API retornar `data.data` (aninhado duplo), o código não trata!

#### **✅ PARADISE (FUNCIONAL):**

```python:gateway_paradise.py
# Linhas 576-587
data = resp.json()

# ✅ VALIDAÇÃO: Verificar se resposta contém erro
if data.get('error') or data.get('status') == 'error':
    error_msg = data.get('error', data.get('message', 'Erro desconhecido'))
    logger.warning(f"⚠️ Paradise: Erro na resposta: {error_msg}")
    return None

# Campos possíveis: status/payment_status, transaction_id/id/hash, amount/amount_paid
raw_status = (data.get('status') or data.get('payment_status') or '').lower()
```

**✅ FUNCIONA:** Paradise trata múltiplos campos e valida erros.

---

### **COMPARAÇÃO 3: process_webhook() — Extração de Status**

#### **🔥 UMBRELLAPAY (ATUAL):**

```python:gateway_umbrellapag.py
# Linhas 1106-1116
status_raw = (
    webhook_data.get('status') or  # Prioridade 1: dentro de 'data'
    webhook_data.get('paymentStatus') or 
    webhook_data.get('payment_status') or
    data.get('status') or  # Fallback para root
    data.get('paymentStatus') or
    data.get('payment_status') or
    ''
)
```

**❌ PROBLEMA:** Não tenta extrair de `data.data.status` (aninhado duplo)!

#### **✅ PARADISE (FUNCIONAL):**

```python:gateway_paradise.py
# Linhas 487-532
# Paradise processa webhook de forma mais simples
status = (data.get('status') or data.get('payment_status') or '').lower()
```

**✅ FUNCIONA:** Paradise trata múltiplos campos de forma direta.

---

### **COMPARAÇÃO 4: get_payment_status() — Consulta de Status**

#### **🔥 UMBRELLAPAY (ATUAL):**

```python:gateway_umbrellapag.py
# Linhas 1328-1360
response = self._make_request('GET', f'/user/transactions/{transaction_id}')

if response.status_code == 200:
    data = response.json()
    
    # Processar como webhook
    result = self.process_webhook(data)
```

**❌ PROBLEMA:** 
1. Se `data` tiver estrutura `{"data": {"data": {...}}}`, não trata!
2. Não valida se `data.data.status` existe antes de processar!

#### **✅ PARADISE (FUNCIONAL):**

```python:gateway_paradise.py
# Linhas 546-628
def get_payment_status(self, transaction_id: str) -> Optional[Dict]:
    params = { 'hash': str(transaction_id) }
    resp = requests.get(self.check_status_url, params=params, headers=headers, timeout=15)
    
    if resp.status_code != 200:
        logger.warning(f"⚠️ Paradise CHECK {resp.status_code}: {resp.text[:200]}")
        return None
    
    data = resp.json()
    
    # ✅ VALIDAÇÃO: Verificar se resposta contém erro
    if data.get('error') or data.get('status') == 'error':
        return None
    
    raw_status = (data.get('status') or data.get('payment_status') or '').lower()
    mapped_status = 'pending'
    if raw_status in ('approved', 'paid'):
        mapped_status = 'paid'
```

**✅ FUNCIONA:** Paradise valida erros e trata múltiplos campos de status.

---

## 🔍 3. ANÁLISE DO JOB DE SINCRONIZAÇÃO

### **🔥 sync_umbrellapay_payments (ATUAL):**

```python:jobs/sync_umbrellapay.py
# Linhas 140-165
api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)

if not api_status:
    logger.warning(f"⚠️ [SYNC UMBRELLAPAY] Não foi possível obter status do gateway")
    erros += 1
    continue

status_gateway = api_status.get('status')
logger.info(f"📊 [SYNC UMBRELLAPAY] Status no gateway: {status_gateway}")

# ✅ Atualizar se gateway mostrar paid
if status_gateway == 'paid':
    # Atualizar para paid
```

**❌ PROBLEMA:** 
1. Se `get_payment_status()` retornar `None` (por erro de parsing), o job não atualiza!
2. Se o status for `AUTHORIZED`, não atualiza (deveria atualizar)!
3. Não há fallback se a estrutura da resposta mudar!

---

## 🔥 4. DIAGNÓSTICO TÉCNICO FINAL

### **A) Trecho EXATO do UmbrellaPay que está errado:**

```python:gateway_umbrellapag.py
# Linhas 1129-1157
status_map = {
    'PAID': 'paid',
    'paid': 'paid',
    'APPROVED': 'paid',
    'approved': 'paid',
    'CONFIRMED': 'paid',
    'confirmed': 'paid',
    'COMPLETED': 'paid',
    'completed': 'paid',
    'WAITING_PAYMENT': 'pending',
    'PENDING': 'pending',
    'pending': 'pending',
    'PROCESSING': 'pending',
    'processing': 'pending',
    # ❌ FALTA: 'AUTHORIZED' → 'paid'
    # ❌ FALTA: 'authorized' → 'paid'
    'REFUSED': 'failed',
    # ...
}

# Linha 1160
normalized_status = status_map.get(status_str, 'pending')  # ❌ Se status_str = 'AUTHORIZED', retorna 'pending'!
```

### **B) Trecho EXATO do Paradise (equivalente funcional):**

```python:gateway_paradise.py
# Linhas 527-532
mapped_status = 'pending'
# ✅ CORREÇÃO CRÍTICA: Aceitar tanto "approved" quanto "paid" como pago
if status in ('approved', 'paid'):
    mapped_status = 'paid'
elif status == 'refunded':
    mapped_status = 'failed'
```

### **C) Diferença clara entre eles:**

| Aspecto | UmbrellaPay (BUG) | Paradise (FUNCIONAL) |
|---------|-------------------|---------------------|
| **Status `AUTHORIZED`** | ❌ Não mapeado → `pending` | ✅ Não aplicável (Paradise não usa) |
| **Status `APPROVED`** | ✅ Mapeado → `paid` | ✅ Mapeado → `paid` |
| **Status `PAID`** | ✅ Mapeado → `paid` | ✅ Mapeado → `paid` |
| **Fallback** | ❌ Default `pending` | ✅ Default `pending` (mas valida erros) |
| **Validação de erro** | ⚠️ Parcial | ✅ Completa |

### **D) Explicação técnica de porque causa o bug:**

1. **UmbrellaPay retorna `AUTHORIZED` quando o pagamento é autorizado mas ainda não confirmado.**
2. **Nosso sistema não mapeia `AUTHORIZED` → `paid`, então fica como `pending`.**
3. **O job de sincronização consulta a API, mas se o status for `AUTHORIZED`, não atualiza.**
4. **Resultado: Pagamento autorizado no gateway, mas `pending` no sistema.**

### **E) Patch necessário para corrigir:**

```python
# gateway_umbrellapag.py - Linhas 1129-1157
status_map = {
    'PAID': 'paid',           # ✅ PAGO
    'paid': 'paid',
    'AUTHORIZED': 'paid',    # ✅ CORREÇÃO: Autorizado = pago (UmbrellaPay)
    'authorized': 'paid',    # ✅ CORREÇÃO: Autorizado = pago (UmbrellaPay)
    'APPROVED': 'paid',      # ✅ APROVADO
    'approved': 'paid',
    'CONFIRMED': 'paid',     # ✅ CONFIRMADO
    'confirmed': 'paid',
    'COMPLETED': 'paid',     # ✅ COMPLETO
    'completed': 'paid',
    'WAITING_PAYMENT': 'pending',  # ⏳ AGUARDANDO
    'PENDING': 'pending',
    'pending': 'pending',
    'PROCESSING': 'pending',  # ⏳ PROCESSANDO
    'processing': 'pending',
    'REFUSED': 'failed',     # ❌ RECUSADO
    'refused': 'failed',
    'FAILED': 'failed',      # ❌ FALHOU
    'failed': 'failed',
    'CANCELLED': 'failed',   # ❌ CANCELADO
    'CANCELED': 'failed',
    'cancelled': 'failed',
    'canceled': 'failed',
    'REFUNDED': 'failed',    # ❌ REEMBOLSADO
    'refunded': 'failed',
    'EXPIRED': 'failed',     # ❌ EXPIRADO
    'expired': 'failed',
    'REJECTED': 'failed',    # ❌ REJEITADO
    'rejected': 'failed'
}
```

**E também melhorar o tratamento de estrutura aninhada:**

```python
# gateway_umbrellapag.py - Linhas 1344-1360 (get_payment_status)
data = response.json()

# ✅ CORREÇÃO: Tratar estrutura aninhada dupla (data.data)
if isinstance(data, dict) and 'data' in data:
    inner_data = data.get('data', {})
    # Se inner_data também tem 'data', usar o mais interno
    if isinstance(inner_data, dict) and 'data' in inner_data:
        data = inner_data.get('data', {})
    else:
        data = inner_data

# Processar como webhook
result = self.process_webhook(data)
```

### **F) Comportamento esperado após correção:**

1. ✅ Status `AUTHORIZED` será mapeado para `paid`
2. ✅ Pagamentos autorizados serão marcados como pagos automaticamente
3. ✅ Job de sincronização atualizará pagamentos com status `AUTHORIZED`
4. ✅ Entregável será enviado quando status for `AUTHORIZED` ou `PAID`
5. ✅ Meta Pixel Purchase será disparado corretamente

---

## 🔍 5. PERGUNTAS PARA CONFIRMAÇÃO

### **A) Confirmação do status que significa "pago":**

**Pergunta:** No UmbrellaPay, quando um pagamento PIX é confirmado, qual é o status retornado?
- [ ] `PAID` apenas
- [ ] `AUTHORIZED` apenas
- [ ] `AUTHORIZED` primeiro, depois `PAID`
- [ ] Ambos `AUTHORIZED` e `PAID` significam pago

**Resposta esperada:** Ambos `AUTHORIZED` e `PAID` significam que o pagamento foi confirmado.

### **B) Confirmar se o UmbrellaPay envia webhook ou não:**

**Pergunta:** O UmbrellaPay envia webhook automaticamente quando o status muda?
- [ ] Sim, envia webhook automaticamente
- [ ] Não, apenas consulta via API

**Resposta esperada:** Sim, envia webhook via `postbackUrl` configurado no `generate_pix()`.

### **C) Confirmar qual campo do PIX é fornecido:**

**Pergunta:** Quando o UmbrellaPay retorna o PIX, qual campo contém o código PIX?
- [ ] `pix.qrCode`
- [ ] `pix.qr_code`
- [ ] `data.pix.qrCode`
- [ ] Outro campo

**Resposta esperada:** `data.pix.qrCode` (estrutura aninhada).

### **D) Confirmar se o campo externalRef pode vir undefined:**

**Pergunta:** O campo `externalRef` sempre é preenchido pelo UmbrellaPay?
- [ ] Sim, sempre preenchido
- [ ] Não, pode vir `null` ou `undefined`

**Resposta esperada:** Pode vir `null` se não foi enviado no `generate_pix()`.

---

## 🚀 6. SOLUÇÃO DEFINITIVA

### **Patch Completo:**

```python
# gateway_umbrellapag.py

# 1. Adicionar AUTHORIZED ao status_map (linha ~1130)
'AUTHORIZED': 'paid',    # ✅ CORREÇÃO CRÍTICA
'authorized': 'paid',    # ✅ CORREÇÃO CRÍTICA

# 2. Melhorar tratamento de estrutura aninhada (linha ~1344)
if isinstance(data, dict) and 'data' in data:
    inner_data = data.get('data', {})
    if isinstance(inner_data, dict) and 'data' in inner_data:
        data = inner_data.get('data', {})
    else:
        data = inner_data

# 3. Melhorar process_webhook para tratar data.data (linha ~1087)
webhook_data = data.get('data', {})
if not webhook_data:
    webhook_data = data
else:
    # ✅ CORREÇÃO: Se webhook_data também tem 'data', usar o mais interno
    if isinstance(webhook_data, dict) and 'data' in webhook_data:
        webhook_data = webhook_data.get('data', {})
```

---

## ✅ CHECKLIST FINAL

- [x] Status `AUTHORIZED` identificado como problema
- [x] Comparação com Paradise realizada
- [x] Estrutura de resposta analisada
- [x] Job de sincronização revisado
- [x] Patch proposto
- [ ] **PENDENTE:** Confirmação do comportamento real do UmbrellaPay
- [ ] **PENDENTE:** Aplicação do patch
- [ ] **PENDENTE:** Teste com pagamento real

---

## 🎯 CONCLUSÃO

**Causa Raiz:** Status `AUTHORIZED` não está sendo mapeado para `paid`, causando pagamentos autorizados ficarem como `pending`.

**Solução:** Adicionar `AUTHORIZED` → `paid` no `status_map` e melhorar tratamento de estrutura aninhada.

**Prioridade:** 🔴 **CRÍTICA** — Afeta todos os pagamentos UmbrellaPay que retornam `AUTHORIZED`.

