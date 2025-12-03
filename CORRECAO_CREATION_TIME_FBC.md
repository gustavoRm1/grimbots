# ✅ CORREÇÃO - CREATION TIME INVÁLIDO NO FBC

## 🔥 ERRO IDENTIFICADO PELA META

**Erro Active:**
- `creationTime` inválido para 11% dos eventos Purchase
- `creationTime` está antes do click ID ser criado ou no futuro

**Causa:**
- Quando geramos `fbc` baseado em `fbclid`, usamos `time.time() * 1000` (timestamp atual)
- Meta espera `creationTime` = timestamp quando `fbclid` foi **primeiro observado/recebido**

---

## ✅ SOLUÇÃO CONFORME META

**Meta diz:**
> "Do not modify the creationTime from the _fbc cookie. Instead, send it as is as part of the fbc parameter. If you don't save the _fbc cookie, use the timestamp in milliseconds when you first observed or received this fbclid value."

**Traduzindo:**
1. ✅ Se cookie `_fbc` existe → usar `creationTime` do cookie (não modificar)
2. ✅ Se não existe cookie → usar timestamp quando `fbclid` foi primeiro observado
3. ❌ NÃO usar timestamp atual (`time.time() * 1000`)

---

## 🔧 CORREÇÃO A APLICAR

**Problema atual (linha 142 de `meta_pixel.py`):**
```python
# ❌ ERRADO: Usa timestamp atual
creation_time_ms = int(time.time() * 1000)
result['fbc'] = f"fb.1.{creation_time_ms}.{fbclid}"
```

**Correção necessária:**
```python
# ✅ CORRETO: Usar timestamp quando fbclid foi primeiro observado
# Prioridade 1: Extrair creationTime do cookie _fbc (se existir)
# Prioridade 2: Usar pageview_ts do tracking_data (quando fbclid foi primeiro observado)
# Prioridade 3: Usar timestamp do Payment/BotUser quando fbclid foi salvo
# Prioridade 4: Fallback para timestamp atual (se nenhum outro disponível)
```

---

**PRÓXIMO PASSO:** Implementar lógica para extrair `creationTime` do cookie `_fbc` ou usar timestamp quando `fbclid` foi primeiro observado.

