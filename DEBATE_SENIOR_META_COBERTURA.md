# 🔥 DEBATE SENIOR - PROBLEMA REAL IDENTIFICADO

## 📊 DADOS DA META

**Cobertura de eventos: 36%** (Meta recomenda >= 75%)
**Redução de custo por resultado: 46,9%** se melhorar para >= 75%

**Chaves de deduplicação:**
- **ID do evento:** 91,77% (browser) vs 100% (server) ✅
- **ID externo (external_id):** 0% (browser) vs 100% (server) ❌ **PROBLEMA!**
- **FBP:** 98,95% (browser) vs 98,75% (server) ✅

**Taxa total de eventos de pixel abrangidos pela API de Conversões: 36,36%**

---

## 🎯 PROBLEMA REAL IDENTIFICADO

### **ARES (Arquiteto Perfeccionista):**

**A Meta está dizendo:**
> "Você não está enviando chaves correspondentes suficientes para eventos idênticos no navegador e no servidor"

**Traduzindo:**
- ✅ Server-side está enviando `external_id` (fbclid)
- ❌ Browser-side NÃO está enviando `external_id` (fbclid)
- Resultado: Meta não consegue fazer matching perfeito
- Cobertura: apenas 36% (deveria ser >= 75%)

---

### **ATHENA (Engenheira Cirúrgica):**

**ARES, você está CERTO!**

**Código atual em `delivery.html` (linha 29-39):**
```javascript
fbq('track', 'Purchase', {
    value: {{ pixel_config.value }},
    currency: '{{ pixel_config.currency }}',
    eventID: '{{ pixel_config.event_id }}',
    content_ids: ['{{ pixel_config.content_id }}'],
    content_name: '{{ pixel_config.content_name }}',
    content_type: 'product',
    num_items: 1
    // ❌ FALTA: external_id (fbclid)
});
```

**Comentário no código (linha 38):**
```
// ✅ external_id será enviado via CAPI (server-side) para melhor matching
```

**PROBLEMA:**
- A Meta diz que precisa estar TANTO no browser quanto no server!
- Sem `external_id` no browser, Meta não consegue fazer matching perfeito
- Cobertura fica baixa (36%)

---

## 🔧 SOLUÇÃO SEGUNDO A META

### **Meta recomenda:**
1. ✅ **Event ID:** Já está sendo enviado (91,77% browser, 100% server)
2. ❌ **External ID:** Precisa adicionar no browser (atualmente 0%)
3. ✅ **FBP:** Já está sendo capturado automaticamente (98,95% browser)

### **Correção necessária:**

**Adicionar `external_id` no evento Purchase do client-side:**

```javascript
fbq('track', 'Purchase', {
    value: {{ pixel_config.value }},
    currency: '{{ pixel_config.currency }}',
    eventID: '{{ pixel_config.event_id }}',
    external_id: '{{ pixel_config.external_id }}',  // ✅ ADICIONAR!
    content_ids: ['{{ pixel_config.content_id }}'],
    content_name: '{{ pixel_config.content_name }}',
    content_type: 'product',
    num_items: 1
});
```

**Segundo a Meta:**
- `external_id` deve ser o `fbclid` (não hasheado no client-side)
- Meta Pixel JS vai hashear automaticamente
- Deve ser o MESMO valor enviado no server-side (CAPI)

---

## ✅ CORREÇÃO A APLICAR

1. ✅ Adicionar `external_id` em `pixel_config` (já existe na linha 9267)
2. ✅ Adicionar `external_id` no evento `fbq('track', 'Purchase')` em `delivery.html`

---

**STATUS:** Problema real identificado - faltando `external_id` no client-side!

