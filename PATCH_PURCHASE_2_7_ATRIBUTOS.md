# ✅ PATCH APLICADO - PURCHASE COM 2/7 ATRIBUTOS

**Data:** 2025-11-14  
**Problema:** Purchase enviado com apenas 2/7 atributos (external_id + fbp)  
**Causa Raiz:** Inconsistência de nomes de campos entre redirect e purchase

---

## 🔍 PROBLEMA IDENTIFICADO

**Log do Purchase:**
```
[META PURCHASE] Purchase - tracking_data recuperado: fbp=✅, fbc=❌, fbclid=❌
[META PURCHASE] Purchase - User Data: 2/7 atributos | external_id=✅ | fbp=✅ | fbc=❌ | email=❌ | phone=❌ | ip=❌ | ua=❌
```

**Causa:**
- Redirect salvava `client_ua` no Redis
- Purchase buscava `client_user_agent` ou `ua`
- **Mismatch de nomes!** Purchase não encontrava o campo

---

## ✅ CORREÇÕES APLICADAS

### **1. Corrigido nome do campo no redirect**

**ANTES:**
```python
tracking_payload = {
    'client_ip': user_ip,
    'client_ua': user_agent,  # ❌ ERRADO: Purchase busca 'client_user_agent'
    # ...
}
```

**DEPOIS:**
```python
tracking_payload = {
    'client_ip': user_ip,  # ✅ CORRETO
    'client_user_agent': user_agent,  # ✅ CORRIGIDO: Mesmo nome que Purchase busca
    'event_source_url': request.url or f'https://{request.host}/go/{pool.slug}',
    'first_page': request.url or f'https://{request.host}/go/{pool.slug}',  # ✅ ADICIONADO
    # ...
}
```

### **2. Melhorado fallback no Purchase**

**ANTES:**
```python
ip_value = tracking_data.get('client_ip') or tracking_data.get('ip')
user_agent_value = tracking_data.get('client_user_agent') or tracking_data.get('ua')
```

**DEPOIS:**
```python
ip_value = tracking_data.get('client_ip') or tracking_data.get('ip') or tracking_data.get('client_ip_address')
user_agent_value = tracking_data.get('client_user_agent') or tracking_data.get('ua') or tracking_data.get('client_ua')
```

### **3. Adicionados logs detalhados**

**No Redirect:**
```python
logger.info(f"[META PIXEL] Redirect - tracking_payload completo: fbclid={'✅' if tracking_payload.get('fbclid') else '❌'}, fbp={'✅' if tracking_payload.get('fbp') else '❌'}, ip={'✅' if tracking_payload.get('client_ip') else '❌'}, ua={'✅' if tracking_payload.get('client_user_agent') else '❌'}")
```

**No Purchase:**
```python
logger.info(f"[META PURCHASE] Purchase - tracking_data recuperado do Redis: fbclid={'✅' if tracking_data.get('fbclid') else '❌'}, fbp={'✅' if tracking_data.get('fbp') else '❌'}, fbc={'✅' if tracking_data.get('fbc') else '❌'}, ip={'✅' if ip_value else '❌'}, ua={'✅' if user_agent_value else '❌'}")
```

---

## 🚀 COMANDOS PARA APLICAR NA VPS

```bash
# 1. Atualizar código
cd /root/grimbots
git pull origin main

# 2. Validar código
python -m py_compile app.py
python -c "from app import app; print('✅ Imports OK')"

# 3. Reiniciar aplicação
./restart-app.sh

# 4. Monitorar logs
tail -f logs/gunicorn.log | grep -iE "\[META (REDIRECT|PURCHASE)\]"
```

---

## ✅ RESULTADO ESPERADO

Após aplicar o patch:

**No Redirect (deve aparecer):**
```
[META PIXEL] Redirect - tracking_payload completo: fbclid=✅, fbp=✅, ip=✅, ua=✅
[META PIXEL] Redirect - tracking_token salvo: ... | Campos: fbclid=✅, fbp=✅, ip=✅, ua=✅
```

**No Purchase (deve aparecer):**
```
[META PURCHASE] Purchase - tracking_data recuperado do Redis: fbclid=✅, fbp=✅, fbc=❌, ip=✅, ua=✅
[META PURCHASE] Purchase - User Data: 4/7 ou 5/7 atributos | external_id=✅ | fbp=✅ | fbc=❌ | ip=✅ | ua=✅
```

**Melhoria esperada:**
- ✅ De 2/7 para 4/7 ou 5/7 atributos (sem fbc) ou 6/7 ou 7/7 (com fbc)
- ✅ Match Quality: de ~3/10 para 6/10 ou 7/10 (sem fbc) ou 9/10 ou 10/10 (com fbc)

---

## 📋 VALIDAÇÃO

Após aplicar o patch, fazer um teste completo:

1. Acessar link de redirecionamento com `fbclid`
2. Verificar logs do redirect (deve mostrar `ip=✅, ua=✅`)
3. Fazer uma compra
4. Verificar logs do purchase (deve mostrar `ip=✅, ua=✅`)
5. Confirmar que Purchase tem 4/7 ou mais atributos

---

**PATCH APLICADO! ✅**

