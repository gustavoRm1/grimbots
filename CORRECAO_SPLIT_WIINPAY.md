# 🔧 CORREÇÃO: Split WiinPay - Conta Igual à Recebimento

**Problema:** Erro 422 - "A conta de split não pode ser a mesma conta de recebimento"

---

## ✅ CORREÇÃO APLICADA

Corrigida a lógica no gateway WiinPay para **não enviar split** quando a conta de split for a mesma da conta de recebimento.

### **Mudanças:**

1. **Decodificação JWT Melhorada:**
   - Tenta usar biblioteca `jwt` se disponível
   - Se não disponível, decodifica manualmente via base64
   - Extrai `userId` do JWT para comparação

2. **Validação de Split:**
   - Compara `split_user_id` com `api_key_user_id` (extraído do JWT)
   - Se forem iguais → **NÃO envia split** no payload
   - Se forem diferentes → envia split normalmente

3. **Logs Melhorados:**
   - Log quando split não é enviado (mesma conta)
   - Log quando split é enviado corretamente

---

## 📋 CÓDIGO APLICADO

```python
# gateway_wiinpay.py (linhas 206-273)

# ✅ Extrai user_id da api_key (JWT)
api_key_user_id = None
try:
    import jwt
    decoded = jwt.decode(self.api_key, options={"verify_signature": False})
    api_key_user_id = decoded.get('userId') or decoded.get('user_id')
except ImportError:
    # Decodifica manualmente via base64 se jwt não estiver instalado
    import base64
    import json
    parts = self.api_key.split('.')
    if len(parts) >= 2:
        payload_b64 = parts[1]
        # ... decodifica base64 ...

# ✅ Valida se split deve ser enviado
should_send_split = True
if api_key_user_id and self.split_user_id == api_key_user_id:
    logger.warning(f"⚠️ split_user_id é o mesmo da conta de recebimento!")
    logger.warning(f"   Removendo split do payload para evitar erro 422")
    should_send_split = False

# ✅ Adiciona split apenas se não for a mesma conta
if should_send_split:
    payload["split"] = {
        "percentage": self.split_percentage,
        "value": split_value,
        "user_id": self.split_user_id
    }
else:
    logger.info(f"ℹ️ Split NÃO será enviado (mesma conta de recebimento)")
```

---

## 🎯 RESULTADO

**Antes:**
```
❌ Erro 422: "A conta de split não pode ser a mesma conta de recebimento"
❌ Payment não foi criado
```

**Depois:**
```
✅ Split NÃO é enviado quando conta de recebimento = conta de split
✅ Payment é criado normalmente
✅ PIX é gerado com sucesso
```

---

## ✅ TESTE

Teste criando um pagamento com uma `api_key` cujo `userId` seja igual ao `split_user_id`. O sistema deve:

1. ✅ Detectar que são iguais
2. ✅ Não enviar split no payload
3. ✅ Criar payment normalmente
4. ✅ Gerar PIX com sucesso

---

**Correção aplicada e pronta para teste!**

