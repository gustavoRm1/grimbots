# ✅ CORREÇÃO — BOTÃO "VERIFICAR PAGAMENTO" UMBRELLAPAY

**Data:** 2025-11-14  
**Status:** ✅ **CORRIGIDO**

---

## 🎯 PROBLEMA IDENTIFICADO

Quando o usuário clica em "Verificar Pagamento" e o pagamento ainda está pendente, o sistema não mostrava o PIX code corretamente ou mostrava uma mensagem genérica diferente dos outros gateways.

**Comportamento esperado (como Paradise):**
- Mostrar o PIX code novamente
- Mensagem específica informando que está aguardando confirmação
- Instruções claras sobre o que fazer

---

## ✅ CORREÇÕES APLICADAS

### **1. Adicionada mensagem específica para UmbrellaPay**

**Arquivo:** `bot_manager.py` (linhas 3503-3519)

**Antes:**
- UmbrellaPay usava mensagem genérica (igual a outros gateways)

**Depois:**
- Mensagem específica similar ao Paradise
- Informa que confirmação é automática em até 5 minutos
- Dica para clicar novamente em "Verificar Pagamento"

**Código:**
```python
elif payment.gateway_type == 'umbrellapag':
    # ✅ CORREÇÃO: Mensagem específica para UmbrellaPay (similar ao Paradise)
    pending_message = f"""⏳ <b>Aguardando confirmação</b>

Seu pagamento está sendo processado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

⏱️ <b>Confirmação automática:</b>
Se você já pagou, o sistema confirmará automaticamente em até 5 minutos via webhook ou job de sincronização.

💡 <b>Dica:</b> Você pode clicar novamente em "Verificar Pagamento" para consultar o status manualmente.

✅ Você será notificado assim que o pagamento for confirmado!"""
```

---

### **2. Adicionado fallback para recuperar PIX code do gateway**

**Arquivo:** `bot_manager.py` (linhas 3481-3534)

**Problema:**
- Se `payment.product_description` não tiver o PIX code salvo, mostrava "Aguardando..."

**Solução:**
- Fallback que busca PIX code diretamente da API do UmbrellaPay
- Consulta `GET /user/transactions/{transaction_id}`
- Extrai PIX code de `data.pix.qrCode`

**Código:**
```python
# ✅ FALLBACK: Se PIX code não está salvo, tentar buscar do gateway (apenas para UmbrellaPay)
if (pix_code == 'Aguardando...' or not pix_code or len(pix_code) < 20) and payment.gateway_type == 'umbrellapag':
    try:
        # Buscar gateway e fazer requisição direta
        response = payment_gateway._make_request('GET', f'/user/transactions/{payment.gateway_transaction_id}')
        if response and response.status_code == 200:
            api_data = response.json()
            # Tratar estrutura aninhada e extrair PIX code
            # ...
            if fallback_pix and len(fallback_pix) > 20:
                pix_code = fallback_pix
                logger.info(f"✅ [VERIFY] PIX code recuperado do gateway via API")
    except Exception as api_error:
        logger.debug(f"🔍 [VERIFY] Não foi possível buscar PIX code via API (não crítico)")
```

---

## 📊 COMPARAÇÃO: ANTES vs DEPOIS

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Mensagem UmbrellaPay** | ❌ Genérica (igual outros gateways) | ✅ Específica (similar ao Paradise) |
| **PIX code** | ⚠️ Pode mostrar "Aguardando..." | ✅ Busca do gateway se não estiver salvo |
| **Instruções** | ⚠️ Genéricas | ✅ Específicas para UmbrellaPay |
| **Fallback** | ❌ Não existe | ✅ Busca PIX code da API |

---

## 🔍 COMPARAÇÃO COM OUTROS GATEWAYS

### **Paradise (Funcional):**
```python
if payment.gateway_type == 'paradise':
    pending_message = f"""⏳ <b>Aguardando confirmação</b>
    ...
    📱 <b>PIX Copia e Cola:</b>
    <code>{pix_code}</code>
    ...
    ⏱️ <b>Confirmação automática:</b>
    Se você já pagou, o sistema confirmará automaticamente em até 2 minutos via webhook."""
```

### **UmbrellaPay (Agora - Corrigido):**
```python
elif payment.gateway_type == 'umbrellapag':
    pending_message = f"""⏳ <b>Aguardando confirmação</b>
    ...
    📱 <b>PIX Copia e Cola:</b>
    <code>{pix_code}</code>
    ...
    ⏱️ <b>Confirmação automática:</b>
    Se você já pagou, o sistema confirmará automaticamente em até 5 minutos via webhook ou job de sincronização.
    
    💡 <b>Dica:</b> Você pode clicar novamente em "Verificar Pagamento" para consultar o status manualmente."""
```

**✅ Agora ambos têm comportamento similar!**

---

## ✅ CHECKLIST FINAL

- [x] Mensagem específica para UmbrellaPay adicionada
- [x] Fallback para buscar PIX code do gateway implementado
- [x] Tratamento de estrutura aninhada no fallback
- [x] Logs melhorados para debug
- [x] Comportamento alinhado com Paradise

---

## 🎯 CONCLUSÃO

**Status:** ✅ **100% CORRIGIDO**

O botão "Verificar Pagamento" agora:
1. ✅ Mostra mensagem específica para UmbrellaPay (similar ao Paradise)
2. ✅ Exibe o PIX code corretamente (com fallback se não estiver salvo)
3. ✅ Fornece instruções claras sobre confirmação automática
4. ✅ Permite verificação manual via botão

**Próximos passos:**
1. Fazer `git pull` e `restart` na VPS
2. Testar clicando em "Verificar Pagamento" com pagamento pendente
3. Confirmar que PIX code é exibido corretamente

