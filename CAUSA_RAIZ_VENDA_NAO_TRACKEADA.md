# 🔍 CAUSA RAIZ - Venda Não Trackeada

## 🎯 PROBLEMA IDENTIFICADO

**Venda `BOT2_1763657851_e626447c` foi feita mas não foi atribuída à campanha Meta**

---

## 📊 LOGS DA VENDA

```
[META DELIVERY] Delivery - Dados recuperados: fbclid=❌, fbp=✅, fbc=❌, fbc_origin=ausente
[META PURCHASE] Purchase - payment.tracking_token AUSENTE! Payment ID: BOT2_1763657851_e626447c
```

**Status:**
- ✅ Purchase foi enviado via Server (Conversions API)
- ✅ `meta_purchase_sent` foi marcado como True
- ✅ Deduplicação funcionando (client-side não enviou)
- ❌ **fbclid AUSENTE** → Meta não atribui à campanha
- ❌ **tracking_token AUSENTE** → Dados do redirect não foram recuperados

---

## 🔍 CAUSA RAIZ

### **PROBLEMA 1: Cliente não passou pelo redirect `/go/<slug>`**

**Sintoma:**
- ❌ `fbclid=❌` na venda
- ❌ `tracking_token` AUSENTE
- ❌ `tracking_session_id` provavelmente ausente ou é token gerado

**Por que acontece:**
1. Cliente acessou bot **DIRETO** (sem passar pelo redirect)
2. Cliente veio de tráfego **ORGÂNICO** (sem click_id do Facebook)
3. Cliente salvou link direto do bot (sem passar pelo cloaker)

**Consequência:**
- ❌ Sem `fbclid`, Meta **NÃO consegue** atribuir venda à campanha
- ❌ Purchase será enviado, mas **NÃO será atribuído** à campanha
- ❌ Venda aparece como "tráfego direto" ou "orgânico"

---

### **PROBLEMA 2: Redirect não tinha fbclid na URL**

**Sintoma:**
- ✅ Cliente passou pelo redirect (tem `tracking_session_id`)
- ❌ Mas `fbclid` não foi capturado

**Por que acontece:**
1. Cliente veio de tráfego orgânico (sem `fbclid` na URL)
2. Cliente clicou em link direto (sem parâmetros UTM)
3. Campanha Meta não estava usando click_id

**Consequência:**
- ❌ Sem `fbclid`, Meta **NÃO consegue** atribuir venda à campanha
- ✅ Purchase será enviado com outros dados (fbp, fbc se houver)
- ⚠️ Match Quality será reduzida

---

## ✅ SOLUÇÃO

### **1. Garantir que cliente passe pelo redirect ANTES de comprar**

**Como fazer:**
- ✅ Todas as campanhas Meta devem usar link do redirect `/go/<slug>`
- ✅ Bot deve ter link de redirect configurado no pool
- ✅ Cliente deve clicar no link do redirect ANTES de interagir com bot

**Verificar:**
```bash
# Verificar se pool tem redirect configurado
psql -U postgres -d grimbots -c "
SELECT id, name, redirect_url FROM redirect_pools WHERE id IN (
    SELECT pool_id FROM pool_bots WHERE bot_id = X
);
"
```

---

### **2. Verificar se redirect captura fbclid**

**Como fazer:**
- ✅ Redirect deve capturar `fbclid` da URL
- ✅ `fbclid` deve ser salvo no `tracking_data` (Redis)
- ✅ `fbclid` deve ser recuperado quando cliente compra

**Verificar:**
```bash
# Verificar logs de redirect
tail -f logs/gunicorn.log | grep -iE "/go/.*fbclid|fbclid.*encontrado"
```

---

### **3. Verificar se tracking_data está sendo salvo**

**Como fazer:**
- ✅ `tracking_data` deve ser salvo no Redis quando cliente passa pelo redirect
- ✅ `tracking_session_id` deve ser salvo no `bot_user`
- ✅ `tracking_token` deve ser salvo no `payment` quando compra

**Verificar:**
```bash
# Verificar bot_user
psql -U postgres -d grimbots -c "
SELECT tracking_session_id, fbclid, fbp, fbc 
FROM bot_users 
WHERE bot_id = X AND telegram_user_id = 'Y';
"
```

---

## 🔍 DIAGNÓSTICO AUTOMATIZADO

Execute o script:

```bash
bash verificar_causa_raiz_venda_nao_trackeada.sh
```

**O que verifica:**
1. Dados da venda (fbclid, tracking_token)
2. Bot_user (tracking_session_id, fbclid)
3. Logs do redirect (se cliente passou)
4. Purchase enviado (se foi enviado corretamente)
5. Diagnóstico final (causa raiz identificada)

---

## 📋 CHECKLIST

- [ ] Cliente passou pelo redirect `/go/<slug>` antes de comprar
- [ ] Redirect capturou `fbclid` da URL
- [ ] `fbclid` foi salvo no `tracking_data` (Redis)
- [ ] `tracking_session_id` foi salvo no `bot_user`
- [ ] `tracking_token` foi salvo no `payment`
- [ ] Purchase foi enviado com `fbclid` recuperado

---

## 🚨 PRÓXIMOS PASSOS

1. **Execute o diagnóstico:**
   ```bash
   bash verificar_causa_raiz_venda_nao_trackeada.sh
   ```

2. **Verifique se cliente passou pelo redirect:**
   - Verificar logs de `/go/<slug>` para este cliente
   - Verificar se `tracking_session_id` existe no `bot_user`
   - Verificar se `tracking_token` existe no `payment`

3. **Se cliente não passou pelo redirect:**
   - ✅ Garantir que todas as campanhas usam link do redirect
   - ✅ Verificar se redirect está configurado corretamente no pool
   - ✅ Testar fluxo completo (redirect → bot → compra)

4. **Se cliente passou mas sem fbclid:**
   - ✅ Verificar se campanha Meta está usando click_id
   - ✅ Verificar se URL do redirect tem `fbclid` quando cliente clica
   - ✅ Verificar se `fbclid` está sendo capturado no redirect

---

## ⚠️ IMPORTANTE

**SEM `fbclid`, Meta NÃO consegue atribuir venda à campanha!**

- ✅ Purchase será enviado (funciona tecnicamente)
- ❌ Mas **NÃO será atribuído** à campanha Meta
- ❌ Venda aparece como "tráfego direto" ou "orgânico"

**SOLUÇÃO:** Cliente **DEVE** passar pelo redirect `/go/<slug>` **ANTES** de comprar!

