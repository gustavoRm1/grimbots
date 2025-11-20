# 🔍 COMO VERIFICAR EM TEMPO REAL

## 📋 Scripts Disponíveis

### 1. **Monitorar Purchase em Tempo Real**
```bash
bash monitorar_purchase_tempo_real.sh
```

**O que monitora:**
- ✅ Acessos à página `/delivery` (Purchase disparado)
- ✅ Purchase client-side disparado
- ✅ Purchase server-side disparado
- ✅ Deduplicação (meta_purchase_sent)
- ✅ Event ID usado (para verificar matching)

**Cores:**
- 🟢 Verde: Purchase disparado com sucesso
- 🟡 Amarelo: Purchase já foi enviado (deduplicação funcionando)
- 🔵 Azul: Dados recuperados
- 🔑 Ciano: Event ID usado
- 🔴 Vermelho: Erros

---

### 2. **Verificar Última Venda**
```bash
bash verificar_venda_tempo_real.sh
```

**O que mostra:**
- Última venda confirmada (status='paid')
- Se tem `delivery_token`
- Se `meta_purchase_sent` está marcado
- Logs relacionados à venda

---

### 3. **Verificar Purchase de Venda Específica**
```bash
bash verificar_purchase_venda.sh <payment_id>
```

**Exemplo:**
```bash
bash verificar_purchase_venda.sh BOT2_1763652057_bf9d998e
```

**O que mostra:**
- Dados da venda (status, delivery_token, meta_purchase_sent)
- Pool do bot (pixel_id configurado)
- Logs de Purchase para esta venda específica

---

## 🔍 Comandos Manuais

### **Monitorar Logs em Tempo Real (Filtrado)**
```bash
tail -f logs/gunicorn.log | grep -iE "DELIVERY|Purchase|meta_purchase_sent|event_id"
```

### **Ver Últimas 50 Linhas de Purchase**
```bash
tail -5000 logs/gunicorn.log | grep -iE "META DELIVERY|Purchase.*disparado|meta_purchase_sent" | tail -50
```

### **Ver Acessos à Página /delivery**
```bash
tail -f logs/gunicorn.log | grep -iE "Delivery.*Renderizando|/delivery/"
```

### **Ver Event IDs Usados**
```bash
tail -f logs/gunicorn.log | grep -iE "event_id|eventID"
```

### **Ver Deduplicação (meta_purchase_sent)**
```bash
tail -f logs/gunicorn.log | grep -iE "meta_purchase_sent"
```

---

## ✅ O Que Verificar

### **1. Purchase Está Sendo Disparado?**
Procure por:
```
✅ Purchase disparado (client-side) com eventID: ...
✅ Purchase via Server enfileirado com sucesso
```

### **2. Deduplicação Está Funcionando?**
Procure por:
```
⚠️ meta_purchase_sent marcado como True (ANTES de enviar)
⚠️ Purchase já foi enviado anteriormente, pulando client-side...
```

### **3. Event ID Está Sendo Usado Corretamente?**
Procure por:
```
🔑 event_id que será usado (mesmo do client-side): ...
🔑 Purchase disparado (client-side) com eventID: ...
```

### **4. Pool Correto Está Sendo Usado?**
Procure por:
```
✅ Pool correto encontrado via tracking_data: pool_id=X
⚠️ Usando primeiro pool do bot (pool_id não encontrado no tracking_data)
```

### **5. Tracking Data Está Sendo Recuperado?**
Procure por:
```
✅ Delivery - tracking_data recuperado via bot_user.tracking_session_id: X campos
✅ Delivery - Dados recuperados: fbclid=✅, fbp=✅, fbc=✅
```

---

## 🚨 Problemas Comuns

### **Purchase Não Está Sendo Disparado**
- ❌ Pool não tem `meta_pixel_id` configurado
- ❌ `has_meta_pixel = False`
- ❌ Página `/delivery/<token>` não está sendo acessada

**Verificar:**
```bash
# Ver se pool tem pixel_id
psql -U postgres -d grimbots -c "SELECT id, name, meta_pixel_id FROM redirect_pools WHERE meta_pixel_id IS NOT NULL;"
```

### **Purchase Está Sendo Disparado Duplicado**
- ❌ `meta_purchase_sent` não está sendo marcado
- ❌ Client-side e server-side não estão usando mesmo `event_id`

**Verificar:**
```bash
# Ver vendas com purchase_sent
psql -U postgres -d grimbots -c "SELECT payment_id, meta_purchase_sent, meta_purchase_sent_at FROM payments WHERE status='paid' ORDER BY paid_at DESC LIMIT 10;"
```

### **Event ID Diferente Entre Client-Side e Server-Side**
- ❌ `pageview_event_id` não está sendo recuperado
- ❌ `event_id` está sendo gerado novamente (timestamp diferente)

**Verificar:**
```bash
# Ver logs de event_id
tail -f logs/gunicorn.log | grep -iE "event_id.*purchase"
```

---

## 📊 Monitoramento Contínuo

### **Dashboard de Monitoramento**
Execute em terminal separado:
```bash
# Terminal 1: Monitorar Purchase
bash monitorar_purchase_tempo_real.sh

# Terminal 2: Monitorar Erros
tail -f logs/gunicorn.log | grep -iE "ERROR|Erro|❌"

# Terminal 3: Monitorar Acessos
tail -f logs/gunicorn.log | grep -iE "Delivery.*Renderizando"
```

---

## 🔍 Verificar Venda Específica em Tempo Real

1. **Quando uma nova venda acontecer:**
   ```bash
   bash verificar_venda_tempo_real.sh
   ```

2. **Ver detalhes da venda:**
   ```bash
   bash verificar_purchase_venda.sh <payment_id>
   ```

3. **Monitorar logs em tempo real:**
   ```bash
   bash monitorar_purchase_tempo_real.sh
   ```

4. **Verificar no Meta Event Manager:**
   - Acesse: https://business.facebook.com/events_manager2
   - Verifique se Purchase aparece com cobertura > 0%

---

## ✅ Checklist de Verificação

- [ ] Pool tem `meta_pixel_id` configurado
- [ ] Venda tem `delivery_token`
- [ ] Venda tem `status='paid'`
- [ ] Cliente acessa `/delivery/<token>`
- [ ] `meta_purchase_sent` está sendo marcado
- [ ] Purchase client-side disparado (log aparece)
- [ ] Purchase server-side disparado (log aparece)
- [ ] `event_id` é o mesmo no client-side e server-side
- [ ] Purchase aparece no Meta Event Manager

---

## 📝 Próximos Passos

1. Execute `monitorar_purchase_tempo_real.sh` em um terminal
2. Aguarde uma nova venda ou simule uma
3. Verifique os logs em tempo real
4. Confirme que Purchase está sendo disparado e deduplicado corretamente

