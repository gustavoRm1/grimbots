# ✅ COMANDOS PÓS-LIMPEZA - VALIDAÇÃO FINAL

## 🎯 STATUS ATUAL

✅ **Limpeza Redis concluída:**
- 398 fbc sintéticos removidos
- 33.947 fbc reais preservados
- Sistema limpo e pronto

## 📋 PRÓXIMOS PASSOS

### 1️⃣ Atualizar Código (se ainda não fez)

```bash
cd /root/grimbots
git pull
```

### 2️⃣ Reiniciar Aplicação

```bash
./restart-app.sh
```

OU manualmente:

```bash
sudo systemctl restart grimbots
sudo systemctl restart celery-worker
```

### 3️⃣ Monitorar Logs em Tempo Real

```bash
# Monitorar redirects (verificar se fbc REAL está sendo capturado)
tail -f logs/gunicorn.log | grep -iE "\[META REDIRECT\]"

# Monitorar purchases (verificar se fbc REAL está sendo usado)
tail -f logs/gunicorn.log | grep -iE "\[META PURCHASE\]"

# Monitorar ambos
tail -f logs/gunicorn.log | grep -iE "\[META (REDIRECT|PURCHASE)\]"
```

## ✅ VALIDAÇÃO ESPERADA NOS LOGS

### ✅ DEVE APARECER (fbc REAL):

```
[META REDIRECT] Redirect - fbc capturado do cookie (ORIGEM REAL): fb.1.1732134409...
[META REDIRECT] Redirect - fbc REAL será salvo no Redis (origem: cookie): fb.1.1732134409...
[META PURCHASE] Purchase - fbc REAL recuperado do tracking_data (origem: cookie): fb.1.1732134409...
[META PURCHASE] Purchase - fbc REAL aplicado: fb.1.1732134409...
```

### ❌ NUNCA DEVE APARECER (fbc sintético):

```
[META REDIRECT] Redirect - fbc gerado do fbclid (formato oficial Meta): fb.1.1763124564...
```

**Timestamp recente (`1763124564`) = sintético ❌**  
**Timestamp antigo (`1732134409`) = real ✅**

## 🔍 TESTE MANUAL

1. Acesse um link de redirect com `fbclid`:
   ```
   https://app.grimbots.online/go/red1?fbclid=PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz
   ```

2. Verifique nos logs:
   - Se `fbc` veio do cookie → ✅ REAL
   - Se `fbc` não foi encontrado → ⚠️ Apenas `external_id` será usado (OK)
   - Se `fbc` foi gerado → ❌ ERRO (não deve acontecer)

3. Faça uma compra de teste e verifique:
   - Purchase deve usar `fbc` REAL se disponível
   - Purchase deve usar apenas `external_id` se `fbc` ausente
   - Purchase NUNCA deve usar `fbc` sintético

## 📊 RESULTADO ESPERADO

Após deploy e validação:

- ✅ Zero geração de `fbc` sintético
- ✅ `fbc` REAL capturado quando disponível
- ✅ `external_id` sempre presente (fbclid hasheado)
- ✅ Match Quality: 7/10 ou superior
- ✅ Vendas atribuídas corretamente no Meta Ads Manager

