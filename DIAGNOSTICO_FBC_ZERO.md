# 🔍 DIAGNÓSTICO - FBC EM 0%

## ⚠️ PROBLEMA IDENTIFICADO

O teste mostrou que:
- ✅ Função `process_meta_parameters` existe e funciona corretamente
- ✅ `_fbi` (client IP) está sendo capturado pelo Parameter Builder
- ❌ **Cobertura de `fbc` está em 0%** (nenhum evento tem `fbc`)

## 🔍 CAUSA PROVÁVEL

O `fbc` está retornando `None` do Parameter Builder porque:

1. **Cookie `_fbc` não está presente** no browser (mais comum)
2. **`fbclid` não está presente** na URL do redirect

## ✅ SOLUÇÕES IMPLEMENTADAS

### **1. Logs de Debug Adicionados**

Agora o sistema vai logar:
- ✅ Quais cookies foram recebidos
- ✅ Quais args foram recebidos
- ✅ Se `_fbc` foi encontrado no cookie
- ✅ Se `fbclid` foi encontrado nos args
- ✅ Por que `fbc` não foi retornado (se for o caso)

### **2. Script de Teste Corrigido**

O script agora:
- ✅ Conta eventos com `fbc` ausente
- ✅ Mostra estatísticas detalhadas
- ✅ Não gera erros de sintaxe

## 🧪 COMO VERIFICAR O PROBLEMA

### **1. Ver Logs em Tempo Real**

```bash
tail -f logs/gunicorn.log | grep -E "PARAM BUILDER|fbc|fbclid"
```

**O que procurar:**
- ✅ `[PARAM BUILDER] Cookie _fbc encontrado` → Cookie está presente
- ✅ `[PARAM BUILDER] fbclid encontrado nos args` → fbclid está presente
- ⚠️ `[PARAM BUILDER] Cookie _fbc não encontrado` → Cookie ausente
- ⚠️ `[PARAM BUILDER] fbclid não encontrado nos args` → fbclid ausente
- ⚠️ `[PARAM BUILDER] ⚠️ fbc NÃO retornado` → Nenhuma fonte disponível

### **2. Verificar URL do Redirect**

**Problema comum:** URL do redirect não tem `fbclid`

**URL correta:**
```
https://app.grimbots.online/go/SEU_SLUG?grim=SEU_GRIM&fbclid=IwAR1234567890...
```

**URL sem fbclid (NÃO funciona):**
```
https://app.grimbots.online/go/SEU_SLUG?grim=SEU_GRIM
```

### **3. Verificar Client-Side Parameter Builder**

O **Client-Side Parameter Builder** deve estar:
- ✅ Carregando na página `telegram_redirect.html`
- ✅ Chamando `clientParamBuilder.processAndCollectAllParams()`
- ✅ Salvando `_fbc` e `_fbp` em cookies

**Como verificar:**
1. Acesse uma URL de redirect
2. Abra DevTools → Application → Cookies
3. Procure por:
   - ✅ `_fbc` (deve existir se `fbclid` estiver na URL)
   - ✅ `_fbp` (deve existir sempre)
   - ✅ `_fbi` (deve existir sempre - Client IP)

## 🎯 PRÓXIMOS PASSOS

### **PASSO 1: Testar com URL com fbclid**

1. Crie uma URL de teste com `fbclid`:
   ```
   https://app.grimbots.online/go/SEU_SLUG?grim=SEU_GRIM&fbclid=IwAR1234567890
   ```

2. Acesse a URL

3. Verifique logs:
   ```bash
   tail -f logs/gunicorn.log | grep -E "PARAM BUILDER.*fbc|fbclid encontrado"
   ```

4. Deve aparecer:
   ```
   [PARAM BUILDER] fbclid encontrado nos args: IwAR1234567890...
   [PARAM BUILDER] ✅ fbc gerado baseado em fbclid (conforme doc Meta): fb.1.1734567890...
   [META PAGEVIEW] PageView - fbc processado pelo Parameter Builder (origem: generated_from_fbclid): fb.1.1734567890...
   ```

### **PASSO 2: Verificar se Client-Side Parameter Builder está funcionando**

1. Acesse uma URL de redirect
2. Abra DevTools → Console
3. Execute:
   ```javascript
   console.log('_fbc:', document.cookie.split('; ').find(c => c.startsWith('_fbc=')));
   console.log('_fbp:', document.cookie.split('; ').find(c => c.startsWith('_fbp=')));
   console.log('_fbi:', document.cookie.split('; ').find(c => c.startsWith('_fbi=')));
   ```

4. Deve retornar valores (não `undefined`)

### **PASSO 3: Executar Script de Teste Novamente**

```bash
bash testar_parameter_builder.sh
```

**Agora deve mostrar:**
- ✅ Estatísticas detalhadas (com eventos ausentes)
- ✅ Por que `fbc` não está sendo retornado
- ✅ Logs mais informativos

## 📊 RESULTADO ESPERADO

### **ANTES (0% cobertura):**
```
PageView: 36/36 com fbc ausente
Purchase: 0/0 com fbc ausente
```

### **DEPOIS (com URL com fbclid):**
```
PageView: 30/36 com fbc (Parameter Builder) - 83% cobertura
Purchase: 10/10 com fbc REAL aplicado - 100% cobertura
```

## ⚠️ IMPORTANTE

**O `fbc` só será gerado se:**
1. ✅ Cookie `_fbc` está presente no browser (do Client-Side Parameter Builder), OU
2. ✅ `fbclid` está presente na URL do redirect

**Se nenhum dos dois estiver presente, `fbc` não será gerado (comportamento esperado).**

---

## 🔧 COMANDOS ÚTEIS

### **Ver últimas ocorrências de fbc:**
```bash
tail -500 logs/gunicorn.log | grep -E "fbc|fbclid" | tail -20
```

### **Contar eventos com fbc:**
```bash
grep -c "fbc processado pelo Parameter Builder" logs/gunicorn.log
grep -c "fbc NÃO retornado" logs/gunicorn.log
```

### **Ver logs detalhados do Parameter Builder:**
```bash
tail -1000 logs/gunicorn.log | grep "PARAM BUILDER" | tail -30
```

