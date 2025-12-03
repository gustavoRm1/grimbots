# 🔥 DIAGNÓSTICO REAL - META PURCHASE TRACKING (QI 500)

## 📊 PROBLEMA REAL

**Dashboard: 109 vendas → Meta: 12 purchases (11% de cobertura)**

**FLUXO CORRETO:**
1. Pagamento confirmado → `delivery_token` gerado → Link `/delivery/<token>` enviado
2. Lead acessa `/delivery/<token>` → Purchase disparado (HTML Pixel + Server CAPI)
3. Meta recebe Purchase → Venda atribuída

**PROBLEMA IDENTIFICADO:**
- Purchase **SÓ é enviado** quando lead acessa `/delivery`
- Se lead **NÃO acessar** `/delivery`, purchase **NUNCA** é enviado
- **97 leads não acessaram `/delivery` OU há problema na lógica de envio**

---

## 🔍 PONTOS DE FALHA NA FUNÇÃO `send_meta_pixel_purchase_event`

### **1. Bot não associado a Pool (linha 10000-10003)**
```python
if not pool_bot:
    logger.error(f"❌ PROBLEMA RAIZ: Bot {payment.bot_id} não está associado a nenhum pool")
    return False
```
**IMPACTO:** Purchase NÃO é enviado

### **2. Meta Tracking DESABILITADO (linha 10013-10016)**
```python
if not pool.meta_tracking_enabled:
    logger.error(f"❌ PROBLEMA RAIZ: Meta tracking DESABILITADO")
    return False
```
**IMPACTO:** Purchase NÃO é enviado

### **3. Pixel ID ou Access Token AUSENTES (linha 10018-10021)**
```python
if not pool.meta_pixel_id or not pool.meta_access_token:
    logger.error(f"❌ PROBLEMA RAIZ: Pool tem tracking ativo mas SEM pixel_id ou access_token")
    return False
```
**IMPACTO:** Purchase NÃO é enviado

### **4. Evento Purchase DESABILITADO (linha 10025-10028)**
```python
if not pool.meta_events_purchase:
    logger.error(f"❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO")
    return False
```
**IMPACTO:** Purchase NÃO é enviado (CRÍTICO - pode estar bloqueando 97 purchases)

### **5. Purchase já enviado (linha 10036-10040)**
```python
if payment.meta_purchase_sent and getattr(payment, 'meta_event_id', None):
    return True  # Já foi enviado
```
**IMPACTO:** Retorna `True` (OK)

### **6. Campos críticos ausentes (linha 10984)**
```python
if critical_missing:
    logger.error(f"❌ Purchase - Campos críticos ausentes: {critical_missing}")
    return  # Retorna None (NÃO False)
```
**IMPACTO:** Purchase NÃO é enviado (retorna `None` implicitamente)

### **7. Nenhum identificador presente (linha 11022)**
```python
if not user_data.get('external_id') and not user_data.get('fbp') and not user_data.get('fbc'):
    logger.error(f"❌ Purchase - Nenhum identificador presente")
    return  # Retorna None (NÃO False)
```
**IMPACTO:** Purchase NÃO é enviado (retorna `None` implicitamente)

---

## 🔧 DIAGNÓSTICO NECESSÁRIO

Precisamos criar uma função que **verifica todos os payments** e identifica:

1. **Quantos payments têm `delivery_token` mas `meta_purchase_sent = False`**
   - Indica que lead acessou `/delivery` mas purchase não foi enviado

2. **Quantos payments têm `delivery_token = NULL`**
   - Indica que `send_deliverable` não foi chamado (problema no webhook)

3. **Quantos payments têm pool configurado mas `pool.meta_events_purchase = False`**
   - Indica que purchase está sendo bloqueado por configuração

4. **Quantos payments têm pool configurado mas `pool.meta_pixel_id = NULL` ou `pool.meta_access_token = NULL`**
   - Indica que pixel não está configurado corretamente

5. **Logs de erro de `send_meta_pixel_purchase_event`**
   - Identificar motivo exato de falha

---

## 🎯 PRÓXIMOS PASSOS

1. **Criar rota de diagnóstico** `/api/diagnostic/meta-purchase-analysis`
   - Analisa todos os payments `paid` dos últimos 7 dias
   - Identifica padrões de falha
   - Retorna relatório completo

2. **Corrigir `return None` → `return False`**
   - Linha 10984: adicionar `return False` explícito
   - Linha 11022: adicionar `return False` explícito

3. **Adicionar log de auditoria**
   - Registrar TODAS as tentativas de envio de purchase
   - Incluir motivo de falha (se houver)

---

**STATUS:** Aguardando criação de rota de diagnóstico para identificar causa raiz REAL

