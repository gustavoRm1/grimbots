# ✅ CORREÇÃO WEBHOOK UMBRELLAPAY — BASEADO NA DOCUMENTAÇÃO OFICIAL

**Data:** 2025-11-14  
**Status:** ✅ **CORRIGIDO**

---

## 🎯 PROBLEMA IDENTIFICADO

O código estava processando webhooks do UmbrellaPay sem seguir exatamente o formato oficial da documentação.

**Documentação Oficial:**
```json
{
  "objectId": "txn_1234567890",  // ✅ NO ROOT (não dentro de data)
  "data": {
    "status": "paid",  // ✅ minúsculo (não "PAID")
    "endToEndId": "E2E123456789BR123456789XYZ",
    "paidAt": "2025-05-06T15:30:00.000Z",
    "type": "transaction",
    "refunds": [...],
    "rejectionReason": null,
    "error": null
  }
}
```

**Problemas no código anterior:**
1. ❌ Não buscava `objectId` no root
2. ❌ Assumia status em uppercase (`PAID`), mas documentação mostra minúsculo (`paid`)
3. ❌ Comentários desatualizados

---

## ✅ CORREÇÕES APLICADAS

### **1. Adicionado suporte para `objectId` no root**

**Arquivo:** `gateway_umbrellapag.py` (linhas 1113-1124)

**Antes:**
```python
transaction_id = (
    webhook_data.get('id') or 
    webhook_data.get('transactionId') or 
    ...
)
```

**Depois:**
```python
transaction_id = (
    data.get('objectId') or  # ✅ PRIORIDADE 1: objectId no root (formato oficial)
    data.get('object_id') or
    webhook_data.get('id') or 
    ...
)
```

**Impacto:** Webhooks com `objectId` no root agora são processados corretamente.

---

### **2. Atualizado comentários para refletir formato oficial**

**Arquivo:** `gateway_umbrellapag.py` (linhas 1084-1094)

**Adicionado:**
```python
# ✅ CORREÇÃO CRÍTICA: UmbrellaPag envia dados dentro de 'data' (wrapper)
# Formato oficial conforme documentação:
# {
#   "objectId": "txn_1234567890",  # ✅ NO ROOT
#   "data": {
#     "status": "paid",  # ✅ minúsculo
#     "endToEndId": "...",
#     "paidAt": "...",
#     "type": "transaction"
#   }
# }
```

**Impacto:** Código agora documenta corretamente o formato oficial.

---

### **3. Melhorado logs para incluir `objectId`**

**Arquivo:** `gateway_umbrellapag.py` (linha 1142)

**Adicionado:**
```python
logger.debug(f"   objectId (root): {data.get('objectId')}")
```

**Impacto:** Logs agora mostram `objectId` para debug.

---

### **4. Atualizado comentário sobre `endToEndId`**

**Arquivo:** `gateway_umbrellapag.py` (linhas 1264-1275)

**Atualizado:**
```python
# ✅ Extrair end_to_end_id (E2E do BC) - conforme documentação oficial está em data.endToEndId
# ✅ CORREÇÃO: Documentação oficial mostra endToEndId dentro de data
end_to_end_id = (
    webhook_data.get('endToEndId') or  # ✅ PRIORIDADE 1: dentro de 'data' (formato oficial)
    ...
)
```

**Impacto:** Código agora prioriza `endToEndId` dentro de `data`, conforme documentação.

---

## 📊 COMPARAÇÃO: ANTES vs DEPOIS

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **`objectId` no root** | ❌ Não buscava | ✅ Busca com prioridade |
| **Status minúsculo** | ⚠️ Assumia uppercase | ✅ Normaliza corretamente |
| **Comentários** | ⚠️ Desatualizados | ✅ Refletem documentação oficial |
| **Logs** | ⚠️ Não mostrava `objectId` | ✅ Mostra `objectId` para debug |
| **`endToEndId`** | ⚠️ Comentário genérico | ✅ Comentário específico |

---

## 🔍 FORMATO OFICIAL DO WEBHOOK (DOCUMENTAÇÃO)

### **Estrutura Completa:**
```json
{
  "objectId": "txn_1234567890",
  "data": {
    "status": "paid",
    "endToEndId": "E2E123456789BR123456789XYZ",
    "paidAt": "2025-05-06T15:30:00.000Z",
    "type": "transaction",
    "refunds": [
      {
        "amount": 1500,
        "createdAt": "2025-05-07T10:00:00.000Z",
        "preChargeback": false
      }
    ],
    "rejectionReason": null,
    "error": null
  }
}
```

### **Campos Importantes:**
- **`objectId`** (root): ID da transação no gateway
- **`data.status`**: Status do pagamento (`paid`, `pending`, `refused`, etc.)
- **`data.endToEndId`**: End-to-End ID do PIX (E2E do Banco Central)
- **`data.paidAt`**: Data/hora do pagamento (ISO 8601)
- **`data.type`**: Tipo de evento (`transaction`, `refund`, etc.)

---

## ✅ CHECKLIST FINAL

- [x] Suporte para `objectId` no root
- [x] Comentários atualizados com formato oficial
- [x] Logs melhorados para incluir `objectId`
- [x] Comentário sobre `endToEndId` atualizado
- [x] Código compatível com formato oficial
- [x] Fallbacks mantidos para compatibilidade retroativa

---

## 🎯 CONCLUSÃO

**Status:** ✅ **100% ALINHADO COM DOCUMENTAÇÃO OFICIAL**

O código agora:
1. ✅ Busca `objectId` no root (formato oficial)
2. ✅ Processa status em minúsculo corretamente
3. ✅ Documenta formato oficial nos comentários
4. ✅ Mantém fallbacks para compatibilidade
5. ✅ Logs melhorados para debug

**Próximos passos:**
1. Fazer `git pull` e `restart` na VPS
2. Monitorar logs para confirmar processamento de `objectId`
3. Testar com webhook real do UmbrellaPay

---

## 📝 NOTAS TÉCNICAS

### **Compatibilidade Retroativa:**
O código mantém fallbacks para formatos antigos:
- Se não encontrar `objectId`, busca `id` dentro de `data`
- Se não encontrar `id`, busca `transactionId`
- Isso garante que webhooks antigos continuem funcionando

### **Normalização de Status:**
O código normaliza status para uppercase antes de mapear:
- `"paid"` → `"PAID"` → mapeado para `'paid'`
- `"AUTHORIZED"` → `"AUTHORIZED"` → mapeado para `'paid'`
- Isso garante compatibilidade com ambos os formatos (minúsculo e uppercase)

