# ✅ PATCH V4.1 - FBC REAL (ZERO SINTÉTICO)

## 🔥 PROBLEMA IDENTIFICADO

O sistema estava gerando `fbc` sintético (`fb.1.{timestamp_atual}.{fbclid}`), o que:
- ✅ Meta aceita o formato (não dá erro)
- ❌ Meta IGNORA para atribuição real (detecta timestamp recente)
- ❌ Match Quality fica travado em 3.8/10 - 4.1/10
- ❌ Vendas não são atribuídas aos anúncios
- ❌ Lookalike não aprende
- ❌ Algoritmo de entrega não é alimentado

## ✅ CORREÇÕES APLICADAS

### 1. **public_redirect** - Removida 100% geração sintética

**ANTES:**
```python
elif fbclid_param and not is_crawler_request:
    fbc_value = f"fb.1.{int(time.time())}.{fbclid_param}"  # ❌ SINTÉTICO
```

**DEPOIS:**
```python
if fbc_cookie:
    fbc_value = fbc_cookie.strip()
    fbc_origin = 'cookie'  # ✅ ORIGEM REAL
else:
    fbc_value = None  # ✅ NÃO GERAR SINTÉTICO
    fbc_origin = None
```

### 2. **Redis** - Adicionado `fbc_origin`

- `fbc_origin = 'cookie'` → fbc REAL (Meta atribui)
- `fbc_origin = 'synthetic'` → fbc sintético (será ignorado)
- `fbc_origin = None` → fbc ausente

### 3. **Purchase** - Usa fbc APENAS se `fbc_origin = 'cookie'`

```python
# ✅ PRIORIDADE 1: tracking_data com fbc_origin = 'cookie'
if tracking_data.get('fbc') and fbc_origin == 'cookie':
    fbc_value = tracking_data.get('fbc')
    
# ✅ CRÍTICO: Se fbc_origin = 'synthetic', IGNORAR
if fbc_origin == 'synthetic':
    fbc_value = None  # Não usar fbc sintético
```

### 4. **TrackingServiceV4** - Preserva fbc REAL

- Preserva fbc apenas se `fbc_origin = 'cookie'`
- Ignora fbc sintético do payload anterior
- Não sobrescreve fbc real com fbc sintético

### 5. **external_id** - Sempre enviado (fbclid hasheado)

- `fbclid` → normalizado → hasheado SHA256 → `external_id`
- Sempre presente no `user_data` do Purchase
- Garante matching mesmo sem `fbc`

## 📋 SCRIPTS CRIADOS

### 1. `static/js/meta_pixel_cookie_capture.js`
- Captura `_fbp` e `_fbc` do navegador
- Envia via URL params (`_fbp_cookie`, `_fbc_cookie`)
- Servidor lê dos params se cookie não estiver disponível

### 2. `scripts/cleanup_redis_synthetic_fbc.py`
- Identifica fbc sintético (timestamp < 1 hora)
- Remove/limpa fbc sintético do Redis
- Marca fbc real como `fbc_origin = 'cookie'`

## 🚀 COMANDOS PARA EXECUTAR

```bash
# 1. Limpar Redis (remover fbc sintético)
cd /root/grimbots
source venv/bin/activate
python scripts/cleanup_redis_synthetic_fbc.py

# 2. Reiniciar aplicação
./restart-app.sh

# 3. Monitorar logs
tail -f logs/gunicorn.log | grep -iE "\[META"
```

## ✅ RESULTADO ESPERADO

- ✅ `fbc` REAL capturado do cookie → Meta atribui vendas
- ✅ `fbc` sintético NUNCA gerado → Zero falsos-positivos
- ✅ `external_id` sempre presente → Matching mesmo sem `fbc`
- ✅ Match Quality: 7/10 ou superior
- ✅ Vendas atribuídas corretamente no Meta Ads Manager
- ✅ Lookalike funcionando
- ✅ Pixel reportando corretamente

## 🔍 VALIDAÇÃO

Após deploy, verificar nos logs:

```
[META REDIRECT] Redirect - fbc capturado do cookie (ORIGEM REAL): fb.1.1732134409...
[META PURCHASE] Purchase - fbc REAL aplicado: fb.1.1732134409...
```

**NUNCA deve aparecer:**
```
[META REDIRECT] Redirect - fbc gerado do fbclid (formato oficial Meta): fb.1.1763124564...
```

Timestamp `1763124564` (recente) = sintético ❌
Timestamp `1732134409` (antigo) = real ✅

