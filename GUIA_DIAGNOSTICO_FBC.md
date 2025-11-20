# 🔍 GUIA PRÁTICO - DIAGNÓSTICO FBC

## ✅ SITUAÇÃO ATUAL

O teste mostrou que:
- ✅ **30 eventos PageView** no total
- ❌ **0 eventos** com `fbc` do Parameter Builder
- ✅ **10 eventos** com `fbc REAL confirmado` (vindo do Redis/fallback)
- ✅ **`_fbi` (client IP)** está sendo capturado corretamente

## 🎯 CONCLUSÃO

**O Parameter Builder está funcionando parcialmente:**
- ✅ **Client-Side Parameter Builder** está funcionando (`_fbi` sendo capturado)
- ❌ **Mas `fbc` não está sendo gerado/capturado**

**Causa provável:** URLs de redirect **não têm `fbclid`** OU cookie `_fbc` não está sendo salvo.

---

## 🔍 DIAGNÓSTICO PASSO A PASSO

### **PASSO 1: Verificar se URLs têm `fbclid`**

#### **Verificar logs de redirect:**
```bash
tail -500 logs/gunicorn.log | grep -E "redirect|fbclid" | tail -20
```

#### **Verificar se `fbclid` está chegando no PageView:**
```bash
tail -500 logs/gunicorn.log | grep -E "PARAM BUILDER.*fbclid|fbclid encontrado|fbclid não encontrado" | tail -20
```

**O que procurar:**
- ✅ `[PARAM BUILDER] fbclid encontrado nos args: ...` → `fbclid` está presente
- ⚠️ `[PARAM BUILDER] fbclid não encontrado nos args` → `fbclid` ausente

---

### **PASSO 2: Verificar se Client-Side Parameter Builder está salvando `_fbc`**

#### **Teste manual (no browser):**

1. **Acesse uma URL de redirect com `fbclid`:**
   ```
   https://app.grimbots.online/go/SEU_SLUG?grim=SEU_GRIM&fbclid=IwAR1234567890...
   ```

2. **Abra DevTools (F12) → Application → Cookies**

3. **Procure por:**
   - ✅ `_fbc` (deve existir se `fbclid` estiver na URL)
   - ✅ `_fbp` (deve existir sempre)
   - ✅ `_fbi` (deve existir sempre - Client IP)

4. **Se `_fbc` não existir:**
   - ⚠️ Client-Side Parameter Builder não está funcionando
   - ⚠️ Ou `fbclid` não estava na URL

---

### **PASSO 3: Verificar logs do Parameter Builder em tempo real**

#### **Executar em tempo real:**
```bash
tail -f logs/gunicorn.log | grep -E "PARAM BUILDER|fbc|fbclid" | grep -v "Client IP"
```

**O que deve aparecer (se funcionando):**
```
[PARAM BUILDER] Cookies recebidos: ['_fbc', '_fbp', '_fbi']
[PARAM BUILDER] Args recebidos: ['fbclid', 'grim', ...]
[PARAM BUILDER] Cookie _fbc encontrado: fb.1.1734567890... (len=50)
[PARAM BUILDER] ✅ fbc capturado do cookie (ORIGEM REAL): fb.1.1734567890...
[META PAGEVIEW] PageView - fbc processado pelo Parameter Builder (origem: cookie): fb.1.1734567890...
```

**OU (se não tiver cookie mas tiver fbclid):**
```
[PARAM BUILDER] Cookie _fbc não encontrado
[PARAM BUILDER] fbclid encontrado nos args: IwAR1234567890... (len=27)
[PARAM BUILDER] ✅ fbc gerado baseado em fbclid (conforme doc Meta): fb.1.1734567890...
[META PAGEVIEW] PageView - fbc processado pelo Parameter Builder (origem: generated_from_fbclid): fb.1.1734567890...
```

**Se não aparecer nada:**
```
[PARAM BUILDER] Cookie _fbc não encontrado
[PARAM BUILDER] fbclid não encontrado nos args (não será gerado fbc)
[PARAM BUILDER] ⚠️ fbc NÃO retornado (cookie _fbc ausente e fbclid ausente)
[META PAGEVIEW] PageView - fbc NÃO retornado pelo Parameter Builder
   Cookie _fbc: ❌ Ausente
   fbclid na URL: ❌ Ausente (len=0)
```

---

### **PASSO 4: Verificar Client-Side Parameter Builder no código**

#### **Verificar se está carregando:**
```bash
grep -n "clientParamBuilder\|processAndCollectAllParams" templates/telegram_redirect.html
```

**Deve aparecer:**
```html
<script src="https://capi-automation.s3.us-east-2.amazonaws.com/public/client_js/capiParamBuilder/clientParamBuilder.bundle.js"></script>
```

E:
```javascript
const updated_cookies = await clientParamBuilder.processAndCollectAllParams(currentUrl, getIpFn);
```

---

### **PASSO 5: Testar com URL de exemplo**

#### **Criar URL de teste com `fbclid`:**

1. **Pegar um slug de redirect ativo:**
   ```bash
   # Ver redirect pools ativos (se tiver acesso ao banco)
   python3 << 'EOF'
   from app import app, db
   from models import RedirectPool
   with app.app_context():
       pools = RedirectPool.query.filter_by(active=True).limit(5).all()
       for pool in pools:
           print(f"Slug: {pool.slug}, Grim: {pool.grim or 'N/A'}")
   EOF
   ```

2. **Criar URL de teste:**
   ```
   https://app.grimbots.online/go/SEU_SLUG?grim=SEU_GRIM&fbclid=IwAR1234567890teste
   ```

3. **Acessar URL e verificar logs:**
   ```bash
   tail -f logs/gunicorn.log | grep -E "PARAM BUILDER|PageView.*fbc"
   ```

4. **Deve aparecer:**
   ```
   [PARAM BUILDER] fbclid encontrado nos args: IwAR1234567890teste
   [PARAM BUILDER] ✅ fbc gerado baseado em fbclid (conforme doc Meta): fb.1.1734567890...IwAR1234567890teste
   [META PAGEVIEW] PageView - fbc processado pelo Parameter Builder (origem: generated_from_fbclid)
   ```

---

## 🛠️ SOLUÇÕES POSSÍVEIS

### **PROBLEMA 1: URLs não têm `fbclid`**

**Solução:** Adicionar `fbclid` nas URLs de redirect do Meta Ads.

**Como fazer:**
1. No Meta Ads, configurar URLs de destino com `fbclid`:
   ```
   https://app.grimbots.online/go/SEU_SLUG?grim=SEU_GRIM&fbclid={{fbclid}}
   ```

2. Ou usar o Utmify (se estiver configurado):
   - Utmify adiciona `fbclid` automaticamente nas URLs

---

### **PROBLEMA 2: Client-Side Parameter Builder não está salvando `_fbc`**

**Solução:** Verificar se o script está sendo carregado e executado corretamente.

**Como verificar:**
1. Abra DevTools → Console
2. Execute:
   ```javascript
   console.log('_fbc:', document.cookie.split('; ').find(c => c.startsWith('_fbc=')));
   console.log('_fbp:', document.cookie.split('; ').find(c => c.startsWith('_fbp=')));
   ```

3. **Se `_fbc` for `undefined`:**
   - Verificar se script está carregando
   - Verificar se `processAndCollectAllParams` está sendo chamado
   - Verificar erros no Console

---

### **PROBLEMA 3: Cookie `_fbc` expira muito rápido**

**Solução:** Verificar TTL do cookie `_fbc`.

**Como verificar:**
1. DevTools → Application → Cookies
2. Verificar **Expires** do cookie `_fbc`
3. **Se expirar muito rápido (< 1 dia):**
   - Pode ser problema do Client-Side Parameter Builder
   - Verificar configuração do script

---

## 📊 RESULTADO ESPERADO

### **DEPOIS DE CORRIGIR:**

```
PageView: 50 eventos
Com fbc (Parameter Builder): 35 (70% cobertura)
Com fbc REAL confirmado: 35
Com fbc ausente: 15 (30%)

Cobertura: 70%
✅ Cobertura EXCELENTE (> 50%)
```

---

## 🔧 COMANDOS ÚTEIS

### **Ver últimas ocorrências de fbc:**
```bash
tail -500 logs/gunicorn.log | grep -E "fbc|fbclid" | grep -v "Client IP" | tail -20
```

### **Contar eventos com fbc do Parameter Builder:**
```bash
grep -c "fbc processado pelo Parameter Builder" logs/gunicorn.log
```

### **Ver se fbclid está chegando:**
```bash
tail -1000 logs/gunicorn.log | grep "fbclid encontrado\|fbclid não encontrado" | tail -20
```

### **Ver logs detalhados do Parameter Builder:**
```bash
tail -1000 logs/gunicorn.log | grep "PARAM BUILDER" | tail -30
```

---

## ✅ CHECKLIST DE VERIFICAÇÃO

- [ ] URLs de redirect têm `fbclid`?
- [ ] Client-Side Parameter Builder está carregando?
- [ ] Cookie `_fbc` está sendo salvo no browser?
- [ ] Logs mostram `fbclid encontrado nos args`?
- [ ] Logs mostram `fbc gerado baseado em fbclid` ou `fbc capturado do cookie`?
- [ ] Logs mostram `PageView - fbc processado pelo Parameter Builder`?

---

## 🎯 PRÓXIMOS PASSOS

1. **Verificar se URLs têm `fbclid`** (PASSO 1)
2. **Testar com URL de exemplo** (PASSO 5)
3. **Verificar logs em tempo real** (PASSO 3)
4. **Aplicar solução** conforme problema identificado

---

## ⚠️ IMPORTANTE

**Se as URLs não tiverem `fbclid` E o cookie `_fbc` não estiver sendo salvo, o Parameter Builder NÃO consegue gerar `fbc`.**

Nesse caso, o sistema usa fallback (Redis/payment/bot_user), mas a cobertura será menor.

