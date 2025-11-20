# ✅ COMO VERIFICAR SE PURCHASE ESTÁ FUNCIONANDO

## 🎯 SITUAÇÃO ATUAL

**PageView está funcionando perfeitamente:**
- ✅ `fbclid` está chegando na URL
- ✅ Parameter Builder está gerando `fbc` baseado em `fbclid`
- ✅ `fbc` está sendo processado no PageView

**Purchase ainda não foi testado:**
- ❓ Não há logs de Purchase nos logs recentes
- ❓ Precisa gerar uma venda para verificar

---

## 🔍 COMO VERIFICAR

### **OPÇÃO 1: Monitorar em Tempo Real (Recomendado)**

```bash
bash monitorar_purchase_tempo_real.sh
```

Este script vai mostrar apenas logs relacionados a Purchase e destacar mensagens críticas.

---

### **OPÇÃO 2: Comando Manual**

```bash
tail -f logs/gunicorn.log | grep -E "Purchase.*fbc|Purchase.*fbclid|Purchase.*Parameter Builder|PARAM BUILDER.*fbc"
```

---

### **OPÇÃO 3: Ver Logs Recentes**

```bash
tail -500 logs/gunicorn.log | grep -E "Purchase.*fbc|Purchase.*fbclid|Purchase.*Parameter Builder" | tail -30
```

---

## ✅ O QUE PROCURAR NOS LOGS DE PURCHASE

### **SE ESTÁ FUNCIONANDO (CORRETO):**

```
[META PURCHASE] Purchase - fbclid recuperado do tracking_data (Redis): IwZXh0bgNhZW0BMABhZGlkAasqlSppV...
[META PURCHASE] Purchase - Chamando Parameter Builder com fbclid=✅ e _fbc=✅ ou ❌
[PARAM BUILDER] ✅ fbclid encontrado nos args: IwZXh0bgNhZW0BMABhZGlkAasqlSppV...
[PARAM BUILDER] ✅ fbc gerado baseado em fbclid (conforme doc Meta): fb.1.1734567890...
[PARAM BUILDER] ✅ fbc retornado com sucesso (origem: generated_from_fbclid) - VENDA SERÁ TRACKEADA
[META PURCHASE] Purchase - ✅ fbc processado pelo Parameter Builder (origem: generated_from_fbclid): fb.1.1734567890...
[META PURCHASE] Purchase - ✅ VENDA SERÁ TRACKEADA CORRETAMENTE (fbc presente)
```

**Se aparecer tudo isso:**
- ✅ **Purchase está funcionando perfeitamente!**
- ✅ **Vendas serão trackeadas corretamente!**

---

### **SE NÃO ESTÁ FUNCIONANDO (PROBLEMA):**

```
[META PURCHASE] Purchase - ❌ CRÍTICO: fbclid NÃO encontrado em nenhuma fonte!
   tracking_data tem fbclid: False
   payment tem fbclid: False
   bot_user tem fbclid: False
   ⚠️ SEM fbclid, Parameter Builder NÃO consegue gerar fbc - VENDAS NÃO SÃO TRACKEADAS!
```

**OU:**

```
[META PURCHASE] Purchase - Chamando Parameter Builder com fbclid=❌ e _fbc=❌
[PARAM BUILDER] ⚠️ fbclid não encontrado nos args (não será gerado fbc)
[PARAM BUILDER] ❌ CRÍTICO: fbc NÃO retornado (cookie _fbc ausente e fbclid ausente)
[META PURCHASE] Purchase - ❌ CRÍTICO: fbc NÃO retornado pelo Parameter Builder
   ❌ SEM fbclid, Parameter Builder NÃO consegue gerar fbc - VENDAS NÃO SÃO TRACKEADAS!
```

**Se aparecer isso:**
- ❌ **Purchase NÃO está funcionando!**
- ❌ **`fbclid` não está sendo recuperado do Redis**
- ⚠️ **Vendas NÃO serão trackeadas corretamente**

---

## 🎯 PRÓXIMO PASSO

### **GERAR UMA VENDA DE TESTE:**

1. **Acessar uma URL de redirect com `fbclid`:**
   ```
   https://app.grimbots.online/go/red1?grim=testecamu01&fbclid=IwZXh0bgNhZW0BMABhZGlkAasqlSppV...
   ```

2. **Interagir com o bot e gerar um pagamento**

3. **Verificar logs em tempo real:**
   ```bash
   tail -f logs/gunicorn.log | grep -E "Purchase.*fbc|Purchase.*fbclid|Parameter Builder"
   ```

4. **Procurar pelas mensagens acima**

---

## ✅ CONCLUSÃO

**PageView está funcionando perfeitamente!**
- ✅ Parameter Builder está gerando `fbc` no PageView
- ✅ `fbclid` está sendo salvo no Redis

**Purchase precisa ser testado:**
- ❓ Precisa gerar uma venda para verificar
- ❓ Logs vão mostrar se está funcionando ou não

**Próximo passo:**
- ✅ Gerar uma venda de teste
- ✅ Monitorar logs em tempo real
- ✅ Verificar se Purchase está funcionando

