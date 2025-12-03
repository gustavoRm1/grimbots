# 🔥 DIAGNÓSTICO COMPLETO - PURCHASE NÃO APARECE NO META

## 📊 DADOS REAIS

**Estatísticas (últimas 24h):**
- Total pagos: 228
- Com delivery_token: 228 (100%)
- `meta_purchase_sent = True`: 97 (42.5%)
- `meta_purchase_sent = True` E `meta_event_id`: 97 (42.5%)

**Pool "ads" (ID: 1):**
- ✅ `meta_events_purchase: True` - CONFIGURADO CORRETO
- ✅ Payments têm `meta_purchase_sent = True` e `meta_event_id`

---

## 🔍 PROBLEMA IDENTIFICADO

**Purchase está sendo enfileirado (97 de 228 = 42.5%), MAS Meta não mostra Purchase!**

**Análise:**
1. ✅ Purchase está sendo enfileirado via Celery
2. ✅ `meta_purchase_sent = True` e `meta_event_id` estão sendo salvos
3. ❌ Meta não mostra Purchase no Events Manager

**Possíveis causas:**
1. **Celery não está processando as tasks**
   - Tasks estão na fila mas não sendo executadas
   - Worker não está rodando

2. **Meta está rejeitando os eventos**
   - Resposta 4xx (token inválido, payload inválido)
   - Tasks falham mas não há log visível

3. **Client-side Purchase não dispara**
   - Browser não está enviando Purchase
   - Meta só recebe PageView

---

## ✅ PRÓXIMOS PASSOS

### **1. Verificar Celery**

Executar na VPS:
```bash
chmod +x verificar_celery_purchase.sh
./verificar_celery_purchase.sh
```

**Ou manualmente:**
```bash
# Verificar se Celery está rodando
systemctl status celery

# Verificar tasks ativas
celery -A celery_app inspect active

# Verificar logs
grep -i "SUCCESS.*Purchase" /var/log/grimbots/app.log | tail -10
grep -i "FAILED.*Purchase" /var/log/grimbots/app.log | tail -10
```

---

### **2. Verificar Logs Específicos**

```bash
# Verificar se Purchase está sendo enviado com sucesso
grep "SUCCESS.*Meta Event.*Purchase" logs/app.log

# Verificar erros
grep "FAILED.*Meta Event.*Purchase" logs/app.log
grep "Meta API Error.*Purchase" logs/app.log
```

---

### **3. Verificar Client-Side**

1. Acessar `/delivery/<token>` no browser
2. Abrir Console (F12)
3. Verificar se aparece: `[META PIXEL] Purchase disparado (client-side)`
4. Verificar Network tab: request para `connect.facebook.net`

---

**STATUS:** Purchase está sendo enfileirado mas não aparece no Meta. Executar diagnóstico para identificar se é problema no Celery ou na Meta API.

