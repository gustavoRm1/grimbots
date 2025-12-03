# ✅ CORREÇÃO - VARIÁVEL `utms` NÃO DEFINIDA

## 🔍 PROBLEMA IDENTIFICADO

**Erro:**
```
UnboundLocalError: local variable 'utms' referenced before assignment
```

**Localização:** `app.py` linha 6157 (endpoint `/go/<slug>`)

**Causa:**
- A variável `utms` só era definida dentro do bloco `if not is_crawler_request:`
- Quando `is_crawler_request = True`, a variável `utms` não era definida
- Mas `utms` ainda era usada na linha 6157 para criar o `tracking_payload`

---

## ✅ CORREÇÃO APLICADA

**Inicializar `utms` ANTES do bloco condicional:**

```python
# ✅ CORREÇÃO: Inicializar utms sempre (mesmo se for crawler)
# Se for crawler, utms será dict vazio (não salvará UTMs)
utms = {}
if not is_crawler_request:
    utms = {
        'utm_source': request.args.get('utm_source', ''),
        'utm_campaign': request.args.get('utm_campaign', ''),
        'utm_medium': request.args.get('utm_medium', ''),
        'utm_content': request.args.get('utm_content', ''),
        'utm_term': request.args.get('utm_term', ''),
        'utm_id': request.args.get('utm_id', '')
    }
```

**Resultado:**
- `utms` sempre existe (dict vazio se for crawler)
- `tracking_payload` pode usar `utms` sem erro
- Se for crawler, UTMs não serão salvos (comportamento esperado)

---

## 📝 ARQUIVO MODIFICADO

**`app.py` - Linha 6128-6139**

---

**STATUS:** ✅ Correção aplicada. Erro resolvido.

